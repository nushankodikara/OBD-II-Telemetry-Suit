# Developer Handoff Documentation - OBD-II Telemetry Suit

This document provides developer-level architecture, module contracts, data flow specifications, and debugging procedures for the OBD-II Telemetry Suit desktop workstation.

IMPORTANT NOTICE: This tool ingests exclusively the Car Scanner ELM OBD2 app's vertical export format (semicolon-delimited with SECONDS, PID, VALUE, UNITS, LATITUDE, LONGTITUDE).

Strict Project Requirement: Zero emojis are used across the entire codebase, UI, tests, and documentation.

---

## 1. System Architecture Overview

The system is organized into a modular four-tier architecture:
1. Ingestion & Pre-Cleanup Tier (`src/data_loader.py`): Validates the Car Scanner ELM OBD2 schema, applies sensor boundary filtering, purges duplicate sequential queries, conditions DFCO coasting spikes, parses hybrid telemetry, and synchronizes asynchronous sensor streams onto a uniform 1.0-second time grid.
2. Analytics & Automotive Physics Tier (`src/analyzer.py`): Pure Python and NumPy/SciPy/scikit-learn engine computing fuel economy, optimal RPM operating curves, 2D efficiency surfaces, thermal stability profiles, deep STFT/LTFT zone analysis with repair recommendations, hybrid battery cell balance diagnostics, automated vehicle intelligence, and physical/multivariate Isolation Forest anomaly detection.
3. Session & Persistence Tier (`src/session_manager.py`): XML serialization and deserialization engine for vehicle profiles (make, model, engine, capacity, tyre size, tank, notes), speed thresholds, and loaded scan file paths.
4. Presentation Tier (`src/ui/`): CustomTkinter dark-mode desktop workstation featuring embedded Matplotlib figures, native Tkinter menu bar, dynamic hybrid battery metrics, and quick vehicle information dialogs.

```
+-------------------------------------------------------------------+
|                        PRESENTATION TIER                          |
|  CarRecordAnalyzerApp (src/ui/app.py)                             |
|  ├── Native Tkinter Menu Bar (File, Vehicle & Settings, Help)     |
|  ├── Top Metric Cards (Dynamic 6th Card: Hybrid SOC vs Idle %)    |
|  ├── RecordListPanel (src/ui/components/record_list.py)           |
|  ├── GraphCanvas (src/ui/components/graph_canvas.py)              |
|  ├── Quick Vehicle Info Dialog (Everyday Driver Diagnostics)     |
|  └── Vehicle Profile & Settings Workstation                       |
+---------------------------------+---------------------------------+
                                  |
         +------------------------+------------------------+
         |                                                 |
         v                                                 v
+----------------------------------+     +----------------------------------+
|     ANALYTICS & ANOMALY TIER     |     |   SESSION & PERSISTENCE TIER     |
|  VehicleAnalyzer                 |     |  session_manager.py              |
|  (src/analyzer.py)               |     |  ├── VehicleProfile dataclass    |
|  ├── calculate_fuel_economy()    |     |  ├── save_session_to_xml()       |
|  ├── analyze_hybrid_powertrain() |     |  ├── load_session_from_xml()     |
|  ├── auto_detect_vehicle_info()  |     |  ├── save_last_session()         |
|  ├── analyze_fuel_trims_in_depth |     |  └── load_last_session()         |
|  ├── compute_optimal_rpm_curve() |     +----------------------------------+
|  ├── compute_efficiency_map()    |
|  ├── analyze_coolant_temp()      |
|  └── detect_anomalies()          |
+-----------------+----------------+
                  |
                  v
+-------------------------------------------------------------------+
|                   INGESTION & CLEANUP TIER                        |
|  ScanTrip & clean_raw_obd_data (src/data_loader.py)               |
|  ├── Car Scanner ELM OBD2 vertical export format validator        |
|  ├── SENSOR_BOUNDS physical range cleaner                         |
|  ├── Duplicate PID polling deduplicator                           |
|  ├── Hybrid telemetry & block voltage parser (V01-V14, SOC, MG)   |
|  ├── Asynchronous PID time synchronization (1.0s grid)            |
|  └── DataCleanupReport audit generation                           |
+-------------------------------------------------------------------+
```

---

## 2. Module Specifications

### 2.1 Ingestion & Cleanup Engine (`src/data_loader.py`)

- `PID_MAP`: Canonical mapping from Car Scanner ELM OBD2 PID strings to standard internal identifiers, including hybrid telemetry (State of Charge, battery current, block voltages V01-V14, battery/inverter temperatures, MG1/MG2 RPM and torque).
- `SENSOR_BOUNDS`: Physical operational boundaries for clamping corrupted telemetry readings.
- `DataCleanupReport`: Audit dataclass tracking raw lines, retained records, dropped records, sensor outliers cleaned, duplicate queries dropped, and DFCO events conditioned.
- `clean_raw_obd_data(raw_df: pd.DataFrame) -> Tuple[pd.DataFrame, DataCleanupReport]`:
  - Verifies presence of required columns `SECONDS`, `PID`, `VALUE`.
  - Removes trailing semicolon artifacts.
  - Drops rows with null timestamps or non-numeric sensor values.
  - Clamps out-of-bounds sensor values to physical limits.
  - Drops duplicate sequential queries.
- `parse_obd_csv(file_path: str, grid_step_seconds: float = 1.0) -> Optional[ScanTrip]`:
  - Executes `clean_raw_obd_data()`.
  - Identifies hybrid vehicle telemetry automatically.
  - Aligns telemetry onto a contiguous 1.0s grid using linear interpolation.
  - Encapsulates results in `ScanTrip`.
- `load_all_records(directory_path: str) -> List[ScanTrip]`:
  - Recursively finds and parses all CSV files across directories and subdirectories, deduplicating paths.

### 2.2 Analytics & Automotive Physics Engine (`src/analyzer.py`)

- `HybridBatteryReport`: Stores high voltage battery metrics: SOC mean/min/max, current, individual block voltages (V01-V14), block voltage delta $V_{\Delta}$, battery health status, temperatures, and EV electric driving percentage.
- `AutoDetectedVehicleInfo`: Plain-English diagnostics for general users: vehicle class (HEV vs ICE), 12V battery health, thermal condition, fuel efficiency rating, fuel trim status, active sensors count, and bulleted takeaways.
- `VehicleAnalyzer.analyze_hybrid_powertrain(trips: List[ScanTrip]) -> HybridBatteryReport`:
  - Calculates cell block delta $V_{\Delta} = V_{\text{max}} - V_{\text{min}}$.
  - Assigns health status: `[OPTIMAL]` (< 0.20V), `[WARNING]` (0.20V - 0.40V), or `[CRITICAL]` (>= 0.40V).
  - Determines EV driving mode ratio where moving speed > 1 km/h with engine off or fuel rate <= 0.05 L/h.
- `VehicleAnalyzer.auto_detect_vehicle_info(trips: List[ScanTrip]) -> AutoDetectedVehicleInfo`:
  - Evaluates telemetry holistically without requiring user input.
- `VehicleAnalyzer.analyze_fuel_trims_in_depth(trips: List[ScanTrip]) -> FuelTrimDiagnostic`:
  - Evaluates differential trim behavior across Idle, Cruise, and High Load regimes.
- `VehicleAnalyzer.detect_anomalies(trips: List[ScanTrip]) -> List[TelemetryAnomaly]`:
  - Detects threshold violations and multivariate Isolation Forest anomalies.

### 2.3 Session & Persistence Manager (`src/session_manager.py`)

- `VehicleProfile`: Dataclass containing `make`, `model`, `year`, `engine_type`, `displacement_cc`, `transmission`, `gears`, `tyre_size`, `fuel_tank_l`, and `notes`. Exposes `is_configured` (boolean) and `forward_gears` (int) properties.
- `save_session_to_xml(file_path, profile, city_threshold, highway_threshold, unit, data_file_paths)`:
  - Produces clean XML adhering to the `OBDIITelemetrySuitSession` schema.
- `load_session_from_xml(file_path)`:
  - Parses XML and reconstructs profile, settings, and file paths.
- `save_last_session()` & `load_last_session()`:
  - Automatically manages `last_session.xml` for seamless state restoration between runs.

### 2.4 Versioning & Software Updates Engine (`src/version.py`)

- `simpleversion.json`: Root JSON file tracking semver releases (e.g., `0.2.0-beta`).
- `parse_semver(v_str: str) -> Tuple[int, int, int, str]`: Robust semver parser handling beta suffixes and build metadata.
- `is_version_newer(remote_v: str, local_v: str) -> bool`: Safe semantic version comparison.
- `get_app_version() -> str`: Reads `simpleversion.json` or falls back to internal default.
- `check_for_updates() -> Optional[Dict[str, Any]]`: Queries the GitHub Releases API (`repos/nushan/CarRecordAnalyzer/releases/latest`) with 4-second timeout to fetch latest tag, release notes, and download links.

### 2.5 Presentation Tier (`src/ui/`)

- `src/ui/app.py`:
  - Workstations:
    1. *Efficiency & Sweet Spot*: 2D heatmap and economy vs. speed scatter.
    2. *RPM & Speed Curves*: Speed vs. RPM scatter, gear lines constrained to `profile.forward_gears`, and median curve.
    3. *Thermal Profile*: Coolant temperature timeline and load correlation.
    4. *Fuel Trim Diagnostics*: Operating zone comparison, diagnostic banner, and action plan.
    5. *Hybrid Battery & Powertrain*: Dynamically added/removed; active ONLY when hybrid data is present; displays block voltage bar chart, SOC timeline, cell delta, and EV driving ratio.
    6. *Anomaly Detection*: Scrollable register of detected anomalies with severity badges and timestamps.
    7. *Data Cleanup & Sessions*: Pre-ingestion audit card, trip comparison table, and Text/CSV exporter.
    8. *Vehicle Profile & Settings*: Inline editor for vehicle parameters and thresholds.
  - Dynamic Hybrid Tab Visibility: Initialized without the hybrid tab. When trips are ingested, `_update_hybrid_tab_visibility(has_hybrid)` attaches or detaches the tab from `CTkTabview`. Top metric card 6 dynamically toggles between `[HYBRID SOC]` and `[IDLE TIME %]`.
  - Automatic Settings Prompt: When importing records while `not profile.is_configured`, automatically opens `VehicleSettingsDialog` so data is analyzed with accurate transmission, displacement, and speed thresholds in mind.
- `src/ui/components/settings_dialog.py`:
  - `VehicleSettingsDialog`: Standalone modal dialog to view and edit vehicle specs, gear configuration, tyre sizes, fuel tank capacity, speed thresholds, and distance/consumption units. Provides "Apply & Analyze", "Save to XML...", and "Skip".
  - `SoftwareUpdateDialog`: Modal dialog displaying remote version, release date, changelog release notes, and a direct "Download Release" button that launches the default web browser.

---

## 3. CI/CD & Automated Release Workflows

The repository uses GitHub Actions (`.github/workflows/release.yml`) for automated testing and multi-platform binary compilation:
- Triggers: Automated push/PR on `main`, release tags (`v*`), or manual `workflow_dispatch`.
- Test & Audit Stage: Runs on Ubuntu, executes unit test suite, and performs the mandatory repository-wide zero-emoji audit.
- Matrix Build Stage: Compiles standalone binaries with PyInstaller with pip dependency caching:
  - macOS (Apple Silicon `macos-14`): Produces `OBD-II-Telemetry-Suit-macos.zip`.
  - Linux (`ubuntu-latest`): Produces `OBD-II-Telemetry-Suit-linux.tar.gz`.
  - Windows (`windows-latest`): Produces `OBD-II-Telemetry-Suit-windows.zip`.
- Automated Release Stage: Uploads built distribution archives to GitHub Releases using `softprops/action-gh-release@v2`.

---

## 4. Verification Workflow

Run the test suite:
```bash
.venv/bin/python -m unittest discover -s tests
```

Verify UI lifecycle:
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

Verify the zero emoji directive:
```bash
.venv/bin/python -c "
import os
for root, _, files in os.walk('.'):
    if '.git' in root or '.venv' in root:
        continue
    for f in files:
        if f.endswith(('.py', '.md', '.txt', '.json', '.yml')):
            p = os.path.join(root, f)
            with open(p, 'r', encoding='utf-8', errors='ignore') as fp:
                txt = fp.read()
                for ch in txt:
                    if ord(ch) > 127000:
                        raise ValueError(f'Emoji detected in {p}: {ch}')
print('Zero emoji rule verified across all repository files.')
"
```
