"""Automotive data science analyzer for OBD-II Telemetry Suit.

Calculates city, highway, and combined fuel economy, optimal RPM-speed curves,
fuel efficiency heatmaps, thermal profiles, deep STFT/LTFT diagnostics with
mechanic repair recommendations, hybrid battery & powertrain diagnostics,
general user auto-detection, and physical/ML telemetry anomaly detection.
Strictly adheres to project rules: no emojis.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter
from sklearn.ensemble import IsolationForest

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
class TelemetryAnomaly:
    """Represents a detected automotive sensor or driving anomaly."""
    timestamp_sec: float
    timestamp_min: float
    category: str  # [ELECTRICAL], [FUEL TRIM], [THERMAL], [DRIVETRAIN], [ML OUTLIER]
    severity: str  # [CRITICAL], [WARNING], [INFO]
    metric_name: str
    detected_value: str
    expected_range: str
    description: str
    trip_file: str


@dataclass
class FuelTrimDiagnostic:
    """Comprehensive diagnostic evaluation of STFT and LTFT fuel trims."""
    has_data: bool
    mean_stft: Optional[float] = None
    mean_ltft: Optional[float] = None
    mean_total_trim: Optional[float] = None
    idle_stft: Optional[float] = None
    idle_ltft: Optional[float] = None
    idle_total_trim: Optional[float] = None
    cruise_stft: Optional[float] = None
    cruise_ltft: Optional[float] = None
    cruise_total_trim: Optional[float] = None
    high_load_stft: Optional[float] = None
    high_load_ltft: Optional[float] = None
    high_load_total_trim: Optional[float] = None
    diagnosis_title: str = "NO DATA"
    severity: str = "INFO"
    likelihood_score: str = "LOW"
    probable_causes: List[str] = field(default_factory=list)
    mechanic_recommendations: List[str] = field(default_factory=list)


@dataclass
class HybridBatteryReport:
    """Diagnostic health assessment for hybrid vehicle high-voltage powertrain."""
    is_hybrid: bool
    soc_mean: Optional[float] = None
    soc_min: Optional[float] = None
    soc_max: Optional[float] = None
    delta_soc: Optional[float] = None
    current_a_mean: Optional[float] = None
    max_charge_a: Optional[float] = None
    max_discharge_a: Optional[float] = None
    block_voltages: Dict[str, float] = field(default_factory=dict)
    max_block_v: Optional[float] = None
    min_block_v: Optional[float] = None
    delta_block_v: Optional[float] = None
    battery_health_status: str = "NOT HYBRID"
    battery_temp_c: Optional[float] = None
    inverter_temp_c: Optional[float] = None
    mg1_temp_c: Optional[float] = None
    mg2_temp_c: Optional[float] = None
    ev_driving_pct: float = 0.0
    observations: List[str] = field(default_factory=list)


@dataclass
class AutoDetectedVehicleInfo:
    """Plain-English vehicle diagnostic summary aimed at general users with minimal knowledge."""
    vehicle_class: str
    engine_health_grade: str
    battery_health_summary: str
    thermal_condition_summary: str
    fuel_efficiency_grade: str
    fuel_trim_summary: str
    total_sensors_communicated: int
    plain_english_takeaways: List[str] = field(default_factory=list)


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
            dt_hours = 1.0 / 3600.0

            if "fuel_rate_lh" in df.columns:
                fuel_rate = df["fuel_rate_lh"].fillna(0.0)
            elif "fuel_economy_kml" in df.columns:
                fe = df["fuel_economy_kml"].replace(0, np.nan)
                fuel_rate = (speed / fe).fillna(0.0)
            else:
                fuel_rate = pd.Series(0.0, index=df.index)

            dist_step = speed * dt_hours
            fuel_step = fuel_rate * dt_hours

            idle_mask = speed <= self.min_moving_speed
            moving_mask = speed > self.min_moving_speed
            city_mask = (speed > self.min_moving_speed) & (speed <= self.city_speed_max)
            hwy_mask = speed >= self.highway_speed_min

            total_city_dist += float(dist_step[city_mask].sum())
            total_city_fuel += float(fuel_step[city_mask].sum())

            total_hwy_dist += float(dist_step[hwy_mask].sum())
            total_hwy_fuel += float(fuel_step[hwy_mask].sum())

            total_moving_dist += float(dist_step[moving_mask].sum())
            total_moving_fuel += float(fuel_step[moving_mask].sum())

            total_idle_time += float(idle_mask.sum())
            total_moving_time += float(moving_mask.sum())
            total_idle_fuel += float(fuel_step[idle_mask].sum())

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
            if df.empty or "speed_kmh" not in df.columns:
                continue
            moving = df[df["speed_kmh"] > self.min_moving_speed].copy()
            if not moving.empty:
                moving["trip_file"] = trip.file_name
                dfs.append(moving)

        if not dfs:
            return pd.DataFrame()
        return pd.concat(dfs, ignore_index=True)

    def compute_optimal_rpm_speed_curve(
        self, trips: List[ScanTrip], speed_step: float = 5.0, max_gears: Optional[int] = None
    ) -> Dict[str, Any]:
        """Compute optimal RPM vs Speed relationship and gear ratio traces."""
        combined = self.extract_moving_dataset(trips)
        if combined.empty or "engine_rpm" not in combined.columns:
            return {
                "speed": np.array([]),
                "rpm": np.array([]),
                "opt_speed": np.array([]),
                "opt_rpm": np.array([]),
                "gear_lines": [],
            }

        speed = combined["speed_kmh"].values
        rpm = combined["engine_rpm"].values

        valid_idx = (rpm > 500) & (speed > 5.0)
        s_val = speed[valid_idx]
        r_val = rpm[valid_idx]

        if len(s_val) < 20:
            return {
                "speed": s_val,
                "rpm": r_val,
                "opt_speed": s_val,
                "opt_rpm": r_val,
                "gear_lines": [],
            }

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
                median_rpm = float(np.median(sub_rpm))
                opt_speed.append(center_speed)
                opt_rpm.append(median_rpm)

        ratios = s_val / r_val
        counts, bin_edges = np.histogram(ratios, bins=50)
        peaks = []
        for i in range(1, len(counts) - 1):
            if counts[i] > counts[i - 1] and counts[i] > counts[i + 1] and counts[i] > 10:
                peak_ratio = 0.5 * (bin_edges[i] + bin_edges[i + 1])
                peaks.append((int(counts[i]), float(peak_ratio)))

        # Limit to configured gear count (e.g. 4 gears for 4-Speed Auto)
        if max_gears is not None:
            if max_gears <= 0:
                selected_ratios = []
            else:
                top_peaks = sorted(peaks, key=lambda x: x[0], reverse=True)[:max_gears]
                selected_ratios = sorted([r for _, r in top_peaks])
        else:
            top_peaks = sorted(peaks, key=lambda x: x[0], reverse=True)[:5]
            selected_ratios = sorted([r for _, r in top_peaks])

        gear_lines = []
        for idx, ratio in enumerate(selected_ratios):
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
        """Compute optimal fuel economy (km/L) surface as a function of RPM and Speed."""
        combined = self.extract_moving_dataset(trips)
        empty_res = {
            "has_data": False,
            "speed_bins": np.array([]),
            "rpm_bins": np.array([]),
            "fe_matrix": np.array([]),
            "opt_speed": np.array([]),
            "opt_rpm": np.array([]),
            "opt_fe": np.array([]),
            "sweet_spot": None,
            "scatter_speed": np.array([]),
            "scatter_rpm": np.array([]),
            "scatter_fe": np.array([]),
        }

        if combined.empty or "engine_rpm" not in combined.columns:
            return empty_res

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

        valid = (speed > 5.0) & (rpm > 500) & (fe_val > 1.0) & (fe_val < 60.0)
        s = speed[valid]
        r = rpm[valid]
        f = fe_val[valid]

        if len(s) < 30:
            return empty_res

        s_min, s_max = 10.0, float(min(125.0, np.max(s) + 5.0))
        r_min, r_max = 700.0, float(min(4500.0, np.max(r) + 100.0))

        s_bins = np.arange(s_min, s_max + speed_step, speed_step)
        r_bins = np.arange(r_min, r_max + rpm_step, rpm_step)

        matrix = np.full((len(r_bins) - 1, len(s_bins) - 1), np.nan)

        for i in range(len(s_bins) - 1):
            s_low, s_high = s_bins[i], s_bins[i + 1]
            s_mask = (s >= s_low) & (s < s_high)
            for j in range(len(r_bins) - 1):
                r_low, r_high = r_bins[j], r_bins[j + 1]
                cell_mask = s_mask & (r >= r_low) & (r < r_high)
                count = int(np.sum(cell_mask))
                if count >= 3:
                    matrix[j, i] = float(np.median(f[cell_mask]))

        opt_speed = []
        opt_rpm = []
        opt_fe = []

        for i in range(len(s_bins) - 1):
            s_center = 0.5 * (s_bins[i] + s_bins[i + 1])
            s_mask = (s >= s_bins[i]) & (s < s_bins[i + 1])
            if np.sum(s_mask) >= 8:
                sub_r = r[s_mask]
                sub_f = f[s_mask]
                top_cutoff = np.percentile(sub_f, 75)
                top_mask = sub_f >= top_cutoff
                best_rpm = float(np.median(sub_r[top_mask]))
                best_fe = float(np.mean(sub_f[top_mask]))
                opt_speed.append(s_center)
                opt_rpm.append(best_rpm)
                opt_fe.append(best_fe)

        smoothed_matrix = matrix.copy()
        nan_mask = np.isnan(smoothed_matrix)
        if not np.all(nan_mask):
            mean_val = np.nanmean(smoothed_matrix)
            smoothed_matrix[nan_mask] = mean_val
            smoothed_matrix = gaussian_filter(smoothed_matrix, sigma=1.0)
            smoothed_matrix[nan_mask] = np.nan

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

    def analyze_hybrid_powertrain(self, trips: List[ScanTrip]) -> HybridBatteryReport:
        """Analyze hybrid battery state of charge, block voltage balance, and electric drive."""
        has_hybrid = any(t.is_hybrid for t in trips)
        if not has_hybrid:
            return HybridBatteryReport(is_hybrid=False, battery_health_status="NOT HYBRID")

        soc_vals = []
        current_vals = []
        block_voltages: Dict[str, List[float]] = {}
        battery_temps = []
        inverter_temps = []
        mg1_temps = []
        mg2_temps = []
        total_moving_time = 0.0
        ev_moving_time = 0.0

        for trip in trips:
            df = trip.data
            if df.empty:
                continue

            # State of Charge
            if "hv_soc_pct" in df.columns:
                s = df["hv_soc_pct"].dropna()
                if not s.empty:
                    soc_vals.extend(s.values)

            # Battery Pack Current
            if "hv_current_a" in df.columns:
                c = df["hv_current_a"].dropna()
                if not c.empty:
                    current_vals.extend(c.values)

            # Extract individual Block Voltages V01 - V14
            for i in range(1, 15):
                col = f"hv_block_v{i:02d}"
                if col in df.columns:
                    b_vals = df[col].dropna()
                    # Filter valid automotive block voltages (10V to 20V)
                    valid_b = b_vals[(b_vals >= 10.0) & (b_vals <= 22.0)]
                    if not valid_b.empty:
                        b_key = f"Block {i:02d}"
                        if b_key not in block_voltages:
                            block_voltages[b_key] = []
                        block_voltages[b_key].extend(valid_b.values)

            # Thermal sensors
            if "hv_batt_temp_c" in df.columns:
                battery_temps.extend(df["hv_batt_temp_c"].dropna().values)
            if "inverter_temp_c" in df.columns:
                inverter_temps.extend(df["inverter_temp_c"].dropna().values)
            if "inverter_mg1_temp_c" in df.columns:
                mg1_temps.extend(df["inverter_mg1_temp_c"].dropna().values)
            if "inverter_mg2_temp_c" in df.columns:
                mg2_temps.extend(df["inverter_mg2_temp_c"].dropna().values)

            # Calculate EV Driving Mode percentage
            if "speed_kmh" in df.columns:
                moving = df[df["speed_kmh"] > 1.0]
                total_moving_time += len(moving)
                # EV mode: moving with engine off (RPM == 0 or fuel_rate == 0)
                if "engine_rpm" in moving.columns:
                    ev_pts = moving[(moving["engine_rpm"] < 300) | (moving.get("fuel_rate_lh", 0.0) <= 0.05)]
                    ev_moving_time += len(ev_pts)

        # Average block voltages
        mean_blocks: Dict[str, float] = {}
        for b_name, vals in sorted(block_voltages.items()):
            if vals:
                mean_blocks[b_name] = float(np.mean(vals))

        max_bv = max(mean_blocks.values()) if mean_blocks else None
        min_bv = min(mean_blocks.values()) if mean_blocks else None
        delta_bv = (max_bv - min_bv) if (max_bv is not None and min_bv is not None) else None

        # Determine battery cell balance status
        observations = []
        if delta_bv is not None:
            if delta_bv < 0.20:
                health_status = "[OPTIMAL] Strong Balance"
                observations.append(f"Hybrid battery block voltage delta is {delta_bv * 1000:.0f} mV (nominal is < 200 mV).")
            elif delta_bv < 0.40:
                health_status = "[WARNING] Mild Imbalance"
                observations.append(f"Hybrid battery block delta is elevated at {delta_bv * 1000:.0f} mV. Cell reconditioning advised.")
            else:
                health_status = "[CRITICAL] Severe Degradation"
                observations.append(f"Critical cell block voltage delta ({delta_bv:.2f} V). Risk of hybrid system shutdown / DTC P0A80.")
        else:
            health_status = "[STANDBY] No Block Voltages"

        soc_mean = float(np.mean(soc_vals)) if soc_vals else None
        soc_min = float(np.min(soc_vals)) if soc_vals else None
        soc_max = float(np.max(soc_vals)) if soc_vals else None
        delta_soc = (soc_max - soc_min) if (soc_max is not None and soc_min is not None) else None

        ev_pct = (ev_moving_time / total_moving_time * 100.0) if total_moving_time > 0 else 0.0
        if ev_pct > 0:
            observations.append(f"EV Electric Driving Ratio: {ev_pct:.1f}% of total driving distance executed with engine off.")

        return HybridBatteryReport(
            is_hybrid=True,
            soc_mean=soc_mean,
            soc_min=soc_min,
            soc_max=soc_max,
            delta_soc=delta_soc,
            current_a_mean=float(np.mean(current_vals)) if current_vals else None,
            max_charge_a=float(np.min(current_vals)) if current_vals else None,
            max_discharge_a=float(np.max(current_vals)) if current_vals else None,
            block_voltages=mean_blocks,
            max_block_v=max_bv,
            min_block_v=min_bv,
            delta_block_v=delta_bv,
            battery_health_status=health_status,
            battery_temp_c=float(np.mean(battery_temps)) if battery_temps else None,
            inverter_temp_c=float(np.mean(inverter_temps)) if inverter_temps else None,
            mg1_temp_c=float(np.mean(mg1_temps)) if mg1_temps else None,
            mg2_temp_c=float(np.mean(mg2_temps)) if mg2_temps else None,
            ev_driving_pct=ev_pct,
            observations=observations,
        )

    def auto_detect_vehicle_info(self, trips: List[ScanTrip]) -> AutoDetectedVehicleInfo:
        """Automatically infer vehicle class and health for general users without requiring inputs."""
        if not trips:
            return AutoDetectedVehicleInfo(
                vehicle_class="No Data",
                engine_health_grade="N/A",
                battery_health_summary="No Scan Data",
                thermal_condition_summary="N/A",
                fuel_efficiency_grade="N/A",
                fuel_trim_summary="N/A",
                total_sensors_communicated=0,
                plain_english_takeaways=["Load one or more scan records to generate vehicle intelligence."],
            )

        # Detect vehicle type
        is_hybrid = any(t.is_hybrid for t in trips)
        vehicle_class = "Hybrid Electric Vehicle (HEV)" if is_hybrid else "Conventional Fuel Vehicle (ICE)"

        # Sensors count
        all_pids = set()
        for t in trips:
            all_pids.update(t.pids_found)

        # Battery 12V
        diag = self.generate_diagnostic_health(trips)
        b_summary = f"{diag.battery_status} (Avg {diag.battery_mean_v:.1f}V)"

        # Thermal
        thermal = self.analyze_coolant_temperature(trips)
        if thermal["has_data"]:
            t_summary = f"Peak {thermal['max_temp']:.0f} C (Normal thermostat range is 82-95 C)"
        else:
            t_summary = "Temperature sensor not recorded"

        # Fuel economy
        fe = self.calculate_fuel_economy(trips)
        comb_str = fe.format_value("combined", "km/L")
        if comb_str != "-":
            c_val = float(comb_str)
            if c_val >= 18.0:
                fe_grade = f"{comb_str} km/L (Excellent Efficiency)"
            elif c_val >= 13.0:
                fe_grade = f"{comb_str} km/L (Good Efficiency)"
            else:
                fe_grade = f"{comb_str} km/L (Moderate Efficiency)"
        else:
            fe_grade = "Insufficient driving data"

        # Hybrid specific
        hybrid_rep = self.analyze_hybrid_powertrain(trips)

        # Plain English takeaways
        takeaways = []
        if is_hybrid:
            takeaways.append(f"Powertrain: Verified Hybrid Electric Vehicle with {len(hybrid_rep.block_voltages)} monitored battery blocks.")
            if hybrid_rep.delta_block_v is not None:
                takeaways.append(f"Hybrid Battery Condition: {hybrid_rep.battery_health_status} with {hybrid_rep.delta_block_v * 1000:.0f} mV cell variance.")
            if hybrid_rep.ev_driving_pct > 0:
                takeaways.append(f"Electric Driving: Vehicle drove {hybrid_rep.ev_driving_pct:.0f}% of the trip purely on electric power.")
        else:
            takeaways.append("Powertrain: Standard Internal Combustion Engine (ICE).")

        takeaways.append(f"12V Auxiliary System: Alternator and battery registered at {diag.battery_mean_v:.1f}V.")
        if thermal["has_data"] and thermal["max_temp"] <= 98:
            takeaways.append(f"Engine Cooling: Engine reached healthy operating temperature ({thermal['max_temp']:.0f} C) with no overheating.")
        takeaways.append(f"Overall Fuel Economy: Averaged {fe.format_value('combined', 'km/L')} km/L across {fe.total_distance_km:.1f} km.")

        return AutoDetectedVehicleInfo(
            vehicle_class=vehicle_class,
            engine_health_grade="Good" if diag.coolant_status != "OVERHEATING" else "Attention Required",
            battery_health_summary=b_summary,
            thermal_condition_summary=t_summary,
            fuel_efficiency_grade=fe_grade,
            fuel_trim_summary=diag.fuel_trim_status,
            total_sensors_communicated=len(all_pids),
            plain_english_takeaways=takeaways,
        )

    def analyze_fuel_trims_in_depth(self, trips: List[ScanTrip]) -> FuelTrimDiagnostic:
        """Analyze Short Term and Long Term Fuel Trims across engine operating zones."""
        stft_all, ltft_all = [], []
        idle_stft, idle_ltft = [], []
        cruise_stft, cruise_ltft = [], []
        high_stft, high_ltft = [], []

        for trip in trips:
            df = trip.data
            if df.empty or "stft_pct" not in df.columns or "ltft_pct" not in df.columns:
                continue

            valid = df.dropna(subset=["stft_pct", "ltft_pct"])
            if valid.empty:
                continue

            stft_all.extend(valid["stft_pct"].values)
            ltft_all.extend(valid["ltft_pct"].values)

            speed = valid["speed_kmh"] if "speed_kmh" in valid.columns else pd.Series(0.0, index=valid.index)
            rpm = valid["engine_rpm"] if "engine_rpm" in valid.columns else pd.Series(1000.0, index=valid.index)
            load = valid["engine_load_pct"] if "engine_load_pct" in valid.columns else pd.Series(30.0, index=valid.index)

            idle_mask = (rpm < 1050) & (speed <= 3.0)
            if np.any(idle_mask):
                idle_stft.extend(valid.loc[idle_mask, "stft_pct"].values)
                idle_ltft.extend(valid.loc[idle_mask, "ltft_pct"].values)

            cruise_mask = (rpm >= 1200) & (rpm <= 2600) & (speed > 20.0) & (load <= 60.0)
            if np.any(cruise_mask):
                cruise_stft.extend(valid.loc[cruise_mask, "stft_pct"].values)
                cruise_ltft.extend(valid.loc[cruise_mask, "ltft_pct"].values)

            high_mask = load > 60.0
            if np.any(high_mask):
                high_stft.extend(valid.loc[high_mask, "stft_pct"].values)
                high_ltft.extend(valid.loc[high_mask, "ltft_pct"].values)

        if not stft_all:
            return FuelTrimDiagnostic(
                has_data=False,
                diagnosis_title="NO FUEL TRIM SENSORS FOUND",
                severity="INFO",
                likelihood_score="NONE",
                probable_causes=["Vehicle ECU does not support Bank 1 Short/Long Term Fuel Trim PIDs."],
                mechanic_recommendations=["Verify OBD-II protocol connection or scanner PID permissions."],
            )

        mean_stft = float(np.mean(stft_all))
        mean_ltft = float(np.mean(ltft_all))
        mean_tot = mean_stft + mean_ltft

        m_idle_stft = float(np.mean(idle_stft)) if idle_stft else None
        m_idle_ltft = float(np.mean(idle_ltft)) if idle_ltft else None
        m_idle_tot = (m_idle_stft + m_idle_ltft) if (m_idle_stft is not None and m_idle_ltft is not None) else None

        m_cr_stft = float(np.mean(cruise_stft)) if cruise_stft else None
        m_cr_ltft = float(np.mean(cruise_ltft)) if cruise_ltft else None
        m_cr_tot = (m_cr_stft + m_cr_ltft) if (m_cr_stft is not None and m_cr_ltft is not None) else None

        m_hi_stft = float(np.mean(high_stft)) if high_stft else None
        m_hi_ltft = float(np.mean(high_ltft)) if high_ltft else None
        m_hi_tot = (m_hi_stft + m_hi_ltft) if (m_hi_stft is not None and m_hi_ltft is not None) else None

        probable_causes = []
        recommendations = []

        if m_idle_tot is not None and m_idle_tot > 10.0 and (m_cr_tot is None or m_idle_tot - m_cr_tot >= 5.0):
            diagnosis_title = "INTAKE VACUUM LEAK SUSPECTED"
            severity = "CRITICAL"
            likelihood_score = "HIGH"
            probable_causes = [
                "Unmetered air entering post-MAF (intake manifold gasket, vacuum line rupture).",
                "Faulty Positive Crankcase Ventilation (PCV) valve or cracked hose.",
                "Leaking brake booster check valve or diaphragm.",
            ]
            recommendations = [
                "Step 1: Perform an automotive smoke test on the intake plenum and vacuum lines.",
                "Step 2: Inspect PCV valve for sticking and check PCV rubber elbow for softening or cracks.",
                "Step 3: Clamp the brake booster vacuum hose while monitoring live STFT; if trim normalizes, replace booster.",
            ]
        elif (m_cr_tot is not None and m_cr_tot > 10.0) or (m_hi_tot is not None and m_hi_tot > 12.0) or mean_tot > 10.0:
            diagnosis_title = "FUEL STARVATION / LOW SYSTEM DELIVERY"
            severity = "CRITICAL"
            likelihood_score = "HIGH"
            probable_causes = [
                "Weak in-tank fuel pump failing to maintain pressure under demand.",
                "Restricted inline fuel filter or dirty fuel pump strainer sock.",
                "Contaminated Mass Air Flow (MAF) sensor under-reporting air mass.",
            ]
            recommendations = [
                "Step 1: Connect mechanical fuel pressure gauge to fuel rail; measure static and load pressure.",
                "Step 2: Clean MAF sensor heated sensing wire using specialized MAF aerosol.",
                "Step 3: Replace inline fuel filter if past service interval (> 40,000 km).",
            ]
        elif mean_tot < -10.0 or (m_idle_tot is not None and m_idle_tot < -10.0):
            diagnosis_title = "SYSTEM RUNNING RICH (OVER-FUELING)"
            severity = "WARNING"
            likelihood_score = "HIGH"
            probable_causes = [
                "Stuck-open or leaking fuel injector dripping uncommanded fuel into cylinder.",
                "Faulty fuel pressure regulator (diaphragm ruptured or high return restriction).",
                "EVAP canister purge solenoid stuck open drawing fuel vapor continuously.",
            ]
            recommendations = [
                "Step 1: Inspect spark plugs for wet black carbon fouling.",
                "Step 2: Disconnect EVAP purge line and cap intake port; observe if STFT climbs back to zero.",
                "Step 3: Check fuel rail pressure regulator vacuum reference hose for presence of liquid fuel.",
            ]
        elif abs(mean_tot) > 7.0:
            diagnosis_title = "MARGINAL CLOSED-LOOP TRIM"
            severity = "WARNING"
            likelihood_score = "MODERATE"
            probable_causes = [
                "Minor aging of pre-catalytic Oxygen / Air-Fuel Ratio (AFR) sensor.",
                "Slight intake manifold seal wear or mild throttle body carbon buildup.",
            ]
            recommendations = [
                "Step 1: Clean throttle body bore and perform electronic throttle relearn.",
                "Step 2: Monitor upstream O2 sensor switching frequency on oscilloscope or live scanner graph.",
            ]
        else:
            diagnosis_title = "OPTIMAL CLOSED-LOOP REGULATION"
            severity = "OPTIMAL"
            likelihood_score = "LOW"
            probable_causes = ["Fuel management and air metering operating within original manufacturer tolerances."]
            recommendations = [
                "System is balanced. Total fuel trim is well within +/- 7% standard factory boundary.",
                "No mechanical or electronic fuel intervention required at this time.",
            ]

        return FuelTrimDiagnostic(
            has_data=True,
            mean_stft=mean_stft,
            mean_ltft=mean_ltft,
            mean_total_trim=mean_tot,
            idle_stft=m_idle_stft,
            idle_ltft=m_idle_ltft,
            idle_total_trim=m_idle_tot,
            cruise_stft=m_cr_stft,
            cruise_ltft=m_cr_ltft,
            cruise_total_trim=m_cr_tot,
            high_load_stft=m_hi_stft,
            high_load_ltft=m_hi_ltft,
            high_load_total_trim=m_hi_tot,
            diagnosis_title=diagnosis_title,
            severity=severity,
            likelihood_score=likelihood_score,
            probable_causes=probable_causes,
            mechanic_recommendations=recommendations,
        )

    def detect_anomalies(self, trips: List[ScanTrip]) -> List[TelemetryAnomaly]:
        """Detect rule-based and multivariate ML anomalies across all selected trips."""
        anomalies: List[TelemetryAnomaly] = []

        for trip in trips:
            df = trip.data
            if df.empty:
                continue

            speed = df["speed_kmh"] if "speed_kmh" in df.columns else pd.Series(0.0, index=df.index)
            rpm = df["engine_rpm"] if "engine_rpm" in df.columns else pd.Series(0.0, index=df.index)
            volt = df["voltage_v"] if "voltage_v" in df.columns else pd.Series(np.nan, index=df.index)
            temp = df["coolant_temp_c"] if "coolant_temp_c" in df.columns else pd.Series(np.nan, index=df.index)
            stft = df["stft_pct"] if "stft_pct" in df.columns else pd.Series(0.0, index=df.index)
            ltft = df["ltft_pct"] if "ltft_pct" in df.columns else pd.Series(0.0, index=df.index)
            fuel_rate = df["fuel_rate_lh"] if "fuel_rate_lh" in df.columns else pd.Series(0.0, index=df.index)

            # Rule 1: Alternator Undercharging (< 12.2V while running)
            running_mask = (rpm > 650) & volt.notna() & (volt < 12.2)
            if np.any(running_mask):
                for idx in df[running_mask].index[:3]:
                    t_sec = float(idx)
                    v_val = float(volt.loc[idx])
                    anomalies.append(TelemetryAnomaly(
                        timestamp_sec=t_sec,
                        timestamp_min=t_sec / 60.0,
                        category="[ELECTRICAL]",
                        severity="[CRITICAL]",
                        metric_name="12V System Voltage",
                        detected_value=f"{v_val:.1f} V",
                        expected_range="13.5 - 14.8 V",
                        description="Battery voltage dropped below 12.2V while engine running. Alternator undercharging or battery failing.",
                        trip_file=trip.file_name,
                    ))

            # Rule 2: Voltage Spike (> 15.2V)
            overvolt_mask = volt.notna() & (volt > 15.2)
            if np.any(overvolt_mask):
                for idx in df[overvolt_mask].index[:2]:
                    t_sec = float(idx)
                    v_val = float(volt.loc[idx])
                    anomalies.append(TelemetryAnomaly(
                        timestamp_sec=t_sec,
                        timestamp_min=t_sec / 60.0,
                        category="[ELECTRICAL]",
                        severity="[CRITICAL]",
                        metric_name="12V System Voltage",
                        detected_value=f"{v_val:.1f} V",
                        expected_range="13.5 - 14.8 V",
                        description="Voltage regulator spike above 15.2V. High risk of electrical ECU/battery damage.",
                        trip_file=trip.file_name,
                    ))

            # Rule 3: Coolant Overheat (> 100 C)
            overheat_mask = temp.notna() & (temp >= 100.0)
            if np.any(overheat_mask):
                for idx in df[overheat_mask].index[:3]:
                    t_sec = float(idx)
                    c_val = float(temp.loc[idx])
                    anomalies.append(TelemetryAnomaly(
                        timestamp_sec=t_sec,
                        timestamp_min=t_sec / 60.0,
                        category="[THERMAL]",
                        severity="[CRITICAL]",
                        metric_name="Engine Coolant Temperature",
                        detected_value=f"{c_val:.1f} C",
                        expected_range="82 - 95 C",
                        description="Coolant exceeded 100 C. Check cooling fan operation, thermostat, and coolant level.",
                        trip_file=trip.file_name,
                    ))

            # Rule 4: Extreme Fuel Trim Spike (> +18% or < -18%)
            total_trim = stft + ltft
            trim_lean_mask = total_trim > 18.0
            if np.any(trim_lean_mask):
                for idx in df[trim_lean_mask].index[:3]:
                    t_sec = float(idx)
                    trim_val = float(total_trim.loc[idx])
                    anomalies.append(TelemetryAnomaly(
                        timestamp_sec=t_sec,
                        timestamp_min=t_sec / 60.0,
                        category="[FUEL TRIM]",
                        severity="[WARNING]",
                        metric_name="Total Fuel Trim (STFT+LTFT)",
                        detected_value=f"{trim_val:+.1f}%",
                        expected_range="-7% to +7%",
                        description="Severe positive fuel trim surge. Fuel delivery deficit or sudden intake vacuum leak.",
                        trip_file=trip.file_name,
                    ))

            # Rule 5: Speed Sensor Dropout (RPM > 1800, Load > 30%, Speed == 0)
            dropout_mask = (rpm > 1800) & (fuel_rate > 3.0) & (speed == 0.0)
            if np.any(dropout_mask):
                for idx in df[dropout_mask].index[:2]:
                    t_sec = float(idx)
                    anomalies.append(TelemetryAnomaly(
                        timestamp_sec=t_sec,
                        timestamp_min=t_sec / 60.0,
                        category="[DRIVETRAIN]",
                        severity="[WARNING]",
                        metric_name="Speed / RPM Coherence",
                        detected_value="0.0 km/h @ high RPM",
                        expected_range="> 15 km/h",
                        description="Vehicle speed sensor (VSS) signal dropped to 0 km/h under load, or severe clutch/transmission slip.",
                        trip_file=trip.file_name,
                    ))

            # Rule 6: Machine Learning Multivariate Anomaly Detection (Isolation Forest)
            ml_cols = []
            for col in ["speed_kmh", "engine_rpm", "fuel_rate_lh", "coolant_temp_c", "voltage_v", "map_kpa"]:
                if col in df.columns:
                    ml_cols.append(col)

            if len(ml_cols) >= 3 and len(df) >= 60:
                try:
                    feat_data = df[ml_cols].copy().interpolate().bfill().ffill()
                    iso = IsolationForest(contamination=0.01, random_state=42, n_estimators=50)
                    preds = iso.fit_predict(feat_data)
                    outlier_indices = df.index[preds == -1]

                    for o_idx in outlier_indices[:2]:
                        t_sec = float(o_idx)
                        anomalies.append(TelemetryAnomaly(
                            timestamp_sec=t_sec,
                            timestamp_min=t_sec / 60.0,
                            category="[ML OUTLIER]",
                            severity="[INFO]",
                            metric_name="Multivariate Telemetry Signature",
                            detected_value="Statistical Outlier",
                            expected_range="Nominal Cluster",
                            description="Isolation Forest detected atypical sensor state correlation (unusual speed, load, and fuel rate combination).",
                            trip_file=trip.file_name,
                        ))
                except Exception:
                    pass

        return anomalies

    def generate_diagnostic_health(self, trips: List[ScanTrip]) -> DiagnosticHealthReport:
        """Evaluate OBD-II health indicators: battery voltage, fuel trims, coolant, and load."""
        notes = []

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

        stft_vals, ltft_vals = [], []
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
                notes.append("Total fuel trim is high positive. Suspect unmetered vacuum leak or weak fuel delivery.")
            elif total_trim < -12.0:
                fuel_trim_status = "RICH RUNNING (< -12%)"
                notes.append("Total fuel trim is negative. Suspect leaky injector, high fuel pressure, or restricted intake.")
            elif abs(total_trim) > 7.0:
                fuel_trim_status = "MARGINAL TRIM (7% - 12%)"
            else:
                fuel_trim_status = "NORMAL TRIM (< +/- 7%)"
        else:
            fuel_trim_status = "NO DATA"

        all_loads, all_maps, all_speeds, all_rpms = [], [], [], []
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
