"""Dark-themed Matplotlib canvas component for CustomTkinter.

Renders high-resolution interactive automotive diagnostic charts with
zoom, pan, and clean toolbars.
Strictly adheres to project rules: no emojis.
"""

import tkinter as tk
import customtkinter as ctk
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from src.ui.theme import (
    BG_DARKEST,
    BG_PANEL,
    BG_PANEL_ALT,
    BORDER_COLOR,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    MPL_STYLE,
)


class DarkNavigationToolbar(NavigationToolbar2Tk):
    """Custom-styled navigation toolbar for dark workshop theme."""

    def __init__(self, canvas, parent):
        self.toolitems = (
            ("Home", "Reset original view", "home", "home"),
            ("Back", "Back to previous view", "back", "back"),
            ("Forward", "Forward to next view", "forward", "forward"),
            (None, None, None, None),
            ("Pan", "Pan with left button, zoom with right", "move", "pan"),
            ("Zoom", "Zoom to rectangle", "zoom_to_rect", "zoom"),
            (None, None, None, None),
            ("Save", "Save figure as image", "filesave", "save_figure"),
        )
        super().__init__(canvas, parent)
        self.config(background=BG_PANEL)
        self._message_label.config(background=BG_PANEL, foreground=TEXT_SECONDARY)
        for child in self.winfo_children():
            if isinstance(child, tk.Button):
                child.config(background=BG_PANEL_ALT, relief="flat", borderwidth=0)


class GraphCanvas(ctk.CTkFrame):
    """Interactive dark workshop graph container."""

    def __init__(self, master, figsize=(7.5, 4.8), dpi=100, **kwargs):
        super().__init__(
            master,
            fg_color=BG_PANEL,
            corner_radius=8,
            border_width=1,
            border_color=BORDER_COLOR,
            **kwargs
        )
        # Apply dark theme to matplotlib
        plt.rcParams.update(MPL_STYLE)

        self.fig = Figure(figsize=figsize, dpi=dpi, facecolor=BG_PANEL)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.configure(bg=BG_PANEL, highlightthickness=0)

        # Toolbar container
        self.toolbar_frame = ctk.CTkFrame(self, fg_color=BG_PANEL, height=36)
        self.toolbar_frame.pack(side="bottom", fill="x", padx=4, pady=(0, 4))

        self.toolbar = DarkNavigationToolbar(self.canvas, self.toolbar_frame)
        self.toolbar.update()

        self.canvas_widget.pack(side="top", fill="both", expand=True, padx=4, pady=4)

    def clear(self):
        """Clear all axes from figure."""
        self.fig.clear()

    def draw(self):
        """Redraw canvas after updating figure."""
        try:
            self.fig.tight_layout()
        except Exception:
            pass
        self.canvas.draw()
