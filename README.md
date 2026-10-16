# Car Record Analyzer - OBD-II Diagnostic Telemetry Suite

A mechanic-grade desktop workstation for analyzing exported OBD-II vehicle scan records. Built with Python, CustomTkinter, and Matplotlib, this application ingests single or multiple CSV trip logs, synchronizes asynchronous sensor streams, and executes automotive data science workflows to compute city, highway, and combined fuel economy, gear operating envelopes, 2D efficiency heatmaps, thermal stability profiles, and sensor fault indicators.

Strict Project Requirement: No emojis are used in this codebase or documentation.

---

## Key Features

1. Multi-Record Ingestion & Session Management
   - Ingests one or more semicolon-delimited OBD-II scan files simultaneously.
   - Live file feed checklist allowing mechanics to toggle individual trips in and out of aggregate calculations.
   - Session metadata inspector reporting file duration, raw query count, peak speed, and operating profile.

2. Automotive Fuel Economy Telemetry
   - Instant computation of City, Highway, and Combined fuel economy.
   - Intelligent fallback displaying "-" whenever insufficient driving distance or speed coverage exists for a category (for example, trips without highway speeds).
   - Real-time unit conversions between km/L (native log format), L/100km, MPG (US), and MPG (UK).
   - Configurable speed thresholds via dedicated dialog (defaults: City <= 45 km/h, Highway >= 70 km/h).
   - Weighted moving distance-to-fuel integration that eliminates idle skew and deceleration fuel cut-off anomalies.

3. Optimal RPM and Speed Operating Curve
   - Visualizes the vehicle speed versus engine RPM operating envelope across all sampled drive points.
   - Identifies median engine operating RPMs across discrete speed bands.
   - Detects transmission gear ratio lines (km/h per 1,000 RPM) to highlight shift profiles and cruising gears.

4. 2D Efficiency Heatmap & Cruising Sweet Spot
   - Generates a 2D surface of fuel economy across binned Speed (km/h) and RPM (rpm) coordinates.
   - Overlays the peak efficiency curve demonstrating the optimal RPM for any road speed.
   - Automatically identifies and highlights the global vehicle "Efficiency Sweet Spot" (speed and RPM yielding maximum cruising economy).

5. Engine Thermal and Cooling Profile
   - Plots engine coolant temperature over elapsed trip time for individual and combined sessions.
   - Visualizes the standard automotive thermostat operating band (82 C to 95 C) and triggers alerts if temperatures exceed 100 C.
   - Analyzes thermal response relative to calculated engine load.

6. Mechanic Diagnostic Sensor Health Suite
   - Fuel Trim Analysis: Computes Short Term Fuel Trim (STFT) and Long Term Fuel Trim (LTFT) distributions against standard +/- 10% bounds to flag vacuum leaks or rich conditions.
   - Battery & Charging Health: Evaluates alternator charging voltage (13.5V to 14.8V normal range) and warns of low battery state or alternator failure.
   - Intake Manifold Pressure (MAP): Maps manifold absolute pressure against RPM to check idle vacuum (25-40 kPa) and boost conditions.

7. Reporting and Data Export
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

Upon launch, the application automatically loads sample records located in the `Records/` folder, analyzes all sessions, and renders the diagnostic telemetry cards and charts.

---

## Automotive Data Science Methodology

### Asynchronous PID Synchronization
Raw OBD-II diagnostic scanners poll PIDs sequentially. A single second of data may record vehicle speed at `t = 1.1s`, engine RPM at `t = 1.3s`, and fuel rate at `t = 1.6s`.
The ingestion engine (`src/data_loader.py`):
1. Normalizes all timestamps relative to trip start (`elapsed_seconds = SECONDS - t0`).
2. Bins queries into uniform 1.0-second intervals.
3. Builds an aligned time-grid using bounded linear interpolation for fast-changing sensors and forward-fill for slow-changing sensors (coolant temp, fuel trims).

### Fuel Economy Calculation Engine
Instantaneous fuel consumption readings often spike to extreme values during deceleration (when injectors shut off) or drop to zero at idle. To compute true physical fuel economy:
- City Segment: Sampled intervals where `1.0 km/h < speed <= city_threshold` (default 45 km/h).
- Highway Segment: Sampled intervals where `speed >= highway_threshold` (default 70 km/h).
- Combined Segment: All moving intervals where `speed > 1.0 km/h`.
- Integration Formula:
  $$\text{Economy (km/L)} = \frac{\sum (v_i \cdot \Delta t)}{\sum (\text{Rate}_i \cdot \Delta t)} = \frac{\text{Distance (km)}}{\text{Fuel Consumed (L)}}$$
- Fallback Condition: If distance on highway or city driving is less than 0.3 km, the metric safely displays `-`.

### Transmission Ratio Clustering
Discrete gear lines are derived from the ratio $R = \frac{\text{Speed (km/h)}}{\text{RPM}}$. Kernel density and histogram peak detection isolate discrete ratios corresponding to 1st, 2nd, 3rd, 4th, and 5th/overdrive gears.

---

## Project Structure

```
CarRecordAnalyzer/
├── main.py                     # Root entry point
├── requirements.txt            # Dependency definitions
├── README.md                   # Application overview and instructions
├── HANDOFF.md                  # Developer handoff and technical design
├── MEMORY.md                   # Architectural decisions and project context
├── AGENTS.md                   # AI agent rules and maintenance guidance
├── Records/                    # Sample OBD-II scan CSV records
│   ├── 2026-09-08 09-19-22.csv
│   ├── 2026-09-08 11-06-29.csv
│   ├── 2026-09-08 11-31-27.csv
│   ├── 2026-10-10 13-23-30.csv
│   ├── 2026-10-10 13-50-16.csv
│   ├── 2026-10-13 07-08-22.csv
│   ├── 2026-10-13 16-50-45.csv
│   └── 2026-10-13 17-13-03.csv
├── src/
│   ├── __init__.py
│   ├── data_loader.py          # CSV parsing, PID mapping, and time synchronization
│   ├── analyzer.py             # Automotive physics, curve fitting, and diagnostic health
│   └── ui/
│       ├── __init__.py
│       ├── app.py              # Main CustomTkinter application window
│       ├── theme.py            # Dark workshop styling constants
│       └── components/
│           ├── __init__.py
│           ├── metric_card.py  # Digital gauge telemetry card
│           ├── graph_canvas.py # Embedded dark Matplotlib canvas
│           └── record_list.py  # Multi-file record checklist panel
└── tests/
    ├── __init__.py
    └── test_analyzer.py        # Automated test suite
```

---

## Running Automated Tests

Execute the unit test suite with:

```bash
.venv/bin/python -m unittest discover -s tests
```

All tests execute synchronously in under 5 seconds.
