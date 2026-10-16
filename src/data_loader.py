"""Data loader and preprocessing engine for OBD-II vehicle scan logs.

Exclusively supports Car Scanner ELM OBD2 app's vertical export CSV format.
Performs thorough multi-stage data cleanup, sensor bounds validation,
GPS teleportation jump filtering, and time synchronization onto a uniform grid.
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
    "Oxygen sensor 1 Bank 1 Voltage": "o2_voltage_v",
    "Oxygen sensor 1 Bank 1 Short term fuel trim": "o2_stft_pct",
    "Distance travelled": "distance_km",
    "Fuel used": "fuel_used_l",
    "Average speed": "avg_speed_kmh",
    "Average fuel consumption": "avg_fc_kml",
    "Vehicle acceleration": "acceleration_g",
    "Instant engine power (based on fuel consumption)": "engine_power_hp",
}

# Physical plausibility boundaries for automotive sensors
SENSOR_BOUNDS = {
    "Vehicle speed": (0.0, 260.0),
    "Engine RPM": (0.0, 9000.0),
    "Engine coolant temperature": (-40.0, 140.0),
    "OBD Module Voltage": (6.0, 18.0),
    "Calculated instant fuel rate": (0.0, 120.0),
    "Calculated instant fuel consumption": (0.0, 100.0),
    "Short term fuel % trim - Bank 1": (-100.0, 100.0),
    "Long term fuel % trim - Bank 1": (-100.0, 100.0),
    "Intake manifold absolute pressure": (10.0, 300.0),
    "Throttle position": (0.0, 100.0),
    "Calculated engine load value": (0.0, 100.0),
}


@dataclass
class DataCleanupReport:
    """Audit report tracking all pre-ingestion cleaning and filtering operations."""
    total_raw_rows: int = 0
    valid_rows_retained: int = 0
    invalid_rows_dropped: int = 0
    sensor_outliers_cleaned: int = 0
    gps_jumps_filtered: int = 0
    duplicate_rows_dropped: int = 0
    dfco_events_conditioned: int = 0


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
    has_gps: bool = False
    latitude_start: Optional[float] = None
    longitude_start: Optional[float] = None

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

    @property
    def gps_coordinates(self) -> List[Tuple[float, float]]:
        """Extract ordered sequence of valid (latitude, longitude) pairs."""
        if not self.has_gps or "latitude" not in self.data.columns or "longitude" not in self.data.columns:
            return []
        gps_valid = self.data.dropna(subset=["latitude", "longitude"])
        # Subsample if excessively dense
        coords = list(zip(gps_valid["latitude"].values, gps_valid["longitude"].values))
        return coords


def _haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two GPS coordinates in kilometers."""
    r_earth = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2.0) ** 2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2.0) ** 2
    return float(2.0 * r_earth * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0))))


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

    # Stage 5: Clean GPS coordinates and filter teleportation spikes
    gps_jumps = 0
    if "LATITUDE" in df.columns and "LONGTITUDE" in df.columns:
        df["LATITUDE"] = pd.to_numeric(df["LATITUDE"], errors="coerce")
        df["LONGTITUDE"] = pd.to_numeric(df["LONGTITUDE"], errors="coerce")

        # Invalidate 0.0, 0.0 or out-of-bounds coordinates
        invalid_gps = (
            (df["LATITUDE"] == 0.0)
            | (df["LONGTITUDE"] == 0.0)
            | (df["LATITUDE"] < -90.0)
            | (df["LATITUDE"] > 90.0)
            | (df["LONGTITUDE"] < -180.0)
            | (df["LONGTITUDE"] > 180.0)
        )
        df.loc[invalid_gps, ["LATITUDE", "LONGTITUDE"]] = np.nan

        # Detect GPS jump anomalies (distance jumps exceeding 2 km between points)
        valid_gps_idx = df.dropna(subset=["LATITUDE", "LONGTITUDE"]).index
        if len(valid_gps_idx) > 1:
            lats = df.loc[valid_gps_idx, "LATITUDE"].values
            lons = df.loc[valid_gps_idx, "LONGTITUDE"].values
            secs = df.loc[valid_gps_idx, "SECONDS"].values

            prev_lat, prev_lon, prev_sec = lats[0], lons[0], secs[0]
            drop_indices = []

            for i in range(1, len(lats)):
                dist = _haversine_distance_km(prev_lat, prev_lon, lats[i], lons[i])
                dt = max(0.1, secs[i] - prev_sec)
                implied_speed = (dist / dt) * 3600.0  # km/h

                # If speed > 220 km/h or jump > 3 km, mark as glitch
                if implied_speed > 220.0 or dist > 3.0:
                    drop_indices.append(valid_gps_idx[i])
                    gps_jumps += 1
                else:
                    prev_lat, prev_lon, prev_sec = lats[i], lons[i], secs[i]

            if drop_indices:
                df.loc[drop_indices, ["LATITUDE", "LONGTITUDE"]] = np.nan

    report.gps_jumps_filtered = gps_jumps

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

    # Step 1: Execute deep pre-ingestion cleanup
    cleaned_df, cleanup_report = clean_raw_obd_data(raw_df)
    if cleaned_df.empty:
        return None

    pids_found = cleaned_df["PID"].unique().tolist()
    total_raw_rows = cleanup_report.total_raw_rows
    min_sec = cleaned_df["SECONDS"].min()
    max_sec = cleaned_df["SECONDS"].max()
    duration_seconds = max(0.0, float(max_sec - min_sec))

    # Step 2: Check GPS availability
    has_gps = False
    lat_start = None
    lon_start = None
    if "LATITUDE" in cleaned_df.columns and "LONGTITUDE" in cleaned_df.columns:
        valid_gps = cleaned_df.dropna(subset=["LATITUDE", "LONGTITUDE"])
        if len(valid_gps) > 5:
            has_gps = True
            lat_start = float(valid_gps["LATITUDE"].iloc[0])
            lon_start = float(valid_gps["LONGTITUDE"].iloc[0])

    # Step 3: Map PIDs to canonical metrics
    cleaned_df["metric"] = cleaned_df["PID"].map(PID_MAP).fillna(cleaned_df["PID"])
    cleaned_df["elapsed_sec"] = cleaned_df["SECONDS"] - min_sec
    cleaned_df["t_bin"] = (cleaned_df["elapsed_sec"] / grid_step_seconds).round() * grid_step_seconds

    # Step 4: Pivot sensor values
    pivot_df = cleaned_df.pivot_table(index="t_bin", columns="metric", values="VALUE", aggfunc="mean")

    # Step 5: Pivot and interpolate GPS coordinates if present
    if has_gps:
        gps_binned = (
            cleaned_df.dropna(subset=["LATITUDE", "LONGTITUDE"])
            .groupby("t_bin")[["LATITUDE", "LONGTITUDE"]]
            .mean()
        )
        pivot_df["latitude"] = gps_binned["LATITUDE"]
        pivot_df["longitude"] = gps_binned["LONGTITUDE"]

    # Step 6: Uniform time grid reconstruction
    uniform_index = np.arange(0, pivot_df.index.max() + grid_step_seconds, grid_step_seconds)
    aligned_df = pivot_df.reindex(uniform_index)

    # Linear interpolation for telemetry
    aligned_df = aligned_df.interpolate(method="linear", limit=6).bfill().ffill()
    aligned_df.index.name = "elapsed_seconds"

    # Step 7: Derived metric calculations & DFCO conditioning
    if "speed_kmh" in aligned_df.columns:
        aligned_df["speed_kmh"] = aligned_df["speed_kmh"].clip(lower=0.0)

    if "engine_rpm" in aligned_df.columns:
        aligned_df["engine_rpm"] = aligned_df["engine_rpm"].clip(lower=0.0)

    # Reconstruct fuel rate / fuel economy cross-metrics
    if "fuel_rate_lh" not in aligned_df.columns and "fuel_economy_kml" in aligned_df.columns and "speed_kmh" in aligned_df.columns:
        speed = aligned_df["speed_kmh"]
        fe = aligned_df["fuel_economy_kml"].replace(0, np.nan)
        aligned_df["fuel_rate_lh"] = (speed / fe).fillna(0.0)

    if "fuel_economy_kml" not in aligned_df.columns and "fuel_rate_lh" in aligned_df.columns and "speed_kmh" in aligned_df.columns:
        speed = aligned_df["speed_kmh"]
        fr = aligned_df["fuel_rate_lh"].replace(0, np.nan)
        aligned_df["fuel_economy_kml"] = (speed / fr).fillna(0.0)

    # Deceleration fuel cut-off (DFCO) conditioning
    if "fuel_economy_kml" in aligned_df.columns:
        # Flag spikes where fuel economy exceeds 60 km/L during coasting
        dfco_mask = aligned_df["fuel_economy_kml"] > 60.0
        cleanup_report.dfco_events_conditioned = int(np.sum(dfco_mask))

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
        has_gps=has_gps,
        latitude_start=lat_start,
        longitude_start=lon_start,
    )


def load_all_records(directory_path: str = "Records") -> List[ScanTrip]:
    """Scan and parse all Car Scanner ELM OBD2 CSV files in the specified directory."""
    trips = []
    csv_files = sorted(glob.glob(os.path.join(directory_path, "*.csv")))
    for path in csv_files:
        trip = parse_obd_csv(path)
        if trip is not None:
            trips.append(trip)
    return trips
