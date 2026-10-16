"""Automated test suite for OBD-II vehicle scan analyzer.

Tests data loader parsing, pre-ingestion cleanup, GPS jump filtering,
fuel economy metrics, fallback behavior, RPM curves, efficiency maps,
deep STFT/LTFT diagnostics with repair plans, and anomaly detection.
Strictly adheres to project rules: no emojis.
"""

import os
import unittest
import numpy as np
import pandas as pd

from src.data_loader import parse_obd_csv, load_all_records, clean_raw_obd_data
from src.analyzer import (
    VehicleAnalyzer,
    FuelEconomyResult,
    DiagnosticHealthReport,
    FuelTrimDiagnostic,
    TelemetryAnomaly,
)


class TestOBDDataLoader(unittest.TestCase):
    """Test data loader, cleanup engine, and synchronization routines."""

    def test_parse_single_csv(self):
        sample_file = "Records/2026-09-08 09-19-22.csv"
        self.assertTrue(os.path.exists(sample_file), f"File {sample_file} not found.")

        trip = parse_obd_csv(sample_file)
        self.assertIsNotNone(trip)
        self.assertGreater(trip.total_raw_rows, 1000)
        self.assertGreater(trip.duration_seconds, 100)
        self.assertIn("speed_kmh", trip.data.columns)
        self.assertIn("engine_rpm", trip.data.columns)
        self.assertTrue(trip.has_gps)
        self.assertIn("latitude", trip.data.columns)
        self.assertIn("longitude", trip.data.columns)

    def test_pre_ingestion_cleanup_report(self):
        sample_file = "Records/2026-09-08 09-19-22.csv"
        trip = parse_obd_csv(sample_file)
        self.assertIsNotNone(trip)
        rep = trip.cleanup_report

        self.assertGreater(rep.total_raw_rows, 0)
        self.assertEqual(rep.valid_rows_retained, rep.total_raw_rows)
        # GPS jumps should have been detected and cleaned
        self.assertGreater(rep.gps_jumps_filtered, 0)

    def test_load_all_records(self):
        trips = load_all_records("Records")
        self.assertGreaterEqual(len(trips), 8)
        for t in trips:
            self.assertGreater(len(t.data), 0)
            self.assertTrue(t.has_gps)
            self.assertGreater(len(t.gps_coordinates), 0)


class TestVehicleAnalyzer(unittest.TestCase):
    """Test automotive analysis algorithms and edge cases."""

    def setUp(self):
        self.analyzer = VehicleAnalyzer(city_speed_max=45.0, highway_speed_min=70.0)
        self.trips = load_all_records("Records")

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
        trip = parse_obd_csv("Records/2026-09-08 09-19-22.csv")
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


if __name__ == "__main__":
    unittest.main()
