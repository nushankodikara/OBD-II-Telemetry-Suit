# Car Record Analyzer - OBD-II Diagnostic Telemetry Suite

A mechanic-grade desktop workstation for analyzing exported vehicle scan records. Built with Python, CustomTkinter, and Matplotlib, this application ingests CSV trip logs, executes multi-stage data cleanup, synchronizes asynchronous sensor streams, and executes automotive data science workflows to compute city, highway, and combined fuel economy, gear operating envelopes, 2D efficiency heatmaps, thermal stability profiles, in-depth fuel trim recommendations, live GPS route telemetry, and physical/ML anomaly detection.

IMPORTANT NOTICE: This tool ingests only Car Scanner ELM OBD2 app's vertical export format (semicolon-delimited with SECONDS, PID, VALUE, UNITS, LATITUDE, LONGTITUDE).

Strict Project Requirement: No emojis are used in this codebase or documentation.

---

## Key Features

1. Car Scanner ELM OBD2 Format & Pre-Ingestion Data Cleanup
   - Exclusively engineered for the vertical export format produced by the Car Scanner ELM OBD2 application.
   - Multi-stage pre-ingestion cleaning pipeline:
     * Sensor bounds sanitization: eliminates corrupted electrical noise spikes (e.g. RPM > 9,000, Speed > 260 km/h, negative fuel consumption).
     * GPS teleportation jump filter: detects impossible positional leaps (> 2 km jump or implied velocity > 220 km/h) and reconstructs clean continuous coordinates.
     * Deduplication: discards redundant sequential PID polling artifacts.
     * Deceleration fuel cut-off (DFCO) conditioning: flags coasting injector shutoff spikes (> 60 km/L) to prevent calculation distortion.
     * Data quality audit card displaying raw rows count, retained valid records, filtered GPS jumps, and sanitized outliers.

2. Automotive Fuel Economy Telemetry
   - Instant computation of City, Highway, and Combined fuel economy.
   - Intelligent fallback displaying "-" whenever insufficient driving distance or speed coverage exists for a category (for example, trips without highway speeds).
   - Real-time unit conversions between km/L (native log format), L/100km, MPG (US), and MPG (UK).
   - Configurable speed thresholds via dedicated dialog (defaults: City <= 45 km/h, Highway >= 70 km/h).
   - Weighted moving distance-to-fuel integration that eliminates idle skew and deceleration fuel cut-off anomalies.

3. Live GPS Route Map & Spatial Telemetry Heatmap
   - Interactive OpenStreetMap (via TkinterMapView) rendering the actual recorded GPS route path.
   - Dynamic start and finish waypoints with anomaly markers pinned at exact geographical fault locations.
   - Spatial Telemetry Heatmap mode: renders high-resolution route traces color-coded by selected telemetry:
     * Fuel Economy (shows where fuel was consumed vs peak efficiency zones)
     * Vehicle Speed (highlights urban stop-and-go vs open highway)
     * Engine RPM (shows high rev acceleration corridors)
     * Engine Coolant Temperature
     * Total Fuel Trim (STFT + LTFT %)

4. In-Depth Fuel Trim Diagnostics (STFT & LTFT) & Repair Recommendations
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

5. Telemetry Anomaly Detection Center
   - Hybrid anomaly detection combining deterministic automotive engineering rules and multivariate Machine Learning:
     * Alternator undercharging / voltage drop (< 12.2V with engine running)
     * Voltage regulator spikes (> 15.2V)
     * Coolant temperature overheating (> 100 C)
     * Fuel trim surge anomalies (> +18% lean spike or < -18% rich spike)
     * Speed sensor dropout / drivetrain slip (0 km/h at high engine load and RPM)
     * Scikit-Learn Isolation Forest identifying subtle multivariate sensor state outliers.
   - Scrollable anomaly event register with severity badges ([CRITICAL], [WARNING], [INFO]), timestamps, observed values, expected ranges, and GPS coordinates.

6. Optimal RPM and Speed Operating Curve
   - Visualizes the vehicle speed versus engine RPM operating envelope across all sampled drive points.
   - Identifies median engine operating RPMs across discrete speed bands.
   - Detects transmission gear ratio lines (km/h per 1,000 RPM) to highlight shift profiles and cruising gears.

7. 2D Efficiency Heatmap & Cruising Sweet Spot
   - Generates a 2D surface of fuel economy across binned Speed (km/h) and RPM (rpm) coordinates.
   - Overlays the peak efficiency curve demonstrating the optimal RPM for any road speed.
   - Automatically identifies and highlights the global vehicle "Efficiency Sweet Spot" (speed and RPM yielding maximum cruising economy).

8. Engine Thermal and Cooling Profile
   - Plots engine coolant temperature over elapsed trip time for individual and combined sessions.
   - Visualizes the standard automotive thermostat operating band (82 C to 95 C) and triggers alerts if temperatures exceed 100 C.
   - Analyzes thermal response relative to calculated engine load.

9. Reporting and Data Export
   - Detailed trip comparison table displaying duration, distance, city/highway/combined fuel economy, peak speed, and peak temperature.
   - Export feature outputting comprehensive diagnostic reports in plain text or CSV format.

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

Upon launch, the application automatically loads sample records located in the `Records/` folder, executes data cleanup, analyzes all sessions, and renders the diagnostic telemetry cards and charts.

---

## Running Automated Tests

Execute the unit test suite with:

```bash
.venv/bin/python -m unittest discover -s tests
```
