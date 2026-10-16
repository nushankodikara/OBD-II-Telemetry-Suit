"""Main CustomTkinter desktop application for OBD-II Telemetry Suit.

Mechanic and driver diagnostic workstation featuring:
- Car Scanner ELM OBD2 format validation and multi-stage pre-ingestion cleanup.
- XML-based vehicle profile configuration (make, model, engine cc, gears, tyres) and persistence.
- Automatic session restore from last_session.xml or clean start with zero data.
- Native application menu bar with File, Vehicle, Settings, and Help menus.
- Quick Vehicle Info auto-detection aimed at general drivers without technical knowledge.
- Hybrid vehicle telemetry, High Voltage battery health, block voltage imbalance, and EV drive ratio.
- City, Highway, and Combined fuel economy with "-" fallback for missing data.
- Optimal RPM & Speed curves and 2D efficiency heatmaps with cruising sweet spot.
- In-depth STFT and LTFT fuel trim diagnostics with mechanic repair recommendations.
- Physical rule and Isolation Forest multivariate anomaly detection.

Strictly adheres to project rules: no emojis.
"""

import os
import sys
import threading
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import List, Optional, Tuple, Dict, Any
import customtkinter as ctk
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from src.version import get_app_version, get_version_info, check_for_updates
from src.data_loader import ScanTrip, load_all_records, parse_obd_csv
from src.analyzer import (
    VehicleAnalyzer,
    FuelEconomyResult,
    DiagnosticHealthReport,
    FuelTrimDiagnostic,
    HybridBatteryReport,
    AutoDetectedVehicleInfo,
    TelemetryAnomaly,
)
from src.session_manager import (
    VehicleProfile,
    save_session_to_xml,
    load_session_from_xml,
    save_last_session,
    load_last_session,
)
from src.ui.components.settings_dialog import VehicleSettingsDialog, SoftwareUpdateDialog
from src.ui.theme import (
    BG_DARKEST,
    BG_PANEL,
    BG_PANEL_ALT,
    BG_CARD_HOVER,
    BORDER_COLOR,
    ACCENT_AMBER,
    ACCENT_GREEN,
    ACCENT_CYAN,
    ACCENT_BLUE,
    ACCENT_RED,
    ACCENT_PURPLE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_MUTED,
    TEXT_AMBER,
    TEXT_GREEN,
    TEXT_CYAN,
    TEXT_RED,
    FONT_TITLE,
    FONT_SUBTITLE,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_CAPTION,
    FONT_BADGE,
    FONT_DIGITAL_SMALL,
)
from src.ui.components.metric_card import MetricCard
from src.ui.components.graph_canvas import GraphCanvas
from src.ui.components.record_list import RecordListPanel


class CarRecordAnalyzerApp(ctk.CTk):
    """Main application window for OBD-II Telemetry Suit."""

    def __init__(self):
        super().__init__()

        # Appearance configuration
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("dark-blue")

        ver = get_app_version()
        self.title(f"OBD-II Telemetry Suit v{ver} | Automotive Diagnostic Workstation")
        self.geometry("1440x940")
        self.minsize(1150, 780)
        self.configure(fg_color=BG_DARKEST)

        # Vehicle Profile & Session state
        self.current_xml_path: Optional[str] = None
        self.profile = VehicleProfile()
        self.city_threshold: float = 45.0
        self.highway_threshold: float = 70.0
        self.current_unit: str = "km/L"
        self.analyzer = VehicleAnalyzer(
            city_speed_max=self.city_threshold,
            highway_speed_min=self.highway_threshold,
        )

        # Loaded records state
        self.all_trips: List[ScanTrip] = []
        self.selected_trips: List[ScanTrip] = []

        # Current computation caches
        self.current_fe_result: Optional[FuelEconomyResult] = None
        self.current_diag_report: Optional[DiagnosticHealthReport] = None
        self.current_trim_diag: Optional[FuelTrimDiagnostic] = None
        self.current_hybrid_rep: Optional[HybridBatteryReport] = None
        self.current_anomalies: List[TelemetryAnomaly] = []

        # Build UI layout
        self._build_menu_bar()
        self._build_header()
        self._build_metric_banner()
        self._build_main_body()

        # Startup: Check if previous session exists; otherwise start empty
        self._initialize_startup_session()

    def _build_menu_bar(self):
        """Construct native application menu bar."""
        menu_bar = tk.Menu(self)

        # File Menu
        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="New Session", accelerator="Ctrl+N", command=self._on_new_session)
        file_menu.add_command(label="Open Session (XML)...", accelerator="Ctrl+O", command=self._on_open_session_xml)
        file_menu.add_command(label="Save Session (XML)", accelerator="Ctrl+S", command=self._on_save_session_xml)
        file_menu.add_command(label="Save Session As (XML)...", command=self._on_save_session_as_xml)
        file_menu.add_separator()
        file_menu.add_command(label="Import Car Scanner CSV Logs...", command=self._on_add_files)
        file_menu.add_command(label="Import Vehicle Folder...", command=self._on_import_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Export Diagnostic Report (TXT)...", command=self._export_report)
        file_menu.add_command(label="Export Diagnostic Summary (CSV)...", command=self._export_report)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", accelerator="Ctrl+Q", command=self.destroy)
        menu_bar.add_cascade(label="File", menu=file_menu)

        # Vehicle & Settings Menu
        veh_menu = tk.Menu(menu_bar, tearoff=0)
        veh_menu.add_command(label="Vehicle Profile & Settings...", command=self._open_vehicle_settings_window)
        veh_menu.add_command(label="Quick Vehicle Info (Auto-Detect)...", command=self._open_quick_vehicle_info)
        veh_menu.add_separator()
        veh_menu.add_command(label="Driving Speed Thresholds...", command=self._open_thresholds_dialog)
        veh_menu.add_separator()
        veh_menu.add_command(label="Unit: km/L", command=lambda: self._on_unit_changed("km/L"))
        veh_menu.add_command(label="Unit: L/100km", command=lambda: self._on_unit_changed("L/100km"))
        veh_menu.add_command(label="Unit: MPG (US)", command=lambda: self._on_unit_changed("MPG (US)"))
        veh_menu.add_command(label="Unit: MPG (UK)", command=lambda: self._on_unit_changed("MPG (UK)"))
        menu_bar.add_cascade(label="Vehicle & Settings", menu=veh_menu)

        # Help Menu
        help_menu = tk.Menu(menu_bar, tearoff=0)
        help_menu.add_command(label="Check for Updates...", command=lambda: self._check_for_updates_ui(silent=False))
        help_menu.add_separator()
        help_menu.add_command(label="Supported Format Info (Car Scanner ELM OBD2)", command=self._show_format_info)
        help_menu.add_command(label="About OBD-II Telemetry Suit", command=self._show_about)
        menu_bar.add_cascade(label="Help", menu=help_menu)

        # Keyboard shortcuts
        self.bind_all("<Control-n>", lambda e: self._on_new_session())
        self.bind_all("<Control-o>", lambda e: self._on_open_session_xml())
        self.bind_all("<Control-s>", lambda e: self._on_save_session_xml())
        self.bind_all("<Command-n>", lambda e: self._on_new_session())
        self.bind_all("<Command-o>", lambda e: self._on_open_session_xml())
        self.bind_all("<Command-s>", lambda e: self._on_save_session_xml())

        self.config(menu=menu_bar)

    def _build_header(self):
        """Build top navigation and telemetry controls."""
        self.header = ctk.CTkFrame(
            self,
            fg_color=BG_PANEL,
            height=60,
            corner_radius=0,
            border_width=0,
        )
        self.header.pack(fill="x", side="top")

        # Brand / Title section
        title_box = ctk.CTkFrame(self.header, fg_color="transparent")
        title_box.pack(side="left", padx=16, pady=10)

        self.lbl_title = ctk.CTkLabel(
            title_box,
            text="OBD-II TELEMETRY SUIT",
            font=FONT_TITLE,
            text_color=TEXT_PRIMARY,
        )
        self.lbl_title.pack(anchor="w")

        self.lbl_subtitle = ctk.CTkLabel(
            title_box,
            text="CAR SCANNER ELM OBD2 PARSING, HYBRID POWERTRAIN, EFFICIENCY MAPPING & DIAGNOSTICS",
            font=FONT_CAPTION,
            text_color=TEXT_MUTED,
        )
        self.lbl_subtitle.pack(anchor="w")

        # Controls section: Vehicle Profile pill, Quick Info button, Unit Selector
        controls_box = ctk.CTkFrame(self.header, fg_color="transparent")
        controls_box.pack(side="right", padx=16, pady=10)

        # Vehicle Profile Quick Pill
        self.btn_active_vehicle = ctk.CTkButton(
            controls_box,
            text="Vehicle: Unspecified Profile",
            font=FONT_CAPTION,
            height=28,
            fg_color=BG_PANEL_ALT,
            hover_color=BG_CARD_HOVER,
            border_width=1,
            border_color=BORDER_COLOR,
            command=self._open_vehicle_settings_window,
        )
        self.btn_active_vehicle.pack(side="left", padx=(0, 10))

        # Quick Vehicle Info button for general drivers
        self.btn_quick_info = ctk.CTkButton(
            controls_box,
            text="Quick Vehicle Info",
            font=FONT_BODY_BOLD,
            height=28,
            fg_color=ACCENT_AMBER,
            hover_color="#D97706",
            text_color=BG_DARKEST,
            command=self._open_quick_vehicle_info,
        )
        self.btn_quick_info.pack(side="left", padx=(0, 14))

        # Unit selector
        unit_lbl = ctk.CTkLabel(
            controls_box,
            text="UNITS:",
            font=FONT_BADGE,
            text_color=TEXT_SECONDARY,
        )
        unit_lbl.pack(side="left", padx=(0, 6))

        self.unit_segment = ctk.CTkSegmentedButton(
            controls_box,
            values=["km/L", "L/100km", "MPG (US)", "MPG (UK)"],
            font=FONT_CAPTION,
            selected_color=ACCENT_AMBER,
            selected_hover_color=ACCENT_AMBER,
            unselected_color=BG_PANEL_ALT,
            unselected_hover_color=BG_CARD_HOVER,
            command=self._on_unit_changed,
        )
        self.unit_segment.set("km/L")
        self.unit_segment.pack(side="left")

    def _build_metric_banner(self):
        """Build top row of mechanic digital gauge cards."""
        self.metric_banner = ctk.CTkFrame(self, fg_color="transparent", height=110)
        self.metric_banner.pack(fill="x", padx=14, pady=(10, 6))

        self.card_city = MetricCard(
            self.metric_banner,
            title="City Fuel Economy",
            value="-",
            unit="km/L",
            subtitle="Speed <= 45 km/h",
            status_text="NO DATA",
            accent_color=TEXT_CYAN,
        )
        self.card_city.pack(side="left", fill="both", expand=True, padx=4)

        self.card_highway = MetricCard(
            self.metric_banner,
            title="Highway Fuel Economy",
            value="-",
            unit="km/L",
            subtitle="Speed >= 70 km/h",
            status_text="NO DATA",
            accent_color=TEXT_GREEN,
        )
        self.card_highway.pack(side="left", fill="both", expand=True, padx=4)

        self.card_combined = MetricCard(
            self.metric_banner,
            title="Combined Fuel Economy",
            value="-",
            unit="km/L",
            subtitle="Weighted Moving Average",
            status_text="NO DATA",
            accent_color=TEXT_AMBER,
        )
        self.card_combined.pack(side="left", fill="both", expand=True, padx=4)

        self.card_distance = MetricCard(
            self.metric_banner,
            title="Sampled Distance & Fuel",
            value="-",
            unit="km",
            subtitle="Total Consumed: - L",
            status_text="TRIP",
            accent_color=TEXT_PRIMARY,
        )
        self.card_distance.pack(side="left", fill="both", expand=True, padx=4)

        self.card_sweet_spot = MetricCard(
            self.metric_banner,
            title="Optimal Efficiency Spot",
            value="-",
            unit="km/h",
            subtitle="Best Cruising RPM",
            status_text="SWEET SPOT",
            accent_color=ACCENT_PURPLE,
        )
        self.card_sweet_spot.pack(side="left", fill="both", expand=True, padx=4)

        self.card_hybrid_battery = MetricCard(
            self.metric_banner,
            title="Hybrid Battery / Idle",
            value="-",
            unit="%",
            subtitle="State of Charge",
            status_text="NO DATA",
            accent_color=ACCENT_GREEN,
        )
        self.card_hybrid_battery.pack(side="left", fill="both", expand=True, padx=4)

    def _build_main_body(self):
        """Build center split view: Sidebar on left, Tabview on right."""
        self.body_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.body_frame.pack(fill="both", expand=True, padx=14, pady=(4, 12))

        # Left Column: Record List & Mechanic Diagnostic Summary Box
        self.left_col = ctk.CTkFrame(self.body_frame, fg_color="transparent", width=340)
        self.left_col.pack(side="left", fill="y", padx=(0, 8))
        self.left_col.pack_propagate(False)

        self.record_panel = RecordListPanel(
            self.left_col,
            on_selection_changed=self._on_records_selection_changed,
            on_add_files=self._on_add_files,
            on_reload_dir=self._reload_active_files,
        )
        self.record_panel.pack(fill="both", expand=True, pady=(0, 8))

        # Diagnostic Quick Status Card
        self.diag_panel = ctk.CTkFrame(
            self.left_col,
            fg_color=BG_PANEL,
            corner_radius=8,
            border_width=1,
            border_color=BORDER_COLOR,
            height=210,
        )
        self.diag_panel.pack(fill="x", side="bottom")

        lbl_diag_title = ctk.CTkLabel(
            self.diag_panel,
            text="MECHANIC SENSOR HEALTH",
            font=FONT_BODY_BOLD,
            text_color=TEXT_PRIMARY,
        )
        lbl_diag_title.pack(anchor="w", padx=12, pady=(10, 4))

        self.lbl_battery_status = ctk.CTkLabel(
            self.diag_panel,
            text="12V Battery: STANDBY",
            font=FONT_CAPTION,
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self.lbl_battery_status.pack(fill="x", padx=12, pady=1)

        self.lbl_coolant_status = ctk.CTkLabel(
            self.diag_panel,
            text="Coolant: STANDBY",
            font=FONT_CAPTION,
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self.lbl_coolant_status.pack(fill="x", padx=12, pady=1)

        self.lbl_trim_status = ctk.CTkLabel(
            self.diag_panel,
            text="Fuel Trim: STANDBY",
            font=FONT_CAPTION,
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self.lbl_trim_status.pack(fill="x", padx=12, pady=1)

        self.lbl_diag_notes = ctk.CTkLabel(
            self.diag_panel,
            text="No scan records loaded. Use File -> Import Car Scanner CSV to load data.",
            font=FONT_CAPTION,
            text_color=TEXT_MUTED,
            anchor="w",
            wraplength=310,
            justify="left",
        )
        self.lbl_diag_notes.pack(fill="x", padx=12, pady=(4, 10))

        # Right Column: Tabview
        self.tabview = ctk.CTkTabview(
            self.body_frame,
            fg_color=BG_PANEL,
            segmented_button_fg_color=BG_PANEL_ALT,
            segmented_button_selected_color=ACCENT_AMBER,
            segmented_button_selected_hover_color=ACCENT_AMBER,
            segmented_button_unselected_color=BG_PANEL_ALT,
            segmented_button_unselected_hover_color=BG_CARD_HOVER,
            corner_radius=8,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.tabview.pack(side="right", fill="both", expand=True)

        # Tabs
        self.tab_fe_map = self.tabview.add("Efficiency & Sweet Spot")
        self.tab_rpm_speed = self.tabview.add("RPM & Speed Curves")
        self.tab_thermal = self.tabview.add("Thermal Profile")
        self.tab_fuel_trims = self.tabview.add("Fuel Trim Diagnostics")
        self.tab_anomalies = self.tabview.add("Anomaly Detection")
        self.tab_settings = self.tabview.add("Vehicle Profile & Settings")
        self.tab_cleanup_sessions = self.tabview.add("Data Cleanup & Sessions")

        # Hybrid tab dynamically managed only when hybrid records are loaded
        self.tab_hybrid = None
        self.canvas_hybrid = None

        # Tab 1: Efficiency Canvas with DFCO & Mode Controls
        self.fe_controls_bar = ctk.CTkFrame(self.tab_fe_map, fg_color="transparent", height=32)
        self.fe_controls_bar.pack(fill="x", padx=8, pady=(4, 2))

        self.lbl_fe_dfco_status = ctk.CTkLabel(
            self.fe_controls_bar,
            text="DFCO Status: Standby",
            font=FONT_CAPTION,
            text_color=TEXT_SECONDARY,
        )
        self.lbl_fe_dfco_status.pack(side="left", padx=4)

        self.fe_mode_seg = ctk.CTkSegmentedButton(
            self.fe_controls_bar,
            values=["Real-World Tractive", "Show All (Incl. DFCO / Coasting)"],
            font=FONT_CAPTION,
            selected_color=ACCENT_CYAN,
            selected_hover_color=ACCENT_CYAN,
            unselected_color=BG_PANEL_ALT,
            unselected_hover_color=BG_CARD_HOVER,
            command=self._on_fe_mode_changed,
        )
        self.fe_mode_seg.set("Real-World Tractive")
        self.fe_mode_seg.pack(side="right", padx=4)
        self.fe_display_mode_val = "tractive"

        self.canvas_fe_map = GraphCanvas(self.tab_fe_map)
        self.canvas_fe_map.pack(fill="both", expand=True, padx=6, pady=6)

        # Tab 2: RPM Speed Canvas
        self.canvas_rpm_speed = GraphCanvas(self.tab_rpm_speed)
        self.canvas_rpm_speed.pack(fill="both", expand=True, padx=6, pady=6)

        # Tab 3: Thermal Canvas
        self.canvas_thermal = GraphCanvas(self.tab_thermal)
        self.canvas_thermal.pack(fill="both", expand=True, padx=6, pady=6)

        # Tab 4: Fuel Trim Diagnostics & Recommendations
        self._build_fuel_trim_tab()

        # Tab 5: Anomaly Detection Center
        self._build_anomalies_tab()

        # Tab 6: Vehicle Profile & Settings Tab
        self._build_settings_tab()

        # Tab 7: Data Cleanup & Sessions Table
        self._build_cleanup_sessions_tab()

    def _update_hybrid_tab_visibility(self, has_hybrid: bool):
        """Show or hide the dedicated Hybrid Battery tab based on telemetry."""
        tab_name = "Hybrid Battery & Powertrain"
        is_present = tab_name in self.tabview._tab_dict
        if has_hybrid and not is_present:
            self.tab_hybrid = self.tabview.add(tab_name)
            self._build_hybrid_tab()
        elif not has_hybrid and is_present:
            if self.tabview.get() == tab_name:
                self.tabview.set("Efficiency & Sweet Spot")
            self.tabview.delete(tab_name)
            self.tab_hybrid = None
            self.canvas_hybrid = None

    def _build_fuel_trim_tab(self):
        """Build Fuel Trim diagnostics workstation with recommendations."""
        container = ctk.CTkFrame(self.tab_fuel_trims, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=6, pady=6)

        self.trim_rec_box = ctk.CTkFrame(container, fg_color=BG_PANEL_ALT, corner_radius=6, border_width=1, border_color=BORDER_COLOR)
        self.trim_rec_box.pack(fill="x", side="top", padx=2, pady=(0, 6))

        rec_header_row = ctk.CTkFrame(self.trim_rec_box, fg_color="transparent")
        rec_header_row.pack(fill="x", padx=12, pady=(8, 4))

        self.lbl_trim_diag_title = ctk.CTkLabel(
            rec_header_row,
            text="DIAGNOSIS: NO DATA",
            font=FONT_BODY_BOLD,
            text_color=TEXT_PRIMARY,
        )
        self.lbl_trim_diag_title.pack(side="left")

        self.lbl_trim_badge = ctk.CTkLabel(
            rec_header_row,
            text="[STANDBY]",
            font=FONT_BADGE,
            text_color=TEXT_MUTED,
        )
        self.lbl_trim_badge.pack(side="right")

        self.lbl_trim_zone_stats = ctk.CTkLabel(
            self.trim_rec_box,
            text="Idle Trim: - | Cruising Trim: - | High Load Trim: -",
            font=FONT_DIGITAL_SMALL,
            text_color=TEXT_AMBER,
            anchor="w",
        )
        self.lbl_trim_zone_stats.pack(fill="x", padx=12, pady=2)

        self.lbl_trim_rec_text = ctk.CTkLabel(
            self.trim_rec_box,
            text="Diagnostic recommendations will appear after loading scan records.",
            font=FONT_CAPTION,
            text_color=TEXT_SECONDARY,
            anchor="w",
            wraplength=950,
            justify="left",
        )
        self.lbl_trim_rec_text.pack(fill="x", padx=12, pady=(2, 8))

        self.canvas_fuel_trims = GraphCanvas(container)
        self.canvas_fuel_trims.pack(fill="both", expand=True, padx=2, pady=2)

    def _build_hybrid_tab(self):
        """Build dedicated Hybrid Battery, cell balance, and powertrain telemetry workstation."""
        container = ctk.CTkFrame(self.tab_hybrid, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=6, pady=6)

        # Top Hybrid Summary Box
        self.hybrid_summary_box = ctk.CTkFrame(container, fg_color=BG_PANEL_ALT, corner_radius=6, border_width=1, border_color=BORDER_COLOR)
        self.hybrid_summary_box.pack(fill="x", side="top", padx=2, pady=(0, 6))

        h_title_row = ctk.CTkFrame(self.hybrid_summary_box, fg_color="transparent")
        h_title_row.pack(fill="x", padx=12, pady=(8, 4))

        self.lbl_hybrid_title = ctk.CTkLabel(
            h_title_row,
            text="HYBRID POWERTRAIN & HIGH-VOLTAGE BATTERY HEALTH",
            font=FONT_BODY_BOLD,
            text_color=TEXT_PRIMARY,
        )
        self.lbl_hybrid_title.pack(side="left")

        self.lbl_hybrid_badge = ctk.CTkLabel(
            h_title_row,
            text="[STANDBY]",
            font=FONT_BADGE,
            text_color=TEXT_MUTED,
        )
        self.lbl_hybrid_badge.pack(side="right")

        self.lbl_hybrid_metrics = ctk.CTkLabel(
            self.hybrid_summary_box,
            text="Battery SOC: - | Cell Block Delta: - | Inverter Temp: - | EV Drive Ratio: -",
            font=FONT_DIGITAL_SMALL,
            text_color=ACCENT_CYAN,
            anchor="w",
        )
        self.lbl_hybrid_metrics.pack(fill="x", padx=12, pady=2)

        self.lbl_hybrid_obs = ctk.CTkLabel(
            self.hybrid_summary_box,
            text="Select hybrid vehicle scan files to evaluate High-Voltage battery cell blocks and inverter telemetry.",
            font=FONT_CAPTION,
            text_color=TEXT_SECONDARY,
            anchor="w",
            wraplength=950,
            justify="left",
        )
        self.lbl_hybrid_obs.pack(fill="x", padx=12, pady=(2, 8))

        # Bottom Canvas for Hybrid charts
        self.canvas_hybrid = GraphCanvas(container)
        self.canvas_hybrid.pack(fill="both", expand=True, padx=2, pady=2)

    def _build_anomalies_tab(self):
        """Build Anomaly Detection Center with severity badges and event log."""
        container = ctk.CTkFrame(self.tab_anomalies, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=6, pady=6)

        top_bar = ctk.CTkFrame(container, fg_color=BG_PANEL_ALT, height=36, corner_radius=6, border_width=1, border_color=BORDER_COLOR)
        top_bar.pack(fill="x", side="top", padx=2, pady=(0, 6))

        self.lbl_anomaly_summary = ctk.CTkLabel(
            top_bar,
            text="ANOMALY DETECTION | 0 TOTAL ANOMALIES IDENTIFIED",
            font=FONT_BODY_BOLD,
            text_color=TEXT_PRIMARY,
        )
        self.lbl_anomaly_summary.pack(side="left", padx=12, pady=6)

        self.lbl_anomaly_badges = ctk.CTkLabel(
            top_bar,
            text="Critical: 0 | Warning: 0 | ML Outliers: 0",
            font=FONT_BADGE,
            text_color=TEXT_AMBER,
        )
        self.lbl_anomaly_badges.pack(side="right", padx=12, pady=6)

        self.anomalies_scroll = ctk.CTkScrollableFrame(
            container,
            fg_color=BG_DARKEST,
            corner_radius=6,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.anomalies_scroll.pack(fill="both", expand=True, padx=2, pady=2)

    def _build_settings_tab(self):
        """Build dedicated Vehicle Profile configuration tab with XML save/load."""
        container = ctk.CTkScrollableFrame(self.tab_settings, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=12, pady=12)

        # Section 1: Vehicle Specifications Card
        card_spec = ctk.CTkFrame(container, fg_color=BG_PANEL_ALT, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        card_spec.pack(fill="x", pady=(0, 12), padx=4)

        ctk.CTkLabel(card_spec, text="VEHICLE SPECIFICATIONS & METADATA", font=FONT_BODY_BOLD, text_color=TEXT_PRIMARY).pack(anchor="w", padx=16, pady=(12, 8))

        # Grid of fields
        grid_frame = ctk.CTkFrame(card_spec, fg_color="transparent")
        grid_frame.pack(fill="x", padx=16, pady=(0, 12))

        # Make & Model
        ctk.CTkLabel(grid_frame, text="Make (Manufacturer):", font=FONT_CAPTION, text_color=TEXT_SECONDARY).grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.entry_make = ctk.CTkEntry(grid_frame, width=180, placeholder_text="e.g. Toyota")
        self.entry_make.grid(row=0, column=1, sticky="w", padx=4, pady=4)

        ctk.CTkLabel(grid_frame, text="Model:", font=FONT_CAPTION, text_color=TEXT_SECONDARY).grid(row=0, column=2, sticky="w", padx=(16, 4), pady=4)
        self.entry_model = ctk.CTkEntry(grid_frame, width=180, placeholder_text="e.g. Aqua / Prius")
        self.entry_model.grid(row=0, column=3, sticky="w", padx=4, pady=4)

        # Year & Engine Type
        ctk.CTkLabel(grid_frame, text="Model Year:", font=FONT_CAPTION, text_color=TEXT_SECONDARY).grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.entry_year = ctk.CTkEntry(grid_frame, width=180, placeholder_text="e.g. 2018")
        self.entry_year.grid(row=1, column=1, sticky="w", padx=4, pady=4)

        ctk.CTkLabel(grid_frame, text="Engine Powertrain Type:", font=FONT_CAPTION, text_color=TEXT_SECONDARY).grid(row=1, column=2, sticky="w", padx=(16, 4), pady=4)
        self.entry_engine_type = ctk.CTkComboBox(grid_frame, width=180, values=["Hybrid Petrol", "Petrol (Naturally Aspirated)", "Turbo Petrol", "Diesel", "Electric (EV)"])
        self.entry_engine_type.set("Hybrid Petrol")
        self.entry_engine_type.grid(row=1, column=3, sticky="w", padx=4, pady=4)

        # Displacement & Transmission
        ctk.CTkLabel(grid_frame, text="Engine Capacity (cc):", font=FONT_CAPTION, text_color=TEXT_SECONDARY).grid(row=2, column=0, sticky="w", padx=4, pady=4)
        self.entry_displacement = ctk.CTkEntry(grid_frame, width=180, placeholder_text="e.g. 1500")
        self.entry_displacement.grid(row=2, column=1, sticky="w", padx=4, pady=4)

        ctk.CTkLabel(grid_frame, text="Transmission / Gears:", font=FONT_CAPTION, text_color=TEXT_SECONDARY).grid(row=2, column=2, sticky="w", padx=(16, 4), pady=4)
        self.entry_gears = ctk.CTkComboBox(grid_frame, width=180, values=["e-CVT (Hybrid)", "CVT", "4-Speed Auto", "5-Speed Manual", "6-Speed Manual", "6-Speed Auto", "7-Speed DCT", "8-Speed Auto"])
        self.entry_gears.set("e-CVT (Hybrid)")
        self.entry_gears.grid(row=2, column=3, sticky="w", padx=4, pady=4)

        # Tyre Size & Fuel Tank
        ctk.CTkLabel(grid_frame, text="Tyre Specification:", font=FONT_CAPTION, text_color=TEXT_SECONDARY).grid(row=3, column=0, sticky="w", padx=4, pady=4)
        self.entry_tyres = ctk.CTkEntry(grid_frame, width=180, placeholder_text="e.g. 185/65R15")
        self.entry_tyres.grid(row=3, column=1, sticky="w", padx=4, pady=4)

        ctk.CTkLabel(grid_frame, text="Fuel Tank Capacity (L):", font=FONT_CAPTION, text_color=TEXT_SECONDARY).grid(row=3, column=2, sticky="w", padx=(16, 4), pady=4)
        self.entry_tank = ctk.CTkEntry(grid_frame, width=180, placeholder_text="e.g. 36")
        self.entry_tank.grid(row=3, column=3, sticky="w", padx=4, pady=4)

        # Notes
        ctk.CTkLabel(grid_frame, text="Workshop Notes:", font=FONT_CAPTION, text_color=TEXT_SECONDARY).grid(row=4, column=0, sticky="nw", padx=4, pady=4)
        self.entry_notes = ctk.CTkEntry(grid_frame, width=460, placeholder_text="Vehicle history, modifications, or diagnostic goals...")
        self.entry_notes.grid(row=4, column=1, columnspan=3, sticky="w", padx=4, pady=4)

        # Section 2: Analysis Thresholds Card
        card_thresh = ctk.CTkFrame(container, fg_color=BG_PANEL_ALT, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        card_thresh.pack(fill="x", pady=(0, 12), padx=4)

        ctk.CTkLabel(card_thresh, text="DRIVING REGIME SPEED BOUNDARIES", font=FONT_BODY_BOLD, text_color=TEXT_PRIMARY).pack(anchor="w", padx=16, pady=(12, 8))

        t_grid = ctk.CTkFrame(card_thresh, fg_color="transparent")
        t_grid.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkLabel(t_grid, text="City Maximum Speed (km/h):", font=FONT_CAPTION, text_color=TEXT_SECONDARY).grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.entry_city_thresh = ctk.CTkEntry(t_grid, width=120)
        self.entry_city_thresh.insert(0, str(int(self.city_threshold)))
        self.entry_city_thresh.grid(row=0, column=1, sticky="w", padx=4, pady=4)

        ctk.CTkLabel(t_grid, text="Highway Minimum Speed (km/h):", font=FONT_CAPTION, text_color=TEXT_SECONDARY).grid(row=0, column=2, sticky="w", padx=(24, 4), pady=4)
        self.entry_hwy_thresh = ctk.CTkEntry(t_grid, width=120)
        self.entry_hwy_thresh.insert(0, str(int(self.highway_threshold)))
        self.entry_hwy_thresh.grid(row=0, column=3, sticky="w", padx=4, pady=4)

        # Section 3: Action Buttons
        btn_bar = ctk.CTkFrame(container, fg_color="transparent")
        btn_bar.pack(fill="x", pady=6, padx=4)

        btn_save_xml = ctk.CTkButton(
            btn_bar,
            text="Save Vehicle Profile to XML...",
            font=FONT_BODY_BOLD,
            height=32,
            fg_color=ACCENT_AMBER,
            hover_color="#D97706",
            text_color=BG_DARKEST,
            command=self._on_save_session_as_xml,
        )
        btn_save_xml.pack(side="left", padx=(0, 8))

        btn_load_xml = ctk.CTkButton(
            btn_bar,
            text="Open Profile from XML...",
            font=FONT_BODY_BOLD,
            height=32,
            fg_color=BG_PANEL_ALT,
            hover_color=BG_CARD_HOVER,
            border_width=1,
            border_color=BORDER_COLOR,
            command=self._on_open_session_xml,
        )
        btn_load_xml.pack(side="left", padx=(0, 8))

        btn_apply = ctk.CTkButton(
            btn_bar,
            text="Apply Profile & Thresholds",
            font=FONT_BODY_BOLD,
            height=32,
            fg_color=ACCENT_GREEN,
            hover_color="#059669",
            text_color=BG_DARKEST,
            command=self._apply_settings_from_tab,
        )
        btn_apply.pack(side="right")

    def _build_cleanup_sessions_tab(self):
        """Build combined Data Quality Audit & Trip Sessions Breakdown tab."""
        container = ctk.CTkFrame(self.tab_cleanup_sessions, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=6, pady=6)

        cleanup_box = ctk.CTkFrame(container, fg_color=BG_PANEL_ALT, corner_radius=6, border_width=1, border_color=BORDER_COLOR)
        cleanup_box.pack(fill="x", side="top", padx=2, pady=(0, 8))

        lbl_clean_title = ctk.CTkLabel(
            cleanup_box,
            text="PRE-INGESTION DATA CLEANUP & QUALITY AUDIT (CAR SCANNER ELM OBD2)",
            font=FONT_BODY_BOLD,
            text_color=TEXT_PRIMARY,
        )
        lbl_clean_title.pack(anchor="w", padx=12, pady=(8, 4))

        self.lbl_cleanup_details = ctk.CTkLabel(
            cleanup_box,
            text="Total Raw Rows: 0 | Retained: 0 | Dropped: 0 | Outliers Sanitized: 0",
            font=FONT_CAPTION,
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self.lbl_cleanup_details.pack(fill="x", padx=12, pady=(0, 8))

        table_bar = ctk.CTkFrame(container, fg_color="transparent")
        table_bar.pack(fill="x", padx=2, pady=(0, 4))

        ctk.CTkLabel(table_bar, text="DETAILED TRIP SESSIONS BREAKDOWN", font=FONT_BODY_BOLD, text_color=TEXT_PRIMARY).pack(side="left")

        btn_export = ctk.CTkButton(
            table_bar,
            text="Export Diagnostic Report...",
            font=FONT_CAPTION,
            height=28,
            fg_color=ACCENT_AMBER,
            hover_color="#D97706",
            text_color=BG_DARKEST,
            command=self._export_report,
        )
        btn_export.pack(side="right")

        self.table_scroll = ctk.CTkScrollableFrame(
            container,
            fg_color=BG_DARKEST,
            corner_radius=6,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.table_scroll.pack(fill="both", expand=True, padx=2, pady=2)

    # Startup & Session Life-Cycle
    def _initialize_startup_session(self):
        """Load last session if exists, otherwise start with a clean blank slate."""
        last_sess = load_last_session()
        if last_sess is not None:
            prof, settings, file_paths = last_sess
            if file_paths:
                self.profile = prof
                self.city_threshold = settings.get("city_threshold", 45.0)
                self.highway_threshold = settings.get("highway_threshold", 70.0)
                self.current_unit = settings.get("unit", "km/L")
                self.unit_segment.set(self.current_unit)
                self.analyzer.city_speed_max = self.city_threshold
                self.analyzer.highway_speed_min = self.highway_threshold
                self._update_settings_fields_from_profile()

                # Load files
                trips = []
                for p in file_paths:
                    trip = parse_obd_csv(p)
                    if trip is not None:
                        trips.append(trip)
                if trips:
                    self.all_trips = trips
                    self.selected_trips = list(trips)
                    self.record_panel.set_trips(trips)
                    self._reanalyze_and_redraw()
                    return

        # Blank startup
        self._set_blank_state()

    def _set_blank_state(self):
        """Set clean blank state with no files loaded."""
        self.all_trips = []
        self.selected_trips = []
        self.record_panel.set_trips([])
        self.current_fe_result = None
        self.current_diag_report = None
        self.current_trim_diag = None
        self.current_hybrid_rep = None
        self.current_anomalies = []

        self._update_hybrid_tab_visibility(False)
        self._update_active_vehicle_pill()
        self._update_metric_cards()
        self._render_blank_canvases()
        self._populate_trip_table()
        self._populate_anomalies_table()
        self._populate_cleanup_audit()

    def _render_blank_canvases(self):
        """Render welcoming instructions on all canvas views when no records are loaded."""
        canvases = [self.canvas_fe_map, self.canvas_rpm_speed, self.canvas_thermal, self.canvas_fuel_trims]
        if getattr(self, "canvas_hybrid", None) is not None:
            canvases.append(self.canvas_hybrid)
        for c in canvases:
            c.clear()
            ax = c.fig.add_subplot(111)
            ax.text(
                0.5, 0.5,
                "No scan records loaded.\nUse File -> Import Car Scanner CSV or Open Session to load data.",
                ha="center", va="center", color=TEXT_MUTED, fontsize=11, fontweight="bold"
            )
            c.draw()

    def _update_active_vehicle_pill(self):
        """Update top bar vehicle profile indicator."""
        summary = self.profile.summary_text()
        self.btn_active_vehicle.configure(text=f"Vehicle: {summary}")

    def _update_settings_fields_from_profile(self):
        """Sync text input fields with current VehicleProfile."""
        self.entry_make.delete(0, "end")
        self.entry_make.insert(0, self.profile.make)
        self.entry_model.delete(0, "end")
        self.entry_model.insert(0, self.profile.model)
        self.entry_year.delete(0, "end")
        self.entry_year.insert(0, self.profile.year)
        if self.profile.engine_type:
            self.entry_engine_type.set(self.profile.engine_type)
        self.entry_displacement.delete(0, "end")
        self.entry_displacement.insert(0, self.profile.displacement_cc)
        if self.profile.gears:
            self.entry_gears.set(self.profile.gears)
        self.entry_tyres.delete(0, "end")
        self.entry_tyres.insert(0, self.profile.tyre_size)
        self.entry_tank.delete(0, "end")
        self.entry_tank.insert(0, self.profile.fuel_tank_l)
        self.entry_notes.delete(0, "end")
        self.entry_notes.insert(0, self.profile.notes)

        self.entry_city_thresh.delete(0, "end")
        self.entry_city_thresh.insert(0, str(int(self.city_threshold)))
        self.entry_hwy_thresh.delete(0, "end")
        self.entry_hwy_thresh.insert(0, str(int(self.highway_threshold)))
        self._update_active_vehicle_pill()

    def _apply_settings_from_tab(self):
        """Save settings fields into profile and re-run analytics."""
        self.profile.make = self.entry_make.get().strip()
        self.profile.model = self.entry_model.get().strip()
        self.profile.year = self.entry_year.get().strip()
        self.profile.engine_type = self.entry_engine_type.get().strip()
        self.profile.displacement_cc = self.entry_displacement.get().strip()
        self.profile.gears = self.entry_gears.get().strip()
        self.profile.tyre_size = self.entry_tyres.get().strip()
        self.profile.fuel_tank_l = self.entry_tank.get().strip()
        self.profile.notes = self.entry_notes.get().strip()

        try:
            c_val = float(self.entry_city_thresh.get())
            h_val = float(self.entry_hwy_thresh.get())
            if c_val > 0 and h_val > c_val:
                self.city_threshold = c_val
                self.highway_threshold = h_val
                self.analyzer.city_speed_max = c_val
                self.analyzer.highway_speed_min = h_val
        except ValueError:
            pass

        self._update_active_vehicle_pill()
        self._persist_session()
        self._reanalyze_and_redraw()
        messagebox.showinfo("Settings Applied", "Vehicle profile and speed thresholds updated successfully.", parent=self)

    def _open_settings_tab(self):
        self.tabview.set("Vehicle Profile & Settings")

    def _persist_session(self):
        """Save active state to last_session.xml."""
        file_paths = [t.file_path for t in self.all_trips]
        save_last_session(
            self.profile,
            self.city_threshold,
            self.highway_threshold,
            self.current_unit,
            file_paths,
        )

    # Menu Actions
    def _on_new_session(self):
        """Reset application to blank new session."""
        if messagebox.askyesno("New Session", "Start a new blank session? This will clear current records and profile.", parent=self):
            self.current_xml_path = None
            self.profile = VehicleProfile()
            self._update_settings_fields_from_profile()
            self._set_blank_state()
            self._persist_session()

    def _on_open_session_xml(self):
        """Open vehicle session from an XML file."""
        file_path = filedialog.askopenfilename(
            title="Open Vehicle Profile / Session XML",
            filetypes=[("XML Session Files", "*.xml"), ("All Files", "*.*")]
        )
        if not file_path:
            return

        res = load_session_from_xml(file_path)
        if res is None:
            messagebox.showerror("Error", f"Failed to parse XML session file:\n{file_path}", parent=self)
            return

        prof, settings, file_paths = res
        self.current_xml_path = file_path
        self.profile = prof
        self.city_threshold = settings.get("city_threshold", 45.0)
        self.highway_threshold = settings.get("highway_threshold", 70.0)
        self.current_unit = settings.get("unit", "km/L")
        self.unit_segment.set(self.current_unit)
        self.analyzer.city_speed_max = self.city_threshold
        self.analyzer.highway_speed_min = self.highway_threshold
        self._update_settings_fields_from_profile()

        # Load linked records
        trips = []
        for p in file_paths:
            trip = parse_obd_csv(p)
            if trip is not None:
                trips.append(trip)

        self.all_trips = trips
        self.selected_trips = list(trips)
        self.record_panel.set_trips(trips)
        self._persist_session()
        self._reanalyze_and_redraw()
        messagebox.showinfo("Session Loaded", f"Loaded vehicle '{self.profile.summary_text()}' with {len(trips)} records.", parent=self)

    def _on_save_session_xml(self):
        """Save active session to XML."""
        if self.current_xml_path and os.path.exists(self.current_xml_path):
            self._save_to_path(self.current_xml_path)
        else:
            self._on_save_session_as_xml()

    def _on_save_session_as_xml(self):
        """Prompt user for XML path and save session."""
        default_name = f"{self.profile.make}_{self.profile.model}_session.xml".replace(" ", "_") if self.profile.model else "vehicle_session.xml"
        file_path = filedialog.asksaveasfilename(
            title="Save Vehicle Session XML",
            initialfile=default_name,
            defaultextension=".xml",
            filetypes=[("XML Session Files", "*.xml"), ("All Files", "*.*")]
        )
        if not file_path:
            return
        self._save_to_path(file_path)

    def _save_to_path(self, path: str):
        file_paths = [t.file_path for t in self.all_trips]
        success = save_session_to_xml(
            path,
            self.profile,
            self.city_threshold,
            self.highway_threshold,
            self.current_unit,
            file_paths,
        )
        if success:
            self.current_xml_path = path
            self._persist_session()
            messagebox.showinfo("Session Saved", f"Session saved successfully as XML to:\n{path}", parent=self)
        else:
            messagebox.showerror("Error", f"Failed to write XML session to:\n{path}", parent=self)

    def _on_import_folder(self):
        """Import all Car Scanner CSV logs in a selected directory."""
        dir_path = filedialog.askdirectory(title="Select Folder Containing Car Scanner CSV Logs")
        if not dir_path:
            return
        trips = load_all_records(dir_path)
        if not trips:
            messagebox.showwarning("No CSV Logs", f"No valid Car Scanner CSV records found in:\n{dir_path}", parent=self)
            return

        self.all_trips = trips
        self.selected_trips = list(trips)
        self.record_panel.set_trips(trips)
        self._persist_session()

        if not self.profile.is_configured:
            self._open_vehicle_settings_window(on_done=self._reanalyze_and_redraw)
        else:
            self._reanalyze_and_redraw()

    def _open_vehicle_settings_window(self, on_done=None):
        """Open separate dialog window to configure vehicle make, model, engine, gears, tyre size, etc."""
        def apply_callback(new_prof: VehicleProfile, city_th: float, hwy_th: float, unit_val: str):
            self.profile = new_prof
            self.city_threshold = city_th
            self.highway_threshold = hwy_th
            self.current_unit = unit_val
            self.unit_segment.set(unit_val)
            self.analyzer.city_speed_max = city_th
            self.analyzer.highway_speed_min = hwy_th
            self._update_settings_fields_from_profile()
            self._update_active_vehicle_pill()
            self._persist_session()
            if on_done:
                on_done()
            else:
                self._reanalyze_and_redraw()

        def save_xml_callback(new_prof: VehicleProfile, city_th: float, hwy_th: float, unit_val: str):
            file_path = filedialog.asksaveasfilename(
                title="Save Session XML As...",
                defaultextension=".xml",
                filetypes=[("XML Session Files", "*.xml"), ("All Files", "*.*")]
            )
            if not file_path:
                return
            self.profile = new_prof
            self.city_threshold = city_th
            self.highway_threshold = hwy_th
            self.current_unit = unit_val
            self.unit_segment.set(unit_val)
            self.analyzer.city_speed_max = city_th
            self.analyzer.highway_speed_min = hwy_th
            self._update_settings_fields_from_profile()
            self._update_active_vehicle_pill()
            data_paths = [t.file_path for t in self.all_trips]
            if save_session_to_xml(file_path, self.profile, self.city_threshold, self.highway_threshold, self.current_unit, data_paths):
                self.current_xml_path = file_path
                self._persist_session()
                messagebox.showinfo("Session Saved", f"Session XML saved to:\n{file_path}", parent=self)
                if on_done:
                    on_done()
                else:
                    self._reanalyze_and_redraw()

        VehicleSettingsDialog(
            parent=self,
            profile=self.profile,
            city_threshold=self.city_threshold,
            highway_threshold=self.highway_threshold,
            unit=self.current_unit,
            on_apply=apply_callback,
            on_save_xml=save_xml_callback,
        )

    def _check_for_updates_ui(self, silent: bool = False):
        """Query GitHub Releases API in background thread and notify user."""
        def worker():
            update_avail, release_data, err = check_for_updates(timeout_sec=4.0)

            def callback():
                if update_avail and release_data:
                    SoftwareUpdateDialog(self, release_data, get_app_version())
                elif not update_avail and release_data:
                    if not silent:
                        cur = get_app_version()
                        messagebox.showinfo(
                            "Software Up to Date",
                            f"OBD-II Telemetry Suit v{cur} is currently up to date.\n(GitHub release: v{release_data.get('tag_name', cur)})",
                            parent=self,
                        )
                elif err:
                    if not silent:
                        messagebox.showwarning("Update Check", err, parent=self)

            self.after(0, callback)

        threading.Thread(target=worker, daemon=True).start()

    def _reload_active_files(self):
        """Reload currently loaded files."""
        if not self.all_trips:
            return
        paths = [t.file_path for t in self.all_trips]
        reloaded = []
        for p in paths:
            t = parse_obd_csv(p)
            if t is not None:
                reloaded.append(t)
        self.all_trips = reloaded
        self.selected_trips = list(reloaded)
        self.record_panel.set_trips(reloaded)
        self._reanalyze_and_redraw()

    def _open_quick_vehicle_info(self):
        """Display friendly auto-detection summary for non-technical users."""
        info = self.analyzer.auto_detect_vehicle_info(self.selected_trips)

        dlg = ctk.CTkToplevel(self)
        dlg.title("Quick Vehicle Information")
        dlg.geometry("540x480")
        dlg.resizable(False, False)
        dlg.configure(fg_color=BG_PANEL)
        dlg.grab_set()

        ctk.CTkLabel(dlg, text="QUICK VEHICLE INTELLIGENCE", font=FONT_TITLE, text_color=TEXT_PRIMARY).pack(pady=(16, 4))
        ctk.CTkLabel(dlg, text="Automated vehicle diagnosis without requiring manual technical entries.", font=FONT_CAPTION, text_color=TEXT_MUTED).pack(pady=(0, 12))

        box = ctk.CTkFrame(dlg, fg_color=BG_PANEL_ALT, corner_radius=6, border_width=1, border_color=BORDER_COLOR)
        box.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        # Rows
        items = [
            ("Powertrain Class:", info.vehicle_class, ACCENT_GREEN if "Hybrid" in info.vehicle_class else TEXT_PRIMARY),
            ("Fuel Economy Score:", info.fuel_efficiency_grade, TEXT_AMBER),
            ("12V Auxiliary System:", info.battery_health_summary, ACCENT_CYAN),
            ("Engine Thermal State:", info.thermal_condition_summary, TEXT_PRIMARY),
            ("Fuel Injection Balance:", info.fuel_trim_summary, TEXT_PRIMARY),
            ("Monitored Sensors:", f"{info.total_sensors_communicated} live OBD PIDs", TEXT_SECONDARY),
        ]

        for lbl_name, val_text, color in items:
            row = ctk.CTkFrame(box, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=4)
            ctk.CTkLabel(row, text=lbl_name, font=FONT_BODY_BOLD, text_color=TEXT_SECONDARY, width=160, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=val_text, font=FONT_BODY, text_color=color, anchor="w").pack(side="left")

        # Plain English takeaways
        ctk.CTkLabel(box, text="KEY TAKEAWAYS FOR DRIVER:", font=FONT_BADGE, text_color=TEXT_AMBER).pack(anchor="w", padx=14, pady=(10, 4))
        for t_line in info.plain_english_takeaways:
            ctk.CTkLabel(box, text=f"- {t_line}", font=FONT_CAPTION, text_color=TEXT_PRIMARY, wraplength=480, justify="left", anchor="w").pack(fill="x", padx=14, pady=2)

        ctk.CTkButton(dlg, text="Close", font=FONT_BODY_BOLD, width=120, fg_color=ACCENT_AMBER, hover_color="#D97706", text_color=BG_DARKEST, command=dlg.destroy).pack(pady=(0, 14))

    def _show_format_info(self):
        msg = (
            "Supported Export Format:\n\n"
            "This application exclusively ingests Car Scanner ELM OBD2 app's vertical CSV export.\n\n"
            "Required semicolon-delimited header:\n"
            "SECONDS;PID;VALUE;UNITS;LATITUDE;LONGTITUDE\n\n"
            "Non-compliant CSV formats will be safely rejected by the pre-ingestion validation pipeline."
        )
        messagebox.showinfo("Supported Format Info", msg, parent=self)

    def _show_about(self):
        ver = get_app_version()
        msg = (
            f"OBD-II Telemetry Suit\n"
            f"Version {ver} (Beta)\n\n"
            "Automotive diagnostic desktop workstation for Car Scanner ELM OBD2 scan logs.\n"
            "Features pre-ingestion cleaning, hybrid battery health diagnostics, "
            "STFT/LTFT recommendations, 2D efficiency heatmaps, and ML anomaly detection."
        )
        messagebox.showinfo("About OBD-II Telemetry Suit", msg, parent=self)

    def _on_records_selection_changed(self, selected_paths: List[str]):
        """Callback when user checks/unchecks files."""
        self.selected_trips = [t for t in self.all_trips if t.file_path in selected_paths]
        self._reanalyze_and_redraw()

    def _on_add_files(self):
        """Open file dialog to import external Car Scanner ELM OBD2 scan CSV files."""
        file_paths = filedialog.askopenfilenames(
            title="Select Car Scanner ELM OBD2 CSV Records",
            filetypes=[("OBD Scan CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if not file_paths:
            return

        added_any = False
        for p in file_paths:
            if not any(t.file_path == p for t in self.all_trips):
                trip = parse_obd_csv(p)
                if trip is not None:
                    self.all_trips.append(trip)
                    added_any = True

        if added_any:
            self.selected_trips = list(self.all_trips)
            self.record_panel.set_trips(self.all_trips)
            self._persist_session()
            if not self.profile.is_configured:
                self._open_vehicle_settings_window(on_done=self._reanalyze_and_redraw)
            else:
                self._reanalyze_and_redraw()

    def _on_unit_changed(self, new_unit: str):
        """Callback when user toggles fuel economy unit."""
        self.current_unit = new_unit
        self.unit_segment.set(new_unit)
        self._update_metric_cards()
        self._render_fe_map_graph()
        self._populate_trip_table()
        self._persist_session()

    def _on_fe_mode_changed(self, mode_str: str):
        """Callback when user toggles fuel economy plot mode."""
        if "All" in mode_str:
            self.fe_display_mode_val = "all"
        else:
            self.fe_display_mode_val = "tractive"
        self._render_fe_map_graph()

    def _open_thresholds_dialog(self):
        """Dialog to adjust city and highway speed boundaries."""
        dlg = ctk.CTkToplevel(self)
        dlg.title("Configure Speed Thresholds")
        dlg.geometry("380x280")
        dlg.resizable(False, False)
        dlg.configure(fg_color=BG_PANEL)
        dlg.grab_set()

        lbl_header = ctk.CTkLabel(
            dlg,
            text="DRIVING SEGMENT SPEED THRESHOLDS",
            font=FONT_BODY_BOLD,
            text_color=TEXT_PRIMARY,
        )
        lbl_header.pack(pady=(16, 12))

        f_city = ctk.CTkFrame(dlg, fg_color="transparent")
        f_city.pack(fill="x", padx=24, pady=6)
        ctk.CTkLabel(f_city, text="City Max Speed (km/h):", font=FONT_BODY, text_color=TEXT_SECONDARY).pack(side="left")
        entry_city = ctk.CTkEntry(f_city, width=80)
        entry_city.insert(0, str(int(self.city_threshold)))
        entry_city.pack(side="right")

        f_hwy = ctk.CTkFrame(dlg, fg_color="transparent")
        f_hwy.pack(fill="x", padx=24, pady=6)
        ctk.CTkLabel(f_hwy, text="Highway Min Speed (km/h):", font=FONT_BODY, text_color=TEXT_SECONDARY).pack(side="left")
        entry_hwy = ctk.CTkEntry(f_hwy, width=80)
        entry_hwy.insert(0, str(int(self.highway_threshold)))
        entry_hwy.pack(side="right")

        def save():
            try:
                c_val = float(entry_city.get())
                h_val = float(entry_hwy.get())
                if c_val <= 0 or h_val <= c_val:
                    messagebox.showerror("Error", "Highway threshold must be greater than City threshold.", parent=dlg)
                    return
                self.city_threshold = c_val
                self.highway_threshold = h_val
                self.analyzer.city_speed_max = c_val
                self.analyzer.highway_speed_min = h_val
                dlg.destroy()
                self._persist_session()
                self._reanalyze_and_redraw()
            except ValueError:
                messagebox.showerror("Error", "Please enter valid numeric speeds.", parent=dlg)

        btn_save = ctk.CTkButton(
            dlg,
            text="Apply Thresholds",
            font=FONT_BODY_BOLD,
            fg_color=ACCENT_AMBER,
            hover_color="#D97706",
            text_color=BG_DARKEST,
            command=save,
        )
        btn_save.pack(pady=(20, 10))

    def _reanalyze_and_redraw(self):
        """Run full data science analysis pipeline and refresh all views."""
        trips = self.selected_trips
        if not trips:
            self._set_blank_state()
            return

        is_hybrid = any(t.is_hybrid for t in trips)
        self._update_hybrid_tab_visibility(is_hybrid)

        self.current_fe_result = self.analyzer.calculate_fuel_economy(trips)
        self.current_diag_report = self.analyzer.generate_diagnostic_health(trips)
        self.current_trim_diag = self.analyzer.analyze_fuel_trims_in_depth(trips)
        self.current_hybrid_rep = self.analyzer.analyze_hybrid_powertrain(trips) if is_hybrid else None
        self.current_anomalies = self.analyzer.detect_anomalies(trips)

        # Update Telemetry & Status Readouts
        self._update_active_vehicle_pill()
        self._update_metric_cards()
        self._update_diagnostic_panel()
        self._update_fuel_trim_recommendations()
        if is_hybrid:
            self._update_hybrid_summary()

        # Render all charts
        self._render_fe_map_graph()
        self._render_rpm_speed_graph()
        self._render_thermal_graph()
        self._render_fuel_trim_graph()
        if is_hybrid:
            self._render_hybrid_graph()
        self._populate_anomalies_table()
        self._populate_cleanup_audit()
        self._populate_trip_table()

    def _update_metric_cards(self):
        """Update top telemetry cards with converted units and status."""
        fe = self.current_fe_result
        unit = self.current_unit
        if fe is None or not self.selected_trips:
            self.card_city.update_card("-", unit, "Speed <= 45 km/h", "NO DATA")
            self.card_highway.update_card("-", unit, "Speed >= 70 km/h", "NO DATA")
            self.card_combined.update_card("-", unit, "Weighted Moving Average", "NO DATA")
            self.card_distance.update_card("-", "km", "Total Consumed: - L", "TRIP")
            self.card_sweet_spot.update_card("-", "km/h", "Best Cruising RPM", "SWEET SPOT")
            self.card_hybrid_battery.update_card("-", "%", "Engine Idle Proportion", "NO DATA", title="Idle Time %")
            return

        city_str = fe.format_value("city", unit)
        city_status = "OPTIMAL" if city_str != "-" else "NO DATA"
        self.card_city.update_card(
            city_str,
            unit,
            f"Sampled: {fe.city_distance_km:.1f} km ({fe.city_fuel_liters:.2f} L)",
            city_status,
            accent_color=TEXT_CYAN if city_str != "-" else TEXT_MUTED,
        )

        hwy_str = fe.format_value("highway", unit)
        hwy_status = "OPTIMAL" if hwy_str != "-" else "NO DATA"
        self.card_highway.update_card(
            hwy_str,
            unit,
            f"Sampled: {fe.highway_distance_km:.1f} km ({fe.highway_fuel_liters:.2f} L)",
            hwy_status,
            accent_color=TEXT_GREEN if hwy_str != "-" else TEXT_MUTED,
        )

        comb_str = fe.format_value("combined", unit)
        comb_status = "OPTIMAL" if comb_str != "-" else "NO DATA"
        self.card_combined.update_card(
            comb_str,
            unit,
            f"Total Moving: {fe.total_distance_km:.1f} km",
            comb_status,
            accent_color=TEXT_AMBER if comb_str != "-" else TEXT_MUTED,
        )

        self.card_distance.update_card(
            f"{fe.total_distance_km:.1f}",
            "km",
            f"Total Consumed: {fe.total_fuel_liters:.2f} L (Avg: {fe.avg_moving_speed_kmh:.0f} km/h)",
            "TRIP",
        )

        # Update 6th Card: Hybrid SOC if hybrid, else Idle Loss %
        hyb = self.current_hybrid_rep
        is_hybrid_veh = any(t.is_hybrid for t in self.selected_trips) if self.selected_trips else False
        if is_hybrid_veh and hyb and hyb.is_hybrid and hyb.soc_mean is not None:
            delta_str = f"Delta V: {hyb.delta_block_v * 1000:.0f}mV" if hyb.delta_block_v is not None else "HV Battery"
            self.card_hybrid_battery.update_card(
                f"{hyb.soc_mean:.1f}",
                "%",
                delta_str,
                "HYBRID SOC",
                accent_color=ACCENT_GREEN if "OPTIMAL" in hyb.battery_health_status else ACCENT_AMBER,
                title="HV Battery SOC",
            )
        else:
            idle_status = "ALERT" if fe.idle_percentage > 25.0 else ("NORMAL" if fe.idle_percentage < 15.0 else "AVG")
            self.card_hybrid_battery.update_card(
                f"{fe.idle_percentage:.1f}",
                "%",
                f"Idle Time: {fe.idle_time_seconds / 60.0:.1f}m",
                idle_status,
                accent_color=ACCENT_RED if fe.idle_percentage > 25 else TEXT_SECONDARY,
                title="Idle Time %",
            )

    def _update_diagnostic_panel(self):
        """Update mechanic diagnostic status card in the left sidebar."""
        rep = self.current_diag_report
        if rep is None:
            return

        b_color = ACCENT_GREEN if "NORMAL" in rep.battery_status else (ACCENT_AMBER if "LOW" in rep.battery_status else ACCENT_RED)
        b_text = f"12V Battery: {rep.battery_status} (Avg {rep.battery_mean_v:.1f}V)"
        self.lbl_battery_status.configure(text=b_text, text_color=b_color)

        c_color = ACCENT_GREEN if "NORMAL" in rep.coolant_status else (ACCENT_RED if "OVERHEAT" in rep.coolant_status else ACCENT_AMBER)
        c_text = f"Coolant: {rep.coolant_status} (Peak {rep.coolant_max_c:.0f} C)"
        self.lbl_coolant_status.configure(text=c_text, text_color=c_color)

        t_color = ACCENT_GREEN if "NORMAL" in rep.fuel_trim_status else (ACCENT_AMBER if "MARGINAL" in rep.fuel_trim_status else ACCENT_RED)
        trim_str = f"{rep.total_trim_pct:+.1f}%" if rep.total_trim_pct is not None else "N/A"
        t_text = f"Fuel Trim: {rep.fuel_trim_status} (Total {trim_str})"
        self.lbl_trim_status.configure(text=t_text, text_color=t_color)

        if rep.notes:
            notes_str = " | ".join(rep.notes)
        else:
            notes_str = "All primary sensor parameters within standard automotive specifications."
        self.lbl_diag_notes.configure(text=notes_str)

    def _update_fuel_trim_recommendations(self):
        """Update detailed fuel trim diagnostic box and action steps."""
        td = self.current_trim_diag
        if td is None or not td.has_data:
            self.lbl_trim_diag_title.configure(text="DIAGNOSIS: NO FUEL TRIM DATA")
            self.lbl_trim_badge.configure(text="[NO DATA]", text_color=TEXT_MUTED)
            self.lbl_trim_zone_stats.configure(text="Idle: N/A | Cruise: N/A | High Load: N/A")
            self.lbl_trim_rec_text.configure(text="Fuel trim PIDs not recorded in selected files.")
            return

        badge_color = ACCENT_GREEN if td.severity == "OPTIMAL" else (ACCENT_AMBER if td.severity == "WARNING" else ACCENT_RED)
        self.lbl_trim_diag_title.configure(text=f"DIAGNOSIS: {td.diagnosis_title} (LIKELIHOOD: {td.likelihood_score})")
        self.lbl_trim_badge.configure(text=f"[{td.severity}]", text_color=badge_color)

        idle_str = f"{td.idle_total_trim:+.1f}%" if td.idle_total_trim is not None else "N/A"
        cruise_str = f"{td.cruise_total_trim:+.1f}%" if td.cruise_total_trim is not None else "N/A"
        hi_str = f"{td.high_load_total_trim:+.1f}%" if td.high_load_total_trim is not None else "N/A"
        self.lbl_trim_zone_stats.configure(
            text=f"Idle Total Trim: {idle_str}   |   Cruising Total Trim: {cruise_str}   |   High-Load Total Trim: {hi_str}"
        )

        rec_lines = []
        if td.probable_causes:
            rec_lines.append("Probable Causes: " + " ".join(td.probable_causes))
        if td.mechanic_recommendations:
            rec_lines.append("Mechanic Action Plan: " + " ".join(td.mechanic_recommendations))
        self.lbl_trim_rec_text.configure(text="\n".join(rec_lines))

    def _update_hybrid_summary(self):
        """Update hybrid summary box."""
        hyb = self.current_hybrid_rep
        if hyb is None or not hyb.is_hybrid:
            self.lbl_hybrid_title.configure(text="HYBRID POWERTRAIN (NON-HYBRID VEHICLE)")
            self.lbl_hybrid_badge.configure(text="[NOT HYBRID]", text_color=TEXT_MUTED)
            self.lbl_hybrid_metrics.configure(text="Vehicle powertrain does not report High-Voltage battery telemetry.")
            self.lbl_hybrid_obs.configure(text="Standard internal combustion telemetry active.")
            return

        badge_color = ACCENT_GREEN if "OPTIMAL" in hyb.battery_health_status else (ACCENT_AMBER if "WARNING" in hyb.battery_health_status else ACCENT_RED)
        self.lbl_hybrid_title.configure(text=f"HYBRID POWERTRAIN HEALTH: {hyb.battery_health_status}")
        self.lbl_hybrid_badge.configure(text="[HYBRID ACTIVE]", text_color=badge_color)

        soc_str = f"{hyb.soc_mean:.1f}% (Range: {hyb.soc_min:.0f}-{hyb.soc_max:.0f}%)" if hyb.soc_mean is not None else "N/A"
        delta_str = f"{hyb.delta_block_v * 1000:.0f} mV" if hyb.delta_block_v is not None else "N/A"
        inv_str = f"{hyb.inverter_temp_c:.0f} C" if hyb.inverter_temp_c is not None else "N/A"
        ev_str = f"{hyb.ev_driving_pct:.1f}%"

        self.lbl_hybrid_metrics.configure(
            text=f"Battery SOC: {soc_str}   |   Block Delta V: {delta_str}   |   Inverter Temp: {inv_str}   |   EV Driving Ratio: {ev_str}"
        )

        obs_text = " | ".join(hyb.observations) if hyb.observations else "Hybrid battery blocks operating with balanced voltage distribution."
        self.lbl_hybrid_obs.configure(text=obs_text)

    def _render_fe_map_graph(self):
        """Render 2D Fuel Economy Heatmap & Sweet Spot Map."""
        canvas = self.canvas_fe_map
        canvas.clear()
        fig = canvas.fig

        trips = self.selected_trips
        if not trips:
            canvas.draw()
            return

        fe_map = self.analyzer.compute_optimal_fuel_economy_rpm_speed_curve(trips)
        if not fe_map["has_data"]:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, "Insufficient fuel economy data in selected records.", ha="center", va="center", color=TEXT_MUTED)
            canvas.draw()
            return

        ax1 = fig.add_subplot(121)
        ax2 = fig.add_subplot(122)

        s_bins = fe_map["speed_bins"]
        r_bins = fe_map["rpm_bins"]
        matrix = fe_map["fe_matrix"]

        unit = self.current_unit
        display_matrix = matrix.copy()
        if unit == "L/100km":
            display_matrix = 100.0 / np.where(display_matrix > 0, display_matrix, np.nan)
        elif unit == "MPG (US)":
            display_matrix = display_matrix * 2.35214583
        elif unit == "MPG (UK)":
            display_matrix = display_matrix * 2.82480936

        cmap_name = "viridis_r" if unit == "L/100km" else "viridis"
        c = ax1.pcolormesh(
            s_bins,
            r_bins,
            display_matrix,
            cmap=cmap_name,
            shading="auto",
            alpha=0.9,
        )
        cbar = fig.colorbar(c, ax=ax1, fraction=0.046, pad=0.04)
        cbar.set_label(f"Efficiency ({unit})", color=TEXT_SECONDARY)
        cbar.ax.yaxis.set_tick_params(color=TEXT_MUTED)
        plt.setp(plt.getp(cbar.ax.axes, "yticklabels"), color=TEXT_SECONDARY)

        opt_s = fe_map["opt_speed"]
        opt_r = fe_map["opt_rpm"]
        if len(opt_s) > 0:
            ax1.plot(
                opt_s,
                opt_r,
                color="#FFFFFF",
                linewidth=2.5,
                linestyle="-",
                label="Optimal Operating Curve",
            )
            ax1.scatter(opt_s, opt_r, color=ACCENT_AMBER, s=40, zorder=5)

        sp = fe_map["sweet_spot"]
        if sp:
            sp_fe = sp["fe_kml"]
            if unit == "L/100km":
                sp_fe_conv = 100.0 / sp_fe if sp_fe > 0 else 0
            elif unit == "MPG (US)":
                sp_fe_conv = sp_fe * 2.35214583
            elif unit == "MPG (UK)":
                sp_fe_conv = sp_fe * 2.82480936
            else:
                sp_fe_conv = sp_fe

            ax1.scatter(
                [sp["speed_kmh"]],
                [sp["rpm"]],
                color="#EF4444",
                s=120,
                marker="*",
                edgecolors="#FFFFFF",
                linewidth=1.5,
                zorder=10,
                label=f"Sweet Spot: {sp['speed_kmh']:.0f} km/h @ {sp['rpm']:.0f} RPM",
            )
            self.card_sweet_spot.update_card(
                f"{sp['speed_kmh']:.0f}",
                "km/h",
                f"RPM: {sp['rpm']:.0f} ({sp_fe_conv:.1f} {unit})",
                "SWEET SPOT",
            )

        ax1.set_title("Fuel Economy Heatmap (Speed vs RPM) [Tractive Cruise]", fontsize=11, fontweight="bold", pad=8)
        ax1.set_xlabel("Vehicle Speed (km/h)", fontsize=10)
        ax1.set_ylabel("Engine RPM (rpm)", fontsize=10)
        ax1.grid(True, linestyle="--", alpha=0.3)
        ax1.legend(loc="upper left", fontsize=8)

        display_mode = getattr(self, "fe_display_mode_val", "tractive")

        scatter_s = fe_map["scatter_speed"]
        scatter_fe = fe_map["scatter_fe"].copy()
        if unit == "L/100km":
            scatter_fe = 100.0 / scatter_fe
        elif unit == "MPG (US)":
            scatter_fe = scatter_fe * 2.35214583
        elif unit == "MPG (UK)":
            scatter_fe = scatter_fe * 2.82480936

        # When requested, display raw deceleration, downhill overrun, and DFCO spikes faintly
        if display_mode == "all" and "coasting_speed" in fe_map and len(fe_map["coasting_speed"]) > 0:
            c_s = fe_map["coasting_speed"]
            c_fe = fe_map["coasting_fe"].copy()
            if unit == "L/100km":
                c_fe = 100.0 / np.where(c_fe > 0, c_fe, np.nan)
            elif unit == "MPG (US)":
                c_fe = c_fe * 2.35214583
            elif unit == "MPG (UK)":
                c_fe = c_fe * 2.82480936

            c_sub = np.random.choice(len(c_s), min(800, len(c_s)), replace=False)
            ax2.scatter(
                c_s[c_sub],
                c_fe[c_sub],
                color="#64748B",
                alpha=0.18,
                s=10,
                marker="x",
                label="DFCO / Overrun Spikes",
                zorder=2,
            )

        sub_idx = np.random.choice(len(scatter_s), min(1200, len(scatter_s)), replace=False)
        ax2.scatter(
            scatter_s[sub_idx],
            scatter_fe[sub_idx],
            color=ACCENT_CYAN,
            alpha=0.30,
            s=12,
            edgecolors="none",
            label="Real-World Tractive Cruise",
            zorder=3,
        )

        # Machine Learning Road Load Steady-State Cruise Model Curve
        ml_s = fe_map.get("ml_curve_speed")
        ml_fe = fe_map.get("ml_curve_fe")
        if ml_s is not None and len(ml_s) > 0 and ml_fe is not None and len(ml_fe) > 0:
            ml_fe_disp = ml_fe.copy()
            if unit == "L/100km":
                ml_fe_disp = 100.0 / ml_fe_disp
            elif unit == "MPG (US)":
                ml_fe_disp = ml_fe_disp * 2.35214583
            elif unit == "MPG (UK)":
                ml_fe_disp = ml_fe_disp * 2.82480936

            ax2.plot(
                ml_s,
                ml_fe_disp,
                color=ACCENT_AMBER,
                linewidth=2.8,
                label="ML Steady Cruise Model",
                zorder=5,
            )

        if len(opt_s) > 0:
            opt_fe_arr = fe_map["opt_fe"].copy()
            if unit == "L/100km":
                opt_fe_arr = 100.0 / opt_fe_arr
            elif unit == "MPG (US)":
                opt_fe_arr = opt_fe_arr * 2.35214583
            elif unit == "MPG (UK)":
                opt_fe_arr = opt_fe_arr * 2.82480936

            ax2.plot(
                opt_s,
                opt_fe_arr,
                color="#FFFFFF",
                linewidth=1.8,
                linestyle="--",
                marker="o",
                markersize=4,
                label="Peak Operating Envelope",
                zorder=6,
            )

        ax2.axvline(self.city_threshold, color="#3B82F6", linestyle="--", alpha=0.6, label=f"City Limit ({self.city_threshold:.0f} km/h)")
        ax2.axvline(self.highway_threshold, color=ACCENT_GREEN, linestyle="--", alpha=0.6, label=f"Highway Gate ({self.highway_threshold:.0f} km/h)")

        ax2.set_title(f"Fuel Economy vs Vehicle Speed ({unit})", fontsize=11, fontweight="bold", pad=8)
        ax2.set_xlabel("Vehicle Speed (km/h)", fontsize=10)
        ax2.set_ylabel(f"Fuel Economy ({unit})", fontsize=10)
        ax2.grid(True, linestyle="--", alpha=0.3)
        ax2.legend(loc="upper right", fontsize=8)

        # Update DFCO status bar in Tab 1
        dfco_info = fe_map.get("dfco_result")
        if dfco_info and hasattr(self, "lbl_fe_dfco_status"):
            self.lbl_fe_dfco_status.configure(
                text=(
                    f"DFCO Status: {dfco_info.status}   |   "
                    f"Engagement: {dfco_info.dfco_engagement_pct:.1f}% ({dfco_info.active_dfco_seconds:.0f}s active / {dfco_info.eligible_decel_seconds:.0f}s eligible)   |   "
                    f"Fuel Saved: {dfco_info.fuel_saved_liters:.2f} L"
                )
            )

        canvas.draw()

    def _render_rpm_speed_graph(self):
        """Render Optimal RPM vs Speed curve with gear traces."""
        canvas = self.canvas_rpm_speed
        canvas.clear()
        fig = canvas.fig

        trips = self.selected_trips
        if not trips:
            canvas.draw()
            return

        max_gears = self.profile.forward_gears
        curve_res = self.analyzer.compute_optimal_rpm_speed_curve(trips, max_gears=max_gears)
        ax = fig.add_subplot(111)

        s_val = curve_res["speed"]
        r_val = curve_res["rpm"]

        if len(s_val) == 0:
            ax.text(0.5, 0.5, "No moving speed and RPM data available.", ha="center", va="center", color=TEXT_MUTED)
            canvas.draw()
            return

        sub_idx = np.random.choice(len(s_val), min(1500, len(s_val)), replace=False)
        ax.scatter(
            s_val[sub_idx],
            r_val[sub_idx],
            color="#3B82F6",
            alpha=0.25,
            s=12,
            edgecolors="none",
            label="OBD Scan Points",
        )

        gear_colors = [ACCENT_CYAN, ACCENT_GREEN, ACCENT_AMBER, ACCENT_PURPLE, "#EC4899", "#38BDF8", "#F59E0B", "#10B981"]
        for idx, g in enumerate(curve_res["gear_lines"]):
            color = gear_colors[idx % len(gear_colors)]
            ax.plot(
                g["speed_line"],
                g["rpm_line"],
                color=color,
                linestyle=":",
                linewidth=1.6,
                label=f"{g['gear_name']} ({g['ratio'] * 1000:.1f} km/h/kRPM)",
            )

        opt_s = curve_res["opt_speed"]
        opt_r = curve_res["opt_rpm"]
        if len(opt_s) > 0:
            ax.plot(
                opt_s,
                opt_r,
                color="#FFFFFF",
                linewidth=3.0,
                marker="o",
                markersize=5,
                label="Median Operating RPM Curve",
            )

        ax.set_title("Vehicle Speed vs Engine RPM & Gear Ratio Mapping", fontsize=12, fontweight="bold", pad=10)
        ax.set_xlabel("Vehicle Speed (km/h)", fontsize=11)
        ax.set_ylabel("Engine Speed (RPM)", fontsize=11)
        ax.set_ylim(bottom=500)
        ax.set_xlim(left=0)
        ax.grid(True, linestyle="--", alpha=0.3)
        ax.legend(loc="upper left", fontsize=9)

        canvas.draw()

    def _render_thermal_graph(self):
        """Render Coolant Temperature timelines, thermostat bands, and load correlation."""
        canvas = self.canvas_thermal
        canvas.clear()
        fig = canvas.fig

        trips = self.selected_trips
        if not trips:
            canvas.draw()
            return

        thermal = self.analyzer.analyze_coolant_temperature(trips)
        if not thermal["has_data"]:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, "No engine coolant temperature sensor data available.", ha="center", va="center", color=TEXT_MUTED)
            canvas.draw()
            return

        ax1 = fig.add_subplot(121)
        ax2 = fig.add_subplot(122)

        norm_low, norm_high = thermal["normal_band"]
        for trip_curve in thermal["trip_curves"]:
            clean_name = os.path.basename(trip_curve["name"]).replace(".csv", "")
            ax1.plot(
                trip_curve["time_minutes"],
                trip_curve["temperature_c"],
                linewidth=1.8,
                label=clean_name,
            )

        ax1.axhspan(norm_low, norm_high, color=ACCENT_GREEN, alpha=0.15, label="Normal Thermostat Band (82-95 C)")
        ax1.axhline(100.0, color=ACCENT_RED, linestyle="--", alpha=0.7, label="Overheat Threshold (100 C)")

        ax1.set_title("Engine Coolant Temperature vs Elapsed Time", fontsize=11, fontweight="bold", pad=8)
        ax1.set_xlabel("Elapsed Time (Minutes)", fontsize=10)
        ax1.set_ylabel("Coolant Temperature (C)", fontsize=10)
        ax1.grid(True, linestyle="--", alpha=0.3)
        ax1.legend(loc="lower right", fontsize=8)

        tvl = thermal["temp_vs_load"]
        temps = tvl["temps"]
        loads = tvl["loads"]

        if len(loads) > 0 and len(temps) == len(loads):
            sub_idx = np.random.choice(len(temps), min(1000, len(temps)), replace=False)
            ax2.scatter(
                loads[sub_idx],
                temps[sub_idx],
                color=ACCENT_AMBER,
                alpha=0.35,
                s=16,
                edgecolors="none",
                label="Sampled Load vs Temp",
            )
            ax2.axhspan(norm_low, norm_high, color=ACCENT_GREEN, alpha=0.15)
            ax2.set_xlabel("Engine Load (%)", fontsize=10)
            ax2.set_ylabel("Coolant Temperature (C)", fontsize=10)
            ax2.set_title("Thermal Response vs Calculated Engine Load", fontsize=11, fontweight="bold", pad=8)
            ax2.grid(True, linestyle="--", alpha=0.3)
            ax2.legend(loc="lower right", fontsize=8)
        else:
            ax2.text(0.5, 0.5, "No engine load data available for correlation.", ha="center", va="center", color=TEXT_MUTED)

        canvas.draw()

    def _render_fuel_trim_graph(self):
        """Render Fuel Trim scatter and operating zone breakdown."""
        canvas = self.canvas_fuel_trims
        canvas.clear()
        fig = canvas.fig

        td = self.current_trim_diag
        trips = self.selected_trips
        if not trips or td is None or not td.has_data:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, "No Short/Long Term Fuel Trim data available in selected records.", ha="center", va="center", color=TEXT_MUTED)
            canvas.draw()
            return

        ax1 = fig.add_subplot(121)
        ax2 = fig.add_subplot(122)

        stft_pts, ltft_pts = [], []
        for trip in trips:
            df = trip.data
            if "stft_pct" in df.columns and "ltft_pct" in df.columns:
                valid = df.dropna(subset=["stft_pct", "ltft_pct"])
                stft_pts.extend(valid["stft_pct"].values)
                ltft_pts.extend(valid["ltft_pct"].values)

        if stft_pts:
            s_arr = np.array(stft_pts)
            l_arr = np.array(ltft_pts)
            sub_idx = np.random.choice(len(s_arr), min(1200, len(s_arr)), replace=False)

            ax1.scatter(
                s_arr[sub_idx],
                l_arr[sub_idx],
                color=ACCENT_CYAN,
                alpha=0.35,
                s=14,
                edgecolors="none",
                label="Trim Samples",
            )

            ax1.fill_between([-10, 10], -10, 10, color=ACCENT_GREEN, alpha=0.12, label="Pass Zone (+/- 10%)")
            ax1.axvline(0, color="#6B7280", linestyle="-", alpha=0.5)
            ax1.axhline(0, color="#6B7280", linestyle="-", alpha=0.5)
            ax1.axvline(-10, color=ACCENT_AMBER, linestyle="--", alpha=0.7)
            ax1.axvline(10, color=ACCENT_AMBER, linestyle="--", alpha=0.7)
            ax1.axhline(-10, color=ACCENT_AMBER, linestyle="--", alpha=0.7)
            ax1.axhline(10, color=ACCENT_AMBER, linestyle="--", alpha=0.7)

            ax1.set_title("Fuel Trim Scatter (STFT vs LTFT)", fontsize=11, fontweight="bold", pad=8)
            ax1.set_xlabel("Short Term Fuel Trim (%)", fontsize=10)
            ax1.set_ylabel("Long Term Fuel Trim (%)", fontsize=10)
            ax1.grid(True, linestyle="--", alpha=0.3)
            ax1.legend(loc="upper left", fontsize=8)

        zones = ["Idle", "Cruising", "High Load", "Overall Mean"]
        vals = [
            td.idle_total_trim if td.idle_total_trim is not None else 0.0,
            td.cruise_total_trim if td.cruise_total_trim is not None else 0.0,
            td.high_load_total_trim if td.high_load_total_trim is not None else 0.0,
            td.mean_total_trim if td.mean_total_trim is not None else 0.0,
        ]

        colors = []
        for v in vals:
            if abs(v) <= 7.0:
                colors.append(ACCENT_GREEN)
            elif abs(v) <= 12.0:
                colors.append(ACCENT_AMBER)
            else:
                colors.append(ACCENT_RED)

        bars = ax2.bar(zones, vals, color=colors, width=0.55, edgecolor=BORDER_COLOR)
        ax2.axhline(0, color=TEXT_SECONDARY, linewidth=0.8)
        ax2.axhspan(-7.0, 7.0, color=ACCENT_GREEN, alpha=0.1, label="Ideal Range (+/- 7%)")
        ax2.axhline(10.0, color=ACCENT_AMBER, linestyle="--", alpha=0.6, label="Lean Limit (+10%)")
        ax2.axhline(-10.0, color=ACCENT_AMBER, linestyle="--", alpha=0.6, label="Rich Limit (-10%)")

        for b, v in zip(bars, vals):
            y_pos = v + (0.5 if v >= 0 else -1.2)
            ax2.text(b.get_x() + b.get_width() / 2.0, y_pos, f"{v:+.1f}%", ha="center", va="bottom" if v >= 0 else "top", fontsize=9, fontweight="bold", color=TEXT_PRIMARY)

        ax2.set_title("Total Fuel Trim by Operating Zone", fontsize=11, fontweight="bold", pad=8)
        ax2.set_ylabel("Total Trim (STFT + LTFT %)", fontsize=10)
        ax2.grid(True, linestyle="--", alpha=0.3)
        ax2.legend(loc="lower right", fontsize=8)

        canvas.draw()

    def _render_hybrid_graph(self):
        """Render Hybrid High-Voltage battery cell block distribution and SOC curves."""
        canvas = self.canvas_hybrid
        canvas.clear()
        fig = canvas.fig

        hyb = self.current_hybrid_rep
        trips = self.selected_trips
        if not trips or hyb is None or not hyb.is_hybrid:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, "Non-hybrid vehicle records or no HV battery PIDs present.", ha="center", va="center", color=TEXT_MUTED)
            canvas.draw()
            return

        ax1 = fig.add_subplot(121)
        ax2 = fig.add_subplot(122)

        # Plot 1: Battery Block Voltage Distribution (V01 - V10/V12)
        if hyb.block_voltages:
            b_names = list(hyb.block_voltages.keys())
            b_vals = list(hyb.block_voltages.values())

            # Mean block voltage line
            avg_bv = float(np.mean(b_vals))
            b_colors = []
            for v in b_vals:
                diff = abs(v - avg_bv)
                if diff <= 0.10:
                    b_colors.append(ACCENT_GREEN)
                elif diff <= 0.25:
                    b_colors.append(ACCENT_AMBER)
                else:
                    b_colors.append(ACCENT_RED)

            bars = ax1.bar(b_names, b_vals, color=b_colors, edgecolor=BORDER_COLOR, width=0.6)
            ax1.axhline(avg_bv, color="#FFFFFF", linestyle="--", linewidth=1.2, label=f"Pack Mean ({avg_bv:.2f}V)")

            # Set y axis around block voltage range (e.g. 14V to 18V)
            min_y = max(10.0, min(b_vals) - 1.5)
            max_y = max(b_vals) + 1.5
            ax1.set_ylim(min_y, max_y)

            for b, v in zip(bars, b_vals):
                ax1.text(b.get_x() + b.get_width() / 2.0, v + 0.15, f"{v:.2f}V", ha="center", va="bottom", fontsize=8, color=TEXT_PRIMARY, rotation=45)

            ax1.set_title("HV Battery Block Voltages (Cell Balance)", fontsize=11, fontweight="bold", pad=8)
            ax1.set_ylabel("Block Voltage (V)", fontsize=10)
            plt.setp(ax1.get_xticklabels(), rotation=45, ha="right", fontsize=8)
            ax1.grid(True, linestyle="--", alpha=0.3)
            ax1.legend(loc="lower right", fontsize=8)
        else:
            ax1.text(0.5, 0.5, "No individual block voltage PIDs logged.", ha="center", va="center", color=TEXT_MUTED)

        # Plot 2: State of Charge (SOC %) timeline & EV Propulsion
        has_soc = False
        for t in trips:
            if "hv_soc_pct" in t.data.columns:
                has_soc = True
                t_min = t.data.index.values / 60.0
                soc_curve = t.data["hv_soc_pct"].values
                ax2.plot(t_min, soc_curve, linewidth=1.8, label=t.file_name)

        if has_soc:
            ax2.axhspan(40.0, 80.0, color=ACCENT_GREEN, alpha=0.12, label="Optimal Working SOC (40-80%)")
            ax2.set_title("Hybrid Battery State of Charge (SOC %)", fontsize=11, fontweight="bold", pad=8)
            ax2.set_xlabel("Elapsed Time (Minutes)", fontsize=10)
            ax2.set_ylabel("Battery SOC (%)", fontsize=10)
            ax2.set_ylim(20.0, 100.0)
            ax2.grid(True, linestyle="--", alpha=0.3)
            ax2.legend(loc="upper right", fontsize=8)
        else:
            ax2.text(0.5, 0.5, "No continuous SOC timeline available.", ha="center", va="center", color=TEXT_MUTED)

        canvas.draw()

    def _populate_anomalies_table(self):
        """Populate list of detected anomalies in Anomaly Detection Center."""
        for w in self.anomalies_scroll.winfo_children():
            w.destroy()

        anomalies = self.current_anomalies
        count = len(anomalies)
        crit_count = sum(1 for a in anomalies if "CRITICAL" in a.severity)
        warn_count = sum(1 for a in anomalies if "WARNING" in a.severity)
        ml_count = sum(1 for a in anomalies if "ML OUTLIER" in a.category)

        self.lbl_anomaly_summary.configure(
            text=f"ANOMALY DETECTION | {count} TOTAL ANOMALIES IDENTIFIED"
        )
        self.lbl_anomaly_badges.configure(
            text=f"Critical: {crit_count} | Warning: {warn_count} | ML Outliers: {ml_count}"
        )

        if not anomalies:
            lbl = ctk.CTkLabel(
                self.anomalies_scroll,
                text="Zero anomalies detected across all sensor telemetry streams. Vehicle operating nominal.",
                font=FONT_BODY,
                text_color=ACCENT_GREEN,
            )
            lbl.pack(pady=30)
            return

        header_frame = ctk.CTkFrame(self.anomalies_scroll, fg_color=BG_PANEL, height=32, corner_radius=4)
        header_frame.pack(fill="x", pady=(0, 4))

        cols = [
            ("TIME", 80),
            ("CATEGORY", 120),
            ("SEVERITY", 100),
            ("METRIC", 180),
            ("VALUE", 120),
            ("EXPECTED", 120),
            ("DESCRIPTION", 340),
        ]
        for col_name, width in cols:
            lbl = ctk.CTkLabel(
                header_frame,
                text=col_name,
                font=FONT_BADGE,
                text_color=TEXT_SECONDARY,
                width=width,
                anchor="w",
            )
            lbl.pack(side="left", padx=6)

        for idx, a in enumerate(anomalies):
            bg_col = BG_PANEL_ALT if idx % 2 == 0 else BG_PANEL
            row_frame = ctk.CTkFrame(self.anomalies_scroll, fg_color=bg_col, height=32, corner_radius=4)
            row_frame.pack(fill="x", pady=1)

            sev_color = ACCENT_RED if "CRITICAL" in a.severity else (ACCENT_AMBER if "WARNING" in a.severity else ACCENT_CYAN)

            row_data = [
                (f"{a.timestamp_min:.1f} min", 80, TEXT_PRIMARY),
                (a.category, 120, ACCENT_AMBER),
                (a.severity, 100, sev_color),
                (a.metric_name, 180, TEXT_PRIMARY),
                (a.detected_value, 120, sev_color),
                (a.expected_range, 120, TEXT_SECONDARY),
                (a.description, 340, TEXT_MUTED),
            ]

            for val, width, color in row_data:
                lbl = ctk.CTkLabel(
                    row_frame,
                    text=val,
                    font=FONT_CAPTION,
                    text_color=color,
                    width=width,
                    anchor="w",
                )
                lbl.pack(side="left", padx=6)

    def _populate_cleanup_audit(self):
        """Update Pre-Ingestion Data Cleanup audit card."""
        trips = self.selected_trips
        if not trips:
            self.lbl_cleanup_details.configure(
                text="No records loaded. Pre-ingestion cleanup standby."
            )
            return

        total_raw = sum(t.cleanup_report.total_raw_rows for t in trips)
        valid_retained = sum(t.cleanup_report.valid_rows_retained for t in trips)
        invalid_dropped = sum(t.cleanup_report.invalid_rows_dropped for t in trips)
        outliers = sum(t.cleanup_report.sensor_outliers_cleaned for t in trips)
        dfco_events = sum(t.cleanup_report.dfco_events_conditioned for t in trips)
        dfco_eligible = sum(t.cleanup_report.dfco_eligible_events for t in trips)
        dfco_fuel_saved = sum(t.cleanup_report.fuel_saved_liters for t in trips)
        dfco_pct = (dfco_events / dfco_eligible * 100.0) if dfco_eligible > 0 else 0.0

        self.lbl_cleanup_details.configure(
            text=(
                f"Total Raw Rows: {total_raw:,}   |   "
                f"Valid Rows Retained: {valid_retained:,}   |   "
                f"Dropped/Sanitized: {invalid_dropped:,}   |   "
                f"DFCO Cut Engagement: {dfco_pct:.1f}% ({dfco_events:,}s active / {dfco_eligible:,}s eligible)   |   "
                f"Fuel Cut Saved: {dfco_fuel_saved:.2f} L"
            )
        )

    def _populate_trip_table(self):
        """Populate tabular list of all loaded scan trips and their metrics."""
        for w in self.table_scroll.winfo_children():
            w.destroy()

        trips = self.selected_trips
        if not trips:
            lbl = ctk.CTkLabel(self.table_scroll, text="No records loaded.", font=FONT_BODY, text_color=TEXT_MUTED)
            lbl.pack(pady=20)
            return

        unit = self.current_unit

        header_frame = ctk.CTkFrame(self.table_scroll, fg_color=BG_PANEL, height=32, corner_radius=4)
        header_frame.pack(fill="x", pady=(0, 4))

        cols = [
            ("RECORD FILE", 200),
            ("DURATION", 90),
            ("DISTANCE", 90),
            (f"CITY ({unit})", 110),
            (f"HWY ({unit})", 110),
            (f"COMBINED ({unit})", 130),
            ("PEAK SPEED", 100),
            ("PEAK TEMP", 100),
            ("TYPE", 90),
        ]

        for col_name, width in cols:
            lbl = ctk.CTkLabel(
                header_frame,
                text=col_name,
                font=FONT_BADGE,
                text_color=TEXT_SECONDARY,
                width=width,
                anchor="w",
            )
            lbl.pack(side="left", padx=6)

        for idx, trip in enumerate(trips):
            row_fe = self.analyzer.calculate_fuel_economy([trip])
            bg_col = BG_PANEL_ALT if idx % 2 == 0 else BG_PANEL

            row_frame = ctk.CTkFrame(self.table_scroll, fg_color=bg_col, height=30, corner_radius=4)
            row_frame.pack(fill="x", pady=1)

            clean_name = os.path.basename(trip.file_path).replace(".csv", "")
            city_str = row_fe.format_value("city", unit)
            hwy_str = row_fe.format_value("highway", unit)
            comb_str = row_fe.format_value("combined", unit)

            row_data = [
                (clean_name, 200, TEXT_PRIMARY),
                (f"{trip.duration_minutes:.1f} min", 90, TEXT_SECONDARY),
                (f"{row_fe.total_distance_km:.2f} km", 90, TEXT_SECONDARY),
                (city_str, 110, TEXT_CYAN if city_str != "-" else TEXT_MUTED),
                (hwy_str, 110, TEXT_GREEN if hwy_str != "-" else TEXT_MUTED),
                (comb_str, 130, TEXT_AMBER if comb_str != "-" else TEXT_MUTED),
                (f"{trip.max_speed:.0f} km/h", 100, TEXT_SECONDARY),
                (f"{trip.max_coolant_temp:.0f} C" if trip.max_coolant_temp > 0 else "N/A", 100, TEXT_SECONDARY),
                ("HYBRID" if trip.is_hybrid else "ICE", 90, ACCENT_GREEN if trip.is_hybrid else TEXT_SECONDARY),
            ]

            for val, width, color in row_data:
                lbl = ctk.CTkLabel(
                    row_frame,
                    text=val,
                    font=FONT_DIGITAL_SMALL if width in (110, 130) else FONT_CAPTION,
                    text_color=color,
                    width=width,
                    anchor="w",
                )
                lbl.pack(side="left", padx=6)

    def _export_report(self):
        """Export comprehensive diagnostic analysis summary to text or CSV."""
        trips = self.selected_trips
        if not trips:
            messagebox.showwarning("Warning", "No active records to export.", parent=self)
            return

        save_path = filedialog.asksaveasfilename(
            title="Save Diagnostic Analysis Report",
            defaultextension=".txt",
            filetypes=[("Text Report", "*.txt"), ("CSV Summary", "*.csv")],
        )
        if not save_path:
            return

        fe = self.current_fe_result
        diag = self.current_diag_report
        td = self.current_trim_diag
        hyb = self.current_hybrid_rep
        anomalies = self.current_anomalies

        if save_path.endswith(".csv"):
            rows = []
            for t in trips:
                t_fe = self.analyzer.calculate_fuel_economy([t])
                rows.append({
                    "File": t.file_name,
                    "Duration_Minutes": round(t.duration_minutes, 2),
                    "Distance_km": round(t_fe.total_distance_km, 2),
                    "City_km_per_L": t_fe.format_value("city", "km/L"),
                    "Highway_km_per_L": t_fe.format_value("highway", "km/L"),
                    "Combined_km_per_L": t_fe.format_value("combined", "km/L"),
                    "Peak_Speed_kmh": round(t.max_speed, 1),
                    "Peak_Coolant_C": round(t.max_coolant_temp, 1),
                    "Mean_Voltage_V": round(t.mean_voltage, 2),
                    "Powertrain": "Hybrid" if t.is_hybrid else "ICE",
                })
            df_export = pd.DataFrame(rows)
            df_export.to_csv(save_path, index=False)
        else:
            with open(save_path, "w", encoding="utf-8") as f:
                f.write("=" * 75 + "\n")
                f.write("OBD-II TELEMETRY SUIT | AUTOMOTIVE DIAGNOSTIC REPORT\n")
                f.write("=" * 75 + "\n\n")
                f.write(f"Vehicle: {self.profile.summary_text()}\n")
                f.write(f"Active Files Loaded: {len(trips)}\n")
                f.write(f"Total Sampled Distance: {fe.total_distance_km:.2f} km\n")
                f.write(f"Total Fuel Consumed: {fe.total_fuel_liters:.2f} L\n\n")

                f.write("--- FUEL ECONOMY ANALYSIS ---\n")
                f.write(f"City Fuel Economy:     {fe.format_value('city', 'km/L')} km/L ({fe.format_value('city', 'L/100km')} L/100km | {fe.format_value('city', 'MPG (US)')} MPG US)\n")
                f.write(f"Highway Fuel Economy:  {fe.format_value('highway', 'km/L')} km/L ({fe.format_value('highway', 'L/100km')} L/100km | {fe.format_value('highway', 'MPG (US)')} MPG US)\n")
                f.write(f"Combined Fuel Economy: {fe.format_value('combined', 'km/L')} km/L ({fe.format_value('combined', 'L/100km')} L/100km | {fe.format_value('combined', 'MPG (US)')} MPG US)\n\n")

                dfco_res = self.analyzer.analyze_dfco(trips)
                f.write("--- DECELERATION FUEL CUT-OFF (DFCO) DIAGNOSTICS ---\n")
                f.write(f"DFCO Overall Status:      {dfco_res.status}\n")
                f.write(f"DFCO Engagement Rate:     {dfco_res.dfco_engagement_pct:.1f}%\n")
                f.write(f"Active Cut Duration:      {dfco_res.active_dfco_seconds:.0f} s\n")
                f.write(f"Eligible Overrun Decel:   {dfco_res.eligible_decel_seconds:.0f} s\n")
                f.write(f"Inactive Overrun Decel:   {dfco_res.inactive_dfco_seconds:.0f} s\n")
                f.write(f"Estimated Fuel Conserved: {dfco_res.fuel_saved_liters:.3f} L\n")
                f.write(f"Summary: {dfco_res.diagnostic_summary}\n")
                if dfco_res.primary_inhibit_reasons:
                    f.write("\nDiagnostic Observations & Inhibit Factors:\n")
                    for reason in dfco_res.primary_inhibit_reasons:
                        f.write(f"- {reason}\n")
                if dfco_res.mechanic_recommendations:
                    f.write("\nMechanic Action Recommendations:\n")
                    for rec in dfco_res.mechanic_recommendations:
                        f.write(f"- {rec}\n")
                f.write("\n")

                if hyb and hyb.is_hybrid:
                    f.write("--- HYBRID POWERTRAIN & HIGH-VOLTAGE BATTERY HEALTH ---\n")
                    f.write(f"Battery Balance Status: {hyb.battery_health_status}\n")
                    f.write(f"Mean State of Charge:  {hyb.soc_mean:.1f}%\n")
                    if hyb.delta_block_v is not None:
                        f.write(f"Block Voltage Delta:   {hyb.delta_block_v * 1000:.0f} mV (Max: {hyb.max_block_v:.2f}V, Min: {hyb.min_block_v:.2f}V)\n")
                    f.write(f"EV Propulsion Ratio:   {hyb.ev_driving_pct:.1f}%\n")
                    if hyb.inverter_temp_c is not None:
                        f.write(f"Inverter Temperature:  {hyb.inverter_temp_c:.0f} C\n")
                    f.write("\n")

                f.write("--- FUEL TRIM DIAGNOSTIC & MECHANIC ACTION PLAN ---\n")
                f.write(f"Diagnosis:        {td.diagnosis_title} [{td.severity}]\n")
                f.write(f"Likelihood:       {td.likelihood_score}\n")
                f.write(f"Mean Total Trim:  {td.mean_total_trim:+.1f}%\n")
                if td.idle_total_trim is not None:
                    f.write(f"Idle Total Trim:  {td.idle_total_trim:+.1f}%\n")
                if td.cruise_total_trim is not None:
                    f.write(f"Cruise Total Trim:{td.cruise_total_trim:+.1f}%\n")
                if td.probable_causes:
                    f.write("\nProbable Causes:\n")
                    for cause in td.probable_causes:
                        f.write(f"- {cause}\n")
                if td.mechanic_recommendations:
                    f.write("\nRecommended Mechanic Procedures:\n")
                    for rec in td.mechanic_recommendations:
                        f.write(f"- {rec}\n")

                f.write("\n--- ANOMALY DETECTION AUDIT ---\n")
                f.write(f"Total Anomalies Identified: {len(anomalies)}\n")
                for a in anomalies[:15]:
                    f.write(f"- {a.category} {a.severity} @ {a.timestamp_min:.1f}m ({a.metric_name}): {a.detected_value} | {a.description}\n")

                f.write("\n" + "=" * 75 + "\n")

        messagebox.showinfo("Report Exported", f"Diagnostic report saved successfully to:\n{save_path}", parent=self)


def main():
    """Application entrypoint."""
    app = CarRecordAnalyzerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
