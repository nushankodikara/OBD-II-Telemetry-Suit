# Project Memory & Architectural Decisions - OBD-II Telemetry Suit

This document preserves institutional memory, technical decisions, automotive domain knowledge, and data findings established during the development and evolution of the OBD-II Telemetry Suit.

IMPORTANT NOTICE: This tool ingests exclusively the Car Scanner ELM OBD2 app's vertical export format (semicolon-delimited with SECONDS, PID, VALUE, UNITS, LATITUDE, LONGTITUDE).

Strict Project Requirement: Zero emojis are used across the entire codebase, UI, tests, and documentation.

---

## 1. Context & User Objectives

- Objective: Build a desktop diagnostic application with a mechanic-focused GUI (using CustomTkinter) that ingests 1 or more exported Car Scanner ELM OBD2 car scan records, cleans and analyzes the telemetry, and provides:
  - Pre-ingestion data cleanup and audit reporting.
  - Average fuel economy (Highway, City, Combined) with "-" fallback for missing data.
  - Optimal RPM and Speed operating curve.
  - Optimal Fuel Economy RPM-Speed curve and 2D efficiency heatmap.
  - Engine coolant temperature profile with thermostat operating bands.
  - In-depth STFT and LTFT fuel trim diagnostics with mechanic repair recommendations.
  - Hybrid vehicle battery health, block voltage delta monitoring, and EV driving ratio.
  - Automated vehicle intelligence (Quick Vehicle Info) for non-technical users.
  - Vehicle Profile & Settings page with XML session saving and loading.
  - Blank startup state on initial launch and automatic previous session restoration.
  - Native application menu bar with File, Vehicle & Settings, and Help cascades.
  - Multi-file support with live checklist selection.
  - Support for 8 diverse vehicle datasets in the `Records/` directory.
  - Required project documents: `README.md`, `HANDOFF.md`, `MEMORY.md`, `AGENTS.md`.
  - Zero emojis allowed in any part of the project.

---

## 2. Key Architectural Decisions (ADRs)

### ADR 001: GUI Framework Selection - CustomTkinter
- Decision: Selected `customtkinter` with embedded `matplotlib` figures.
- Rationale: Provides a native dark workshop appearance resembling professional automotive diagnostic scan tools (Autel MaxiSys, Snap-on, Bosch KTS) while running on pure Python and Tkinter primitives.

### ADR 002: Python Runtime Selection on macOS
- Decision: Virtual environment built with Homebrew Python 3.14 (`/opt/homebrew/bin/python3.14`) and `python-tk@3.14`.
- Rationale: Modern Tcl/Tk 9.1 integration on macOS prevents crashes associated with Apple's legacy Python 3.9 and ensures crisp Retina rendering.

### ADR 003: Pre-Ingestion Data Cleanup Pipeline
- Decision: Implemented `clean_raw_obd_data()` in `src/data_loader.py` that validates Car Scanner ELM OBD2 format, strips syntax artifacts, filters physical sensor outliers, removes sequential duplicate queries, and conditions DFCO coasting spikes.
- Rationale: Raw mobile OBD-II exports frequently contain connection drops, sensor glitch spikes, and polling latency. Pre-cleaning guarantees pristine telemetry and reliable statistics.

### ADR 004: Removal of GPS Map
- Decision: Removed the GPS map and `tkintermapview` dependency completely.
- Rationale: User confirmed that spatial mapping was not useful for their diagnostic workflows. Removing it eliminated network map tile loading overhead, reduced window clutter, and focused the application on automotive powertrain diagnostics.

### ADR 005: Zone-Based STFT and LTFT Fuel Trim Analysis
- Decision: Partitioned driving records into Idle, Cruising, and High Load regimes to analyze differential trim behavior.
- Rationale: Vacuum leaks create high positive trim exclusively at idle that normalizes during cruise, whereas fuel pump/injector delivery deficits remain lean across all operating speeds.

### ADR 006: Hybrid Anomaly Detection (Physical Rules + Isolation Forest)
- Decision: Combined deterministic threshold checks with an `sklearn.ensemble.IsolationForest` multivariate outlier detector.
- Rationale: Hard rules catch known critical automotive failure modes, while the unsupervised ML model catches subtle multivariate sensor divergences that individually stay within normal bounds.

### ADR 007: Renaming to "OBD-II Telemetry Suit"
- Decision: Renamed the application and all corresponding headers, window titles, and menus to "OBD-II Telemetry Suit".
- Rationale: Reflects the full telemetry, hybrid, and diagnostic scope of the desktop tool beyond simple record viewing.

### ADR 008: XML Session & Vehicle Profile Persistence
- Decision: Implemented XML serialization and deserialization (`src/session_manager.py`) storing `VehicleProfile` (make, model, year, engine, capacity, transmission, gears, tyre size, tank, notes), speed thresholds, and loaded scan file paths.
- Rationale: Standard XML format allows interoperability, transparent inspection, and easy archiving of complete vehicle diagnostic sessions.

### ADR 009: Hybrid Battery Health & Block Voltage Diagnostics
- Decision: Implemented `analyze_hybrid_powertrain()` in `src/analyzer.py` supporting Toyota / Lexus THS-II and general HEVs.
- Rationale: Tracks High Voltage battery State of Charge (SOC %), monitors individual block voltages V01-V14, filters non-plausible voltage channels, and computes the critical Block Voltage Delta ($V_{\Delta} = V_{\text{max}} - V_{\text{min}}$). Grades battery cell balance into `[OPTIMAL]` (< 0.20V), `[WARNING]` (0.20V - 0.40V), and `[CRITICAL]` (>= 0.40V). Also tracks electric propulsion ratio (EV Driving %).

### ADR 010: Quick Vehicle Info for Everyday Drivers
- Decision: Added `auto_detect_vehicle_info()` and a quick dialog accessible from the top toolbar and menu.
- Rationale: General users or mechanics performing quick triage can assess vehicle class (HEV vs ICE), 12V battery health, thermal condition, and efficiency without having to manually input vehicle specifications.

### ADR 011: Startup State Machine (Blank vs Last Session)
- Decision: If no previous session file (`last_session.xml`) exists, the application boots into a clean blank state. When a session was previously saved, it automatically restores the vehicle profile, thresholds, and scan records on startup.
- Rationale: Prevents unwanted automatic loading of old data on fresh installations while preserving session continuity for daily use.

### ADR 012: Git History Purge of Telemetry Records
- Decision: Purged `Records/` and historical CSV files across all git commits using `git filter-branch --tree-filter`, ran `git reflog expire` and `git gc --prune=now`, and added `Records/` and `last_session.xml` to `.gitignore`.
- Rationale: Proprietary vehicle scan records must never be pushed to public or remote GitHub repositories. The data files remain accessible locally in the developer's working tree for testing.

### ADR 013: Dynamic Hybrid Workstation Tab Visibility
- Decision: "Hybrid Battery & Powertrain" workstation tab is excluded at initialization and only added to `CTkTabview` when the active dataset contains hybrid telemetry (e.g. `is_hybrid == True`). If non-hybrid records are loaded, the tab is removed. Metric card 6 dynamically swaps between `[HYBRID SOC]` and `[IDLE TIME %]`.
- Rationale: Prevents confusion and cluttered UI when analyzing standard internal combustion engine vehicles.

### ADR 014: Transmission Forward Gear Constraint on RPM-Speed Curve
- Decision: Constrained prominent gear slope detection in `compute_optimal_rpm_speed_curve()` to at most `max_gears` (parsed from `VehicleProfile.forward_gears`).
- Rationale: Eliminates phantom 5th/6th gear lines caused by torque converter slip and deceleration spikes when analyzing 4-speed automatic transmissions.

### ADR 015: Standalone Modal Settings Window & Pre-Analysis Trigger
- Decision: Created `VehicleSettingsDialog` as a standalone modal dialog. When importing records and `not profile.is_configured`, this modal automatically appears so users can confirm engine capacity, transmission gears, and speed thresholds before analysis runs.
- Rationale: Streamlines the mechanic workflow, ensuring optimal gear curves and fuel economy partitions match the actual vehicle hardware.

### ADR 016: Multi-Platform GitHub Binary Releases with Caching & In-App Updates
- Decision: Created `.github/workflows/release.yml` with pip dependency caching and matrix PyInstaller builds producing macOS zip, Linux tar.gz, and Windows zip release artifacts. Implemented `src/version.py` tracking `simpleversion.json` (`0.x.x` beta pattern) and an in-software update checker under `Help -> Check for Updates...`.
- Rationale: Provides seamless cross-platform binary distributions for end users without Python installations, and keeps users informed of updates.

---

## 3. Dataset Characteristics (Local Records Subdirectories)

NOTE: The `Records/` directory is permanently ignored in `.gitignore` and purged from git history. The local dataset includes 8 distinct vehicle datasets:
1. `Records/exported_records/`: 3 CSV trip logs from a petrol passenger car.
2. `Records/exported_records (1)/`: 2 CSV trip logs.
3. `Records/exported_records (2)/`: Toyota Aqua / Prius c Hybrid (1NZ-FXE 1.5L Atkinson cycle + THS-II). Contains 54+ hybrid PIDs including State of Charge (SOC ~55-65%), battery current, 10 active battery blocks (V01-V10 averaging ~16.38V per block with low delta < 100 mV), inverter temps, and MG1/MG2 RPM.
4. `Records/exported_records (3)/`: Additional vehicle scan log.
5. `Records/exported_records (4)/`: Additional vehicle scan log.
6. `Records/exported_records (5)/`: 3 CSV trip logs from an ICE vehicle.
7. `Records/exported_records (6)/`: 8 CSV trip logs with extensive urban and highway driving.
8. `Records/exported_records 2/`: 2 CSV trip logs.

