"""Automotive data science analyzer for OBD-II vehicle scan records.

Calculates city, highway, and combined fuel economy, optimal RPM-speed curves,
fuel efficiency heatmaps, thermal profiles, and mechanic diagnostic checks.
Strictly adheres to project rules: no emojis.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter

from src.data_loader import ScanTrip


@dataclass
class FuelEconomyResult:
    """Stores fuel economy figures and supporting distance/fuel metrics."""
    city_kml: Optional[float]
    highway_kml: Optional[float]
    combined_kml: Optional[float]
    total_distance_km: float
    total_fuel_liters: float
    city_distance_km: float
    city_fuel_liters: float
    highway_distance_km: float
    highway_fuel_liters: float
    idle_time_seconds: float
    moving_time_seconds: float
    idle_fuel_liters: float
    idle_percentage: float
    avg_moving_speed_kmh: float

    def get_value(self, category: str, unit: str = "km/L") -> Optional[float]:
        """Convert fuel economy to requested unit: 'km/L', 'L/100km', 'MPG (US)', 'MPG (UK)'."""
        raw_val = None
        if category == "city":
            raw_val = self.city_kml
        elif category == "highway":
            raw_val = self.highway_kml
        elif category == "combined":
            raw_val = self.combined_kml

        if raw_val is None or raw_val <= 0:
            return None

        if unit == "km/L":
            return raw_val
        elif unit == "L/100km":
            return 100.0 / raw_val
        elif unit == "MPG (US)":
            return raw_val * 2.35214583
        elif unit == "MPG (UK)":
            return raw_val * 2.82480936
        return raw_val

    def format_value(self, category: str, unit: str = "km/L") -> str:
        """Format metric string or '-' if data is insufficient."""
        val = self.get_value(category, unit)
        if val is None:
            return "-"
        return f"{val:.2f}"


@dataclass
class DiagnosticHealthReport:
    """Mechanic-grade diagnostic overview of vehicle health indicators."""
    battery_status: str
    battery_min_v: float
    battery_max_v: float
    battery_mean_v: float
    coolant_status: str
    coolant_max_c: float
    coolant_min_c: float
    warmup_time_sec: Optional[float]
    fuel_trim_status: str
    mean_stft_pct: Optional[float]
    mean_ltft_pct: Optional[float]
    total_trim_pct: Optional[float]
    mean_engine_load_pct: Optional[float]
    max_engine_load_pct: Optional[float]
    mean_map_kpa: Optional[float]
    max_rpm: float
    max_speed_kmh: float
    notes: List[str] = field(default_factory=list)


class VehicleAnalyzer:
    """Engine for performing automotive calculations across one or more trips."""

    def __init__(
        self,
        city_speed_max: float = 45.0,
        highway_speed_min: float = 70.0,
        min_moving_speed: float = 1.0,
        min_distance_threshold_km: float = 0.3,
    ):
        self.city_speed_max = city_speed_max
        self.highway_speed_min = highway_speed_min
        self.min_moving_speed = min_moving_speed
        self.min_distance_threshold_km = min_distance_threshold_km

    def calculate_fuel_economy(self, trips: List[ScanTrip]) -> FuelEconomyResult:
        """Calculate city, highway, and combined fuel economy across supplied trips."""
        total_city_dist = 0.0
        total_city_fuel = 0.0
        total_hwy_dist = 0.0
        total_hwy_fuel = 0.0
        total_moving_dist = 0.0
        total_moving_fuel = 0.0
        total_idle_time = 0.0
        total_moving_time = 0.0
        total_idle_fuel = 0.0

        for trip in trips:
            df = trip.data
            if df.empty or "speed_kmh" not in df.columns:
                continue

            speed = df["speed_kmh"]
            # dt in hours assuming 1 second grid step
            dt_hours = 1.0 / 3600.0

            # Fuel rate in L/h
            if "fuel_rate_lh" in df.columns:
                fuel_rate = df["fuel_rate_lh"].fillna(0.0)
            elif "fuel_economy_kml" in df.columns:
                fe = df["fuel_economy_kml"].replace(0, np.nan)
                fuel_rate = (speed / fe).fillna(0.0)
            else:
                fuel_rate = pd.Series(0.0, index=df.index)

            dist_step = speed * dt_hours
            fuel_step = fuel_rate * dt_hours

            # Masks
            idle_mask = speed <= self.min_moving_speed
            moving_mask = speed > self.min_moving_speed
            city_mask = (speed > self.min_moving_speed) & (speed <= self.city_speed_max)
            hwy_mask = speed >= self.highway_speed_min

            # Accumulate distance and fuel
            total_city_dist += float(dist_step[city_mask].sum())
            total_city_fuel += float(fuel_step[city_mask].sum())

            total_hwy_dist += float(dist_step[hwy_mask].sum())
            total_hwy_fuel += float(fuel_step[hwy_mask].sum())

            total_moving_dist += float(dist_step[moving_mask].sum())
            total_moving_fuel += float(fuel_step[moving_mask].sum())

            total_idle_time += float(idle_mask.sum())
            total_moving_time += float(moving_mask.sum())
            total_idle_fuel += float(fuel_step[idle_mask].sum())

        # Determine figures (with sufficient data checks)
        city_kml = None
        if total_city_dist >= self.min_distance_threshold_km and total_city_fuel > 0.01:
            city_kml = total_city_dist / total_city_fuel

        hwy_kml = None
        if total_hwy_dist >= self.min_distance_threshold_km and total_hwy_fuel > 0.01:
            hwy_kml = total_hwy_dist / total_hwy_fuel

        comb_kml = None
        if total_moving_dist >= self.min_distance_threshold_km and total_moving_fuel > 0.01:
            comb_kml = total_moving_dist / total_moving_fuel

        total_distance = total_moving_dist
        total_fuel = total_moving_fuel + total_idle_fuel
        total_time = total_idle_time + total_moving_time
        idle_pct = (total_idle_time / total_time * 100.0) if total_time > 0 else 0.0
        avg_speed = (total_moving_dist / (total_moving_time / 3600.0)) if total_moving_time > 0 else 0.0

        return FuelEconomyResult(
            city_kml=city_kml,
            highway_kml=hwy_kml,
            combined_kml=comb_kml,
            total_distance_km=total_distance,
            total_fuel_liters=total_fuel,
            city_distance_km=total_city_dist,
            city_fuel_liters=total_city_fuel,
            highway_distance_km=total_hwy_dist,
            highway_fuel_liters=total_hwy_fuel,
            idle_time_seconds=total_idle_time,
            moving_time_seconds=total_moving_time,
            idle_fuel_liters=total_idle_fuel,
            idle_percentage=idle_pct,
            avg_moving_speed_kmh=avg_speed,
        )

    def extract_moving_dataset(self, trips: List[ScanTrip]) -> pd.DataFrame:
        """Combine moving records from all trips into a unified dataframe."""
        dfs = []
        for trip in trips:
            df = trip.data
            if df.empty or "speed_kmh" not in df.columns or "engine_rpm" not in df.columns:
                continue
            moving = df[(df["speed_kmh"] > self.min_moving_speed) & (df["engine_rpm"] > 500)].copy()
            if not moving.empty:
                dfs.append(moving)

        if not dfs:
            return pd.DataFrame()
        return pd.concat(dfs, ignore_index=True)

    def compute_optimal_rpm_speed_curve(
        self, trips: List[ScanTrip], speed_step: float = 5.0
    ) -> Dict[str, Any]:
        """Compute optimal RPM vs Speed relationship and gear ratio traces.

        Returns data points, gear regression lines, and optimal operating curve.
        """
        combined = self.extract_moving_dataset(trips)
        if combined.empty:
            return {
                "speed": np.array([]),
                "rpm": np.array([]),
                "opt_speed": np.array([]),
                "opt_rpm": np.array([]),
                "gear_ratios": [],
            }

        speed = combined["speed_kmh"].values
        rpm = combined["engine_rpm"].values

        # Ratio speed / RPM (km/h per RPM)
        valid_idx = (rpm > 600) & (speed > 5.0)
        s_val = speed[valid_idx]
        r_val = rpm[valid_idx]

        if len(s_val) < 20:
            return {
                "speed": s_val,
                "rpm": r_val,
                "opt_speed": s_val,
                "opt_rpm": r_val,
                "gear_ratios": [],
            }

        # Bin speed to compute central operating RPM line
        s_min = max(5.0, float(np.percentile(s_val, 2)))
        s_max = float(np.percentile(s_val, 98))
        speed_bins = np.arange(s_min, s_max + speed_step, speed_step)

        opt_speed = []
        opt_rpm = []

        for i in range(len(speed_bins) - 1):
            low, high = speed_bins[i], speed_bins[i + 1]
            mask = (s_val >= low) & (s_val < high)
            if np.sum(mask) >= 5:
                sub_rpm = r_val[mask]
                center_speed = 0.5 * (low + high)
                # Median RPM represents the primary operating band for this road speed
                median_rpm = float(np.median(sub_rpm))
                opt_speed.append(center_speed)
                opt_rpm.append(median_rpm)

        # Detect discrete gear lines via ratio clustering / histogram peaks
        ratios = s_val / r_val
        counts, bin_edges = np.histogram(ratios, bins=50)
        # Find local peaks in ratio distribution
        peaks = []
        for i in range(1, len(counts) - 1):
            if counts[i] > counts[i - 1] and counts[i] > counts[i + 1] and counts[i] > 10:
                peak_ratio = 0.5 * (bin_edges[i] + bin_edges[i + 1])
                peaks.append(peak_ratio)

        gear_lines = []
        for idx, ratio in enumerate(sorted(peaks)):
            gear_lines.append({
                "gear_name": f"Gear Ratio {idx + 1}",
                "ratio": float(ratio),
                "rpm_line": np.array([800, 3500]),
                "speed_line": np.array([800, 3500]) * ratio,
            })

        return {
            "speed": s_val,
            "rpm": r_val,
            "opt_speed": np.array(opt_speed),
            "opt_rpm": np.array(opt_rpm),
            "gear_lines": gear_lines,
        }

    def compute_optimal_fuel_economy_rpm_speed_curve(
        self, trips: List[ScanTrip], speed_step: float = 5.0, rpm_step: float = 100.0
    ) -> Dict[str, Any]:
        """Compute optimal fuel economy (km/L) as a function of RPM and Speed.

        Produces 2D heatmap matrix, optimal efficiency curve, and sweet-spot zone.
        """
        combined = self.extract_moving_dataset(trips)
        empty_res = {
            "has_data": False,
            "speed_grid": None,
            "rpm_grid": None,
            "fe_matrix": None,
            "opt_speed": np.array([]),
            "opt_rpm": np.array([]),
            "opt_fe": np.array([]),
            "sweet_spot": None,
        }

        if combined.empty:
            return empty_res

        # Determine fuel economy (km/L)
        if "fuel_economy_kml" in combined.columns:
            fe = combined["fuel_economy_kml"].copy()
        elif "fuel_rate_lh" in combined.columns:
            fr = combined["fuel_rate_lh"].replace(0, np.nan)
            fe = (combined["speed_kmh"] / fr).fillna(0.0)
        else:
            return empty_res

        speed = combined["speed_kmh"].values
        rpm = combined["engine_rpm"].values
        fe_val = fe.values

        # Filter deceleration cut-off spikes (> 60 km/L) and noise
        valid = (speed > 5.0) & (rpm > 600) & (fe_val > 1.0) & (fe_val < 60.0)
        s = speed[valid]
        r = rpm[valid]
        f = fe_val[valid]

        if len(s) < 30:
            return empty_res

        # Speed and RPM grid edges
        s_min, s_max = 10.0, float(min(120.0, np.max(s) + 5.0))
        r_min, r_max = 700.0, float(min(4000.0, np.max(r) + 100.0))

        s_bins = np.arange(s_min, s_max + speed_step, speed_step)
        r_bins = np.arange(r_min, r_max + rpm_step, rpm_step)

        matrix = np.full((len(r_bins) - 1, len(s_bins) - 1), np.nan)
        counts = np.zeros_like(matrix)

        for i in range(len(s_bins) - 1):
            s_low, s_high = s_bins[i], s_bins[i + 1]
            s_mask = (s >= s_low) & (s < s_high)
            for j in range(len(r_bins) - 1):
                r_low, r_high = r_bins[j], r_bins[j + 1]
                cell_mask = s_mask & (r >= r_low) & (r < r_high)
                count = int(np.sum(cell_mask))
                if count >= 3:
                    matrix[j, i] = float(np.median(f[cell_mask]))
                    counts[j, i] = count

        # Extract optimal RPM per speed bin (curve maximizing fuel economy)
        opt_speed = []
        opt_rpm = []
        opt_fe = []

        for i in range(len(s_bins) - 1):
            s_center = 0.5 * (s_bins[i] + s_bins[i + 1])
            s_mask = (s >= s_bins[i]) & (s < s_bins[i + 1])
            if np.sum(s_mask) >= 8:
                sub_r = r[s_mask]
                sub_f = f[s_mask]
                # Look at top quartile efficiency points
                top_cutoff = np.percentile(sub_f, 75)
                top_mask = sub_f >= top_cutoff
                best_rpm = float(np.median(sub_r[top_mask]))
                best_fe = float(np.mean(sub_f[top_mask]))
                opt_speed.append(s_center)
                opt_rpm.append(best_rpm)
                opt_fe.append(best_fe)

        # Smooth matrix for contour visualization
        smoothed_matrix = matrix.copy()
        nan_mask = np.isnan(smoothed_matrix)
        if not np.all(nan_mask):
            mean_val = np.nanmean(smoothed_matrix)
            smoothed_matrix[nan_mask] = mean_val
            smoothed_matrix = gaussian_filter(smoothed_matrix, sigma=1.0)
            smoothed_matrix[nan_mask] = np.nan

        # Identify vehicle efficiency sweet spot (speed & RPM with maximum cruising FE)
        sweet_spot = None
        if opt_fe:
            best_idx = int(np.argmax(opt_fe))
            sweet_spot = {
                "speed_kmh": opt_speed[best_idx],
                "rpm": opt_rpm[best_idx],
                "fe_kml": opt_fe[best_idx],
            }

        return {
            "has_data": True,
            "speed_bins": s_bins,
            "rpm_bins": r_bins,
            "fe_matrix": smoothed_matrix,
            "raw_matrix": matrix,
            "opt_speed": np.array(opt_speed),
            "opt_rpm": np.array(opt_rpm),
            "opt_fe": np.array(opt_fe),
            "sweet_spot": sweet_spot,
            "scatter_speed": s,
            "scatter_rpm": r,
            "scatter_fe": f,
        }

    def analyze_coolant_temperature(self, trips: List[ScanTrip]) -> Dict[str, Any]:
        """Analyze coolant temperature timelines, warm-up characteristics, and operating bands."""
        trip_curves = []
        all_temps = []
        all_loads = []

        for trip in trips:
            df = trip.data
            if df.empty or "coolant_temp_c" not in df.columns:
                continue

            time_min = df.index.values / 60.0
            temps = df["coolant_temp_c"].values
            trip_curves.append({
                "name": trip.file_name,
                "time_minutes": time_min,
                "temperature_c": temps,
            })
            all_temps.extend(temps)

            if "engine_load_pct" in df.columns:
                all_loads.extend(df["engine_load_pct"].values)

        if not all_temps:
            return {"has_data": False}

        arr_temps = np.array(all_temps)
        min_temp = float(np.min(arr_temps))
        max_temp = float(np.max(arr_temps))
        mean_temp = float(np.mean(arr_temps))

        # Check warm-up behavior (time to reach 80 C)
        warmup_time = None
        for trip in trips:
            df = trip.data
            if "coolant_temp_c" in df.columns:
                warm = df[df["coolant_temp_c"] >= 80.0]
                if not warm.empty and df["coolant_temp_c"].iloc[0] < 70.0:
                    warmup_time = float(warm.index[0])
                    break

        return {
            "has_data": True,
            "trip_curves": trip_curves,
            "min_temp": min_temp,
            "max_temp": max_temp,
            "mean_temp": mean_temp,
            "normal_band": (82.0, 95.0),
            "warmup_time_sec": warmup_time,
            "temp_vs_load": {
                "temps": np.array(all_temps),
                "loads": np.array(all_loads) if len(all_loads) == len(all_temps) else np.array([]),
            },
        }

    def generate_diagnostic_health(self, trips: List[ScanTrip]) -> DiagnosticHealthReport:
        """Evaluate OBD-II health indicators: battery voltage, fuel trims, coolant, and load."""
        notes = []

        # Battery voltage analysis
        all_voltages = []
        for t in trips:
            if "voltage_v" in t.data.columns:
                v = t.data["voltage_v"].dropna()
                if not v.empty:
                    all_voltages.extend(v.values)

        if all_voltages:
            v_arr = np.array(all_voltages)
            v_min = float(np.min(v_arr))
            v_max = float(np.max(v_arr))
            v_mean = float(np.mean(v_arr))

            if v_min < 11.5:
                battery_status = "CRITICAL LOW (< 11.5V)"
                notes.append("Battery voltage dipped below 11.5V. Check battery state of charge.")
            elif v_mean < 13.0:
                battery_status = "LOW CHARGING (< 13.0V)"
                notes.append("Average voltage below 13.0V while running. Inspect alternator output.")
            elif v_max > 15.2:
                battery_status = "HIGH CHARGING (> 15.2V)"
                notes.append("Voltage peaked above 15.2V. Potential alternator regulator fault.")
            else:
                battery_status = "NORMAL (13.5V - 14.8V)"
        else:
            battery_status = "NO DATA"
            v_min = v_max = v_mean = 0.0

        # Coolant temperature analysis
        coolant_res = self.analyze_coolant_temperature(trips)
        if coolant_res["has_data"]:
            c_min = coolant_res["min_temp"]
            c_max = coolant_res["max_temp"]
            warmup = coolant_res["warmup_time_sec"]

            if c_max > 102.0:
                coolant_status = "OVERHEATING WARNING (> 102 C)"
                notes.append("Coolant temperature exceeded 102 C. Inspect radiator, cooling fan, and coolant level.")
            elif c_max < 75.0:
                coolant_status = "UNDERCOOLING / THERMOSTAT STUCK OPEN (< 75 C)"
                notes.append("Engine ran below 75 C. Thermostat may be stuck open.")
            else:
                coolant_status = "NORMAL OPERATING (82 C - 95 C)"
        else:
            coolant_status = "NO DATA"
            c_min = c_max = 0.0
            warmup = None

        # Fuel trims analysis
        stft_vals = []
        ltft_vals = []
        for t in trips:
            if "stft_pct" in t.data.columns:
                stft_vals.extend(t.data["stft_pct"].dropna().values)
            if "ltft_pct" in t.data.columns:
                ltft_vals.extend(t.data["ltft_pct"].dropna().values)

        mean_stft = float(np.mean(stft_vals)) if stft_vals else None
        mean_ltft = float(np.mean(ltft_vals)) if ltft_vals else None
        total_trim = None
        if mean_stft is not None and mean_ltft is not None:
            total_trim = mean_stft + mean_ltft

        if total_trim is not None:
            if total_trim > 12.0:
                fuel_trim_status = "LEAN RUNNING (> +12%)"
                notes.append("Total fuel trim is high positive. Suspect unmetered air leak (vacuum leak) or weak fuel delivery.")
            elif total_trim < -12.0:
                fuel_trim_status = "RICH RUNNING (< -12%)"
                notes.append("Total fuel trim is negative. Suspect leaky injector, high fuel pressure, or restricted intake.")
            elif abs(total_trim) > 7.0:
                fuel_trim_status = "MARGINAL TRIM (7% - 12%)"
            else:
                fuel_trim_status = "NORMAL TRIM (< +/- 7%)"
        else:
            fuel_trim_status = "NO DATA"

        # Engine load and MAP
        all_loads = []
        all_maps = []
        all_speeds = []
        all_rpms = []

        for t in trips:
            df = t.data
            if "engine_load_pct" in df.columns:
                all_loads.extend(df["engine_load_pct"].dropna().values)
            if "map_kpa" in df.columns:
                all_maps.extend(df["map_kpa"].dropna().values)
            if "speed_kmh" in df.columns:
                all_speeds.extend(df["speed_kmh"].dropna().values)
            if "engine_rpm" in df.columns:
                all_rpms.extend(df["engine_rpm"].dropna().values)

        mean_load = float(np.mean(all_loads)) if all_loads else None
        max_load = float(np.max(all_loads)) if all_loads else None
        mean_map = float(np.mean(all_maps)) if all_maps else None
        max_speed = float(np.max(all_speeds)) if all_speeds else 0.0
        max_rpm = float(np.max(all_rpms)) if all_rpms else 0.0

        return DiagnosticHealthReport(
            battery_status=battery_status,
            battery_min_v=v_min,
            battery_max_v=v_max,
            battery_mean_v=v_mean,
            coolant_status=coolant_status,
            coolant_max_c=c_max,
            coolant_min_c=c_min,
            warmup_time_sec=warmup,
            fuel_trim_status=fuel_trim_status,
            mean_stft_pct=mean_stft,
            mean_ltft_pct=mean_ltft,
            total_trim_pct=total_trim,
            mean_engine_load_pct=mean_load,
            max_engine_load_pct=max_load,
            mean_map_kpa=mean_map,
            max_rpm=max_rpm,
            max_speed_kmh=max_speed,
            notes=notes,
        )
