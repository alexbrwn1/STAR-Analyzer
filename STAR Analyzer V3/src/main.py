"""
STAR Analyzer V3 - Main entry point.

Run this file to launch the application.
"""

import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from gui.app import run


if __name__ == '__main__':
    run()
