"""Data loader and preprocessing engine for OBD-II vehicle scan logs.

Exclusively supports Car Scanner ELM OBD2 app's vertical export CSV format.
Performs thorough multi-stage data cleanup, sensor bounds validation,
and time synchronization onto a uniform grid.
Supports hybrid vehicle telemetry (HV battery, block voltages, inverter, MG1/MG2).
Strictly adheres to project rules: no emojis.
"""

import os
import glob
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import pandas as pd
import numpy as np


# Standardized internal metric names mapped from Car Scanner ELM OBD2 PID descriptions
PID_MAP = {
    # Speed & Engine Dynamics
    "Vehicle speed": "speed_kmh",
    "Engine RPM": "engine_rpm",
    "Engine RPM x1000": "engine_rpm_k",
    "Engine coolant temperature": "coolant_temp_c",
    "Calculated instant fuel rate": "fuel_rate_lh",
    "Calculated instant fuel consumption": "fuel_economy_kml",
    "Calculated engine load value": "engine_load_pct",
    "Throttle position": "throttle_pct",
    "Intake manifold absolute pressure": "map_kpa",
    "Calculated boost": "boost_bar",
    "Intake air temperature": "intake_temp_c",
    "Timing advance": "timing_advance_deg",
    "Short term fuel % trim - Bank 1": "stft_pct",
    "Long term fuel % trim - Bank 1": "ltft_pct",
    "OBD Module Voltage": "voltage_v",
    "BATTERY VOLTAGE 12 V": "voltage_v",
    "Oxygen sensor 1 Bank 1 Voltage": "o2_voltage_v",
    "Oxygen sensor 1 Bank 1 Short term fuel trim": "o2_stft_pct",
    "Distance travelled": "distance_km",
    "Fuel used": "fuel_used_l",
    "Average speed": "avg_speed_kmh",
    "Average fuel consumption": "avg_fc_kml",
    "Vehicle acceleration": "acceleration_g",
    "Instant engine power (based on fuel consumption)": "engine_power_hp",

    # Hybrid Vehicle Telemetry (Toyota / Lexus THS-II & General HEV)
    "State of Charge": "hv_soc_pct",
    "State of Charge (All Bat)": "hv_soc_pct",
    "Hybrid/EV battery pack remaining charge": "hv_soc_pct",
    "Delta SOC": "hv_delta_soc_pct",
    "Batt Pack Current Val": "hv_current_ma",
    "Battery block maximum voltage": "hv_block_max_v",
    "Battery block minimum voltage": "hv_block_min_v",
    "Battery block number with maximum voltage": "hv_block_max_num",
    "Battery block number with minimum voltage": "hv_block_min_num",
    "Temp of Batt TB1": "hv_batt_temp_c",
    "Temp of Batt TB2": "hv_batt_temp_tb2_c",
    "Temp of Batt TB3": "hv_batt_temp_tb3_c",
    "HV battery intake air temperature": "hv_intake_temp_c",
    "Inverter Coolant Temp": "inverter_temp_c",
    "Inverter MG1 Temp": "inverter_mg1_temp_c",
    "Inverter MG2 Temp": "inverter_mg2_temp_c",
    "MG1 revolution": "mg1_rpm",
    "MG2 revolution": "mg2_rpm",
    "MG1 torque": "mg1_torque_nm",
    "MG2 torque": "mg2_torque_nm",
    "HV battery charge control (kW)": "hv_charge_kw",
    "HV battery discharge control (kW)": "hv_discharge_kw",
}

# Add individual battery block voltage mappings V01 to V14
for i in range(1, 15):
    PID_MAP[f"Battery Block Voltage -V{i:02d}"] = f"hv_block_v{i:02d}"

# Physical plausibility boundaries for automotive sensors
SENSOR_BOUNDS = {
    "Vehicle speed": (0.0, 260.0),
    "Engine RPM": (0.0, 9000.0),
    "Engine coolant temperature": (-40.0, 140.0),
    "OBD Module Voltage": (6.0, 18.0),
    "BATTERY VOLTAGE 12 V": (6.0, 18.0),
    "Calculated instant fuel rate": (0.0, 120.0),
    "Calculated instant fuel consumption": (0.0, 100.0),
    "Short term fuel % trim - Bank 1": (-100.0, 100.0),
    "Long term fuel % trim - Bank 1": (-100.0, 100.0),
    "Intake manifold absolute pressure": (10.0, 300.0),
    "Throttle position": (0.0, 100.0),
    "Calculated engine load value": (0.0, 100.0),
    "State of Charge": (0.0, 100.0),
    "Hybrid/EV battery pack remaining charge": (0.0, 100.0),
}


@dataclass
class DataCleanupReport:
    """Audit report tracking all pre-ingestion cleaning and filtering operations."""
    total_raw_rows: int = 0
    valid_rows_retained: int = 0
    invalid_rows_dropped: int = 0
    sensor_outliers_cleaned: int = 0
    duplicate_rows_dropped: int = 0
    dfco_events_conditioned: int = 0
    dfco_eligible_events: int = 0
    dfco_active_events: int = 0
    dfco_inactive_events: int = 0
    fuel_saved_liters: float = 0.0


@dataclass
class ScanTrip:
    """Represents a single parsed, cleaned, and synchronized OBD-II scan session."""
    file_path: str
    file_name: str
    start_seconds: float
    duration_seconds: float
    total_raw_rows: int
    data: pd.DataFrame
    cleanup_report: DataCleanupReport = field(default_factory=DataCleanupReport)
    pids_found: List[str] = field(default_factory=list)
    is_hybrid: bool = False

    @property
    def duration_minutes(self) -> float:
        return self.duration_seconds / 60.0

    @property
    def max_speed(self) -> float:
        if "speed_kmh" in self.data.columns and not self.data["speed_kmh"].dropna().empty:
            return float(self.data["speed_kmh"].max())
        return 0.0

    @property
    def avg_speed(self) -> float:
        if "speed_kmh" in self.data.columns and not self.data["speed_kmh"].dropna().empty:
            moving = self.data[self.data["speed_kmh"] > 1.0]
            if not moving.empty:
                return float(moving["speed_kmh"].mean())
        return 0.0

    @property
    def max_coolant_temp(self) -> float:
        if "coolant_temp_c" in self.data.columns and not self.data["coolant_temp_c"].dropna().empty:
            return float(self.data["coolant_temp_c"].max())
        return 0.0

    @property
    def mean_voltage(self) -> float:
        if "voltage_v" in self.data.columns and not self.data["voltage_v"].dropna().empty:
            return float(self.data["voltage_v"].mean())
        return 0.0


def clean_raw_obd_data(raw_df: pd.DataFrame) -> Tuple[pd.DataFrame, DataCleanupReport]:
    """Execute multi-stage sanitization and outlier removal on raw OBD scan dataframe."""
    report = DataCleanupReport(total_raw_rows=len(raw_df))

    # Stage 1: Drop empty rows and trailing semicolon columns
    df = raw_df.dropna(how="all").copy()

    # Verify Car Scanner ELM OBD2 vertical export structure
    required_cols = {"SECONDS", "PID", "VALUE"}
    if not required_cols.issubset(set(df.columns)):
        report.invalid_rows_dropped = report.total_raw_rows
        return pd.DataFrame(), report

    # Strip extraneous whitespaces from string columns
    df["PID"] = df["PID"].astype(str).str.strip()

    # Stage 2: Coerce numeric values
    df["SECONDS"] = pd.to_numeric(df["SECONDS"], errors="coerce")
    df["VALUE"] = pd.to_numeric(df["VALUE"], errors="coerce")

    # Drop null timestamps or invalid sensor values
    valid_mask = df["SECONDS"].notna() & df["VALUE"].notna() & (df["SECONDS"] > 0)
    dropped_initial = int(np.sum(~valid_mask))
    df = df[valid_mask].copy()

    # Stage 3: Remove duplicate sequential queries
    initial_len = len(df)
    df = df.drop_duplicates(subset=["SECONDS", "PID"], keep="last")
    report.duplicate_rows_dropped = initial_len - len(df)

    # Stage 4: Physical bounds filtering
    outlier_count = 0
    for pid, (low, high) in SENSOR_BOUNDS.items():
        pid_mask = df["PID"] == pid
        if np.any(pid_mask):
            sub_vals = df.loc[pid_mask, "VALUE"]
            invalid_bounds = (sub_vals < low) | (sub_vals > high)
            num_outliers = int(np.sum(invalid_bounds))
            if num_outliers > 0:
                outlier_count += num_outliers
                df.loc[pid_mask & (df["VALUE"] < low), "VALUE"] = low
                df.loc[pid_mask & (df["VALUE"] > high), "VALUE"] = high

    report.sensor_outliers_cleaned = outlier_count

    # Sort strictly by timestamp
    df = df.sort_values(by="SECONDS").reset_index(drop=True)

    report.valid_rows_retained = len(df)
    report.invalid_rows_dropped = dropped_initial + report.duplicate_rows_dropped

    return df, report


def parse_obd_csv(file_path: str, grid_step_seconds: float = 1.0) -> Optional[ScanTrip]:
    """Parse, clean, and synchronize a single Car Scanner ELM OBD2 CSV file."""
    if not os.path.isfile(file_path):
        return None

    try:
        raw_df = pd.read_csv(
            file_path,
            sep=";",
            dtype=str,
            on_bad_lines="skip"
        )
    except Exception:
        return None

    if raw_df.empty:
        return None

    # Step 1: Pre-ingestion cleanup
    cleaned_df, cleanup_report = clean_raw_obd_data(raw_df)
    if cleaned_df.empty:
        return None

    pids_found = cleaned_df["PID"].unique().tolist()
    total_raw_rows = cleanup_report.total_raw_rows
    min_sec = cleaned_df["SECONDS"].min()
    max_sec = cleaned_df["SECONDS"].max()
    duration_seconds = max(0.0, float(max_sec - min_sec))

    # Detect if hybrid vehicle based on PIDs
    is_hybrid = any(
        kw in p.lower()
        for p in pids_found
        for kw in ["hybrid", "hv ", "soc", "inverter", "mg1", "mg2", "block voltage"]
    )

    # Step 2: Map PIDs to canonical metrics
    cleaned_df["metric"] = cleaned_df["PID"].map(PID_MAP).fillna(cleaned_df["PID"])
    cleaned_df["elapsed_sec"] = cleaned_df["SECONDS"] - min_sec
    cleaned_df["t_bin"] = (cleaned_df["elapsed_sec"] / grid_step_seconds).round() * grid_step_seconds

    # Step 3: Pivot sensor values
    pivot_df = cleaned_df.pivot_table(index="t_bin", columns="metric", values="VALUE", aggfunc="mean")

    # Step 4: Uniform time grid reconstruction
    uniform_index = np.arange(0, pivot_df.index.max() + grid_step_seconds, grid_step_seconds)
    aligned_df = pivot_df.reindex(uniform_index)

    # Bounded linear interpolation for continuous telemetry
    aligned_df = aligned_df.interpolate(method="linear", limit=6).bfill().ffill()
    aligned_df.index.name = "elapsed_seconds"

    # Step 5: Derived metric calculations & DFCO conditioning
    if "speed_kmh" in aligned_df.columns:
        aligned_df["speed_kmh"] = aligned_df["speed_kmh"].clip(lower=0.0)

    if "engine_rpm" in aligned_df.columns:
        aligned_df["engine_rpm"] = aligned_df["engine_rpm"].clip(lower=0.0)

    # Compute vehicle acceleration (in g) if not directly supplied by sensor log
    if "acceleration_g" not in aligned_df.columns and "speed_kmh" in aligned_df.columns:
        dv_ms = (aligned_df["speed_kmh"].diff() * (1000.0 / 3600.0)) / grid_step_seconds
        aligned_df["acceleration_g"] = (dv_ms / 9.80665).fillna(0.0)

    # Reconstruct fuel rate / fuel economy cross-metrics
    if "fuel_rate_lh" not in aligned_df.columns and "fuel_economy_kml" in aligned_df.columns and "speed_kmh" in aligned_df.columns:
        speed = aligned_df["speed_kmh"]
        fe = aligned_df["fuel_economy_kml"].replace(0, np.nan)
        aligned_df["fuel_rate_lh"] = (speed / fe).fillna(0.0)

    if "fuel_economy_kml" not in aligned_df.columns and "fuel_rate_lh" in aligned_df.columns and "speed_kmh" in aligned_df.columns:
        speed = aligned_df["speed_kmh"]
        fr = aligned_df["fuel_rate_lh"].replace(0, np.nan)
        aligned_df["fuel_economy_kml"] = (speed / fr).fillna(0.0)

    # Deceleration fuel cut-off (DFCO) conditioning and tractive driving mode classification
    min_thr = float(aligned_df["throttle_pct"].min()) if "throttle_pct" in aligned_df.columns else 11.4
    closed_thr = min_thr + 1.5

    # Overrun deceleration criteria (DFCO eligibility)
    decel_cand = pd.Series(False, index=aligned_df.index)
    if "speed_kmh" in aligned_df.columns and "engine_rpm" in aligned_df.columns:
        decel_cand = (aligned_df["speed_kmh"] >= 15.0) & (aligned_df["engine_rpm"] >= 1100.0)
        if "throttle_pct" in aligned_df.columns:
            decel_cand &= (aligned_df["throttle_pct"] <= closed_thr)
        if "acceleration_g" in aligned_df.columns:
            decel_cand &= (aligned_df["acceleration_g"] < 0.0)
        elif "map_kpa" in aligned_df.columns:
            decel_cand &= (aligned_df["map_kpa"] <= 35.0)

    # Active fuel cut vs inactive fuel delivery during overrun
    active_cut = decel_cand.copy()
    if "fuel_rate_lh" in aligned_df.columns or "fuel_economy_kml" in aligned_df.columns:
        cut_crit = pd.Series(False, index=aligned_df.index)
        if "fuel_rate_lh" in aligned_df.columns:
            cut_crit |= (aligned_df["fuel_rate_lh"] <= 0.15)
        if "fuel_economy_kml" in aligned_df.columns:
            cut_crit |= (aligned_df["fuel_economy_kml"] >= 35.0)
        if "o2_voltage_v" in aligned_df.columns:
            cut_crit |= (aligned_df["o2_voltage_v"] <= 0.15)
        active_cut &= cut_crit

    inactive_cut = decel_cand & (~active_cut)

    aligned_df["is_dfco"] = active_cut
    if "fuel_rate_lh" in aligned_df.columns:
        aligned_df.loc[active_cut, "fuel_rate_lh"] = 0.0

    cleanup_report.dfco_eligible_events = int(np.sum(decel_cand))
    cleanup_report.dfco_active_events = int(np.sum(active_cut))
    cleanup_report.dfco_inactive_events = int(np.sum(inactive_cut))
    cleanup_report.dfco_events_conditioned = cleanup_report.dfco_active_events
    cleanup_report.fuel_saved_liters = float(cleanup_report.dfco_active_events) * (1.1 / 3600.0)

    # Tractive propulsion classification (positive load / cruise / acceleration)
    is_tractive = pd.Series(True, index=aligned_df.index)
    if "speed_kmh" in aligned_df.columns:
        is_tractive &= (aligned_df["speed_kmh"] >= 5.0)
    is_tractive &= (~decel_cand)
    if "throttle_pct" in aligned_df.columns:
        is_tractive &= (aligned_df["throttle_pct"] > closed_thr)
    if "acceleration_g" in aligned_df.columns:
        is_tractive &= (aligned_df["acceleration_g"] >= -0.05)
    if "fuel_rate_lh" in aligned_df.columns:
        is_tractive &= (aligned_df["fuel_rate_lh"] > 0.4)
    if "fuel_economy_kml" in aligned_df.columns:
        is_tractive &= (aligned_df["fuel_economy_kml"] >= 0.5) & (aligned_df["fuel_economy_kml"] <= 28.0)
    aligned_df["is_tractive"] = is_tractive

    # Convert battery current from mA to A if present
    if "hv_current_ma" in aligned_df.columns:
        aligned_df["hv_current_a"] = aligned_df["hv_current_ma"] / 1000.0

    file_name = os.path.basename(file_path)

    return ScanTrip(
        file_path=file_path,
        file_name=file_name,
        start_seconds=float(min_sec),
        duration_seconds=duration_seconds,
        total_raw_rows=total_raw_rows,
        data=aligned_df,
        cleanup_report=cleanup_report,
        pids_found=pids_found,
        is_hybrid=is_hybrid,
    )


def load_all_records(directory_path: str = "Records") -> List[ScanTrip]:
    """Scan and parse all Car Scanner ELM OBD2 CSV files in the directory and subdirectories."""
    trips = []
    # Search root and all nested subdirectories
    csv_files = sorted(
        glob.glob(os.path.join(directory_path, "*.csv"))
        + glob.glob(os.path.join(directory_path, "**", "*.csv"), recursive=True)
    )
    for path in csv_files:
        trip = parse_obd_csv(path)
        if trip is not None:
            trips.append(trip)
    return trips
