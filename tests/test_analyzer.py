"""Automated test suite for OBD-II Telemetry Suit.

Tests data loader parsing, pre-ingestion cleanup, fuel economy metrics,
fallback behavior, RPM curves, efficiency maps, deep STFT/LTFT diagnostics,
hybrid battery & powertrain analysis, auto-detection vehicle info,
and XML session saving and loading.
Strictly adheres to project rules: no emojis.
"""

import os
import tempfile
import unittest
import numpy as np

from src.data_loader import parse_obd_csv, load_all_records, clean_raw_obd_data
from src.analyzer import (
    VehicleAnalyzer,
    FuelEconomyResult,
    DFCOAnalysisResult,
    DiagnosticHealthReport,
    FuelTrimDiagnostic,
    HybridBatteryReport,
    AutoDetectedVehicleInfo,
    TelemetryAnomaly,
)
from src.session_manager import (
    VehicleProfile,
    save_session_to_xml,
    load_session_from_xml,
)


class TestOBDDataLoader(unittest.TestCase):
    """Test data loader, cleanup engine, and synchronization routines."""

    def test_parse_single_csv(self):
        sample_file = "Records/exported_records (6)/2026-09-08 09-19-22.csv"
        self.assertTrue(os.path.exists(sample_file), f"File {sample_file} not found.")

        trip = parse_obd_csv(sample_file)
        self.assertIsNotNone(trip)
        self.assertGreater(trip.total_raw_rows, 1000)
        self.assertGreater(trip.duration_seconds, 100)
        self.assertIn("speed_kmh", trip.data.columns)
        self.assertIn("engine_rpm", trip.data.columns)

    def test_pre_ingestion_cleanup_report(self):
        sample_file = "Records/exported_records (6)/2026-09-08 09-19-22.csv"
        trip = parse_obd_csv(sample_file)
        self.assertIsNotNone(trip)
        rep = trip.cleanup_report

        self.assertGreater(rep.total_raw_rows, 0)
        self.assertEqual(rep.valid_rows_retained, rep.total_raw_rows)

    def test_load_records_directory(self):
        trips = load_all_records("Records/exported_records (6)")
        self.assertEqual(len(trips), 8)
        file_paths = [t.file_path for t in trips]
        self.assertEqual(len(file_paths), len(set(file_paths)))
        for t in trips:
            self.assertGreater(len(t.data), 0)


class TestVehicleAnalyzer(unittest.TestCase):
    """Test automotive analysis algorithms and edge cases."""

    def setUp(self):
        self.analyzer = VehicleAnalyzer(city_speed_max=45.0, highway_speed_min=70.0)
        self.trips = load_all_records("Records/exported_records (6)")

    def test_fuel_economy_calculation(self):
        fe = self.analyzer.calculate_fuel_economy(self.trips)
        self.assertIsNotNone(fe.city_kml)
        self.assertIsNotNone(fe.highway_kml)
        self.assertIsNotNone(fe.combined_kml)

        self.assertGreater(fe.city_kml, 5.0)
        self.assertLess(fe.city_kml, 30.0)
        self.assertGreater(fe.highway_kml, 8.0)
        self.assertLess(fe.highway_kml, 40.0)

    def test_insufficient_highway_data_fallback(self):
        trip = parse_obd_csv("Records/exported_records (6)/2026-09-08 09-19-22.csv")
        fe = self.analyzer.calculate_fuel_economy([trip])

        self.assertIsNotNone(fe.city_kml)
        self.assertIsNone(fe.highway_kml)
        self.assertEqual(fe.format_value("highway", "km/L"), "-")
        self.assertNotEqual(fe.format_value("city", "km/L"), "-")

    def test_unit_conversions(self):
        res = FuelEconomyResult(
            city_kml=10.0,
            highway_kml=20.0,
            combined_kml=12.5,
            total_distance_km=100.0,
            total_fuel_liters=8.0,
            city_distance_km=50.0,
            city_fuel_liters=5.0,
            highway_distance_km=50.0,
            highway_fuel_liters=2.5,
            idle_time_seconds=300.0,
            moving_time_seconds=3600.0,
            idle_fuel_liters=0.5,
            idle_percentage=7.7,
            avg_moving_speed_kmh=50.0,
        )

        self.assertEqual(res.get_value("city", "km/L"), 10.0)
        self.assertAlmostEqual(res.get_value("city", "L/100km"), 10.0, places=2)
        self.assertAlmostEqual(res.get_value("highway", "L/100km"), 5.0, places=2)
        self.assertAlmostEqual(res.get_value("city", "MPG (US)"), 23.52, places=1)
        self.assertEqual(res.format_value("city", "km/L"), "10.00")

    def test_optimal_rpm_speed_curve(self):
        res = self.analyzer.compute_optimal_rpm_speed_curve(self.trips)
        self.assertIn("opt_speed", res)
        self.assertIn("opt_rpm", res)
        self.assertGreater(len(res["opt_speed"]), 0)
        self.assertTrue(np.all(np.diff(res["opt_speed"]) > 0))

    def test_optimal_fuel_economy_map(self):
        fe_map = self.analyzer.compute_optimal_fuel_economy_rpm_speed_curve(self.trips)
        self.assertTrue(fe_map["has_data"])
        self.assertIsNotNone(fe_map["sweet_spot"])
        sp = fe_map["sweet_spot"]
        self.assertGreater(sp["speed_kmh"], 20.0)
        self.assertGreater(sp["rpm"], 600.0)
        self.assertGreater(sp["fe_kml"], 5.0)
        # Verify realistic fuel economy bound under tractive cruise (max < 25.0 km/L)
        self.assertLess(sp["fe_kml"], 25.0)
        self.assertIn("ml_curve_speed", fe_map)
        self.assertIn("ml_curve_fe", fe_map)
        self.assertIn("dfco_result", fe_map)

    def test_dfco_diagnostics_and_detection(self):
        dfco_res = self.analyzer.analyze_dfco(self.trips)
        self.assertTrue(dfco_res.has_data)
        self.assertGreater(dfco_res.eligible_decel_seconds, 0)
        self.assertGreater(dfco_res.active_dfco_seconds, 0)
        self.assertGreater(dfco_res.inactive_dfco_seconds, 0)
        self.assertGreater(dfco_res.dfco_engagement_pct, 0.0)
        self.assertLessEqual(dfco_res.dfco_engagement_pct, 100.0)
        self.assertGreater(dfco_res.fuel_saved_liters, 0.0)
        self.assertIn(dfco_res.status, ["[OPTIMAL]", "[GOOD]", "[PARTIAL]", "[INACTIVE]"])
        self.assertTrue(len(dfco_res.diagnostic_summary) > 0)

    def test_coolant_thermal_analysis(self):
        thermal = self.analyzer.analyze_coolant_temperature(self.trips)
        self.assertTrue(thermal["has_data"])
        self.assertGreater(thermal["max_temp"], 70.0)
        self.assertLess(thermal["max_temp"], 115.0)

    def test_deep_fuel_trim_diagnostics_and_recommendations(self):
        td = self.analyzer.analyze_fuel_trims_in_depth(self.trips)
        self.assertTrue(td.has_data)
        self.assertIsNotNone(td.diagnosis_title)
        self.assertIsNotNone(td.severity)
        self.assertIn(td.severity, ["OPTIMAL", "WARNING", "CRITICAL"])
        self.assertGreater(len(td.mechanic_recommendations), 0)
        self.assertIsNotNone(td.mean_total_trim)

    def test_anomaly_detection_engine(self):
        anomalies = self.analyzer.detect_anomalies(self.trips)
        self.assertIsInstance(anomalies, list)
        self.assertGreater(len(anomalies), 0)
        for a in anomalies:
            self.assertIn(a.severity, ["[CRITICAL]", "[WARNING]", "[INFO]"])
            self.assertIsNotNone(a.metric_name)
            self.assertIsNotNone(a.detected_value)
            self.assertIsNotNone(a.description)


class TestHybridAndAutoDetect(unittest.TestCase):
    """Test hybrid battery analysis and automated vehicle intelligence."""

    def setUp(self):
        self.analyzer = VehicleAnalyzer()
        self.hybrid_trips = load_all_records("Records/exported_records (2)")

    def test_hybrid_powertrain_analysis(self):
        self.assertGreater(len(self.hybrid_trips), 0)
        rep = self.analyzer.analyze_hybrid_powertrain(self.hybrid_trips)

        self.assertTrue(rep.is_hybrid)
        self.assertIsNotNone(rep.soc_mean)
        self.assertGreater(rep.soc_mean, 20.0)
        self.assertLess(rep.soc_mean, 90.0)
        self.assertIsNotNone(rep.delta_block_v)
        self.assertLess(rep.delta_block_v, 1.0)
        self.assertIn("Block 01", rep.block_voltages)
        self.assertIn("Block 10", rep.block_voltages)
        self.assertEqual(len(rep.block_voltages), 10)
        self.assertIn("[OPTIMAL]", rep.battery_health_status)

    def test_auto_detect_vehicle_info_hybrid(self):
        info = self.analyzer.auto_detect_vehicle_info(self.hybrid_trips)
        self.assertIn("Hybrid Electric Vehicle", info.vehicle_class)
        self.assertGreater(info.total_sensors_communicated, 20)
        self.assertGreater(len(info.plain_english_takeaways), 2)

    def test_auto_detect_vehicle_info_ice(self):
        ice_trips = load_all_records("Records/exported_records (6)")
        info = self.analyzer.auto_detect_vehicle_info(ice_trips)
        self.assertIn("Conventional Fuel Vehicle (ICE)", info.vehicle_class)
        self.assertGreater(len(info.plain_english_takeaways), 2)


class TestSessionManager(unittest.TestCase):
    """Test XML session persistence and vehicle profile serialization."""

    def test_save_and_load_xml_session(self):
        profile = VehicleProfile(
            make="Toyota",
            model="Aqua",
            year="2015",
            engine_type="Hybrid Petrol",
            displacement_cc="1500",
            transmission="e-CVT",
            gears="1",
            tyre_size="175/65R15",
            fuel_tank_l="36",
            notes="1NZ-FXE Atkinson cycle",
        )
        data_paths = [
            os.path.abspath("Records/exported_records (2)/2026-07-27 11-46-24.csv")
        ]

        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            saved = save_session_to_xml(
                file_path=tmp_path,
                profile=profile,
                city_threshold=42.0,
                highway_threshold=68.0,
                unit="MPG (US)",
                data_file_paths=data_paths,
            )
            self.assertTrue(saved)

            loaded = load_session_from_xml(tmp_path)
            self.assertIsNotNone(loaded)
            loaded_prof, loaded_settings, loaded_files = loaded

            self.assertEqual(loaded_prof.make, "Toyota")
            self.assertEqual(loaded_prof.model, "Aqua")
            self.assertEqual(loaded_prof.year, "2015")
            self.assertEqual(loaded_prof.engine_type, "Hybrid Petrol")
            self.assertEqual(loaded_prof.displacement_cc, "1500")
            self.assertEqual(loaded_prof.transmission, "e-CVT")
            self.assertEqual(loaded_prof.tyre_size, "175/65R15")
            self.assertEqual(loaded_prof.fuel_tank_l, "36")
            self.assertEqual(loaded_prof.notes, "1NZ-FXE Atkinson cycle")

            self.assertEqual(loaded_settings["city_threshold"], 42.0)
            self.assertEqual(loaded_settings["highway_threshold"], 68.0)
            self.assertEqual(loaded_settings["unit"], "MPG (US)")

            self.assertEqual(len(loaded_files), 1)
            self.assertEqual(loaded_files[0], data_paths[0])
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_vehicle_profile_gears_and_configured(self):
        p1 = VehicleProfile(gears="4-Speed Auto")
        self.assertEqual(p1.forward_gears, 4)
        self.assertFalse(p1.is_configured)

        p2 = VehicleProfile(make="Mazda", model="3", gears="6-Speed Manual")
        self.assertEqual(p2.forward_gears, 6)
        self.assertTrue(p2.is_configured)

        p3 = VehicleProfile(gears="e-CVT (Hybrid)")
        self.assertEqual(p3.forward_gears, 1)


class TestGearsAndVersioning(unittest.TestCase):
    """Test gear constraint logic and version management."""

    def test_optimal_rpm_speed_curve_max_gears_constraint(self):
        analyzer = VehicleAnalyzer()
        trips = load_all_records("Records/exported_records (6)")
        res_4 = analyzer.compute_optimal_rpm_speed_curve(trips, max_gears=4)
        self.assertLessEqual(len(res_4["gear_lines"]), 4)

        res_5 = analyzer.compute_optimal_rpm_speed_curve(trips, max_gears=5)
        self.assertLessEqual(len(res_5["gear_lines"]), 5)

    def test_version_helpers(self):
        from src.version import parse_semver, is_version_newer, get_app_version
        v = get_app_version()
        self.assertIsNotNone(v)
        self.assertTrue(v.startswith("0."))
        self.assertTrue(is_version_newer("0.3.0", "0.2.0-beta"))
        self.assertFalse(is_version_newer("0.1.0", "0.2.0-beta"))
        self.assertFalse(is_version_newer("0.2.0-beta", "0.2.0-beta"))


if __name__ == "__main__":
    unittest.main()
