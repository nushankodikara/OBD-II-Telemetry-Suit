# OBD-II Telemetry Suit

A mechanic-grade desktop diagnostic workstation for analyzing exported vehicle scan records. Built with Python, CustomTkinter, and Matplotlib, this application ingests CSV trip logs, executes multi-stage data cleanup, synchronizes asynchronous sensor streams, and executes automotive data science workflows to compute city, highway, and combined fuel economy, gear operating envelopes, 2D efficiency heatmaps, thermal stability profiles, in-depth fuel trim recommendations, hybrid battery cell diagnostics, automated plain-English vehicle intelligence, and physical/ML anomaly detection.

IMPORTANT NOTICE: This tool exclusively ingests the Car Scanner ELM OBD2 app's vertical export format (semicolon-delimited with SECONDS, PID, VALUE, UNITS, LATITUDE, LONGTITUDE).

Strict Project Requirement: Zero emojis are used across the entire codebase, UI, tests, and documentation.

---

## Key Features

1. Car Scanner ELM OBD2 Format & Pre-Ingestion Data Cleanup
   - Exclusively engineered for the vertical export format produced by the Car Scanner ELM OBD2 application.
   - Multi-stage pre-ingestion cleaning pipeline:
     * Sensor bounds sanitization: clamps physical sensor ranges (e.g. RPM 0-9,000, Speed 0-260 km/h, Coolant -40 to 140 C).
     * Deduplication: discards redundant sequential PID polling artifacts.
     * Deceleration fuel cut-off (DFCO) conditioning: flags coasting injector shutoff spikes (> 60 km/L) to prevent calculation distortion.
     * Data quality audit card displaying raw rows count, retained valid records, duplicate queries eliminated, and sanitized outliers.

2. Automotive Fuel Economy Telemetry
   - Instant computation of City, Highway, and Combined fuel economy.
   - Intelligent fallback displaying "-" whenever insufficient driving distance or speed coverage exists for a category (for example, trips without highway speeds).
   - Real-time unit conversions between km/L (native log format), L/100km, MPG (US), and MPG (UK).
   - Configurable speed thresholds (defaults: City <= 45 km/h, Highway >= 70 km/h).
   - Weighted moving distance-to-fuel integration that eliminates idle skew and deceleration fuel cut-off anomalies.

3. Dynamic Hybrid Powertrain & Battery Health Workstation
   - Dynamically active: The dedicated "Hybrid Battery & Powertrain" tab is hidden by default and only appears when analyzing records from a hybrid vehicle (HEV / PHEV).
   - Computes High Voltage (HV) battery State of Charge (SOC %) range, mean, and swing.
   - Monitors individual Battery Block Voltages (V01 to V14) and computes the critical Block Voltage Delta ($V_{\Delta} = V_{\text{max}} - V_{\text{min}}$).
   - Real-time cell health grading:
     * [OPTIMAL] Strong Balance ($V_{\Delta} < 0.20$ V / 200 mV)
     * [WARNING] Mild Imbalance ($0.20 \text{ V} \le V_{\Delta} < 0.40$ V)
     * [CRITICAL] Severe Degradation ($V_{\Delta} \ge 0.40$ V, risk of DTC P0A80)
   - High-voltage battery pack current (charge/discharge rates in Amperes), battery temperatures, and inverter/MG temperatures.
   - Pure electric propulsion ratio (EV Driving %) tracking time and distance executed with the internal combustion engine off.
   - Dynamic top metric card 6: Displays [HYBRID SOC] and block delta for HEVs, or [IDLE TIME %] for standard combustion vehicles.

4. Quick Vehicle Info for Everyday Drivers
   - Automated vehicle intelligence tool designed for non-technical vehicle owners and general users without requiring manual specification inputs.
   - Automatically identifies powertrain category: Hybrid Electric Vehicle (HEV) vs Conventional Fuel Vehicle (ICE).
   - Generates plain-English health summaries for the 12V auxiliary battery, cooling system, fuel efficiency rating, and powertrain condition.
   - Accessible at any time via the top toolbar button or the Vehicle & Settings menu.

5. Vehicle Profile, Settings & XML Session Persistence
   - Dedicated Vehicle Profile & Settings page and standalone modal dialog:
     * Automatically opens a standalone configuration window by default when importing records if vehicle profile settings are not yet configured.
     * Configure Vehicle Make, Model, and Year
     * Engine Type (Petrol, Diesel, Hybrid Petrol, Turbo Petrol, EV)
     * Engine Displacement (cc)
     * Transmission Type and Number of Gears / Ratios (e.g. 4-Speed Auto, 5-Speed Manual, 6-Speed Auto, etc.)
     * Accurately constrains the RPM vs Speed operating curve to the configured number of forward gears (e.g. 4-speed auto displays only gears 1 through 4).
     * Tyre Size (e.g. 185/65R15)
     * Fuel Tank Capacity (L) and Mechanic Notes
     * City and Highway Speed Thresholds
   - Clean XML persistence format (`OBDIITelemetrySuitSession` schema): saves vehicle profile, threshold settings, and exact file paths to imported scan records.
   - Save, Save As, and Open session workflows.
   - Startup state: starts clean with no data loaded on initial launch, or automatically restores the previous working state if `last_session.xml` is present.

6. Native Application Menu Bar & Software Updates
   - Full native menu bar replacing default Tkinter options:
     * File: New Session (Ctrl+N), Open Session XML (Ctrl+O), Save Session XML (Ctrl+S), Save Session As XML, Import Car Scanner CSV, Import Records Folder, Export Comprehensive Diagnostic Report, Exit.
     * Vehicle & Settings: Vehicle Profile & Settings, Quick Vehicle Info, Speed Thresholds, Fuel Economy Units.
     * Help: Check for Updates..., ELM OBD2 Format Guide, About OBD-II Telemetry Suit.
   - In-Software Update Checker: Queries GitHub Releases API in a background thread to check for new binary builds and directs users to download releases.
   - Versioning & Changelog: Version tracked via `simpleversion.json` (beta `0.x.x` pattern) with detailed revision history in `CHANGELOG.md`.

7. In-Depth Fuel Trim Diagnostics (STFT & LTFT) & Repair Recommendations
   - Diagnostic separation of fuel trim performance into 3 distinct automotive operating regimes:
     * Idle Zone (RPM < 1,000, Speed < 5 km/h, Load < 35%)
     * Cruising Zone (RPM 1,200 - 2,500, Speed > 25 km/h, Load 15 - 55%)
     * High Load / WOT Zone (Load > 60%)
   - Differential diagnosis engine identifying:
     * Intake Vacuum Leak (idle trim high positive, normalizing during cruise)
     * Weak Fuel Delivery / Clogged Injectors / Under-reporting MAF (positive trim across all zones)
     * Fuel Over-Delivery / Leaking Injector / Stuck Purge Valve (negative rich trim across all zones)
     * Optimal Closed-Loop Stoichiometric Control (+/- 7% ideal band)
   - Step-by-step diagnostic test procedures and likelihood scores designed for automotive technicians.

8. Telemetry Anomaly Detection Center
   - Hybrid anomaly detection combining deterministic automotive engineering rules and multivariate Machine Learning:
     * Alternator undercharging / voltage drop (< 12.2V with engine running)
     * Voltage regulator spikes (> 15.2V)
     * Coolant temperature overheating (> 100 C)
     * Fuel trim surge anomalies (> +18% lean spike or < -18% rich spike)
     * Speed sensor dropout / drivetrain slip (0 km/h at high engine load and RPM)
     * Scikit-Learn Isolation Forest identifying subtle multivariate sensor state outliers.
   - Scrollable anomaly event register with severity badges ([CRITICAL], [WARNING], [INFO]), timestamps, observed values, and expected ranges.

9. Optimal RPM Operating Curve & 2D Efficiency Heatmap
   - Visualizes vehicle speed versus engine RPM operating envelope across all sampled drive points.
   - Detects transmission gear ratio lines (km/h per 1,000 RPM) to highlight shift profiles and cruising gears.
   - Generates a 2D surface of fuel economy across binned Speed (km/h) and RPM (rpm) coordinates.
   - Automatically identifies and highlights the global vehicle "Efficiency Sweet Spot" (speed and RPM yielding maximum cruising economy).

10. Multi-Vehicle Datasets
    - Pre-loaded with 8 distinct vehicle datasets inside the `Records/` directory, spanning ICE passenger cars and Toyota Hybrid Synergy Drive (THS-II) vehicles.

---

## System Requirements and Installation

### Prerequisites
- macOS 12+ (Apple Silicon or Intel), Linux, or Windows.
- Python 3.10+ (Python 3.14 via Homebrew recommended on macOS for updated Tcl/Tk support).

### Virtual Environment Setup

```bash
# Clone or navigate to the project directory
cd /path/to/CarRecordAnalyzer

# Create virtual environment using your Python installation
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # macOS / Linux
# or .venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt
```

### Note on macOS Tcl/Tk
Apple's legacy system Python 3.9 has an outdated Tcl/Tk version incompatible with modern macOS windowing. If running on macOS, use Homebrew Python with `python-tk`:
```bash
brew install python@3.14 python-tk@3.14
/opt/homebrew/bin/python3.14 -m venv --clear .venv
.venv/bin/pip install -r requirements.txt
```

---

## Running the Application

To launch the desktop workstation:

```bash
.venv/bin/python main.py
```

- Initial Startup: Launches in a clean blank state. Use `File -> Import Records Folder` or `File -> Import Car Scanner CSV` to load records from `Records/`.
- Subsequent Startups: Automatically restores the previous session and vehicle profile if `last_session.xml` exists.
- Reset: Use `File -> New Session` or `Ctrl+N` to clear the workspace at any time.

---

## Running Automated Tests

Execute the unit test suite with:

```bash
.venv/bin/python -m unittest discover -s tests
```
