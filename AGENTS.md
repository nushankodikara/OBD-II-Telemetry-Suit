# Agent Instructions & Operating Rules - Car Record Analyzer

This file provides mandatory guidelines and constraints for any AI agent modifying or extending the Car Record Analyzer codebase.

---

## 1. Non-Negotiable System Directives

1. ZERO EMOJIS RULE
   - Do NOT use emojis anywhere in this project.
   - This applies without exception to:
     - Python source code and comments
     - UI widget labels, button texts, tooltips, and dialogs
     - Console print and logging messages
     - Test descriptions and assertions
     - Markdown documentation (README, HANDOFF, MEMORY, AGENTS, etc.)
     - Commit messages and diff annotations
   - If an indicator or status badge is needed, use plain text brackets such as `[NORMAL]`, `[ALERT]`, `[OPTIMAL]`, `[NO DATA]`, `[HWY+CITY]`, `[PASS]`, `[WARNING]`, `[CRITICAL]`, or `[FAULT]`.

2. Supported Log Export Format
   - This application exclusively supports the Car Scanner ELM OBD2 app's vertical export CSV format (semicolon-delimited with headers: `SECONDS`, `PID`, `VALUE`, `UNITS`, `LATITUDE`, `LONGTITUDE`).
   - Any extension to the data ingestion engine must preserve this specification and pass raw data through the `clean_raw_obd_data()` pipeline prior to ingestion.

3. Python Environment & Execution
   - Always run commands and tests using `.venv/bin/python` or `.venv/bin/pip`.
   - Do NOT invoke system `/usr/bin/python3` directly on macOS because it lacks working Tcl/Tk bindings.
   - The virtual environment is configured with Python 3.14 via Homebrew with `python-tk@3.14`.

4. Architectural Boundaries
   - Ingestion Layer (`src/data_loader.py`): Handles CSV file I/O, format validation, physical sensor cleaning, GPS jump sanitization, and time synchronization. Keep this layer UI-agnostic.
   - Analytics Layer (`src/analyzer.py`): Contains automotive physics, metric calculations, anomaly detection (rules and Isolation Forest), and diagnostic health logic. Keep this layer pure Python/NumPy/SciPy/scikit-learn with zero UI dependencies.
   - Presentation Layer (`src/ui/`): Contains CustomTkinter components, Matplotlib canvases, and `tkintermapview`. It should only call methods on `VehicleAnalyzer` and `ScanTrip` and never perform raw CSV file parsing or recalculate core physics algorithms directly.

---

## 2. Coding and Naming Standards

- Language: Python 3.10+ with modern typing annotations (`from typing import List, Dict, Optional, Tuple, Any`).
- Classes: PascalCase (e.g., `VehicleAnalyzer`, `ScanTrip`, `MetricCard`, `GraphCanvas`).
- Functions & Variables: snake_case (e.g., `calculate_fuel_economy`, `clean_raw_obd_data`, `analyze_fuel_trims_in_depth`).
- Constants: UPPER_SNAKE_CASE (e.g., `PID_MAP`, `SENSOR_BOUNDS`, `BG_DARKEST`, `ACCENT_AMBER`).
- Styling: PEP 8 compliant. Use descriptive docstrings adhering to the zero emoji directive.

---

## 3. Telemetry and Automotive Math Rules

1. Fallback for Insufficient Data
   - When a trip or selection lacks sufficient data for highway or city driving (for instance, distance < 0.3 km or fuel < 0.01 L), the method MUST return `None` for that category.
   - The UI MUST format `None` values strictly as `"-"`. Do NOT display `0.00` or `NaN`.

2. Physical Numerical Integration
   - Fuel economy MUST always be calculated as:
     $$\text{FE} = \frac{\sum (v_i \cdot \Delta t)}{\sum (\text{Rate}_i \cdot \Delta t)} = \frac{\text{Distance}}{\text{Fuel}}$$
   - Never take an arithmetic mean of instantaneous `km/L` due to deceleration fuel cut-off skew.

3. Unit Conversions
   - Native storage is metric (`km/L`, `km/h`, `L/h`, `C`, `kPa`, `bar`).
   - Any unit conversion must use standard physical constants:
     - $1 \text{ km/L} = 2.35214583 \text{ MPG (US)}$
     - $1 \text{ km/L} = 2.82480936 \text{ MPG (UK)}$
     - $\text{L/100km} = \frac{100}{\text{km/L}}$

---

## 4. Verification Workflow

Before reporting completion on any code modification, agents MUST:

1. Run the automated test suite:
   ```bash
   .venv/bin/python -m unittest discover -s tests
   ```
   Ensure all tests pass with zero failures or errors.

2. Verify UI instantiation and lifecycle:
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

3. Perform an automated emoji audit:
   ```bash
   .venv/bin/python -c "
   import os
   for root, _, files in os.walk('.'):
       if '.git' in root or '.venv' in root:
           continue
       for f in files:
           if f.endswith(('.py', '.md', '.txt', '.json')):
               p = os.path.join(root, f)
               with open(p, 'r', encoding='utf-8', errors='ignore') as fp:
                   txt = fp.read()
                   for ch in txt:
                       if ord(ch) > 127000:
                           raise ValueError(f'Emoji detected in {p}: {ch}')
   print('Zero emoji rule verified across all repository files.')
   "
   ```
