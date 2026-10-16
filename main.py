"""Root entry point for Car Record Analyzer.

Run this script to launch the OBD-II diagnostic workstation desktop application.
Strictly adheres to project rules: no emojis.
"""

import sys
import os

# Add project root directory to python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.ui.app import main

if __name__ == "__main__":
    main()
