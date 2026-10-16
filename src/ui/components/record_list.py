"""Record file selector and session management component.

Provides multi-file selection, session metadata inspection, and instant callbacks.
Strictly adheres to project rules: no emojis.
"""

from typing import Callable, List, Optional
import os
import tkinter as tk
import customtkinter as ctk

from src.data_loader import ScanTrip
from src.ui.theme import (
    BG_DARKEST,
    BG_PANEL,
    BG_PANEL_ALT,
    BG_CARD_HOVER,
    BORDER_COLOR,
    ACCENT_AMBER,
    ACCENT_GREEN,
    ACCENT_CYAN,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_MUTED,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_CAPTION,
    FONT_BADGE,
)


class RecordItemWidget(ctk.CTkFrame):
    """Row item representing a single OBD trip record file."""

    def __init__(
        self,
        master,
        trip: ScanTrip,
        is_selected: bool = True,
        on_toggle: Optional[Callable[[str, bool], None]] = None,
        **kwargs
    ):
        super().__init__(
            master,
            fg_color=BG_PANEL_ALT,
            corner_radius=6,
            border_width=1,
            border_color=BORDER_COLOR,
            **kwargs
        )
        self.trip = trip
        self.on_toggle = on_toggle

        self.var = ctk.BooleanVar(value=is_selected)

        # Checkbox
        self.checkbox = ctk.CTkCheckBox(
            self,
            text="",
            variable=self.var,
            width=20,
            checkbox_width=18,
            checkbox_height=18,
            corner_radius=4,
            border_color=BORDER_COLOR,
            fg_color=ACCENT_AMBER,
            hover_color=ACCENT_AMBER,
            command=self._handle_toggle,
        )
        self.checkbox.pack(side="left", padx=(8, 4), pady=6)

        # Info column
        info_col = ctk.CTkFrame(self, fg_color="transparent")
        info_col.pack(side="left", fill="x", expand=True, padx=4, pady=4)

        title_row = ctk.CTkFrame(info_col, fg_color="transparent")
        title_row.pack(fill="x")

        clean_name = os.path.basename(trip.file_path).replace(".csv", "")
        self.name_label = ctk.CTkLabel(
            title_row,
            text=clean_name,
            font=FONT_BODY_BOLD,
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self.name_label.pack(side="left")

        # Speed badge
        hwy_capable = trip.max_speed >= 70.0
        badge_text = "HWY+CITY" if hwy_capable else "CITY ONLY"
        badge_color = ACCENT_GREEN if hwy_capable else ACCENT_CYAN

        self.badge = ctk.CTkLabel(
            title_row,
            text=f"[{badge_text}]",
            font=FONT_BADGE,
            text_color=badge_color,
            anchor="e",
        )
        self.badge.pack(side="right", padx=(0, 6))

        # Meta row: duration, rows, max speed
        meta_row = ctk.CTkFrame(info_col, fg_color="transparent")
        meta_row.pack(fill="x")

        meta_str = (
            f"Duration: {trip.duration_minutes:.1f}m | "
            f"Rows: {trip.total_raw_rows:,} | "
            f"Peak: {trip.max_speed:.0f} km/h"
        )
        self.meta_label = ctk.CTkLabel(
            meta_row,
            text=meta_str,
            font=FONT_CAPTION,
            text_color=TEXT_MUTED,
            anchor="w",
        )
        self.meta_label.pack(side="left")

    def _handle_toggle(self):
        if self.on_toggle:
            self.on_toggle(self.trip.file_path, self.var.get())

    def set_selected(self, selected: bool):
        self.var.set(selected)


class RecordListPanel(ctk.CTkFrame):
    """Panel managing multiple loaded scan records with batch actions."""

    def __init__(
        self,
        master,
        on_selection_changed: Callable[[List[str]], None],
        on_add_files: Callable[[], None],
        on_reload_dir: Callable[[], None],
        **kwargs
    ):
        super().__init__(
            master,
            fg_color=BG_PANEL,
            corner_radius=8,
            border_width=1,
            border_color=BORDER_COLOR,
            **kwargs
        )
        self.on_selection_changed = on_selection_changed
        self.on_add_files = on_add_files
        self.on_reload_dir = on_reload_dir

        self.item_widgets: List[RecordItemWidget] = []
        self.trips: List[ScanTrip] = []

        # Header with title and count
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=12, pady=(12, 6))

        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text="SCAN RECORD FEED",
            font=FONT_BODY_BOLD,
            text_color=TEXT_PRIMARY,
        )
        self.title_label.pack(side="left")

        self.count_badge = ctk.CTkLabel(
            self.header_frame,
            text="0 Active",
            font=FONT_BADGE,
            text_color=ACCENT_AMBER,
        )
        self.count_badge.pack(side="right")

        # Action bar: Add, Reload, Select All, Deselect
        action_bar = ctk.CTkFrame(self, fg_color="transparent")
        action_bar.pack(fill="x", padx=10, pady=(2, 6))

        self.btn_add = ctk.CTkButton(
            action_bar,
            text="Import CSV...",
            font=FONT_CAPTION,
            height=26,
            fg_color=BG_PANEL_ALT,
            hover_color=BG_CARD_HOVER,
            border_width=1,
            border_color=BORDER_COLOR,
            command=self.on_add_files,
        )
        self.btn_add.pack(side="left", padx=(0, 4), expand=True, fill="x")

        self.btn_reload = ctk.CTkButton(
            action_bar,
            text="Reload Folder",
            font=FONT_CAPTION,
            height=26,
            fg_color=BG_PANEL_ALT,
            hover_color=BG_CARD_HOVER,
            border_width=1,
            border_color=BORDER_COLOR,
            command=self.on_reload_dir,
        )
        self.btn_reload.pack(side="left", expand=True, fill="x")

        # Quick toggles row
        toggle_bar = ctk.CTkFrame(self, fg_color="transparent")
        toggle_bar.pack(fill="x", padx=10, pady=(0, 6))

        self.btn_select_all = ctk.CTkButton(
            toggle_bar,
            text="Select All",
            font=FONT_CAPTION,
            height=22,
            fg_color="transparent",
            text_color=TEXT_SECONDARY,
            hover_color=BG_PANEL_ALT,
            command=self._select_all,
        )
        self.btn_select_all.pack(side="left")

        self.btn_clear = ctk.CTkButton(
            toggle_bar,
            text="Clear All",
            font=FONT_CAPTION,
            height=22,
            fg_color="transparent",
            text_color=TEXT_SECONDARY,
            hover_color=BG_PANEL_ALT,
            command=self._deselect_all,
        )
        self.btn_clear.pack(side="right")

        # Scrollable items list
        self.scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color=BG_DARKEST,
            corner_radius=6,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def set_trips(self, trips: List[ScanTrip]):
        """Populate list with parsed trips."""
        self.trips = trips
        # Clear existing
        for widget in self.item_widgets:
            widget.destroy()
        self.item_widgets.clear()

        for trip in trips:
            item = RecordItemWidget(
                self.scroll_frame,
                trip=trip,
                is_selected=True,
                on_toggle=self._handle_item_toggle,
            )
            item.pack(fill="x", pady=3)
            self.item_widgets.append(item)

        self._update_count()

    def _handle_item_toggle(self, file_path: str, is_active: bool):
        self._update_count()
        selected = self.get_selected_paths()
        self.on_selection_changed(selected)

    def _select_all(self):
        for w in self.item_widgets:
            w.set_selected(True)
        self._update_count()
        self.on_selection_changed(self.get_selected_paths())

    def _deselect_all(self):
        for w in self.item_widgets:
            w.set_selected(False)
        self._update_count()
        self.on_selection_changed(self.get_selected_paths())

    def _update_count(self):
        active_count = sum(1 for w in self.item_widgets if w.var.get())
        total_count = len(self.item_widgets)
        self.count_badge.configure(text=f"{active_count} of {total_count} Active")

    def get_selected_paths(self) -> List[str]:
        return [w.trip.file_path for w in self.item_widgets if w.var.get()]
