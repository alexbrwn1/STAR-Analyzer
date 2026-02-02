"""
Progress Tracker for animal training progression through acquisition phases.
Contains CohortTracker and helper functions for tracking progression.
"""

import re
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

from .data_models import (
    Stage,
    PassStatus,
    SessionResult,
    AnimalState,
)
from .parser import extract_protocol_info, detect_training_stage


# =============================================================================
# Pass Criteria Checking
# =============================================================================

def check_pass_criteria(stage: Stage, licks: int, lever_pref: float) -> tuple:
    """
    Check if session meets advancement criteria for given stage.

    Criteria:
    - MAG_TRAIN: >=100 licks
    - FR1-30: >=100 licks
    - FR1-10: >=100 licks
    - FR5-10: >=100 licks AND >=70% active lever

    Returns:
        Tuple of (passed: bool, status: str)
        status is one of: PassStatus.PASS, PassStatus.FAIL, PassStatus.PARTIAL
    """
    MIN_LICKS = 100
    MIN_LEVER_PREF = 0.70

    if stage == Stage.MAG_TRAIN:
        passed = licks >= MIN_LICKS
        return (passed, PassStatus.PASS if passed else PassStatus.FAIL)

    if stage == Stage.FR1_30:
        passed = licks >= MIN_LICKS
        return (passed, PassStatus.PASS if passed else PassStatus.FAIL)

    if stage == Stage.FR1_10:
        passed = licks >= MIN_LICKS
        return (passed, PassStatus.PASS if passed else PassStatus.FAIL)

    if stage == Stage.FR5_10:
        met_licks = licks >= MIN_LICKS
        met_discrim = lever_pref >= MIN_LEVER_PREF

        if met_licks and met_discrim:
            return (True, PassStatus.PASS)
        elif met_licks or met_discrim:
            # Partial: met one criterion but not the other
            return (False, PassStatus.PARTIAL)
        else:
            return (False, PassStatus.FAIL)

    # Testing phase always passes
    if stage == Stage.TESTING:
        return (True, PassStatus.PASS)

    return (False, PassStatus.FAIL)


# =============================================================================
# Date Parsing Helpers
# =============================================================================

def parse_date_from_filename(filename: str) -> Optional[str]:
    """
    Extract date from filename in format YYYY-MM-DD.

    Expected patterns:
    - "!2026-01-20_13h22m.Subject 1"
    - "2026-01-20_Subject1_MagTrain.txt"
    """
    # Try to find YYYY-MM-DD pattern
    match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
    if match:
        return match.group(1)
    return None


def parse_date_from_header(date_str: str) -> Optional[str]:
    """
    Parse date from MedPC header format to YYYY-MM-DD.

    Expected formats:
    - "01/20/26" (MM/DD/YY)
    - "01/20/2026" (MM/DD/YYYY)
    - "2026-01-20" (YYYY-MM-DD)
    """
    if not date_str:
        return None

    # Already YYYY-MM-DD
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return date_str

    # MM/DD/YY or MM/DD/YYYY
    match = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{2,4})$', date_str)
    if match:
        month, day, year = match.groups()
        if len(year) == 2:
            year = f"20{year}"
        return f"{year}-{int(month):02d}-{int(day):02d}"

    return None


# =============================================================================
# Cohort Tracker
# =============================================================================

class CohortTracker:
    """Manages tracking state for multiple animals in a cohort."""

    def __init__(self, cohort_name: str = ""):
        self.cohort_name = cohort_name
        self.animals: Dict[str, AnimalState] = {}
        self.folder_path: Optional[Path] = None
        self.last_scan_time: Optional[datetime] = None

    def get_animal(self, subject_id: str) -> Optional[AnimalState]:
        """Get state for a specific animal."""
        return self.animals.get(subject_id)

    def get_all_animals(self) -> List[AnimalState]:
        """Get all animal states sorted by subject ID."""
        def sort_key(animal: AnimalState):
            # Extract numeric part for natural sorting
            match = re.search(r'(\d+)', animal.subject_id)
            if match:
                return (int(match.group(1)), animal.subject_id)
            return (999999, animal.subject_id)
        return sorted(self.animals.values(), key=sort_key)

    def get_next_day_report(self) -> Dict[str, List[str]]:
        """
        Generate summary of what each animal needs tomorrow.

        Returns dict mapping stage name to list of subject IDs.
        """
        report = {
            str(Stage.MAG_TRAIN): [],
            str(Stage.FR1_30): [],
            str(Stage.FR1_10): [],
            str(Stage.FR5_10): [],
            "FR10-10": [],  # Testing stage
        }

        for animal in self.animals.values():
            if animal.is_trained or animal.current_stage == Stage.TESTING:
                # In testing phase
                if animal.test_day < 7:
                    report["FR10-10"].append(f"{animal.subject_id} (Day {animal.test_day + 1})")
                # Day 7+ completed testing, don't include
            else:
                stage_key = str(animal.current_stage)
                if stage_key in report:
                    report[stage_key].append(animal.subject_id)

        return report

    def export_status(self) -> List[Dict[str, Any]]:
        """Export current status for all animals as list of dicts."""
        status_list = []
        for animal in self.get_all_animals():
            status_list.append({
                "Subject": animal.subject_id,
                "Stage": str(animal.current_stage),
                "Streak": animal.get_streak_text(),
                "Sessions": animal.get_session_count(),
                "Status": animal.get_status_text(),
                "Trained": "Yes" if animal.is_trained else "No",
                "Test Day": animal.test_day if animal.is_trained else "",
            })
        return status_list

    def save_cache(self, cache_path: Path):
        """Save tracker state to JSON cache file."""
        data = {
            "cohort_name": self.cohort_name,
            "folder_path": str(self.folder_path) if self.folder_path else None,
            "last_scan_time": self.last_scan_time.isoformat() if self.last_scan_time else None,
            "animals": {
                subject_id: animal.to_dict()
                for subject_id, animal in self.animals.items()
            },
        }
        with open(cache_path, 'w') as f:
            json.dump(data, f, indent=2)

    def load_cache(self, cache_path: Path) -> bool:
        """Load tracker state from JSON cache file. Returns True if successful."""
        try:
            with open(cache_path, 'r') as f:
                data = json.load(f)

            self.cohort_name = data.get("cohort_name", "")
            self.folder_path = Path(data["folder_path"]) if data.get("folder_path") else None
            self.last_scan_time = datetime.fromisoformat(data["last_scan_time"]) if data.get("last_scan_time") else None

            self.animals = {
                subject_id: AnimalState.from_dict(animal_data)
                for subject_id, animal_data in data.get("animals", {}).items()
            }
            return True
        except Exception as e:
            print(f"Error loading cache: {e}")
            return False


# =============================================================================
# Report Generation
# =============================================================================

def generate_next_day_report(tracker: CohortTracker) -> str:
    """
    Generate a formatted text report of next day setup.

    Args:
        tracker: CohortTracker with current state

    Returns:
        Formatted string report
    """
    report = tracker.get_next_day_report()

    lines = ["NEXT DAY SETUP", "=" * 40, ""]

    stage_order = [
        (str(Stage.MAG_TRAIN), "MagTrain"),
        (str(Stage.FR1_30), "FR1-30"),
        (str(Stage.FR1_10), "FR1-10"),
        (str(Stage.FR5_10), "FR5-10"),
        ("FR10-10", "FR10-10"),
    ]

    for key, label in stage_order:
        animals = report.get(key, [])
        count = len(animals)
        animal_str = ", ".join(animals) if animals else "-"
        lines.append(f"{label} ({count}): {animal_str}")

    lines.append("")
    lines.append(f"Total animals: {len(tracker.animals)}")

    return "\n".join(lines)


def process_cohort_folder(folder_path: str) -> CohortTracker:
    """
    Convenience function to scan a folder and return a tracker.

    Note: This function is a placeholder. The actual folder processing
    is done in SessionManager to avoid duplicating parsing logic.

    Args:
        folder_path: Path to cohort folder

    Returns:
        Empty CohortTracker (use SessionManager.load_folder instead)
    """
    path = Path(folder_path)
    cohort_name = path.name

    tracker = CohortTracker(cohort_name)
    tracker.folder_path = path

    return tracker
