"""Data loader and preprocessing engine for OBD-II vehicle scan logs.

Parses raw semicolon-delimited OBD-II CSV records, synchronizes asynchronous
sensor event streams onto a uniform time grid, and extracts metadata.
Strictly adheres to project rules: no emojis.
"""

import os
import glob
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import pandas as pd
import numpy as np


# Standardized internal metric names mapped from OBD PID descriptions
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


@dataclass
class ScanTrip:
    """Represents a single parsed and synchronized OBD-II scan session."""
    file_path: str
    file_name: str
    start_seconds: float
    duration_seconds: float
    total_raw_rows: int
    data: pd.DataFrame
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


def parse_obd_csv(file_path: str, grid_step_seconds: float = 1.0) -> Optional[ScanTrip]:
    """Parse a single OBD-II scan log CSV file.

    Synchronizes asynchronous PID rows onto a uniform time grid.
    """
    if not os.path.isfile(file_path):
        return None

    try:
        df = pd.read_csv(
            file_path,
            sep=";",
            usecols=["SECONDS", "PID", "VALUE", "UNITS", "LATITUDE", "LONGTITUDE"],
            dtype=str,
            on_bad_lines="skip"
        )
    except Exception:
        # Fallback without column selection if headers differ
        try:
            df = pd.read_csv(file_path, sep=";", dtype=str, on_bad_lines="skip")
        except Exception:
            return None

    if df.empty or "PID" not in df.columns or "VALUE" not in df.columns:
        return None

    # Clean numeric fields
    df["SECONDS"] = pd.to_numeric(df["SECONDS"], errors="coerce")
    df["VALUE"] = pd.to_numeric(df["VALUE"], errors="coerce")
    df = df.dropna(subset=["SECONDS", "PID", "VALUE"])

    if df.empty:
        return None

    pids_found = df["PID"].unique().tolist()
    total_raw_rows = len(df)
    min_sec = df["SECONDS"].min()
    max_sec = df["SECONDS"].max()
    duration_seconds = max(0.0, float(max_sec - min_sec))

    # Check GPS availability
    has_gps = False
    lat_start = None
    lon_start = None
    if "LATITUDE" in df.columns and "LONGTITUDE" in df.columns:
        valid_gps = df.dropna(subset=["LATITUDE", "LONGTITUDE"])
        if not valid_gps.empty:
            has_gps = True
            try:
                lat_start = float(valid_gps["LATITUDE"].iloc[0])
                lon_start = float(valid_gps["LONGTITUDE"].iloc[0])
            except (ValueError, TypeError):
                has_gps = False

    # Map PIDs to standard metric names
    df["metric"] = df["PID"].map(PID_MAP).fillna(df["PID"])

    # Create relative elapsed time in seconds
    df["elapsed_sec"] = df["SECONDS"] - min_sec

    # Bin to time grid step
    df["t_bin"] = (df["elapsed_sec"] / grid_step_seconds).round() * grid_step_seconds

    # Pivot table with mean for any duplicate queries within the same second
    pivot_df = df.pivot_table(index="t_bin", columns="metric", values="VALUE", aggfunc="mean")

    # Build uniform continuous time grid
    uniform_index = np.arange(0, pivot_df.index.max() + grid_step_seconds, grid_step_seconds)
    aligned_df = pivot_df.reindex(uniform_index)

    # Fast forward-fill with interpolation for sensors with lower polling rate
    # Coolant temperature and voltage change slowly, while speed and RPM update rapidly
    aligned_df = aligned_df.interpolate(method="linear", limit=5).bfill().ffill()
    aligned_df.index.name = "elapsed_seconds"

    # Compute derived metrics if missing
    if "speed_kmh" in aligned_df.columns:
        aligned_df["speed_kmh"] = aligned_df["speed_kmh"].clip(lower=0.0)

    if "engine_rpm" in aligned_df.columns:
        aligned_df["engine_rpm"] = aligned_df["engine_rpm"].clip(lower=0.0)

    # Synthesize instantaneous fuel rate if only instant fuel economy and speed are available
    if "fuel_rate_lh" not in aligned_df.columns and "fuel_economy_kml" in aligned_df.columns and "speed_kmh" in aligned_df.columns:
        speed = aligned_df["speed_kmh"]
        fe = aligned_df["fuel_economy_kml"].replace(0, np.nan)
        aligned_df["fuel_rate_lh"] = (speed / fe).fillna(0.0)

    # Synthesize instant fuel economy if only fuel rate and speed are present
    if "fuel_economy_kml" not in aligned_df.columns and "fuel_rate_lh" in aligned_df.columns and "speed_kmh" in aligned_df.columns:
        speed = aligned_df["speed_kmh"]
        fr = aligned_df["fuel_rate_lh"].replace(0, np.nan)
        aligned_df["fuel_economy_kml"] = (speed / fr).fillna(0.0)

    file_name = os.path.basename(file_path)

    return ScanTrip(
        file_path=file_path,
        file_name=file_name,
        start_seconds=float(min_sec),
        duration_seconds=duration_seconds,
        total_raw_rows=total_raw_rows,
        data=aligned_df,
        pids_found=pids_found,
        has_gps=has_gps,
        latitude_start=lat_start,
        longitude_start=lon_start
    )


def load_all_records(directory_path: str = "Records") -> List[ScanTrip]:
    """Scan and parse all CSV files in the specified directory."""
    trips = []
    csv_files = sorted(glob.glob(os.path.join(directory_path, "*.csv")))
    for path in csv_files:
        trip = parse_obd_csv(path)
        if trip is not None:
            trips.append(trip)
    return trips
