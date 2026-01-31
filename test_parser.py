#!/usr/bin/env python3
"""
Test script for STAR Analyzer parser.
Verifies parsing works correctly with actual data files.
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

from core.parser import MedPCParser, parse_medpc_file
from core.file_discovery import discover_medpc_files
from core.data_models import MedPCSession


def test_single_file():
    """Test parsing a single file."""
    print("=" * 60)
    print("Testing single file parse")
    print("=" * 60)

    test_file = Path("Mock Cohort 1 Data by Day/Day 2/!2026-01-26_13h25m.Subject 1")
    if not test_file.exists():
        print(f"Test file not found: {test_file}")
        return False

    try:
        session = parse_medpc_file(test_file)
        print(f"File: {session.metadata.filename}")
        print(f"Subject: {session.metadata.subject}")
        print(f"Date: {session.metadata.start_date}")
        print(f"Time: {session.metadata.start_time}")
        print(f"Experiment: {session.metadata.experiment}")
        print(f"Group: {session.metadata.group}")
        print(f"Box: {session.metadata.box}")
        print(f"MSN: {session.metadata.msn}")
        print()
        print("Scalars:")
        print(f"  Active presses (A): {session.scalars.active_lever_presses}")
        print(f"  Inactive presses (B): {session.scalars.inactive_lever_presses}")
        print(f"  Reinforcers (D): {session.scalars.reinforcers}")
        print(f"  Lick onsets (E): {session.scalars.lick_onsets}")
        print(f"  Lick offsets (F): {session.scalars.lick_offsets}")
        print(f"  Session time (T): {session.scalars.session_time} seconds")
        print()
        print("Arrays:")
        print(f"  Active lever timestamps (J): {len(session.timestamps.active_lever_timestamps)} values")
        if session.timestamps.active_lever_timestamps:
            print(f"    First 5: {session.timestamps.active_lever_timestamps[:5]}")
        print(f"  Inactive lever timestamps (K): {len(session.timestamps.inactive_lever_timestamps)} values")
        print(f"  Reinforcer timestamps (L): {len(session.timestamps.reinforcer_timestamps)} values")
        print(f"  Lick onset timestamps (N): {len(session.timestamps.lick_onset_timestamps)} values")
        print(f"  Lick offset timestamps (O): {len(session.timestamps.lick_offset_timestamps)} values")
        print()

        # Validate
        if session.has_warnings:
            print("Warnings:")
            for w in session.warnings:
                print(f"  - {w}")
        else:
            print("No warnings - data validated successfully!")

        # Check array counts match scalars
        print()
        print("Validation:")
        checks = [
            ('A/J', session.scalars.active_lever_presses, len(session.timestamps.active_lever_timestamps)),
            ('B/K', session.scalars.inactive_lever_presses, len(session.timestamps.inactive_lever_timestamps)),
            ('D/L', session.scalars.reinforcers, len(session.timestamps.reinforcer_timestamps)),
            ('E/N', session.scalars.lick_onsets, len(session.timestamps.lick_onset_timestamps)),
            ('F/O', session.scalars.lick_offsets, len(session.timestamps.lick_offset_timestamps)),
        ]
        all_match = True
        for name, counter, array_len in checks:
            status = "OK" if counter == array_len else "MISMATCH"
            if counter != array_len:
                all_match = False
            print(f"  {name}: counter={counter}, array={array_len} [{status}]")

        return all_match

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_folder_discovery():
    """Test discovering files in folder."""
    print()
    print("=" * 60)
    print("Testing folder discovery")
    print("=" * 60)

    folder = Path("Mock Cohort 1 Data by Day")
    if not folder.exists():
        print(f"Test folder not found: {folder}")
        return False

    files = discover_medpc_files(folder, recursive=True)
    print(f"Found {len(files)} Med-PC files")

    # Show first few
    for f in files[:5]:
        print(f"  - {f.relative_to(folder)}")
    if len(files) > 5:
        print(f"  ... and {len(files) - 5} more")

    return len(files) > 0


def test_parse_all():
    """Test parsing all files in test folder."""
    print()
    print("=" * 60)
    print("Testing parse all files")
    print("=" * 60)

    folder = Path("Mock Cohort 1 Data by Day")
    if not folder.exists():
        print(f"Test folder not found: {folder}")
        return False

    files = discover_medpc_files(folder, recursive=True)
    parser = MedPCParser()

    success = 0
    errors = 0
    warnings_count = 0

    for f in files:
        try:
            session = parser.parse_file(f)
            success += 1
            if session.has_warnings:
                warnings_count += 1
                print(f"Warnings in {f.name}:")
                for w in session.warnings:
                    print(f"  - {w}")
        except Exception as e:
            errors += 1
            print(f"Error parsing {f.name}: {e}")

    print()
    print(f"Results: {success} parsed, {errors} errors, {warnings_count} with warnings")

    return errors == 0


def main():
    print("STAR Analyzer Parser Tests")
    print()

    results = []
    results.append(("Single file parse", test_single_file()))
    results.append(("Folder discovery", test_folder_discovery()))
    results.append(("Parse all files", test_parse_all()))

    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"  {name}: {status}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
