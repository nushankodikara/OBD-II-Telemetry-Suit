# Developer Handoff Documentation - Car Record Analyzer

This document provides developer-level architecture, module contracts, data flow specifications, and debugging procedures for the Car Record Analyzer application.

IMPORTANT NOTICE: This tool ingests exclusively Car Scanner ELM OBD2 app's vertical export format (semicolon-delimited with SECONDS, PID, VALUE, UNITS, LATITUDE, LONGTITUDE).

Strict Project Requirement: No emojis are used in this codebase or documentation.

---

## 1. System Architecture Overview

The system is organized into a decoupled three-tier architecture:
1. Ingestion & Pre-Cleanup Tier (`src/data_loader.py`): Validates the Car Scanner ELM OBD2 schema, applies sensor boundary filtering, sanitizes GPS teleportation leaps, conditions DFCO coasting spikes, and synchronizes asynchronous queries onto uniform 1.0-second time grids with interpolated GPS positions.
2. Analytics & Anomaly Tier (`src/analyzer.py`): Pure Python and NumPy/SciPy/scikit-learn computing engine calculating fuel economy, 2D efficiency surfaces, gear ratio curves, deep STFT/LTFT zone analysis with repair recommendations, and physical/multivariate Isolation Forest anomaly detection.
3. Presentation Tier (`src/ui/`): CustomTkinter dark-mode desktop workstation featuring embedded Matplotlib figures, interactive OpenStreetMap routes via `tkintermapview`, telemetry cards, and multi-file selection.

```
+-------------------------------------------------------------------+
|                        PRESENTATION TIER                          |
|  CarRecordAnalyzerApp (src/ui/app.py)                             |
|  ├── MetricCard (src/ui/components/metric_card.py)                |
|  ├── RecordListPanel (src/ui/components/record_list.py)           |
|  ├── GraphCanvas (src/ui/components/graph_canvas.py)              |
|  └── TkinterMapView (OpenStreetMap Route & Telemetry Viewer)     |
+---------------------------------+---------------------------------+
                                  |
                                  v
+-------------------------------------------------------------------+
|                   ANALYTICS & ANOMALY TIER                        |
|  VehicleAnalyzer (src/analyzer.py)                                |
|  ├── calculate_fuel_economy() -> FuelEconomyResult                |
|  ├── compute_optimal_rpm_speed_curve() -> Dict                    |
|  ├── compute_optimal_fuel_economy_rpm_speed_curve() -> Dict       |
|  ├── analyze_coolant_temperature() -> Dict                        |
|  ├── analyze_fuel_trims_in_depth() -> FuelTrimDiagnostic          |
|  ├── detect_anomalies() -> List[TelemetryAnomaly]                 |
|  └── generate_diagnostic_health() -> DiagnosticHealthReport       |
+---------------------------------+---------------------------------+
                                  |
                                  v
+-------------------------------------------------------------------+
|                   INGESTION & CLEANUP TIER                        |
|  ScanTrip & clean_raw_obd_data (src/data_loader.py)               |
|  ├── Car Scanner ELM OBD2 format validator                        |
|  ├── SENSOR_BOUNDS physical range cleaner                         |
|  ├── Haversine GPS jump and teleportation filter                  |
|  ├── Asynchronous PID time synchronization (1.0s grid)            |
|  └── DataCleanupReport audit generation                           |
+-------------------------------------------------------------------+
```

---

## 2. Module Specifications

### 2.1 Ingestion & Cleanup Engine (`src/data_loader.py`)

- `PID_MAP`: Canonical mapping from Car Scanner ELM OBD2 PID strings to standard internal identifiers.
- `SENSOR_BOUNDS`: Physical operational boundaries for clamping corrupted telemetry readings.
- `DataCleanupReport`: Audit dataclass tracking raw lines, retained records, dropped records, sensor outliers cleaned, GPS teleportation jumps filtered, and DFCO events conditioned.
- `clean_raw_obd_data(raw_df: pd.DataFrame) -> Tuple[pd.DataFrame, DataCleanupReport]`:
  - Verifies presence of `SECONDS`, `PID`, `VALUE`.
  - Removes trailing semicolon artifacts.
  - Drops rows with null timestamps or non-numeric sensor values.
  - Clamps out-of-bounds sensor values to physical limits.
  - Detects GPS teleportation jumps using Haversine distance (> 2 km jump or implied speed > 220 km/h) and invalidates corrupted coordinates.
  - Drops duplicate sequential queries.
- `parse_obd_csv(file_path: str, grid_step_seconds: float = 1.0) -> Optional[ScanTrip]`:
  - Executes `clean_raw_obd_data()`.
  - Aligns telemetry and GPS coordinates onto a contiguous 1.0s grid using linear interpolation.
  - Encapsulates results in `ScanTrip`.

### 2.2 Analytics & Anomaly Engine (`src/analyzer.py`)

- `TelemetryAnomaly`: Dataclass containing `timestamp_sec`, `category`, `severity`, `metric_name`, `detected_value`, `expected_range`, `description`, `trip_file`, `latitude`, `longitude`.
- `FuelTrimDiagnostic`: Dataclass storing zone-specific trims (Idle, Cruise, High Load), diagnostic hypothesis title, severity, likelihood score, probable mechanical causes, and actionable technician repair steps.
- `VehicleAnalyzer.analyze_fuel_trims_in_depth(trips)`:
  - Partitions driving samples into Idle (RPM < 1000, Speed <= 3 km/h), Cruise (RPM 1200-2600, Speed > 20 km/h, Load <= 60%), and High Load (Load > 60%).
  - Evaluates differential trim behavior to distinguish intake vacuum leaks from fuel delivery restrictions or rich conditions.
- `VehicleAnalyzer.detect_anomalies(trips)`:
  - Physical rules: Voltage < 12.2V with engine running, voltage spikes > 15.2V, coolant temp > 100 C, total fuel trim > +18% or < -18%, speed sensor dropouts (RPM > 1800 with speed = 0).
  - Machine Learning: Fits `sklearn.ensemble.IsolationForest` on multi-sensor telemetry to flag multivariate outliers.

### 2.3 Presentation Tier (`src/ui/app.py`)

- Orchestrates 7 specialized diagnostic workstations:
  1. *Efficiency & Sweet Spot*: 2D heatmap and economy vs. speed scatter.
  2. *RPM & Speed Curves*: Speed vs. RPM scatter, gear lines, and median curve.
  3. *Thermal Profile*: Coolant temperature timeline and load correlation.
  4. *Fuel Trim Diagnostics*: Operating zone comparison, diagnostic banner, and action plan.
  5. *Live GPS Route Map*: Dual-mode view with `TkinterMapView` (OpenStreetMap) and Matplotlib spatial telemetry heatmap.
  6. *Anomaly Detection*: Scrollable register of detected anomalies with severity badges and timestamps.
  7. *Data Cleanup & Sessions*: Pre-ingestion audit card, trip comparison table, and Text/CSV exporter.

---

## 3. Verification Workflow

Run the test suite:
```bash
.venv/bin/python -m unittest discover -s tests
```

Execute the UI lifecycle and zero-emoji verification:
```bash
.venv/bin/python -c "
from src.ui.app import CarRecordAnalyzerApp
app = CarRecordAnalyzerApp()
app.withdraw()
app.update()
app.destroy()
print('UI lifecycle check passed.')
"
```
