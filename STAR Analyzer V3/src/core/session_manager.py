"""
Central session manager for STAR Analyzer V3.

This module provides a unified data layer that:
1. Parses MedPC files from a folder
2. Computes session statistics (licks, presses, pass/fail)
3. Builds animal progression state
4. Notifies GUI views when data changes

Both Raster Plots and Progress Tracker tabs use this single data source.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
import re

from .parser import parse_medpc_file, get_session_display_name, detect_training_stage
from .file_discovery import discover_medpc_files
from .data_models import (
    MedPCSession,
    Stage,
    PassStatus,
    SessionResult,
    AnimalState,
)
from .tracker import (
    CohortTracker,
    check_pass_criteria,
    parse_date_from_header,
    parse_date_from_filename,
)


@dataclass
class ParsedSession:
    """A parsed session with all data needed for plotting and tracking."""

    # Full session object
    session: MedPCSession

    # Quick-access metadata
    subject_id: str
    date: str
    display_name: str
    filepath: str

    # Stage info
    stage: Optional[Stage]
    stage_name: str

    # Session metrics
    licks: int
    active_presses: int
    inactive_presses: int
    reinforcers: int

    # Pass/fail
    passed: bool
    pass_status: str

    # Day within cohort (extracted from folder name like "Day 5")
    day_in_cohort: int = 0

    @property
    def lever_preference(self) -> float:
        """Calculate active lever preference ratio."""
        total = self.active_presses + self.inactive_presses
        if total == 0:
            return 0.0
        return self.active_presses / total

    @property
    def raw_data(self) -> Dict[str, Any]:
        """Get raw data dict for plotting compatibility."""
        session = self.session
        return {
            'header': {
                'subject': session.metadata.subject,
                'start_date': session.metadata.start_date.strftime("%m/%d/%y"),
                'start_time': session.metadata.start_time.strftime("%H:%M:%S"),
                'experiment': session.metadata.experiment,
                'group': session.metadata.group,
                'box': session.metadata.box,
                'msn': session.metadata.msn,
            },
            'scalars': {
                'A': session.scalars.active_lever_presses,
                'B': session.scalars.inactive_lever_presses,
                'C': session.scalars.lick_count,
                'D': session.scalars.reinforcers,
                'E': session.scalars.lick_onsets,
                'F': session.scalars.lick_offsets,
                'T': session.scalars.session_time,
            },
            'arrays': {
                'J': session.timestamps.active_lever_timestamps,
                'K': session.timestamps.inactive_lever_timestamps,
                'L': session.timestamps.reinforcer_timestamps,
                'N': session.timestamps.lick_onset_timestamps,
                'O': session.timestamps.lick_offset_timestamps,
            },
            'protocol': {
                'active_lever': session.protocol.active_lever,
                'fr_schedule': session.protocol.fr_schedule,
                'sipper_duration': session.protocol.sipper_duration,
            },
            'filepath': str(session.metadata.file_path),
            'filename': session.metadata.filename,
        }


class SessionManager:
    """Central data manager for the application.

    Loads data once and provides it to both Raster Plots and Progress Tracker tabs.
    """

    def __init__(self):
        # Raw parsed sessions for plotting
        self.parsed_sessions: List[ParsedSession] = []

        # Progress tracking state
        self.tracker: Optional[CohortTracker] = None

        # Current folder path
        self.folder_path: Optional[Path] = None

        # Callbacks for notifying views
        self._on_data_changed_callbacks: List[Callable[[], None]] = []

    def add_data_changed_callback(self, callback: Callable[[], None]):
        """Register a callback to be called when data changes."""
        self._on_data_changed_callbacks.append(callback)

    def remove_data_changed_callback(self, callback: Callable[[], None]):
        """Remove a registered callback."""
        if callback in self._on_data_changed_callbacks:
            self._on_data_changed_callbacks.remove(callback)

    def _notify_data_changed(self):
        """Notify all registered callbacks that data has changed."""
        for callback in self._on_data_changed_callbacks:
            try:
                callback()
            except Exception as e:
                print(f"Error in data changed callback: {e}")

    def load_folder(self, folder_path: str) -> int:
        """
        Load all MedPC files from a folder.

        Args:
            folder_path: Path to the folder containing MedPC files

        Returns:
            Number of sessions successfully loaded
        """
        self.folder_path = Path(folder_path)
        self.parsed_sessions.clear()

        # Discover MedPC files
        files = discover_medpc_files(self.folder_path, recursive=True)

        # If no files found with pattern, try fallback scanning
        if not files:
            files = self._fallback_file_scan()

        # Parse each file and collect session data
        file_sessions: List[tuple] = []  # (filepath, date_str, ParsedSession)

        for filepath in files:
            try:
                session = self._parse_session(filepath)
                if session:
                    file_sessions.append((filepath, session.date or "9999-99-99", session))
            except Exception as e:
                print(f"Error parsing {filepath}: {e}")
                continue

        # Sort by date for chronological processing (used for tracker state)
        file_sessions.sort(key=lambda x: x[1])

        # Store parsed sessions sorted by subject ID (numeric), then by day_in_cohort
        def subject_sort_key(item):
            session = item[2]
            # Try to extract numeric part from subject_id for natural sorting
            subject_num = 0
            match = re.search(r'(\d+)', session.subject_id)
            if match:
                subject_num = int(match.group(1))
            return (subject_num, session.subject_id, session.day_in_cohort, item[1])

        file_sessions.sort(key=subject_sort_key)
        self.parsed_sessions = [s for _, _, s in file_sessions]

        # Build tracker state from the same data
        self._build_tracker_state()

        # Notify views that data has changed
        self._notify_data_changed()

        return len(self.parsed_sessions)

    def _fallback_file_scan(self) -> List[Path]:
        """Fallback file scanning for non-standard file naming."""
        skip_extensions = {'.md', '.xlsx', '.csv', '.xls', '.json', '.py', '.bat', '.pyw', '.txt', '.log'}
        files: List[Path] = []

        for item in self.folder_path.iterdir():
            if item.is_file() and item.suffix.lower() not in skip_extensions:
                files.append(item)

        # Also check subdirectories one level deep
        for subdir in self.folder_path.iterdir():
            if subdir.is_dir():
                for item in subdir.iterdir():
                    if item.is_file() and item.suffix.lower() not in skip_extensions:
                        files.append(item)

        return sorted(files)

    def _parse_session(self, filepath: Path) -> Optional[ParsedSession]:
        """Parse a single file into a ParsedSession."""
        try:
            session = parse_medpc_file(filepath)
        except Exception:
            return None

        subject_id = session.metadata.subject
        msn = session.metadata.msn

        # Determine stage from protocol
        stage = detect_training_stage(msn)
        if stage is None:
            # Skip files we can't identify as valid MedPC sessions
            return None

        # Get date
        date_str = session.metadata.start_date.strftime("%Y-%m-%d")

        # Extract metrics
        licks = session.licks
        active_presses = session.scalars.active_lever_presses
        inactive_presses = session.scalars.inactive_lever_presses
        reinforcers = session.scalars.reinforcers

        # Fallback to array counts if scalars are zero
        if active_presses == 0:
            active_presses = len(session.timestamps.active_lever_timestamps)
        if inactive_presses == 0:
            inactive_presses = len(session.timestamps.inactive_lever_timestamps)
        if reinforcers == 0:
            reinforcers = len(session.timestamps.reinforcer_timestamps)

        # Calculate lever preference
        total_presses = active_presses + inactive_presses
        lever_pref = active_presses / total_presses if total_presses > 0 else 0.0

        # Check pass criteria
        passed, pass_status = check_pass_criteria(stage, licks, lever_pref)

        # Generate display name
        display_name = get_session_display_name(session)

        # Stage name for display
        stage_names = {
            Stage.MAG_TRAIN: "MagTrain",
            Stage.FR1_30: "FR1-30",
            Stage.FR1_10: "FR1-10",
            Stage.FR5_10: "FR5-10",
            Stage.TRAINED: "Trained",
            Stage.TESTING: "FR10-10",
        }
        stage_name = stage_names.get(stage, str(stage))

        # Extract day number from folder name (e.g., "Day 5" -> 5)
        day_in_cohort = self._extract_day_from_path(filepath)

        return ParsedSession(
            session=session,
            subject_id=subject_id,
            date=date_str,
            display_name=display_name,
            filepath=str(filepath),
            stage=stage,
            stage_name=stage_name,
            licks=licks,
            active_presses=active_presses,
            inactive_presses=inactive_presses,
            reinforcers=reinforcers,
            passed=passed,
            pass_status=pass_status,
            day_in_cohort=day_in_cohort,
        )

    def _extract_day_from_path(self, filepath: Path) -> int:
        """Extract day number from folder path (e.g., 'Day 5' -> 5)."""
        # Check parent folder name for "Day N" pattern
        parent_name = filepath.parent.name
        match = re.search(r'[Dd]ay\s*(\d+)', parent_name)
        if match:
            return int(match.group(1))
        # Fallback: check the filename itself
        match = re.search(r'[Dd]ay\s*(\d+)', filepath.name)
        if match:
            return int(match.group(1))
        return 0

    def _build_tracker_state(self):
        """Build CohortTracker state from parsed sessions."""
        cohort_name = self.folder_path.name if self.folder_path else ""
        self.tracker = CohortTracker(cohort_name)
        self.tracker.folder_path = self.folder_path

        # Group sessions by subject and sort by date
        sessions_by_subject: Dict[str, List[ParsedSession]] = {}
        for session in self.parsed_sessions:
            if session.subject_id not in sessions_by_subject:
                sessions_by_subject[session.subject_id] = []
            sessions_by_subject[session.subject_id].append(session)

        # Process each subject's sessions chronologically
        for subject_id, sessions in sessions_by_subject.items():
            # Sessions are already sorted by date from load_folder
            animal = AnimalState(subject_id=subject_id, cohort=cohort_name)

            for session in sessions:
                if session.stage is None:
                    continue

                # Calculate day in stage
                day_in_stage = 1
                for prev_result in animal.history:
                    if prev_result.stage == session.stage:
                        day_in_stage += 1

                result = SessionResult(
                    date=session.date,
                    subject_id=subject_id,
                    stage=session.stage,
                    licks=session.licks,
                    active_presses=session.active_presses,
                    inactive_presses=session.inactive_presses,
                    passed=session.passed,
                    filename=Path(session.filepath).name,
                    pass_status=session.pass_status,
                    day_in_stage=day_in_stage,
                )

                animal.process_session(result)

            self.tracker.animals[subject_id] = animal

        self.tracker.last_scan_time = datetime.now()

    def clear(self):
        """Clear all loaded data."""
        self.parsed_sessions.clear()
        self.tracker = None
        self.folder_path = None
        self._notify_data_changed()

    def get_all_sessions(self) -> List[ParsedSession]:
        """Get all parsed sessions."""
        return self.parsed_sessions

    def get_session(self, index: int) -> Optional[ParsedSession]:
        """Get a specific session by index."""
        if 0 <= index < len(self.parsed_sessions):
            return self.parsed_sessions[index]
        return None

    def get_sessions_for_subject(self, subject_id: str) -> List[ParsedSession]:
        """Get all sessions for a specific subject."""
        return [s for s in self.parsed_sessions if s.subject_id == subject_id]

    def get_all_subjects(self) -> List[str]:
        """Get list of all subject IDs."""
        subjects = set(s.subject_id for s in self.parsed_sessions)
        # Natural sort (numeric order)
        def sort_key(s):
            match = re.search(r'(\d+)', s)
            if match:
                return (int(match.group(1)), s)
            return (999999, s)
        return sorted(subjects, key=sort_key)

    def get_raw_data_for_plotting(self, indices: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        """Get raw parsed data dicts for plotting.

        Args:
            indices: Optional list of session indices. If None, returns all.

        Returns:
            List of raw data dicts suitable for plotting functions.
        """
        if indices is None:
            return [s.raw_data for s in self.parsed_sessions]
        return [self.parsed_sessions[i].raw_data for i in indices if i < len(self.parsed_sessions)]

    def get_tracker(self) -> Optional[CohortTracker]:
        """Get the CohortTracker instance."""
        return self.tracker

    def get_animal_states(self) -> List[AnimalState]:
        """Get all animal states from tracker."""
        if self.tracker:
            return self.tracker.get_all_animals()
        return []

    def has_data(self) -> bool:
        """Check if any data is loaded."""
        return len(self.parsed_sessions) > 0

    def get_session_count(self) -> int:
        """Get total number of loaded sessions."""
        return len(self.parsed_sessions)

    def get_subject_count(self) -> int:
        """Get number of unique subjects."""
        return len(self.get_all_subjects())
