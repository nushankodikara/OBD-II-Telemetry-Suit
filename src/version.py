"""Version management and update checking for OBD-II Telemetry Suit.

Loads version metadata from simpleversion.json and queries GitHub Releases
for application updates.
Strictly adheres to project rules: no emojis.
"""

import json
import os
import re
from typing import Optional, Dict, Any, Tuple
import requests

VERSION_FILE_NAME = "simpleversion.json"


def get_version_info() -> Dict[str, Any]:
    """Load application version and build metadata from simpleversion.json."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    version_path = os.path.join(base_dir, VERSION_FILE_NAME)
    if os.path.isfile(version_path):
        try:
            with open(version_path, "r", encoding="utf-8") as fp:
                return json.load(fp)
        except Exception:
            pass
    return {
        "version": "0.2.0-beta",
        "name": "OBD-II Telemetry Suit",
        "status": "beta",
        "release_date": "2026-10-16",
        "github_repo": "nushankodi/OBD-II-Telemetry-Suit",
    }


def get_app_version() -> str:
    """Return the active semver string."""
    return get_version_info().get("version", "0.2.0-beta")


def parse_semver(v_str: str) -> Tuple[int, int, int, str]:
    """Parse semver string into comparable tuple: (major, minor, patch, pre-release)."""
    clean = v_str.lstrip("vV").strip()
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9.]+))?", clean)
    if match:
        major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))
        pre = match.group(4) or ""
        return (major, minor, patch, pre)
    return (0, 0, 0, clean)


def is_version_newer(remote_v: str, local_v: str) -> bool:
    """Check if remote version is strictly newer than local version."""
    r_maj, r_min, r_pat, r_pre = parse_semver(remote_v)
    l_maj, l_min, l_pat, l_pre = parse_semver(local_v)

    if (r_maj, r_min, r_pat) > (l_maj, l_min, l_pat):
        return True
    if (r_maj, r_min, r_pat) < (l_maj, l_min, l_pat):
        return False
    # If numeric parts are equal: release without pre-release is newer than beta
    if not r_pre and l_pre:
        return True
    if r_pre and not l_pre:
        return False
    return r_pre > l_pre


def check_for_updates(timeout_sec: float = 4.0) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """Query GitHub Releases API to detect available updates.

    Returns:
        (update_available: bool, release_data: Optional[dict], error_message: Optional[str])
    """
    info = get_version_info()
    repo = info.get("github_repo", "nushankodi/OBD-II-Telemetry-Suit")
    current_ver = info.get("version", "0.2.0-beta")
    url = f"https://api.github.com/repos/{repo}/releases/latest"

    headers = {
        "User-Agent": f"OBD-II-Telemetry-Suit/{current_ver}",
        "Accept": "application/vnd.github.v3+json",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=timeout_sec)
        if resp.status_code == 200:
            data = resp.json()
            remote_tag = data.get("tag_name", "").lstrip("vV")
            if is_version_newer(remote_tag, current_ver):
                return True, {
                    "tag_name": remote_tag,
                    "name": data.get("name") or f"Release {remote_tag}",
                    "body": data.get("body") or "No changelog provided.",
                    "html_url": data.get("html_url") or f"https://github.com/{repo}/releases",
                    "published_at": data.get("published_at", "")[:10],
                }, None
            return False, {
                "tag_name": remote_tag,
                "current_version": current_ver,
            }, None
        elif resp.status_code == 404:
            return False, None, "[NOTICE] No published GitHub releases found for this repository yet."
        else:
            return False, None, f"[HTTP {resp.status_code}] Unable to fetch release info."
    except requests.exceptions.Timeout:
        return False, None, "[TIMEOUT] Network connection timed out while checking for updates."
    except Exception as e:
        return False, None, f"[OFFLINE] Could not connect to update server: {e}"
