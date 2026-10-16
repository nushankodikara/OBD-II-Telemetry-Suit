"""Main CustomTkinter desktop application for Car Record Analyzer.

Mechanic-focused automotive telemetry workstation featuring:
- Car Scanner ELM OBD2 format validation and multi-stage pre-ingestion cleanup.
- City, Highway, Combined fuel economy with "-" fallback for insufficient data.
- Optimal RPM & Speed curves and 2D efficiency heatmaps with cruising sweet spot.
- Engine thermal analysis and thermostat operating bands.
- Deep STFT and LTFT fuel trim diagnostics with concrete mechanic repair recommendations.
- Live interactive GPS route map (OpenStreetMap) and spatial telemetry heatmaps.
- Physical rule and Isolation Forest multivariate anomaly detection.
- Data cleanup audit reporting and CSV/Text diagnostic report exports.

Strictly adheres to project rules: no emojis.
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import List, Optional, Tuple, Dict, Any
import customtkinter as ctk
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import tkintermapview

from src.data_loader import ScanTrip, load_all_records, parse_obd_csv
from src.analyzer import (
    VehicleAnalyzer,
    FuelEconomyResult,
    DiagnosticHealthReport,
    FuelTrimDiagnostic,
    TelemetryAnomaly,
)
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
    """Main application window for Car Record Analyzer."""

    def __init__(self):
        super().__init__()

        # Appearance configuration
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("dark-blue")

        self.title("Car Record Analyzer - Car Scanner ELM OBD2 Workstation")
        self.geometry("1440x940")
        self.minsize(1150, 780)
        self.configure(fg_color=BG_DARKEST)

        # Analysis engine state
        self.city_threshold: float = 45.0
        self.highway_threshold: float = 70.0
        self.current_unit: str = "km/L"
        self.map_metric: str = "Fuel Economy"
        self.map_view_mode: str = "Live Map"
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
        self.current_anomalies: List[TelemetryAnomaly] = []

        # Build UI layout
        self._build_header()
        self._build_metric_banner()
        self._build_main_body()

        # Initial load from Records folder
        self._load_records_directory("Records")

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
            text="CAR RECORD ANALYZER // CAR SCANNER ELM OBD2 SUITE",
            font=FONT_TITLE,
            text_color=TEXT_PRIMARY,
        )
        self.lbl_title.pack(anchor="w")

        self.lbl_subtitle = ctk.CTkLabel(
            title_box,
            text="CLEANUP PIPELINE, EFFICIENCY MAPPING, LIVE GPS ROUTE & ANOMALY DETECTION",
            font=FONT_CAPTION,
            text_color=TEXT_MUTED,
        )
        self.lbl_subtitle.pack(anchor="w")

        # Controls section: Unit Selector & Threshold Quick Config
        controls_box = ctk.CTkFrame(self.header, fg_color="transparent")
        controls_box.pack(side="right", padx=16, pady=10)

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
        self.unit_segment.pack(side="left", padx=(0, 16))

        self.btn_thresholds = ctk.CTkButton(
            controls_box,
            text="Speed Thresholds...",
            font=FONT_CAPTION,
            height=28,
            fg_color=BG_PANEL_ALT,
            hover_color=BG_CARD_HOVER,
            border_width=1,
            border_color=BORDER_COLOR,
            command=self._open_thresholds_dialog,
        )
        self.btn_thresholds.pack(side="left")

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

        self.card_anomalies = MetricCard(
            self.metric_banner,
            title="Detected Anomalies",
            value="0",
            unit="events",
            subtitle="ML & Physical Rules",
            status_text="OPTIMAL",
            accent_color=ACCENT_GREEN,
        )
        self.card_anomalies.pack(side="left", fill="both", expand=True, padx=4)

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
            on_reload_dir=lambda: self._load_records_directory("Records"),
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
            text="Battery: STANDBY",
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
            text="Select 1 or more Car Scanner ELM OBD2 scan records.",
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
        self.tab_map = self.tabview.add("Live GPS Route Map")
        self.tab_anomalies = self.tabview.add("Anomaly Detection")
        self.tab_cleanup_sessions = self.tabview.add("Data Cleanup & Sessions")

        # Tab 1: Efficiency Canvas
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

        # Tab 5: Live GPS Route Map
        self._build_gps_map_tab()

        # Tab 6: Anomaly Detection Center
        self._build_anomalies_tab()

        # Tab 7: Data Cleanup & Sessions Table
        self._build_cleanup_sessions_tab()

    def _build_fuel_trim_tab(self):
        """Build Fuel Trim diagnostics workstation with recommendations."""
        container = ctk.CTkFrame(self.tab_fuel_trims, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=6, pady=6)

        # Top diagnostic recommendation banner
        self.trim_rec_box = ctk.CTkFrame(container, fg_color=BG_PANEL_ALT, corner_radius=6, border_width=1, border_color=BORDER_COLOR)
        self.trim_rec_box.pack(fill="x", side="top", padx=2, pady=(0, 6))

        rec_header_row = ctk.CTkFrame(self.trim_rec_box, fg_color="transparent")
        rec_header_row.pack(fill="x", padx=12, pady=(8, 4))

        self.lbl_trim_diag_title = ctk.CTkLabel(
            rec_header_row,
            text="DIAGNOSIS: EVALUATING...",
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

        # Zone metrics row
        self.lbl_trim_zone_stats = ctk.CTkLabel(
            self.trim_rec_box,
            text="Idle Trim: - | Cruising Trim: - | High Load Trim: -",
            font=FONT_DIGITAL_SMALL,
            text_color=TEXT_AMBER,
            anchor="w",
        )
        self.lbl_trim_zone_stats.pack(fill="x", padx=12, pady=2)

        # Concrete recommendations label
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

        # Bottom Canvas for Fuel Trim graphs
        self.canvas_fuel_trims = GraphCanvas(container)
        self.canvas_fuel_trims.pack(fill="both", expand=True, padx=2, pady=2)

    def _build_gps_map_tab(self):
        """Build Live GPS Route Map tab featuring OpenStreetMap and Spatial Heatmap."""
        container = ctk.CTkFrame(self.tab_map, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=6, pady=6)

        # Map controls toolbar
        map_tools = ctk.CTkFrame(container, fg_color=BG_PANEL_ALT, height=36, corner_radius=6, border_width=1, border_color=BORDER_COLOR)
        map_tools.pack(fill="x", side="top", padx=2, pady=(0, 6))

        ctk.CTkLabel(map_tools, text="MAP MODE:", font=FONT_BADGE, text_color=TEXT_SECONDARY).pack(side="left", padx=(12, 6), pady=6)
        self.seg_map_mode = ctk.CTkSegmentedButton(
            map_tools,
            values=["Live Map", "Spatial Heatmap"],
            font=FONT_CAPTION,
            selected_color=ACCENT_AMBER,
            selected_hover_color=ACCENT_AMBER,
            unselected_color=BG_PANEL,
            unselected_hover_color=BG_CARD_HOVER,
            command=self._on_map_mode_changed,
        )
        self.seg_map_mode.set("Live Map")
        self.seg_map_mode.pack(side="left", padx=(0, 16), pady=4)

        ctk.CTkLabel(map_tools, text="TELEMETRY COLOR:", font=FONT_BADGE, text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6), pady=6)
        self.opt_map_metric = ctk.CTkOptionMenu(
            map_tools,
            values=["Fuel Economy", "Vehicle Speed", "Engine RPM", "Coolant Temp", "Total Fuel Trim"],
            font=FONT_CAPTION,
            fg_color=BG_PANEL,
            button_color=ACCENT_AMBER,
            button_hover_color="#D97706",
            command=self._on_map_metric_changed,
        )
        self.opt_map_metric.set("Fuel Economy")
        self.opt_map_metric.pack(side="left", padx=(0, 16), pady=4)

        self.lbl_map_telemetry_info = ctk.CTkLabel(
            map_tools,
            text="Coordinates: 0 tracked points | Route Distance: 0.0 km",
            font=FONT_CAPTION,
            text_color=TEXT_MUTED,
        )
        self.lbl_map_telemetry_info.pack(side="right", padx=12, pady=6)

        # Center frame supporting switching between TkinterMapView and Matplotlib Heatmap Canvas
        self.map_view_container = ctk.CTkFrame(container, fg_color=BG_DARKEST, corner_radius=6, border_width=1, border_color=BORDER_COLOR)
        self.map_view_container.pack(fill="both", expand=True, padx=2, pady=2)

        # TkinterMapView widget
        self.osm_map = tkintermapview.TkinterMapView(
            self.map_view_container,
            corner_radius=6,
            bg_color=BG_DARKEST,
        )
        self.osm_map.pack(fill="both", expand=True)

        # Matplotlib Spatial Heatmap Canvas (hidden initially)
        self.canvas_spatial_map = GraphCanvas(self.map_view_container)

    def _build_anomalies_tab(self):
        """Build Anomaly Detection Center with severity badges and event log."""
        container = ctk.CTkFrame(self.tab_anomalies, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=6, pady=6)

        # Top summary bar
        top_bar = ctk.CTkFrame(container, fg_color=BG_PANEL_ALT, height=36, corner_radius=6, border_width=1, border_color=BORDER_COLOR)
        top_bar.pack(fill="x", side="top", padx=2, pady=(0, 6))

        self.lbl_anomaly_summary = ctk.CTkLabel(
            top_bar,
            text="ANOMALY DETECTION // 0 TOTAL ANOMALIES IDENTIFIED",
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

        # Scrollable table of anomalies
        self.anomalies_scroll = ctk.CTkScrollableFrame(
            container,
            fg_color=BG_DARKEST,
            corner_radius=6,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.anomalies_scroll.pack(fill="both", expand=True, padx=2, pady=2)

    def _build_cleanup_sessions_tab(self):
        """Build combined Data Quality Audit & Trip Sessions Breakdown tab."""
        container = ctk.CTkFrame(self.tab_cleanup_sessions, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=6, pady=6)

        # Upper Card: Pre-Ingestion Data Cleanup Audit
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
            text="Total Raw Rows: 0 | Retained: 0 | Dropped: 0 | GPS Jumps Filtered: 0 | Outliers Sanitized: 0",
            font=FONT_CAPTION,
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self.lbl_cleanup_details.pack(fill="x", padx=12, pady=(0, 8))

        # Lower Section: Trip Sessions Table and Export
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

    def _load_records_directory(self, dir_path: str):
        """Load all scan files from the specified folder."""
        trips = load_all_records(dir_path)
        self.all_trips = trips
        self.selected_trips = list(trips)
        self.record_panel.set_trips(trips)
        self._reanalyze_and_redraw()

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
            self._reanalyze_and_redraw()

    def _on_unit_changed(self, new_unit: str):
        """Callback when user toggles fuel economy unit."""
        self.current_unit = new_unit
        self._update_metric_cards()
        self._render_fe_map_graph()
        self._render_gps_map()
        self._populate_trip_table()

    def _on_map_mode_changed(self, mode: str):
        """Switch between Live OpenStreetMap and Spatial Telemetry Heatmap."""
        self.map_view_mode = mode
        if mode == "Live Map":
            self.canvas_spatial_map.pack_forget()
            self.osm_map.pack(fill="both", expand=True)
        else:
            self.osm_map.pack_forget()
            self.canvas_spatial_map.pack(fill="both", expand=True)
        self._render_gps_map()

    def _on_map_metric_changed(self, metric: str):
        """Update color-coded metric on GPS route map."""
        self.map_metric = metric
        self._render_gps_map()

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
        self.current_fe_result = self.analyzer.calculate_fuel_economy(trips)
        self.current_diag_report = self.analyzer.generate_diagnostic_health(trips)
        self.current_trim_diag = self.analyzer.analyze_fuel_trims_in_depth(trips)
        self.current_anomalies = self.analyzer.detect_anomalies(trips)

        # Update Telemetry & Status Readouts
        self._update_metric_cards()
        self._update_diagnostic_panel()
        self._update_fuel_trim_recommendations()

        # Render all charts
        self._render_fe_map_graph()
        self._render_rpm_speed_graph()
        self._render_thermal_graph()
        self._render_fuel_trim_graph()
        self._render_gps_map()
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
            self.card_anomalies.update_card("0", "events", "ML & Physical Rules", "OPTIMAL")
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

        anomaly_count = len(self.current_anomalies)
        crit_count = sum(1 for a in self.current_anomalies if "CRITICAL" in a.severity)
        anomaly_status = "ALERT" if crit_count > 0 else ("WARNING" if anomaly_count > 0 else "OPTIMAL")
        anomaly_color = ACCENT_RED if crit_count > 0 else (ACCENT_AMBER if anomaly_count > 0 else ACCENT_GREEN)
        self.card_anomalies.update_card(
            str(anomaly_count),
            "events",
            f"Critical: {crit_count} | Warnings: {anomaly_count - crit_count}",
            anomaly_status,
            accent_color=anomaly_color,
        )

    def _update_diagnostic_panel(self):
        """Update mechanic diagnostic status card in the left sidebar."""
        rep = self.current_diag_report
        if rep is None:
            return

        b_color = ACCENT_GREEN if "NORMAL" in rep.battery_status else (ACCENT_AMBER if "LOW" in rep.battery_status else ACCENT_RED)
        b_text = f"Battery: {rep.battery_status} (Avg {rep.battery_mean_v:.1f}V)"
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

        ax1.set_title("Fuel Economy Heatmap (Speed vs RPM)", fontsize=11, fontweight="bold", pad=8)
        ax1.set_xlabel("Vehicle Speed (km/h)", fontsize=10)
        ax1.set_ylabel("Engine RPM (rpm)", fontsize=10)
        ax1.grid(True, linestyle="--", alpha=0.3)
        ax1.legend(loc="upper left", fontsize=8)

        scatter_s = fe_map["scatter_speed"]
        scatter_fe = fe_map["scatter_fe"].copy()
        if unit == "L/100km":
            scatter_fe = 100.0 / scatter_fe
        elif unit == "MPG (US)":
            scatter_fe = scatter_fe * 2.35214583
        elif unit == "MPG (UK)":
            scatter_fe = scatter_fe * 2.82480936

        sub_idx = np.random.choice(len(scatter_s), min(1200, len(scatter_s)), replace=False)
        ax2.scatter(
            scatter_s[sub_idx],
            scatter_fe[sub_idx],
            color=ACCENT_CYAN,
            alpha=0.25,
            s=12,
            edgecolors="none",
            label="Sampled Points",
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
                color=ACCENT_AMBER,
                linewidth=2.5,
                marker="o",
                label="Peak Efficiency Envelope",
            )

        ax2.axvline(self.city_threshold, color="#3B82F6", linestyle="--", alpha=0.6, label=f"City Limit ({self.city_threshold:.0f} km/h)")
        ax2.axvline(self.highway_threshold, color=ACCENT_GREEN, linestyle="--", alpha=0.6, label=f"Highway Gate ({self.highway_threshold:.0f} km/h)")

        ax2.set_title(f"Fuel Economy vs Vehicle Speed ({unit})", fontsize=11, fontweight="bold", pad=8)
        ax2.set_xlabel("Vehicle Speed (km/h)", fontsize=10)
        ax2.set_ylabel(f"Fuel Economy ({unit})", fontsize=10)
        ax2.grid(True, linestyle="--", alpha=0.3)
        ax2.legend(loc="upper right", fontsize=8)

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

        curve_res = self.analyzer.compute_optimal_rpm_speed_curve(trips)
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

        gear_colors = [ACCENT_CYAN, ACCENT_GREEN, ACCENT_AMBER, ACCENT_PURPLE, "#EC4899"]
        for idx, g in enumerate(curve_res["gear_lines"][:5]):
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

        # Plot 1: STFT vs LTFT Scatter with Pass Box
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

            # Pass Box (+/- 10%)
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

        # Plot 2: Total Trim Bar Chart across Operating Zones
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

        # Label bars
        for b, v in zip(bars, vals):
            y_pos = v + (0.5 if v >= 0 else -1.2)
            ax2.text(b.get_x() + b.get_width() / 2.0, y_pos, f"{v:+.1f}%", ha="center", va="bottom" if v >= 0 else "top", fontsize=9, fontweight="bold", color=TEXT_PRIMARY)

        ax2.set_title("Total Fuel Trim by Operating Zone", fontsize=11, fontweight="bold", pad=8)
        ax2.set_ylabel("Total Trim (STFT + LTFT %)", fontsize=10)
        ax2.grid(True, linestyle="--", alpha=0.3)
        ax2.legend(loc="lower right", fontsize=8)

        canvas.draw()

    def _render_gps_map(self):
        """Render Live OpenStreetMap or Spatial Telemetry Heatmap."""
        trips = self.selected_trips
        if not trips:
            return

        # Combine all GPS tracks
        coords_all: List[Tuple[float, float]] = []
        lats, lons, metric_vals = [], [], []

        metric_name = self.map_metric
        unit = self.current_unit

        for trip in trips:
            df = trip.data
            if "latitude" not in df.columns or "longitude" not in df.columns:
                continue

            valid_gps = df.dropna(subset=["latitude", "longitude"])
            if valid_gps.empty:
                continue

            for _, row in valid_gps.iterrows():
                lat = float(row["latitude"])
                lon = float(row["longitude"])
                coords_all.append((lat, lon))
                lats.append(lat)
                lons.append(lon)

                # Extract metric
                if metric_name == "Fuel Economy":
                    val = float(row["fuel_economy_kml"]) if "fuel_economy_kml" in row and pd.notna(row["fuel_economy_kml"]) else 0.0
                    if unit == "L/100km":
                        val = 100.0 / val if val > 0 else 0.0
                    elif unit == "MPG (US)":
                        val = val * 2.35214583
                    elif unit == "MPG (UK)":
                        val = val * 2.82480936
                elif metric_name == "Vehicle Speed":
                    val = float(row["speed_kmh"]) if "speed_kmh" in row and pd.notna(row["speed_kmh"]) else 0.0
                elif metric_name == "Engine RPM":
                    val = float(row["engine_rpm"]) if "engine_rpm" in row and pd.notna(row["engine_rpm"]) else 0.0
                elif metric_name == "Coolant Temp":
                    val = float(row["coolant_temp_c"]) if "coolant_temp_c" in row and pd.notna(row["coolant_temp_c"]) else 0.0
                elif metric_name == "Total Fuel Trim":
                    st = float(row["stft_pct"]) if "stft_pct" in row and pd.notna(row["stft_pct"]) else 0.0
                    lt = float(row["ltft_pct"]) if "ltft_pct" in row and pd.notna(row["ltft_pct"]) else 0.0
                    val = st + lt
                else:
                    val = 0.0
                metric_vals.append(val)

        # Update summary label
        total_dist_km = self.current_fe_result.total_distance_km if self.current_fe_result else 0.0
        self.lbl_map_telemetry_info.configure(
            text=f"GPS Points: {len(coords_all):,} | Tracked Route: {total_dist_km:.2f} km"
        )

        if not coords_all:
            return

        # Render 1: Live OpenStreetMap view
        if self.map_view_mode == "Live Map":
            # Clear old paths and markers
            self.osm_map.delete_all_path()
            self.osm_map.delete_all_marker()

            # Center map
            mean_lat = float(np.mean(lats))
            mean_lon = float(np.mean(lons))
            self.osm_map.set_position(mean_lat, mean_lon)
            self.osm_map.set_zoom(13)

            # Subsample coordinates for path performance
            step = max(1, len(coords_all) // 600)
            sub_coords = coords_all[::step]
            if len(sub_coords) > 1:
                self.osm_map.set_path(sub_coords, color=ACCENT_AMBER, width=4)

            # Set Start and Finish markers
            start_coord = coords_all[0]
            finish_coord = coords_all[-1]
            self.osm_map.set_marker(start_coord[0], start_coord[1], text="[START]", marker_color_circle=ACCENT_GREEN)
            self.osm_map.set_marker(finish_coord[0], finish_coord[1], text="[FINISH]", marker_color_circle=ACCENT_RED)

            # Place markers on detected anomaly locations
            for a in self.current_anomalies[:8]:
                if a.latitude is not None and a.longitude is not None:
                    txt = f"{a.category} {a.metric_name}: {a.detected_value}"
                    self.osm_map.set_marker(a.latitude, a.longitude, text=txt, marker_color_circle=ACCENT_AMBER)

        # Render 2: Spatial Telemetry Heatmap (Matplotlib)
        else:
            canvas = self.canvas_spatial_map
            canvas.clear()
            fig = canvas.fig
            ax = fig.add_subplot(111)

            arr_lons = np.array(lons)
            arr_lats = np.array(lats)
            arr_vals = np.array(metric_vals)

            sub_idx = np.random.choice(len(arr_lats), min(2500, len(arr_lats)), replace=False)
            sc = ax.scatter(
                arr_lons[sub_idx],
                arr_lats[sub_idx],
                c=arr_vals[sub_idx],
                cmap="viridis" if metric_name != "Total Fuel Trim" else "coolwarm",
                s=20,
                alpha=0.8,
                edgecolors="none",
            )
            cbar = fig.colorbar(sc, ax=ax, fraction=0.035, pad=0.04)
            cbar.set_label(f"{metric_name} ({unit if metric_name == 'Fuel Economy' else ''})", color=TEXT_SECONDARY)
            cbar.ax.yaxis.set_tick_params(color=TEXT_MUTED)
            plt.setp(plt.getp(cbar.ax.axes, "yticklabels"), color=TEXT_SECONDARY)

            # Mark start and finish
            ax.scatter([lons[0]], [lats[0]], color=ACCENT_GREEN, s=100, marker="o", edgecolors="#FFFFFF", label="Start")
            ax.scatter([lons[-1]], [lats[-1]], color=ACCENT_RED, s=100, marker="X", edgecolors="#FFFFFF", label="Finish")

            ax.set_title(f"GPS Spatial Route - Color-Coded by {metric_name}", fontsize=11, fontweight="bold", pad=8)
            ax.set_xlabel("Longitude (Degrees)", fontsize=10)
            ax.set_ylabel("Latitude (Degrees)", fontsize=10)
            ax.grid(True, linestyle="--", alpha=0.3)
            ax.legend(loc="upper left", fontsize=8)

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
            text=f"ANOMALY DETECTION // {count} TOTAL ANOMALIES IDENTIFIED"
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

        # Header Row
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

        # Rows
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
        gps_jumps = sum(t.cleanup_report.gps_jumps_filtered for t in trips)
        outliers = sum(t.cleanup_report.sensor_outliers_cleaned for t in trips)
        dfco_events = sum(t.cleanup_report.dfco_events_conditioned for t in trips)

        self.lbl_cleanup_details.configure(
            text=(
                f"Total Raw Rows: {total_raw:,}   |   "
                f"Valid Rows Retained: {valid_retained:,}   |   "
                f"Dropped/Sanitized: {invalid_dropped:,}   |   "
                f"GPS Teleportation Jumps Filtered: {gps_jumps:,}   |   "
                f"Sensor Outliers Sanitized: {outliers}   |   "
                f"DFCO Spikes Conditioned: {dfco_events}"
            )
        )

    def _populate_trip_table(self):
        """Populate tabular list of all loaded scan trips and their metrics."""
        for w in self.table_scroll.winfo_children():
            w.destroy()

        trips = self.selected_trips
        if not trips:
            lbl = ctk.CTkLabel(self.table_scroll, text="No records selected.", font=FONT_BODY, text_color=TEXT_MUTED)
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
            ("VOLTAGE", 90),
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
                (f"{trip.mean_voltage:.1f} V" if trip.mean_voltage > 0 else "N/A", 90, TEXT_SECONDARY),
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
                })
            df_export = pd.DataFrame(rows)
            df_export.to_csv(save_path, index=False)
        else:
            with open(save_path, "w", encoding="utf-8") as f:
                f.write("=" * 75 + "\n")
                f.write("CAR RECORD ANALYZER // CAR SCANNER ELM OBD2 DIAGNOSTIC REPORT\n")
                f.write("=" * 75 + "\n\n")
                f.write(f"Active Files Loaded: {len(trips)}\n")
                f.write(f"Total Sampled Distance: {fe.total_distance_km:.2f} km\n")
                f.write(f"Total Fuel Consumed: {fe.total_fuel_liters:.2f} L\n")
                f.write(f"Idle Percentage: {fe.idle_percentage:.1f}%\n\n")

                f.write("--- FUEL ECONOMY ANALYSIS ---\n")
                f.write(f"City Fuel Economy:     {fe.format_value('city', 'km/L')} km/L ({fe.format_value('city', 'L/100km')} L/100km | {fe.format_value('city', 'MPG (US)')} MPG US)\n")
                f.write(f"Highway Fuel Economy:  {fe.format_value('highway', 'km/L')} km/L ({fe.format_value('highway', 'L/100km')} L/100km | {fe.format_value('highway', 'MPG (US)')} MPG US)\n")
                f.write(f"Combined Fuel Economy: {fe.format_value('combined', 'km/L')} km/L ({fe.format_value('combined', 'L/100km')} L/100km | {fe.format_value('combined', 'MPG (US)')} MPG US)\n\n")

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
