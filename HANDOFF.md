# Developer Handoff Documentation - Car Record Analyzer

This document provides developer-level architecture, module contracts, data flow specifications, and debugging procedures for the Car Record Analyzer application.

Strict Project Requirement: No emojis are used in this codebase or documentation.

---

## 1. System Architecture Overview

The system is organized into a clean decoupled three-tier architecture:
1. Ingestion Tier (`src/data_loader.py`): Parses raw event-stream CSV files, maps OBD PIDs into standard engineering fields, and synchronizes asynchronous queries into uniform 1.0-second time grids.
2. Analytics Tier (`src/analyzer.py`): Pure Python and NumPy/SciPy computing engine that calculates city/highway/combined fuel economy, 2D fuel economy surfaces, gear ratio curves, and mechanic health parameters.
3. Presentation Tier (`src/ui/`): CustomTkinter dark-mode desktop workstation with embedded Matplotlib interactive figures, digital telemetry cards, and multi-file selection.

```
+-------------------------------------------------------------------+
|                        PRESENTATION TIER                          |
|  CarRecordAnalyzerApp (src/ui/app.py)                             |
|  ├── MetricCard (src/ui/components/metric_card.py)                |
|  ├── RecordListPanel (src/ui/components/record_list.py)           |
|  └── GraphCanvas (src/ui/components/graph_canvas.py)              |
+---------------------------------+---------------------------------+
                                  |
                                  v
+-------------------------------------------------------------------+
|                         ANALYTICS TIER                            |
|  VehicleAnalyzer (src/analyzer.py)                                |
|  ├── calculate_fuel_economy() -> FuelEconomyResult                |
|  ├── compute_optimal_rpm_speed_curve() -> Dict                    |
|  ├── compute_optimal_fuel_economy_rpm_speed_curve() -> Dict       |
|  ├── analyze_coolant_temperature() -> Dict                        |
|  └── generate_diagnostic_health() -> DiagnosticHealthReport       |
+---------------------------------+---------------------------------+
                                  |
                                  v
+-------------------------------------------------------------------+
|                         INGESTION TIER                            |
|  ScanTrip & parse_obd_csv (src/data_loader.py)                    |
|  ├── Semicolon-delimited CSV parser                               |
|  ├── Asynchronous PID time synchronization (1.0s grid)            |
|  └── Multi-trip loader                                            |
+-------------------------------------------------------------------+
```

---

## 2. Module Specifications

### 2.1 Ingestion Engine (`src/data_loader.py`)

- `PID_MAP`: Dictionary mapping raw OBD PID strings (e.g., "Calculated instant fuel rate", "Intake manifold absolute pressure") to canonical snake_case identifiers (`fuel_rate_lh`, `map_kpa`, `speed_kmh`, `engine_rpm`, `coolant_temp_c`, `stft_pct`, `ltft_pct`, `voltage_v`).
- `ScanTrip`: Dataclass containing:
  - `file_path` (str)
  - `file_name` (str)
  - `start_seconds` (float): Epoch or session starting timestamp
  - `duration_seconds` (float): Elapsed duration
  - `total_raw_rows` (int): Number of raw lines processed
  - `data` (pd.DataFrame): Time-aligned DataFrame indexed by `elapsed_seconds`
  - `has_gps`, `latitude_start`, `longitude_start`
- `parse_obd_csv(file_path: str, grid_step_seconds: float = 1.0) -> Optional[ScanTrip]`:
  - Strips empty fields created by trailing semicolons.
  - Converts `SECONDS` to numeric seconds, computes relative elapsed time, bins to 1.0s intervals, pivots by metric, reindexes onto a contiguous grid, and uses linear interpolation (`limit=5`) followed by `bfill()` and `ffill()`.
- `load_all_records(directory_path: str = "Records") -> List[ScanTrip]`:
  - Scans directory and returns all successfully parsed `ScanTrip` objects.

### 2.2 Analytics Engine (`src/analyzer.py`)

- `FuelEconomyResult`:
  - Stores `city_kml`, `highway_kml`, `combined_kml`, distance breakdowns, and fuel amounts.
  - `get_value(category, unit)`: Supports `"km/L"`, `"L/100km"`, `"MPG (US)"`, `"MPG (UK)"`.
  - `format_value(category, unit)`: Returns formatted string or `"-"` if data is `None`.
- `VehicleAnalyzer`:
  - Parameters:
    - `city_speed_max` (default 45.0 km/h)
    - `highway_speed_min` (default 70.0 km/h)
    - `min_moving_speed` (default 1.0 km/h)
    - `min_distance_threshold_km` (default 0.3 km)
  - Methods:
    - `calculate_fuel_economy(trips: List[ScanTrip]) -> FuelEconomyResult`:
      Aggregates distance and fuel across valid driving intervals.
    - `compute_optimal_rpm_speed_curve(trips)`:
      Computes median operating RPM across 5 km/h speed bins and identifies transmission gear ratios via histogram peak detection of `speed / RPM`.
    - `compute_optimal_fuel_economy_rpm_speed_curve(trips)`:
      Generates 2D matrix of fuel economy against (Speed, RPM), smooths using Gaussian filter, extracts the top efficiency RPM envelope per speed, and identifies the global cruising sweet spot.
    - `analyze_coolant_temperature(trips)`:
      Extracts temperature timelines per trip, thermostat normal band (82 C to 95 C), warm-up time to 80 C, and temperature versus engine load correlation.
    - `generate_diagnostic_health(trips) -> DiagnosticHealthReport`:
      Assesses battery charging voltage, coolant peak temperature, fuel trims (STFT + LTFT), and logs mechanic observations.

### 2.3 Presentation Tier (`src/ui/`)

- `src/ui/theme.py`: Tactical dark workshop color tokens (`BG_DARKEST = "#0F1215"`, `BG_PANEL = "#171B20"`, `ACCENT_AMBER = "#F59E0B"`, `ACCENT_GREEN = "#10B981"`, `ACCENT_CYAN = "#06B6D4"`, `ACCENT_RED = "#EF4444"`), fonts, and Matplotlib rcParams.
- `src/ui/components/metric_card.py`: Digital gauge card widget displaying large numeric readouts, unit tags, metadata, and colored status badges.
- `src/ui/components/graph_canvas.py`: Matplotlib canvas wrapped in CustomTkinter frame with a customized dark `NavigationToolbar2Tk`.
- `src/ui/components/record_list.py`: Scrollable list of loaded scan files with multi-select checkboxes, metadata labels, batch action buttons, and selection change callbacks.
- `src/ui/app.py`: Main `ctk.CTk` root window orchestrating top navigation, unit switching, threshold configuration, telemetry updates, and chart rendering across 5 tabs:
  - Tab 1: Efficiency Map & Sweet Spot
  - Tab 2: Optimal RPM & Speed Curve
  - Tab 3: Engine Thermal Profile
  - Tab 4: Diagnostic Sensor Health
  - Tab 5: Trip Sessions & Export

---

## 3. Data Flow & Event Lifecycle

1. Application Initialization:
   - `CarRecordAnalyzerApp` starts, initializes UI layout, and calls `_load_records_directory("Records")`.
   - Records are parsed and stored in `self.all_trips` and `self.selected_trips`.
   - `_reanalyze_and_redraw()` is invoked.
2. Re-analysis Pipeline:
   - `calculate_fuel_economy(self.selected_trips)` generates aggregate figures.
   - `generate_diagnostic_health(self.selected_trips)` produces sensor report.
   - `_update_metric_cards()` updates top cards, showing `"-"` if highway or city data is absent.
   - Graphs are refreshed in the canvas widgets.
   - Detailed trip rows are rendered in Tab 5.
3. User Interactions:
   - Checkbox Toggle: Fires `_on_records_selection_changed`, immediately re-running analysis and updating charts.
   - Unit Switch: Changes `self.current_unit`, instantly recalculating and re-rendering cards, heatmap axes, and session table.
   - Threshold Adjustment: Updates `city_speed_max` and `highway_speed_min`, reclassifying trip segments.
   - Import CSV: Appends external files to `self.all_trips` and refreshes list.
   - Export: Generates plain text or CSV diagnostic summary.

---

## 4. Key Troubleshooting Notes

### macOS Tkinter Initialization Issue
If running on Apple Silicon / macOS Sequoia with the default system Python (`/usr/bin/python3`), Tkinter may abort due to an obsolete Cocoa version check in Apple's bundled Tcl/Tk.
Solution: Ensure the virtual environment is constructed using Homebrew's modern Python:
```bash
/opt/homebrew/bin/python3.14 -m venv --clear .venv
.venv/bin/pip install -r requirements.txt
```

### Missing Sensors in Scans
Certain vehicle scans may omit specific PIDs (for example, fuel trims or coolant temperature if the vehicle ECU did not report them). All data loaders and analysis methods are written defensively:
- Sensor absence returns empty arrays or `None`.
- The UI displays informative labels such as "Sensor data not available in records" rather than throwing uncaught exceptions.

---

## 5. Maintenance and Extension Guidelines

- Preserving Project Rules: Never introduce emojis into any file, UI label, or log message.
- Adding New Diagnostics: Add metric extraction in `PID_MAP` within `src/data_loader.py`, implement diagnostic evaluation inside `generate_diagnostic_health()` in `src/analyzer.py`, and add a visual panel or graph inside `src/ui/app.py`.
- Automated Verification: Run `tests/test_analyzer.py` before committing changes to ensure no metric calculation regressions.
