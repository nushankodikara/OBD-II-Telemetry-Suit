"""Mechanic digital metric card component.

Displays large digital readouts, units, subtitle metadata, and LED status badges.
Strictly adheres to project rules: no emojis.
"""

from typing import Optional
import customtkinter as ctk

from src.ui.theme import (
    BG_PANEL,
    BG_PANEL_ALT,
    BORDER_COLOR,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_MUTED,
    TEXT_AMBER,
    TEXT_GREEN,
    TEXT_CYAN,
    TEXT_RED,
    ACCENT_GREEN,
    ACCENT_AMBER,
    ACCENT_RED,
    FONT_SUBTITLE,
    FONT_DIGITAL_LARGE,
    FONT_DIGITAL_SMALL,
    FONT_CAPTION,
    FONT_BADGE,
)


class MetricCard(ctk.CTkFrame):
    """Mechanic-grade digital telemetry gauge card."""

    def __init__(
        self,
        master,
        title: str,
        value: str = "-",
        unit: str = "km/L",
        subtitle: str = "",
        status_text: str = "NO DATA",
        accent_color: str = TEXT_AMBER,
        width: int = 180,
        height: int = 110,
        **kwargs
    ):
        super().__init__(
            master,
            width=width,
            height=height,
            fg_color=BG_PANEL,
            corner_radius=8,
            border_width=1,
            border_color=BORDER_COLOR,
            **kwargs
        )
        self.accent_color = accent_color

        # Header row: Title + Status Badge
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=10, pady=(8, 2))

        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text=title.upper(),
            font=FONT_CAPTION,
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self.title_label.pack(side="left")

        self.badge_label = ctk.CTkLabel(
            self.header_frame,
            text=f"[{status_text}]",
            font=FONT_BADGE,
            text_color=self._get_status_color(status_text),
            anchor="e",
        )
        self.badge_label.pack(side="right")

        # Value + Unit row
        self.value_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.value_frame.pack(fill="x", padx=10, pady=(2, 2))

        self.value_label = ctk.CTkLabel(
            self.value_frame,
            text=value,
            font=FONT_DIGITAL_LARGE,
            text_color=self.accent_color,
            anchor="w",
        )
        self.value_label.pack(side="left")

        self.unit_label = ctk.CTkLabel(
            self.value_frame,
            text=f" {unit}",
            font=FONT_DIGITAL_SMALL,
            text_color=TEXT_MUTED,
            anchor="sw",
        )
        self.unit_label.pack(side="left", padx=(4, 0), pady=(6, 0))

        # Subtitle / Metadata row
        self.sub_label = ctk.CTkLabel(
            self,
            text=subtitle,
            font=FONT_CAPTION,
            text_color=TEXT_MUTED,
            anchor="w",
        )
        self.sub_label.pack(fill="x", padx=10, pady=(0, 8))

    def _get_status_color(self, status: str) -> str:
        s = status.upper()
        if any(w in s for w in ["OPTIMAL", "NORMAL", "PASS", "GOOD", "OPERATING"]):
            return ACCENT_GREEN
        elif any(w in s for w in ["ALERT", "FAULT", "CRITICAL", "OVERHEAT", "LOW"]):
            return ACCENT_RED
        elif any(w in s for w in ["WARNING", "MARGINAL", "AVG", "STANDBY"]):
            return ACCENT_AMBER
        return TEXT_MUTED

    def update_card(
        self,
        value: str,
        unit: Optional[str] = None,
        subtitle: Optional[str] = None,
        status_text: Optional[str] = None,
        accent_color: Optional[str] = None,
    ):
        """Update displayed telemetry and status."""
        self.value_label.configure(text=value)
        if accent_color:
            self.accent_color = accent_color
            self.value_label.configure(text_color=accent_color)
        if unit is not None:
            self.unit_label.configure(text=f" {unit}")
        if subtitle is not None:
            self.sub_label.configure(text=subtitle)
        if status_text is not None:
            self.badge_label.configure(
                text=f"[{status_text}]",
                text_color=self._get_status_color(status_text)
            )
