"""Mechanic workshop dark theme definition for OBD-II scan tool interface.

Tactical, high-contrast dark color palette inspired by professional automotive
diagnostic workstations (Autel, Snap-on, Bosch KTS).
Strictly adheres to project rules: no emojis.
"""

# Color Palette
BG_DARKEST = "#0F1215"       # Window background
BG_PANEL = "#171B20"         # Primary card and container panels
BG_PANEL_ALT = "#1E232A"     # Secondary containers and table rows
BG_CARD_HOVER = "#262C35"    # Hover state for interactive cards
BORDER_COLOR = "#2F3642"     # Subtle mechanical borders
BORDER_ACTIVE = "#F59E0B"    # Active focus border

# Diagnostic Status Colors
ACCENT_AMBER = "#F59E0B"     # Primary tool brand & warning highlight
ACCENT_GREEN = "#10B981"     # Normal / Optimal / High Efficiency
ACCENT_CYAN = "#06B6D4"      # Speed / Velocity / Active data streams
ACCENT_BLUE = "#3B82F6"      # RPM / Engine dynamics
ACCENT_RED = "#EF4444"       # Fault / Alert / Overheat / Low Battery
ACCENT_PURPLE = "#A855F7"    # Secondary map / Thermal transitions

# Text Colors
TEXT_PRIMARY = "#F3F4F6"     # High readability primary text
TEXT_SECONDARY = "#9CA3AF"   # Metadata and secondary labels
TEXT_MUTED = "#6B7280"       # Disabled / hint text
TEXT_AMBER = "#FBBF24"       # Digital readout amber
TEXT_GREEN = "#34D399"       # Digital readout green
TEXT_CYAN = "#22D3EE"        # Digital readout cyan
TEXT_RED = "#F87171"         # Digital readout red alert

# Typography Configurations
FONT_TITLE = ("SF Pro Display", 16, "bold")
FONT_SUBTITLE = ("SF Pro Display", 13, "bold")
FONT_DIGITAL_LARGE = ("Menlo", 24, "bold")
FONT_DIGITAL_MEDIUM = ("Menlo", 18, "bold")
FONT_DIGITAL_SMALL = ("Menlo", 12, "bold")
FONT_BODY = ("SF Pro Text", 12, "normal")
FONT_BODY_BOLD = ("SF Pro Text", 12, "bold")
FONT_CAPTION = ("SF Pro Text", 10, "normal")
FONT_BADGE = ("Menlo", 10, "bold")

# Matplotlib Dark Theme Parameters
MPL_STYLE = {
    "figure.facecolor": BG_PANEL,
    "axes.facecolor": "#12151A",
    "axes.edgecolor": BORDER_COLOR,
    "axes.labelcolor": TEXT_SECONDARY,
    "axes.titlecolor": TEXT_PRIMARY,
    "xtick.color": TEXT_MUTED,
    "ytick.color": TEXT_MUTED,
    "grid.color": "#222731",
    "grid.linestyle": "--",
    "grid.alpha": 0.7,
    "text.color": TEXT_PRIMARY,
    "legend.facecolor": BG_PANEL_ALT,
    "legend.edgecolor": BORDER_COLOR,
}
