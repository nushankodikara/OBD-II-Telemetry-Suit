# Project Memory & Architectural Decisions - Car Record Analyzer

This document preserves the institutional memory, technical decisions, automotive domain knowledge, and data findings established during the creation and extension of the Car Record Analyzer project.

IMPORTANT NOTICE: This tool ingests exclusively Car Scanner ELM OBD2 app's vertical export format.

Strict Project Requirement: No emojis are used in this codebase or documentation.

---

## 1. Context & User Objectives

- Objective: Build a desktop diagnostic application with a mechanic-focused GUI (using CustomTkinter) that ingests 1 or more exported Car Scanner ELM OBD2 car scan records, cleans and analyzes the telemetry, and provides:
  - Pre-ingestion data cleanup and audit reporting.
  - Average fuel economy (Highway, City, Combined) with "-" fallback for missing data.
  - Optimal RPM and Speed operating curve.
  - Optimal Fuel Economy RPM-Speed curve and 2D efficiency heatmap.
  - Engine coolant temperature profile with thermostat operating bands.
  - In-depth STFT and LTFT fuel trim diagnostics with mechanic repair recommendations.
  - Live GPS route map with OpenStreetMap tiles and spatial telemetry heatmaps.
  - Physical and Machine Learning (Isolation Forest) anomaly detection.
  - Multi-file support with live checklist selection.
  - Required project documents: `README.md`, `HANDOFF.md`, `MEMORY.md`, `AGENTS.md`.
  - Zero emojis allowed in any part of the project.

---

## 2. Key Architectural Decisions (ADRs)

### ADR 001: GUI Framework Selection - CustomTkinter
- Decision: Selected `customtkinter` with embedded `matplotlib` figures and `tkintermapview`.
- Rationale: Provides a native dark workshop appearance resembling professional automotive diagnostic scan tools (Autel MaxiSys, Snap-on, Bosch KTS) while running on pure Python and Tkinter primitives.

### ADR 002: Python Runtime Selection on macOS
- Decision: Built the virtual environment using Homebrew Python 3.14 (`/opt/homebrew/bin/python3.14`) and installed `python-tk@3.14`.
- Rationale: Homebrew Python uses modern Tcl/Tk 9.1 with updated macOS Cocoa integration, ensuring zero crashes, smooth window lifecycle, and high-DPI retina rendering.

### ADR 003: Pre-Ingestion Data Cleanup Pipeline
- Decision: Implemented `clean_raw_obd_data()` in `src/data_loader.py` that validates Car Scanner ELM OBD2 format, strips syntax artifacts, filters physical sensor outliers, removes sequential duplicate queries, conditions DFCO coasting spikes, and purges GPS teleportation glitches.
- Rationale: Raw mobile OBD-II exports frequently contain connection drops, sensor glitch spikes, and GPS jumps from satellite acquisition delays. Cleaning prior to ingestion guarantees pristine telemetry and reliable statistics.

### ADR 004: Haversine GPS Jump Filtering
- Decision: Integrated Haversine distance tracking between consecutive GPS coordinates to detect and drop teleportation leaps (> 2 km jump or implied speed > 220 km/h).
- Rationale: In mobile phone OBD logs, GPS chipsets frequently log erroneous coordinates (for example, jumping 900 km away before satellite lock). Filtering these maintains clean route rendering and prevents false spatial telemetry mapping.

### ADR 005: Zone-Based STFT and LTFT Fuel Trim Analysis
- Decision: Partitioned driving records into Idle, Cruising, and High Load regimes to analyze differential trim behavior.
- Rationale: Automotive fuel trim diagnosis relies on regime comparison: vacuum leaks create high positive trim exclusively at idle that normalizes during cruise, whereas fuel pump/injector delivery deficits remain lean across all operating speeds.

### ADR 006: Hybrid Anomaly Detection (Physical Rules + Isolation Forest)
- Decision: Combined deterministic threshold checks (alternator undercharging, coolant overheat, fuel trim surge, VSS dropouts) with an `sklearn.ensemble.IsolationForest` multivariate outlier detector.
- Rationale: Hard rules catch known critical automotive failure modes, while the unsupervised ML model catches subtle multivariate sensor divergences that individually stay within normal bounds.

### ADR 007: Dual-Mode GPS Mapping (`tkintermapview` & Matplotlib)
- Decision: Integrated `tkintermapview` for interactive OpenStreetMap tile navigation and overlaid a Matplotlib spatial scatter mode for high-resolution continuous telemetry gradient coloring.
- Rationale: Mechanics can visually inspect the actual geographical route driven while observing where fuel was consumed or where electrical and sensor anomalies occurred.

---

## 3. Dataset Characteristics (Records Folder)

Analysis of the 8 sample files in `Records/`:
1. `2026-09-08 09-19-22.csv`:
   - Duration: 19.9 minutes (1,193 s)
   - Max Speed: 50.0 km/h (City only, no highway data; highway FE evaluates to `-`)
   - GPS Jumps Cleaned: 408 points
2. `2026-09-08 11-06-29.csv`:
   - Duration: 15.8 minutes (950 s)
   - Max Speed: 48.0 km/h (City only)
   - GPS Jumps Cleaned: 185 points
3. `2026-09-08 11-31-27.csv`:
   - Duration: 5.1 minutes (308 s)
   - Max Speed: 42.0 km/h (City only)
   - GPS Jumps Cleaned: 191 points
4. `2026-10-10 13-23-30.csv`:
   - Duration: 18.5 minutes (1,109 s)
   - Max Speed: 65.0 km/h
   - GPS Jumps Cleaned: 1,401 points
5. `2026-10-10 13-50-16.csv`:
   - Duration: 13.1 minutes (785 s)
   - Max Speed: 57.0 km/h
   - GPS Jumps Cleaned: 405 points
6. `2026-10-13 07-08-22.csv`:
   - Duration: 51.9 minutes (3,115 s)
   - Max Speed: 94.0 km/h (Substantial highway driving: City FE ~11.6 km/L, Highway FE ~16.7 km/L, Combined ~12.5 km/L)
7. `2026-10-13 16-50-45.csv`:
   - Duration: 9.3 minutes (555 s)
   - Max Speed: 35.0 km/h (City only)
8. `2026-10-13 17-13-03.csv`:
   - Duration: 87.8 minutes (5,266 s)
   - Max Speed: 56.0 km/h (Long congested urban trip)
