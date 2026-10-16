# Project Memory & Architectural Decisions - Car Record Analyzer

This document preserves the institutional memory, technical decisions, automotive domain knowledge, and data findings established during the creation of the Car Record Analyzer project.

Strict Project Requirement: No emojis are used in this codebase or documentation.

---

## 1. Context & User Objectives

- Objective: Build a desktop diagnostic application with a mechanic-focused GUI (using Tkinter/CustomTkinter) that ingests 1 or more exported OBD-II car scan records, analyzes the telemetry using automotive data science, and outputs:
  - Average fuel economy (Highway, City, Combined). If insufficient data is present, displays `-`.
  - Optimal RPM and Speed operating curve.
  - Optimal Fuel Economy RPM-Speed curve and 2D efficiency heatmap.
  - Engine coolant temperature profile with thermostat operating bands.
  - Mechanic diagnostic health suite (fuel trims, battery/alternator voltage, manifold vacuum).
  - Multi-file support with live checklist selection.
  - Required project documents: `README.md`, `HANDOFF.md`, `MEMORY.md`, `AGENTS.md`.
  - Zero emojis allowed in any part of the project.

---

## 2. Key Architectural Decisions (ADRs)

### ADR 001: GUI Framework Selection - CustomTkinter
- Context: The user requested a "UI like tkinter" with a mechanic-focused aesthetic familiar to workshop technicians.
- Decision: Selected `customtkinter` with embedded `matplotlib` figures.
- Rationale: Standard Tkinter widgets appear dated and low-contrast. CustomTkinter provides a native dark workshop appearance resembling professional automotive diagnostic scan tools (Autel MaxiSys, Snap-on, Bosch KTS) while running on pure Python and Tkinter primitives.

### ADR 002: Python Runtime Selection on macOS
- Context: Apple's system Python 3.9 (`/usr/bin/python3`) bundled on macOS Sequoia has a known Cocoa version mismatch inside its outdated Tcl/Tk build (`macOS 26 or later required, have instead 16 !`), causing Tkinter processes to abort.
- Decision: Built the virtual environment using Homebrew Python 3.14 (`/opt/homebrew/bin/python3.14`) and installed `python-tk@3.14`.
- Rationale: Homebrew Python uses modern Tcl/Tk 9.1 with updated macOS Cocoa integration, ensuring zero crashes, smooth window lifecycle, and high-DPI retina rendering.

### ADR 003: Time-Grid Synchronization for Asynchronous OBD PIDs
- Context: OBD-II scanners query PIDs sequentially in an event stream. Each row in the CSV contains a single PID at its own floating-point timestamp.
- Decision: Implemented a 1.0-second continuous grid synchronization in `src/data_loader.py` that pivots raw records, reindexes to a uniform time axis, and applies bounded linear interpolation for fast signals (speed, RPM, throttle) and forward-fill for slow signals (coolant temp, battery voltage, trims).
- Rationale: True vehicle performance analysis requires cross-sensor correlation (for example, instantaneous fuel rate evaluated at the exact same second as vehicle speed). Without time-alignment, mathematical integration produces noisy and inaccurate results.

### ADR 004: Physical Integration vs Arithmetic Mean for Fuel Economy
- Context: Calculating average fuel economy by taking a simple arithmetic mean of instantaneous `km/L` creates massive distortion due to deceleration fuel shut-off (DFCO) where instantaneous consumption approaches infinity or 999 km/L.
- Decision: Implemented physical numerical integration over moving segments:
  $$\text{Fuel Economy} = \frac{\sum v_i \cdot \Delta t}{\sum \text{Rate}_i \cdot \Delta t} = \frac{\text{Total Moving Distance (km)}}{\text{Total Fuel Consumed (L)}}$$
- Rationale: This reflects true vehicle fuel efficiency as measured by dynamometers and trip computers.

### ADR 005: Fallback to "-" for Missing Driving Segments
- Context: Several scan files in `Records/` (for example, short urban trips) never reach highway speeds (>= 70 km/h).
- Decision: If a trip or selection has less than 0.3 km of driving or less than 0.01 L of fuel consumed in the highway or city segment, the fuel economy value returns `None` and formats strictly as `-`.
- Rationale: Directly satisfies the user specification: "with available data, if there are not enough data show -".

### ADR 006: Gear Ratio Extraction via Histogram Peak Clustering
- Context: The user requested an "optimal RPM and Speed curve". In geared vehicles, speed and RPM are coupled through fixed transmission gear ratios.
- Decision: In `src/analyzer.py`, we calculate the ratio $R = \text{Speed} / \text{RPM}$, run a histogram peak finder to detect transmission gear lines, and overlay a median operating RPM curve.
- Rationale: Gives mechanics clear visibility into shift behavior, cruising gear engagement, and engine speed regulation.

---

## 3. Dataset Characteristics (Records Folder)

Analysis of the 8 sample files in `Records/`:
1. `2026-09-08 09-19-22.csv`:
   - Duration: 19.9 minutes (1,193 s)
   - Max Speed: 50.0 km/h (City only, no highway data; highway FE evaluates to `-`)
   - Coolant Temp: 89.0 C (Normal operating temperature)
2. `2026-09-08 11-06-29.csv`:
   - Duration: 15.8 minutes (950 s)
   - Max Speed: 48.0 km/h (City only)
3. `2026-09-08 11-31-27.csv`:
   - Duration: 5.1 minutes (308 s)
   - Max Speed: 42.0 km/h (City only)
4. `2026-10-10 13-23-30.csv`:
   - Duration: 18.5 minutes (1,109 s)
   - Max Speed: 65.0 km/h
5. `2026-10-10 13-50-16.csv`:
   - Duration: 13.1 minutes (785 s)
   - Max Speed: 57.0 km/h
   - Coolant Temp: 91.0 C
6. `2026-10-13 07-08-22.csv`:
   - Duration: 51.9 minutes (3,115 s)
   - Max Speed: 94.0 km/h (Substantial highway driving: City FE ~11.6 km/L, Highway FE ~16.7 km/L, Combined ~12.5 km/L)
7. `2026-10-13 16-50-45.csv`:
   - Duration: 9.3 minutes (555 s)
   - Max Speed: 35.0 km/h (City only)
8. `2026-10-13 17-13-03.csv`:
   - Duration: 87.8 minutes (5,266 s)
   - Max Speed: 56.0 km/h (Long congested urban trip)

Across all 8 trips combined:
- Total Distance: ~70.4 km
- Total Fuel Consumed: ~7.39 L
- Combined Fleet Economy: 10.71 km/L
- City Economy: 9.89 km/L
- Highway Economy: 16.75 km/L
- Efficiency Sweet Spot: ~62.5 km/h at ~1,300 RPM yielding ~47.5 km/L steady cruising efficiency.

---

## 4. Key Automotive Constants and Formulas

- Speed conversion to distance per 1-second step:
  $$\Delta d = v \times \frac{1}{3,600} \text{ km}$$
- Instantaneous fuel rate conversion to liters per 1-second step:
  $$\Delta F = \text{Rate (L/h)} \times \frac{1}{3,600} \text{ L}$$
- Unit Conversions:
  - $\text{km/L}$ is native.
  - $\text{L/100km} = \frac{100}{\text{km/L}}$
  - $\text{MPG (US)} = \text{km/L} \times 2.35214583$
  - $\text{MPG (UK)} = \text{km/L} \times 2.82480936$
- Thermostat Standard Band: 82 C to 95 C.
- Overheat Alert: > 100 C.
- Fuel Trim Diagnostic Limits: Normal is within +/- 7%. Alert is > +/- 10%.
- Alternator Charging Voltage Range: 13.5 V to 14.8 V.
