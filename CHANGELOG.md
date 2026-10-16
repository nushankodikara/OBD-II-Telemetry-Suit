# Changelog - OBD-II Telemetry Suit

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Software is currently in beta status using the `0.x.x` versioning convention.

Strict Project Requirement: Zero emojis are used across this changelog and entire repository.

---

## [0.2.0-beta] - 2026-10-16

### Added
- Created `simpleversion.json` in the root repository to track and manage application versioning.
- Added version management module (`src/version.py`) providing semver parsing, comparison, and update checking.
- Added standalone `VehicleSettingsDialog` modal component allowing users to configure vehicle specifications (make, model, year, displacement, transmission, gears, tyre size, tank capacity, and speed thresholds) in a separate window.
- Added automatic prompt to open the Vehicle Settings window by default whenever importing records when settings are not yet configured.
- Added `SoftwareUpdateDialog` and in-software update checker under `Help -> Check for Updates...` that queries the GitHub Releases API and directs users to download new binary packages.
- Added GitHub Actions CI/CD workflow (`.github/workflows/release.yml`) with dependency caching to automatically run test suites and build standalone executables/archives for macOS (.zip / .app), Linux (.tar.gz), and Windows (.zip / .exe) on tagged releases.
- Added `CHANGELOG.md` to track project history, enhancements, and bug fixes across all versions.

### Changed
- Re-architected the `Hybrid Battery & Powertrain` tab to be dynamic: this tab is now completely hidden by default and only appears when the selected scan records contain hybrid telemetry.
- Updated top metric card 6 to dynamically switch between `[HYBRID SOC]` and `[IDLE TIME %]` based on whether a hybrid vehicle is being analyzed.
- Updated `compute_optimal_rpm_speed_curve()` in `src/analyzer.py` to accept `max_gears` constraint.
- Updated RPM vs Speed curve rendering in `src/ui/app.py` to respect the configured vehicle transmission forward gear count (e.g. 4 forward gears for a 4-speed automatic transmission).

### Fixed
- Fixed RPM vs Speed curve displaying a 5th gear line even when transmission settings were set for a 4-speed automatic transmission.
- Completely removed `Records/` folder and all historical data files from git history across all commits.
- Hardened `.gitignore` to prevent any telemetry scan records or local session caches from ever entering the git index.

---

## [0.1.0-beta] - 2026-10-16

### Added
- Initial beta workstation release named "OBD-II Telemetry Suit".
- Multi-stage pre-ingestion cleaning pipeline (`clean_raw_obd_data`) supporting Car Scanner ELM OBD2 vertical export format.
- Fuel economy analytics with numerical integration for City, Highway, and Combined metrics, with fallback `-` for insufficient data.
- 2D efficiency heatmap and optimal cruising sweet spot locator.
- Engine coolant thermal stability profiling with standard thermostat operating bands.
- In-depth Short Term (STFT) and Long Term (LTFT) fuel trim diagnostics across Idle, Cruise, and High Load regimes with mechanic repair plans.
- High-voltage battery pack diagnostics including State of Charge (SOC %), individual block voltages (V01-V14), block delta $V_{\Delta}$, and EV driving ratio %.
- Quick Vehicle Info automated intelligence dialog for non-technical drivers.
- XML vehicle profile and session persistence engine (`save_session_to_xml`, `load_session_from_xml`).
- Clean blank initial startup state with automatic session restoration from `last_session.xml`.
- Native Tkinter menu bar with File, Vehicle & Settings, and Help cascades.
- Pre-loaded with 8 multi-vehicle scan datasets in `Records/` (including Toyota Aqua hybrid).
