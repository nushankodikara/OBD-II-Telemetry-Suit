"""Modal dialogs for vehicle profile configuration and software updates.

Provides standalone window interfaces for:
1. VehicleSettingsDialog: Setting vehicle make, model, engine, capacity, gears, tyre size,
   and analysis thresholds, invoked by default upon importing unconfigured records.
2. SoftwareUpdateDialog: Notifying user of available GitHub binary releases.
Strictly adheres to project rules: no emojis.
"""

import os
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Optional, Callable, Dict, Any
import customtkinter as ctk

from src.session_manager import VehicleProfile
from src.ui.theme import (
    BG_DARKEST,
    BG_PANEL,
    BG_PANEL_ALT,
    BG_CARD_HOVER,
    BORDER_COLOR,
    ACCENT_AMBER,
    ACCENT_CYAN,
    ACCENT_GREEN,
    ACCENT_RED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_MUTED,
    TEXT_AMBER,
    FONT_TITLE,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_CAPTION,
    FONT_BADGE,
    FONT_DIGITAL_SMALL,
)


class VehicleSettingsDialog(ctk.CTkToplevel):
    """Separate window dialog to configure vehicle specifications and analysis settings."""

    def __init__(
        self,
        parent,
        profile: VehicleProfile,
        city_threshold: float,
        highway_threshold: float,
        unit: str,
        on_apply: Callable[[VehicleProfile, float, float, str], None],
        on_save_xml: Optional[Callable[[VehicleProfile, float, float, str], None]] = None,
    ):
        super().__init__(parent)
        self.parent = parent
        self.profile = profile
        self.city_threshold = city_threshold
        self.highway_threshold = highway_threshold
        self.unit = unit
        self.on_apply = on_apply
        self.on_save_xml = on_save_xml

        self.title("Vehicle Profile & Analysis Settings")
        self.geometry("640x720")
        self.resizable(False, False)
        self.configure(fg_color=BG_DARKEST)

        # Center on parent
        self.transient(parent)
        self.grab_set()

        self._build_ui()
        self._populate_fields()

    def _build_ui(self):
        """Construct form layout."""
        # Top Header Banner
        header = ctk.CTkFrame(self, fg_color=BG_PANEL, corner_radius=0, height=70)
        header.pack(fill="x", side="top")

        lbl_title = ctk.CTkLabel(
            header,
            text="VEHICLE PROFILE & ANALYSIS SETTINGS",
            font=FONT_TITLE,
            text_color=TEXT_PRIMARY,
        )
        lbl_title.pack(anchor="w", padx=20, pady=(12, 2))

        lbl_sub = ctk.CTkLabel(
            header,
            text="Configure vehicle parameters so scan logs are analyzed with tailored gear lines and thresholds.",
            font=FONT_CAPTION,
            text_color=TEXT_MUTED,
        )
        lbl_sub.pack(anchor="w", padx=20, pady=(0, 10))

        # Main Scrollable Form Body
        form_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        form_frame.pack(fill="both", expand=True, padx=20, pady=12)

        # Section 1: Vehicle Identification
        self._build_section_header(form_frame, "1. VEHICLE SPECIFICATIONS")

        grid1 = ctk.CTkFrame(form_frame, fg_color=BG_PANEL, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        grid1.pack(fill="x", pady=(0, 14))

        # Make & Model
        ctk.CTkLabel(grid1, text="Make:", font=FONT_CAPTION, text_color=TEXT_SECONDARY).grid(row=0, column=0, sticky="w", padx=(16, 6), pady=(12, 6))
        self.entry_make = ctk.CTkEntry(grid1, width=220, placeholder_text="e.g. Toyota, Honda, Ford")
        self.entry_make.grid(row=0, column=1, sticky="w", padx=(0, 16), pady=(12, 6))

        ctk.CTkLabel(grid1, text="Model:", font=FONT_CAPTION, text_color=TEXT_SECONDARY).grid(row=0, column=2, sticky="w", padx=(12, 6), pady=(12, 6))
        self.entry_model = ctk.CTkEntry(grid1, width=220, placeholder_text="e.g. Aqua, Civic, Focus")
        self.entry_model.grid(row=0, column=3, sticky="w", padx=(0, 16), pady=(12, 6))

        # Year & Engine Type
        ctk.CTkLabel(grid1, text="Model Year:", font=FONT_CAPTION, text_color=TEXT_SECONDARY).grid(row=1, column=0, sticky="w", padx=(16, 6), pady=6)
        self.entry_year = ctk.CTkEntry(grid1, width=220, placeholder_text="e.g. 2018")
        self.entry_year.grid(row=1, column=1, sticky="w", padx=(0, 16), pady=6)

        ctk.CTkLabel(grid1, text="Engine Type:", font=FONT_CAPTION, text_color=TEXT_SECONDARY).grid(row=1, column=2, sticky="w", padx=(12, 6), pady=6)
        self.combo_engine_type = ctk.CTkComboBox(
            grid1,
            width=220,
            values=["Petrol", "Diesel", "Hybrid Petrol", "Turbo Petrol", "Electric (EV)"],
        )
        self.combo_engine_type.grid(row=1, column=3, sticky="w", padx=(0, 16), pady=6)

        # Displacement (cc) & Transmission / Forward Gears
        ctk.CTkLabel(grid1, text="Displacement (cc):", font=FONT_CAPTION, text_color=TEXT_SECONDARY).grid(row=2, column=0, sticky="w", padx=(16, 6), pady=6)
        self.entry_cc = ctk.CTkEntry(grid1, width=220, placeholder_text="e.g. 1500")
        self.entry_cc.grid(row=2, column=1, sticky="w", padx=(0, 16), pady=6)

        ctk.CTkLabel(grid1, text="Transmission / Gears:", font=FONT_CAPTION, text_color=TEXT_SECONDARY).grid(row=2, column=2, sticky="w", padx=(12, 6), pady=6)
        self.combo_gears = ctk.CTkComboBox(
            grid1,
            width=220,
            values=[
                "4-Speed Auto",
                "5-Speed Manual",
                "6-Speed Manual",
                "6-Speed Auto",
                "7-Speed DCT",
                "8-Speed Auto",
                "CVT",
                "e-CVT (Hybrid)",
            ],
        )
        self.combo_gears.grid(row=2, column=3, sticky="w", padx=(0, 16), pady=6)

        # Tyre Size & Fuel Tank
        ctk.CTkLabel(grid1, text="Tyre Dimensions:", font=FONT_CAPTION, text_color=TEXT_SECONDARY).grid(row=3, column=0, sticky="w", padx=(16, 6), pady=6)
        self.entry_tyre = ctk.CTkEntry(grid1, width=220, placeholder_text="e.g. 185/65R15")
        self.entry_tyre.grid(row=3, column=1, sticky="w", padx=(0, 16), pady=6)

        ctk.CTkLabel(grid1, text="Tank Capacity (L):", font=FONT_CAPTION, text_color=TEXT_SECONDARY).grid(row=3, column=2, sticky="w", padx=(12, 6), pady=6)
        self.entry_tank = ctk.CTkEntry(grid1, width=220, placeholder_text="e.g. 45")
        self.entry_tank.grid(row=3, column=3, sticky="w", padx=(0, 16), pady=6)

        # Notes
        ctk.CTkLabel(grid1, text="Mechanic Notes:", font=FONT_CAPTION, text_color=TEXT_SECONDARY).grid(row=4, column=0, sticky="w", padx=(16, 6), pady=(6, 12))
        self.entry_notes = ctk.CTkEntry(grid1, width=500, placeholder_text="e.g. 1NZ-FXE Atkinson cycle engine, low-viscosity 0W-20 oil")
        self.entry_notes.grid(row=4, column=1, columnspan=3, sticky="w", padx=(0, 16), pady=(6, 12))

        # Section 2: Analysis Thresholds & Units
        self._build_section_header(form_frame, "2. DRIVING THRESHOLDS & UNITS")

        grid2 = ctk.CTkFrame(form_frame, fg_color=BG_PANEL, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        grid2.pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(grid2, text="City Speed Max (km/h):", font=FONT_CAPTION, text_color=TEXT_SECONDARY).grid(row=0, column=0, sticky="w", padx=(16, 6), pady=(12, 6))
        self.entry_city = ctk.CTkEntry(grid2, width=160)
        self.entry_city.grid(row=0, column=1, sticky="w", padx=(0, 16), pady=(12, 6))

        ctk.CTkLabel(grid2, text="Highway Speed Min (km/h):", font=FONT_CAPTION, text_color=TEXT_SECONDARY).grid(row=0, column=2, sticky="w", padx=(12, 6), pady=(12, 6))
        self.entry_highway = ctk.CTkEntry(grid2, width=160)
        self.entry_highway.grid(row=0, column=3, sticky="w", padx=(0, 16), pady=(12, 6))

        ctk.CTkLabel(grid2, text="Fuel Economy Display Unit:", font=FONT_CAPTION, text_color=TEXT_SECONDARY).grid(row=1, column=0, sticky="w", padx=(16, 6), pady=(6, 12))
        self.combo_unit = ctk.CTkComboBox(
            grid2,
            width=220,
            values=["km/L", "L/100km", "MPG (US)", "MPG (UK)"],
        )
        self.combo_unit.grid(row=1, column=1, columnspan=2, sticky="w", padx=(0, 16), pady=(6, 12))

        # Action Buttons Footer
        footer = ctk.CTkFrame(self, fg_color=BG_PANEL, corner_radius=0, height=64)
        footer.pack(fill="x", side="bottom")

        btn_box = ctk.CTkFrame(footer, fg_color="transparent")
        btn_box.pack(side="right", padx=16, pady=14)

        btn_skip = ctk.CTkButton(
            btn_box,
            text="Skip / Keep Current",
            font=FONT_BODY,
            width=140,
            fg_color=BG_PANEL_ALT,
            hover_color=BG_CARD_HOVER,
            text_color=TEXT_SECONDARY,
            command=self.destroy,
        )
        btn_skip.pack(side="left", padx=6)

        if self.on_save_xml:
            btn_save_xml = ctk.CTkButton(
                btn_box,
                text="Save to XML...",
                font=FONT_BODY,
                width=130,
                fg_color=BG_PANEL_ALT,
                hover_color=BG_CARD_HOVER,
                text_color=ACCENT_CYAN,
                command=self._handle_save_xml,
            )
            btn_save_xml.pack(side="left", padx=6)

        btn_apply = ctk.CTkButton(
            btn_box,
            text="Apply & Analyze",
            font=FONT_BODY_BOLD,
            width=160,
            fg_color=ACCENT_AMBER,
            hover_color="#D97706",
            text_color=BG_DARKEST,
            command=self._handle_apply,
        )
        btn_apply.pack(side="left", padx=6)

    def _build_section_header(self, parent, text: str):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(8, 4))
        ctk.CTkLabel(row, text=text, font=FONT_BADGE, text_color=ACCENT_AMBER).pack(side="left")

    def _populate_fields(self):
        """Load initial profile values into widgets."""
        self.entry_make.insert(0, self.profile.make)
        self.entry_model.insert(0, self.profile.model)
        self.entry_year.insert(0, self.profile.year)
        if self.profile.engine_type:
            self.combo_engine_type.set(self.profile.engine_type)
        self.entry_cc.insert(0, self.profile.displacement_cc)
        if self.profile.gears:
            self.combo_gears.set(self.profile.gears)
        self.entry_tyre.insert(0, self.profile.tyre_size)
        self.entry_tank.insert(0, self.profile.fuel_tank_l)
        self.entry_notes.insert(0, self.profile.notes)

        self.entry_city.insert(0, str(self.city_threshold))
        self.entry_highway.insert(0, str(self.highway_threshold))
        self.combo_unit.set(self.unit)

    def _extract_profile(self) -> VehicleProfile:
        return VehicleProfile(
            make=self.entry_make.get().strip(),
            model=self.entry_model.get().strip(),
            year=self.entry_year.get().strip(),
            engine_type=self.combo_engine_type.get().strip(),
            displacement_cc=self.entry_cc.get().strip(),
            transmission=self.combo_gears.get().strip(),
            gears=self.combo_gears.get().strip(),
            tyre_size=self.entry_tyre.get().strip(),
            fuel_tank_l=self.entry_tank.get().strip(),
            notes=self.entry_notes.get().strip(),
        )

    def _extract_thresholds(self) -> Tuple[float, float, str]:
        try:
            c = float(self.entry_city.get().strip())
        except ValueError:
            c = 45.0
        try:
            h = float(self.entry_highway.get().strip())
        except ValueError:
            h = 70.0
        u = self.combo_unit.get().strip()
        return c, h, u

    def _handle_apply(self):
        prof = self._extract_profile()
        c, h, u = self._extract_thresholds()
        self.on_apply(prof, c, h, u)
        self.destroy()

    def _handle_save_xml(self):
        prof = self._extract_profile()
        c, h, u = self._extract_thresholds()
        if self.on_save_xml:
            self.on_save_xml(prof, c, h, u)
        self.destroy()


class SoftwareUpdateDialog(ctk.CTkToplevel):
    """Modal dialog displaying GitHub binary release update information."""

    def __init__(self, parent, release_data: Dict[str, Any], current_version: str):
        super().__init__(parent)
        self.parent = parent
        self.release_data = release_data
        self.current_version = current_version

        self.title("Software Update Available")
        self.geometry("540x440")
        self.resizable(False, False)
        self.configure(fg_color=BG_DARKEST)

        self.transient(parent)
        self.grab_set()

        self._build_ui()

    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color=BG_PANEL, corner_radius=0, height=64)
        header.pack(fill="x", side="top")

        ctk.CTkLabel(
            header,
            text="SOFTWARE UPDATE AVAILABLE",
            font=FONT_TITLE,
            text_color=ACCENT_GREEN,
        ).pack(anchor="w", padx=20, pady=(12, 2))

        ctk.CTkLabel(
            header,
            text=f"Current: v{self.current_version}  ->  Latest: v{self.release_data.get('tag_name', 'new')}",
            font=FONT_DIGITAL_SMALL,
            text_color=TEXT_AMBER,
        ).pack(anchor="w", padx=20, pady=(0, 10))

        # Body Container
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=12)

        release_name = self.release_data.get("name", "New Release")
        pub_date = self.release_data.get("published_at", "")
        ctk.CTkLabel(
            body,
            text=f"{release_name} (Released {pub_date})",
            font=FONT_BODY_BOLD,
            text_color=TEXT_PRIMARY,
            anchor="w",
        ).pack(fill="x", pady=(0, 6))

        # Changelog / Release Notes
        notes_box = ctk.CTkScrollableFrame(body, fg_color=BG_PANEL, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        notes_box.pack(fill="both", expand=True, pady=(0, 12))

        body_text = self.release_data.get("body", "No changelog provided.")
        ctk.CTkLabel(
            notes_box,
            text=body_text,
            font=FONT_CAPTION,
            text_color=TEXT_SECONDARY,
            wraplength=460,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=10, pady=10)

        # Footer Buttons
        footer = ctk.CTkFrame(self, fg_color=BG_PANEL, corner_radius=0, height=60)
        footer.pack(fill="x", side="bottom")

        btn_box = ctk.CTkFrame(footer, fg_color="transparent")
        btn_box.pack(side="right", padx=16, pady=12)

        btn_close = ctk.CTkButton(
            btn_box,
            text="Remind Me Later",
            font=FONT_BODY,
            width=130,
            fg_color=BG_PANEL_ALT,
            hover_color=BG_CARD_HOVER,
            text_color=TEXT_SECONDARY,
            command=self.destroy,
        )
        btn_close.pack(side="left", padx=6)

        btn_download = ctk.CTkButton(
            btn_box,
            text="Download Release",
            font=FONT_BODY_BOLD,
            width=160,
            fg_color=ACCENT_GREEN,
            hover_color="#059669",
            text_color=BG_DARKEST,
            command=self._open_download_url,
        )
        btn_download.pack(side="left", padx=6)

    def _open_download_url(self):
        url = self.release_data.get("html_url", "https://github.com/nushankodi/OBD-II-Telemetry-Suit/releases")
        webbrowser.open(url)
        self.destroy()
