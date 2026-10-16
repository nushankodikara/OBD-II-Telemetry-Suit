"""Main CustomTkinter desktop application for Car Record Analyzer.

Mechanic-focused automotive telemetry workstation featuring multi-record ingestion,
fuel economy breakdowns, optimal RPM-speed curves, 2D efficiency heatmaps,
thermal diagnostics, and sensor health inspections.
Strictly adheres to project rules: no emojis.
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import List, Optional
import customtkinter as ctk
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator

from src.data_loader import ScanTrip, load_all_records, parse_obd_csv
from src.analyzer import VehicleAnalyzer, FuelEconomyResult, DiagnosticHealthReport
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

        self.title("Car Record Analyzer - OBD-II Diagnostic Suite")
        self.geometry("1400x900")
        self.minsize(1100, 750)
        self.configure(fg_color=BG_DARKEST)

        # Analysis engine state
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
            text="CAR RECORD ANALYZER // OBD-II WORKSHOP DIAGNOSTIC SUITE",
            font=FONT_TITLE,
            text_color=TEXT_PRIMARY,
        )
        self.lbl_title.pack(anchor="w")

        self.lbl_subtitle = ctk.CTkLabel(
            title_box,
            text="AUTOMOTIVE TELEMETRY, FUEL EFFICIENCY MAPPING & ENGINE HEALTH",
            font=FONT_CAPTION,
            text_color=TEXT_MUTED,
        )
        self.lbl_subtitle.pack(anchor="w")

        # Controls section: Unit Selector & Threshold Quick Config
        controls_box = ctk.CTkFrame(self.header, fg_color="transparent")
        controls_box.pack(side="right", padx=16, pady=10)

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
        self.unit_segment.pack(side="left", padx=(0, 16))

        # Thresholds button
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

        # 6 Telemetry Cards
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

        self.card_idle = MetricCard(
            self.metric_banner,
            title="Idle Loss & Stability",
            value="-",
            unit="%",
            subtitle="Idle Fuel: - L",
            status_text="IDLE",
            accent_color=ACCENT_RED,
        )
        self.card_idle.pack(side="left", fill="both", expand=True, padx=4)

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

    def _build_main_body(self):
        """Build center split view: Sidebar on left, Tabview on right."""
        self.body_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.body_frame.pack(fill="both", expand=True, padx=14, pady=(4, 12))

        # Left Column: Record List & Mechanic Diagnostic Summary Box
        self.left_col = ctk.CTkFrame(self.body_frame, fg_color="transparent", width=340)
        self.left_col.pack(side="left", fill="y", padx=(0, 8))
        self.left_col.pack_propagate(False)

        # Record List Panel
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
            height=200,
        )
        self.diag_panel.pack(fill="x", side="bottom")

        lbl_diag_title = ctk.CTkLabel(
            self.diag_panel,
            text="MECHANIC SENSOR HEALTH",
            font=FONT_BODY_BOLD,
            text_color=TEXT_PRIMARY,
        )
        lbl_diag_title.pack(anchor="w", padx=12, pady=(10, 6))

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
            text="Select 1 or more scan records to evaluate engine parameters.",
            font=FONT_CAPTION,
            text_color=TEXT_MUTED,
            anchor="w",
            wraplength=310,
            justify="left",
        )
        self.lbl_diag_notes.pack(fill="x", padx=12, pady=(6, 10))

        # Right Column: Diagnostic Workstations Tabview
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
        self.tab_fe_map = self.tabview.add("Efficiency Map & Sweet Spot")
        self.tab_rpm_speed = self.tabview.add("Optimal RPM & Speed Curve")
        self.tab_thermal = self.tabview.add("Engine Thermal Profile")
        self.tab_mechanic = self.tabview.add("Diagnostic Sensor Health")
        self.tab_trip_table = self.tabview.add("Trip Sessions & Export")

        # Build Canvas in each graph tab
        self.canvas_fe_map = GraphCanvas(self.tab_fe_map)
        self.canvas_fe_map.pack(fill="both", expand=True, padx=6, pady=6)

        self.canvas_rpm_speed = GraphCanvas(self.tab_rpm_speed)
        self.canvas_rpm_speed.pack(fill="both", expand=True, padx=6, pady=6)

        self.canvas_thermal = GraphCanvas(self.tab_thermal)
        self.canvas_thermal.pack(fill="both", expand=True, padx=6, pady=6)

        self.canvas_mechanic = GraphCanvas(self.tab_mechanic)
        self.canvas_mechanic.pack(fill="both", expand=True, padx=6, pady=6)

        self._build_trip_table_tab()

    def _build_trip_table_tab(self):
        """Build tabular view of all trips and CSV export."""
        top_bar = ctk.CTkFrame(self.tab_trip_table, fg_color="transparent")
        top_bar.pack(fill="x", padx=10, pady=(8, 6))

        lbl_desc = ctk.CTkLabel(
            top_bar,
            text="DETAILED TRIP SESSIONS BREAKDOWN",
            font=FONT_BODY_BOLD,
            text_color=TEXT_PRIMARY,
        )
        lbl_desc.pack(side="left")

        btn_export = ctk.CTkButton(
            top_bar,
            text="Export Diagnostic Report...",
            font=FONT_CAPTION,
            height=28,
            fg_color=ACCENT_AMBER,
            hover_color="#D97706",
            text_color=BG_DARKEST,
            command=self._export_report,
        )
        btn_export.pack(side="right")

        # Table container with scrollable textbox / frame
        self.table_scroll = ctk.CTkScrollableFrame(
            self.tab_trip_table,
            fg_color=BG_DARKEST,
            corner_radius=6,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.table_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

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
        """Open file dialog to import external scan CSV files."""
        file_paths = filedialog.askopenfilenames(
            title="Select OBD-II Scan CSV Records",
            filetypes=[("OBD Scan CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if not file_paths:
            return

        added_any = False
        for p in file_paths:
            # Check if already loaded
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
        self._populate_trip_table()

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

        # City threshold
        f_city = ctk.CTkFrame(dlg, fg_color="transparent")
        f_city.pack(fill="x", padx=24, pady=6)
        ctk.CTkLabel(f_city, text="City Max Speed (km/h):", font=FONT_BODY, text_color=TEXT_SECONDARY).pack(side="left")
        entry_city = ctk.CTkEntry(f_city, width=80)
        entry_city.insert(0, str(int(self.city_threshold)))
        entry_city.pack(side="right")

        # Highway threshold
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

        # Update Telemetry & Status Readouts
        self._update_metric_cards()
        self._update_diagnostic_panel()

        # Render all charts
        self._render_fe_map_graph()
        self._render_rpm_speed_graph()
        self._render_thermal_graph()
        self._render_mechanic_graph()

        # Populate Sessions Table
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
            self.card_idle.update_card("-", "%", "Idle Fuel: - L", "IDLE")
            self.card_sweet_spot.update_card("-", "km/h", "Best Cruising RPM", "SWEET SPOT")
            return

        # City
        city_str = fe.format_value("city", unit)
        city_status = "OPTIMAL" if city_str != "-" else "NO DATA"
        self.card_city.update_card(
            city_str,
            unit,
            f"Sampled: {fe.city_distance_km:.1f} km ({fe.city_fuel_liters:.2f} L)",
            city_status,
            accent_color=TEXT_CYAN if city_str != "-" else TEXT_MUTED,
        )

        # Highway
        hwy_str = fe.format_value("highway", unit)
        hwy_status = "OPTIMAL" if hwy_str != "-" else "NO DATA"
        self.card_highway.update_card(
            hwy_str,
            unit,
            f"Sampled: {fe.highway_distance_km:.1f} km ({fe.highway_fuel_liters:.2f} L)",
            hwy_status,
            accent_color=TEXT_GREEN if hwy_str != "-" else TEXT_MUTED,
        )

        # Combined
        comb_str = fe.format_value("combined", unit)
        comb_status = "OPTIMAL" if comb_str != "-" else "NO DATA"
        self.card_combined.update_card(
            comb_str,
            unit,
            f"Total Moving: {fe.total_distance_km:.1f} km",
            comb_status,
            accent_color=TEXT_AMBER if comb_str != "-" else TEXT_MUTED,
        )

        # Distance & Fuel
        self.card_distance.update_card(
            f"{fe.total_distance_km:.1f}",
            "km",
            f"Total Consumed: {fe.total_fuel_liters:.2f} L (Avg: {fe.avg_moving_speed_kmh:.0f} km/h)",
            "TRIP",
        )

        # Idle
        idle_status = "ALERT" if fe.idle_percentage > 25.0 else ("NORMAL" if fe.idle_percentage < 15.0 else "AVG")
        self.card_idle.update_card(
            f"{fe.idle_percentage:.1f}",
            "%",
            f"Idle Time: {fe.idle_time_seconds / 60.0:.1f}m ({fe.idle_fuel_liters:.2f} L)",
            idle_status,
        )

    def _update_diagnostic_panel(self):
        """Update mechanic diagnostic status card in the left sidebar."""
        rep = self.current_diag_report
        if rep is None:
            return

        # Battery
        b_color = ACCENT_GREEN if "NORMAL" in rep.battery_status else (ACCENT_AMBER if "LOW" in rep.battery_status else ACCENT_RED)
        b_text = f"Battery: {rep.battery_status} (Avg {rep.battery_mean_v:.1f}V)"
        self.lbl_battery_status.configure(text=b_text, text_color=b_color)

        # Coolant
        c_color = ACCENT_GREEN if "NORMAL" in rep.coolant_status else (ACCENT_RED if "OVERHEAT" in rep.coolant_status else ACCENT_AMBER)
        c_text = f"Coolant: {rep.coolant_status} (Peak {rep.coolant_max_c:.0f} C)"
        self.lbl_coolant_status.configure(text=c_text, text_color=c_color)

        # Fuel Trim
        t_color = ACCENT_GREEN if "NORMAL" in rep.fuel_trim_status else (ACCENT_AMBER if "MARGINAL" in rep.fuel_trim_status else ACCENT_RED)
        trim_str = f"{rep.total_trim_pct:+.1f}%" if rep.total_trim_pct is not None else "N/A"
        t_text = f"Fuel Trim: {rep.fuel_trim_status} (Total {trim_str})"
        self.lbl_trim_status.configure(text=t_text, text_color=t_color)

        # Notes
        if rep.notes:
            notes_str = " | ".join(rep.notes)
        else:
            notes_str = "All primary sensor parameters within standard automotive specifications."
        self.lbl_diag_notes.configure(text=notes_str)

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

        # Dual subplot: Left = 2D Heatmap/Contour, Right = Economy vs Speed curve
        ax1 = fig.add_subplot(121)
        ax2 = fig.add_subplot(122)

        s_bins = fe_map["speed_bins"]
        r_bins = fe_map["rpm_bins"]
        matrix = fe_map["fe_matrix"]

        # Convert matrix values if unit is not km/L
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

        # Plot optimal RPM curve overlay on heatmap
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

        # Highlight Sweet Spot
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
            # Update sweet spot metric card
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

        # Subplot 2: Fuel Economy vs Speed Scatter & Trendline
        scatter_s = fe_map["scatter_speed"]
        scatter_fe = fe_map["scatter_fe"].copy()
        if unit == "L/100km":
            scatter_fe = 100.0 / scatter_fe
        elif unit == "MPG (US)":
            scatter_fe = scatter_fe * 2.35214583
        elif unit == "MPG (UK)":
            scatter_fe = scatter_fe * 2.82480936

        # Subsample for rendering speed
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

        # Optimal FE points curve
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

        # City / Highway vertical guide lines
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

        # Subsample scatter points
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

        # Plot gear ratio lines
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

        # Plot optimal RPM curve
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

        # Subplot 1: Coolant Temp vs Elapsed Time
        norm_low, norm_high = thermal["normal_band"]
        for trip_curve in thermal["trip_curves"]:
            clean_name = os.path.basename(trip_curve["name"]).replace(".csv", "")
            ax1.plot(
                trip_curve["time_minutes"],
                trip_curve["temperature_c"],
                linewidth=1.8,
                label=clean_name,
            )

        # Highlight normal thermostat band (82-95 C)
        ax1.axhspan(norm_low, norm_high, color=ACCENT_GREEN, alpha=0.15, label="Normal Thermostat Band (82-95 C)")
        ax1.axhline(100.0, color=ACCENT_RED, linestyle="--", alpha=0.7, label="Overheat Threshold (100 C)")

        ax1.set_title("Engine Coolant Temperature vs Elapsed Time", fontsize=11, fontweight="bold", pad=8)
        ax1.set_xlabel("Elapsed Time (Minutes)", fontsize=10)
        ax1.set_ylabel("Coolant Temperature (C)", fontsize=10)
        ax1.grid(True, linestyle="--", alpha=0.3)
        ax1.legend(loc="lower right", fontsize=8)

        # Subplot 2: Coolant Temp vs Engine Load
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

    def _render_mechanic_graph(self):
        """Render Mechanic Diagnostic health charts: Fuel Trims and Manifold Pressure / Voltage."""
        canvas = self.canvas_mechanic
        canvas.clear()
        fig = canvas.fig

        trips = self.selected_trips
        if not trips:
            canvas.draw()
            return

        ax1 = fig.add_subplot(121)
        ax2 = fig.add_subplot(122)

        # Extract trims
        stft_list = []
        ltft_list = []
        volt_time = []
        volt_val = []
        map_val = []
        rpm_val = []

        for trip in trips:
            df = trip.data
            if "stft_pct" in df.columns:
                stft_list.extend(df["stft_pct"].dropna().values)
            if "ltft_pct" in df.columns:
                ltft_list.extend(df["ltft_pct"].dropna().values)
            if "voltage_v" in df.columns:
                t_arr = df.index.values / 60.0
                v_arr = df["voltage_v"].values
                volt_time.extend(t_arr)
                volt_val.extend(v_arr)
            if "map_kpa" in df.columns and "engine_rpm" in df.columns:
                map_val.extend(df["map_kpa"].dropna().values)
                rpm_val.extend(df["engine_rpm"].dropna().values)

        # Plot 1: Short Term vs Long Term Fuel Trims
        if stft_list and ltft_list and len(stft_list) == len(ltft_list):
            s_arr = np.array(stft_list)
            l_arr = np.array(ltft_list)
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

            # Normal diagnostic boundaries (+/- 10%)
            ax1.axvline(-10.0, color=ACCENT_AMBER, linestyle="--", alpha=0.7)
            ax1.axvline(10.0, color=ACCENT_AMBER, linestyle="--", alpha=0.7)
            ax1.axhline(-10.0, color=ACCENT_AMBER, linestyle="--", alpha=0.7)
            ax1.axhline(10.0, color=ACCENT_AMBER, linestyle="--", alpha=0.7)
            ax1.axvline(0, color="#6B7280", linestyle="-", alpha=0.5)
            ax1.axhline(0, color="#6B7280", linestyle="-", alpha=0.5)

            # Shaded pass box
            ax1.fill_between([-10, 10], -10, 10, color=ACCENT_GREEN, alpha=0.1, label="Pass Zone (+/- 10%)")

            ax1.set_title("Fuel Trim Health (STFT vs LTFT)", fontsize=11, fontweight="bold", pad=8)
            ax1.set_xlabel("Short Term Fuel Trim (%)", fontsize=10)
            ax1.set_ylabel("Long Term Fuel Trim (%)", fontsize=10)
            ax1.grid(True, linestyle="--", alpha=0.3)
            ax1.legend(loc="upper left", fontsize=8)
        else:
            ax1.text(0.5, 0.5, "Fuel trim sensor data not available in records.", ha="center", va="center", color=TEXT_MUTED)

        # Plot 2: Manifold Absolute Pressure (MAP) vs RPM or Battery Voltage
        if map_val and rpm_val and len(map_val) == len(rpm_val):
            m_arr = np.array(map_val)
            r_arr = np.array(rpm_val)
            sub_idx = np.random.choice(len(m_arr), min(1200, len(m_arr)), replace=False)

            ax2.scatter(
                r_arr[sub_idx],
                m_arr[sub_idx],
                color=ACCENT_PURPLE,
                alpha=0.3,
                s=14,
                edgecolors="none",
                label="MAP vs RPM",
            )
            ax2.axhline(100.0, color=TEXT_SECONDARY, linestyle="--", alpha=0.6, label="Atmospheric (100 kPa)")
            ax2.axhspan(25.0, 40.0, color=ACCENT_GREEN, alpha=0.15, label="Normal Idle Vacuum (25-40 kPa)")

            ax2.set_title("Intake Manifold Absolute Pressure vs RPM", fontsize=11, fontweight="bold", pad=8)
            ax2.set_xlabel("Engine RPM", fontsize=10)
            ax2.set_ylabel("Manifold Pressure (kPa)", fontsize=10)
            ax2.grid(True, linestyle="--", alpha=0.3)
            ax2.legend(loc="upper left", fontsize=8)
        elif volt_val:
            ax2.plot(volt_time[:800], volt_val[:800], color=ACCENT_GREEN, linewidth=1.5, label="OBD Module Voltage (V)")
            ax2.axhspan(13.5, 14.8, color=ACCENT_GREEN, alpha=0.15, label="Normal Charging (13.5-14.8V)")
            ax2.set_title("Alternator Charging Voltage Profile", fontsize=11, fontweight="bold", pad=8)
            ax2.set_xlabel("Time (Minutes)", fontsize=10)
            ax2.set_ylabel("Voltage (V)", fontsize=10)
            ax2.grid(True, linestyle="--", alpha=0.3)
            ax2.legend(loc="lower right", fontsize=8)
        else:
            ax2.text(0.5, 0.5, "MAP and Voltage telemetry not available.", ha="center", va="center", color=TEXT_MUTED)

        canvas.draw()

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

        # Header Row
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

        # Rows
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
                f.write("=" * 70 + "\n")
                f.write("CAR RECORD ANALYZER // OBD-II DIAGNOSTIC SUMMARY REPORT\n")
                f.write("=" * 70 + "\n\n")
                f.write(f"Active Files Loaded: {len(trips)}\n")
                f.write(f"Total Sampled Distance: {fe.total_distance_km:.2f} km\n")
                f.write(f"Total Fuel Consumed: {fe.total_fuel_liters:.2f} L\n")
                f.write(f"Idle Percentage: {fe.idle_percentage:.1f}%\n\n")

                f.write("--- FUEL ECONOMY ANALYSIS ---\n")
                f.write(f"City Fuel Economy:     {fe.format_value('city', 'km/L')} km/L ({fe.format_value('city', 'L/100km')} L/100km | {fe.format_value('city', 'MPG (US)')} MPG US)\n")
                f.write(f"Highway Fuel Economy:  {fe.format_value('highway', 'km/L')} km/L ({fe.format_value('highway', 'L/100km')} L/100km | {fe.format_value('highway', 'MPG (US)')} MPG US)\n")
                f.write(f"Combined Fuel Economy: {fe.format_value('combined', 'km/L')} km/L ({fe.format_value('combined', 'L/100km')} L/100km | {fe.format_value('combined', 'MPG (US)')} MPG US)\n\n")

                f.write("--- MECHANIC DIAGNOSTIC HEALTH ---\n")
                f.write(f"Battery Status:   {diag.battery_status} (min: {diag.battery_min_v:.1f}V, mean: {diag.battery_mean_v:.1f}V)\n")
                f.write(f"Coolant Status:   {diag.coolant_status} (peak: {diag.coolant_max_c:.1f} C)\n")
                f.write(f"Fuel Trim Status: {diag.fuel_trim_status}\n")
                if diag.notes:
                    f.write("\nDiagnostic Observations:\n")
                    for note in diag.notes:
                        f.write(f"- {note}\n")
                f.write("\n" + "=" * 70 + "\n")

        messagebox.showinfo("Report Exported", f"Diagnostic report saved successfully to:\n{save_path}", parent=self)


def main():
    """Application entrypoint."""
    app = CarRecordAnalyzerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
