"""Session manager and XML persistence for OBD-II Telemetry Suit.

Manages vehicle profiles (make, model, engine, capacity, tyre size, etc.),
session settings, and XML serialization/deserialization.
Strictly adheres to project rules: no emojis.
"""

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any

LAST_SESSION_FILE = "last_session.xml"


@dataclass
class VehicleProfile:
    """Stores detailed vehicle specifications entered by the user."""
    make: str = ""
    model: str = ""
    year: str = ""
    engine_type: str = "Petrol"  # Petrol, Diesel, Hybrid Petrol, Turbo Petrol, EV
    displacement_cc: str = ""    # e.g. 1500
    transmission: str = "Automatic"  # Manual, Automatic, CVT, e-CVT
    gears: str = "5"             # Number of gears / ratios
    tyre_size: str = ""          # e.g. 185/65R15
    fuel_tank_l: str = ""        # e.g. 45
    notes: str = ""

    def summary_text(self) -> str:
        parts = []
        if self.year:
            parts.append(self.year)
        if self.make:
            parts.append(self.make)
        if self.model:
            parts.append(self.model)
        if self.displacement_cc:
            parts.append(f"{self.displacement_cc}cc")
        if self.engine_type:
            parts.append(f"({self.engine_type})")
        return " ".join(parts) if parts else "Unspecified Vehicle"

    @property
    def is_configured(self) -> bool:
        """Return True if make, model, or custom parameters have been explicitly populated."""
        return bool(self.make.strip() or self.model.strip() or self.displacement_cc.strip())

    @property
    def forward_gears(self) -> int:
        """Return parsed integer count of forward transmission gears (e.g. 4 for 4-Speed Auto)."""
        s = self.gears.strip().lower()
        if "e-cvt" in s or "cvt" in s:
            return 1
        import re
        m = re.search(r"(\d+)", s)
        if m:
            try:
                return max(1, min(int(m.group(1)), 10))
            except ValueError:
                pass
        return 5


def save_session_to_xml(
    file_path: str,
    profile: VehicleProfile,
    city_threshold: float,
    highway_threshold: float,
    unit: str,
    data_file_paths: List[str],
) -> bool:
    """Save vehicle profile, settings, and file paths to XML format."""
    try:
        root = ET.Element("OBDIITelemetrySuitSession", version="1.0")

        # Vehicle Profile node
        prof_node = ET.SubElement(root, "VehicleProfile")
        ET.SubElement(prof_node, "Make").text = profile.make
        ET.SubElement(prof_node, "Model").text = profile.model
        ET.SubElement(prof_node, "Year").text = profile.year
        ET.SubElement(prof_node, "EngineType").text = profile.engine_type
        ET.SubElement(prof_node, "DisplacementCc").text = profile.displacement_cc
        ET.SubElement(prof_node, "Transmission").text = profile.transmission
        ET.SubElement(prof_node, "Gears").text = profile.gears
        ET.SubElement(prof_node, "TyreSize").text = profile.tyre_size
        ET.SubElement(prof_node, "FuelTankL").text = profile.fuel_tank_l
        ET.SubElement(prof_node, "Notes").text = profile.notes

        # Settings node
        settings_node = ET.SubElement(root, "AnalysisSettings")
        ET.SubElement(settings_node, "CityThresholdKmh").text = str(city_threshold)
        ET.SubElement(settings_node, "HighwayThresholdKmh").text = str(highway_threshold)
        ET.SubElement(settings_node, "FuelEconomyUnit").text = unit

        # Data Files node
        files_node = ET.SubElement(root, "DataFiles")
        for p in data_file_paths:
            # Store absolute or relative path
            f_elem = ET.SubElement(files_node, "File")
            f_elem.set("path", os.path.abspath(p))

        tree = ET.ElementTree(root)
        ET.indent(tree, space="    ", level=0)
        tree.write(file_path, encoding="utf-8", xml_declaration=True)
        return True
    except Exception as e:
        print(f"Error saving XML session: {e}")
        return False


def load_session_from_xml(
    file_path: str
) -> Optional[Tuple[VehicleProfile, Dict[str, Any], List[str]]]:
    """Parse XML session file and return vehicle profile, settings, and data file paths."""
    if not os.path.isfile(file_path):
        return None

    try:
        tree = ET.parse(file_path)
        root = tree.getroot()

        # Parse Profile
        profile = VehicleProfile()
        p_node = root.find("VehicleProfile")
        if p_node is not None:
            profile.make = p_node.findtext("Make", "") or ""
            profile.model = p_node.findtext("Model", "") or ""
            profile.year = p_node.findtext("Year", "") or ""
            profile.engine_type = p_node.findtext("EngineType", "Petrol") or "Petrol"
            profile.displacement_cc = p_node.findtext("DisplacementCc", "") or ""
            profile.transmission = p_node.findtext("Transmission", "Automatic") or "Automatic"
            profile.gears = p_node.findtext("Gears", "5") or "5"
            profile.tyre_size = p_node.findtext("TyreSize", "") or ""
            profile.fuel_tank_l = p_node.findtext("FuelTankL", "") or ""
            profile.notes = p_node.findtext("Notes", "") or ""

        # Parse Settings
        settings = {
            "city_threshold": 45.0,
            "highway_threshold": 70.0,
            "unit": "km/L",
        }
        s_node = root.find("AnalysisSettings")
        if s_node is not None:
            try:
                settings["city_threshold"] = float(s_node.findtext("CityThresholdKmh", "45.0"))
                settings["highway_threshold"] = float(s_node.findtext("HighwayThresholdKmh", "70.0"))
            except ValueError:
                pass
            settings["unit"] = s_node.findtext("FuelEconomyUnit", "km/L") or "km/L"

        # Parse Data Files
        file_paths = []
        f_node = root.find("DataFiles")
        if f_node is not None:
            for f_elem in f_node.findall("File"):
                p = f_elem.get("path")
                if p and os.path.exists(p):
                    file_paths.append(p)

        return profile, settings, file_paths
    except Exception as e:
        print(f"Error loading XML session: {e}")
        return None


def save_last_session(
    profile: VehicleProfile,
    city_threshold: float,
    highway_threshold: float,
    unit: str,
    data_file_paths: List[str],
):
    """Persist current application state to last_session.xml."""
    save_session_to_xml(
        LAST_SESSION_FILE,
        profile,
        city_threshold,
        highway_threshold,
        unit,
        data_file_paths,
    )


def load_last_session() -> Optional[Tuple[VehicleProfile, Dict[str, Any], List[str]]]:
    """Restore state from last_session.xml if present."""
    if os.path.exists(LAST_SESSION_FILE):
        return load_session_from_xml(LAST_SESSION_FILE)
    return None
