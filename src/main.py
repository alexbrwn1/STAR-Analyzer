#!/usr/bin/env python3
"""
STAR Analyzer - Data Parser/Importer Module

Entry point for the STAR Analyzer application.
Parses Med-PC IV data files from STAR rodent operant self-administration experiments.
"""

import sys
from pathlib import Path


def main():
    """Main entry point."""
    # Add src to path for imports when running directly
    src_path = Path(__file__).parent
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    # Import here to ensure path is set first
    from gui.app import StarAnalyzerApp

    app = StarAnalyzerApp()
    app.mainloop()


if __name__ == '__main__':
    main()
