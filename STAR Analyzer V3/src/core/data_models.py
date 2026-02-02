"""
Data models for STAR Analyzer V3.
Combines V2's clean dataclasses with V1's tracking models.
"""

from dataclasses import dataclass, field
from datetime import datetime, date, time
from enum import Enum, auto
from pathlib import Path
from typing import List, Optional, Dict, Any


# =============================================================================
# Session Data Models (from V2, extended)
# =============================================================================

@dataclass
class SessionMetadata:
    """Metadata extracted from Med-PC file header."""
    file_path: Path
    subject: str
    start_date: date
    start_time: time
    end_time: Optional[time]
    experiment: str
    group: str
    box: int
    msn: str

    @property
    def start_datetime(self) -> datetime:
        """Combine date and time into datetime object."""
        return datetime.combine(self.start_date, self.start_time)

    @property
    def filename(self) -> str:
        """Return just the filename without path."""
        return self.file_path.name


@dataclass
class ScalarVariables:
    """Scalar (counter/timer) variables from Med-PC session."""
    active_lever_presses: int = 0      # Variable A
    inactive_lever_presses: int = 0    # Variable B
    lick_count: int = 0                # Variable C (added in V3)
    reinforcers: int = 0               # Variable D
    lick_onsets: int = 0               # Variable E
    lick_offsets: int = 0              # Variable F
    session_time: float = 0.0          # Variable T (seconds)


@dataclass
class TimestampArrays:
    """Timestamp arrays from Med-PC session."""
    active_lever_timestamps: List[float] = field(default_factory=list)      # Array J
    inactive_lever_timestamps: List[float] = field(default_factory=list)    # Array K
    reinforcer_timestamps: List[float] = field(default_factory=list)        # Array L
    lick_onset_timestamps: List[float] = field(default_factory=list)        # Array N
    lick_offset_timestamps: List[float] = field(default_factory=list)       # Array O


@dataclass
class ProtocolInfo:
    """Protocol information extracted from MSN string."""
    active_lever: Optional[str] = None       # "LEFT" or "RIGHT"
    fr_schedule: Optional[int] = None        # 1, 3, 5, 10, etc.
    sipper_duration: Optional[int] = None    # 10, 30 seconds


@dataclass
class ParseWarning:
    """Warning generated during parsing (non-fatal issues)."""
    message: str
    variable: Optional[str] = None

    def __str__(self) -> str:
        if self.variable:
            return f"[{self.variable}] {self.message}"
        return self.message


@dataclass
class MedPCSession:
    """Complete parsed Med-PC session data."""
    metadata: SessionMetadata
    scalars: ScalarVariables
    timestamps: TimestampArrays
    protocol: ProtocolInfo = field(default_factory=ProtocolInfo)
    warnings: List[ParseWarning] = field(default_factory=list)

    @property
    def subject(self) -> str:
        return self.metadata.subject

    @property
    def date(self) -> date:
        return self.metadata.start_date

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    @property
    def licks(self) -> int:
        """Get lick count, preferring C scalar, falling back to array length."""
        if self.scalars.lick_count > 0:
            return self.scalars.lick_count
        return len(self.timestamps.lick_onset_timestamps)

    @property
    def lever_preference(self) -> float:
        """Calculate active lever preference ratio."""
        total = self.scalars.active_lever_presses + self.scalars.inactive_lever_presses
        if total == 0:
            return 0.0
        return self.scalars.active_lever_presses / total

    def validate_array_lengths(self) -> List[ParseWarning]:
        """Check if array lengths match counter values."""
        warnings = []

        checks = [
            ('A/J', self.scalars.active_lever_presses,
             len(self.timestamps.active_lever_timestamps), 'active lever'),
            ('B/K', self.scalars.inactive_lever_presses,
             len(self.timestamps.inactive_lever_timestamps), 'inactive lever'),
            ('D/L', self.scalars.reinforcers,
             len(self.timestamps.reinforcer_timestamps), 'reinforcer'),
            ('E/N', self.scalars.lick_onsets,
             len(self.timestamps.lick_onset_timestamps), 'lick onset'),
            ('F/O', self.scalars.lick_offsets,
             len(self.timestamps.lick_offset_timestamps), 'lick offset'),
        ]

        for var_name, counter, array_len, desc in checks:
            if counter != array_len:
                warnings.append(ParseWarning(
                    f"{desc} count mismatch: counter={counter}, array length={array_len}",
                    variable=var_name
                ))

        return warnings


@dataclass
class Cohort:
    """Collection of sessions from a folder/cohort."""
    name: str
    sessions: List[MedPCSession] = field(default_factory=list)
    source_path: Optional[Path] = None

    @property
    def session_count(self) -> int:
        return len(self.sessions)

    @property
    def subjects(self) -> List[str]:
        """Return unique subjects in this cohort."""
        return sorted(set(s.subject for s in self.sessions))

    def get_sessions_by_subject(self, subject: str) -> List[MedPCSession]:
        """Filter sessions by subject."""
        return [s for s in self.sessions if s.subject == subject]

    def get_sessions_by_date(self, target_date: date) -> List[MedPCSession]:
        """Filter sessions by date."""
        return [s for s in self.sessions if s.date == target_date]


# =============================================================================
# Progress Tracking Models (from V1)
# =============================================================================

class Stage(Enum):
    """Training stages in sequential order."""
    MAG_TRAIN = auto()
    FR1_30 = auto()
    FR1_10 = auto()
    FR5_10 = auto()
    TRAINED = auto()
    TESTING = auto()

    def __str__(self) -> str:
        """Human-readable stage name."""
        names = {
            Stage.MAG_TRAIN: "MagTrain",
            Stage.FR1_30: "FR1-30",
            Stage.FR1_10: "FR1-10",
            Stage.FR5_10: "FR5-10",
            Stage.TRAINED: "Trained",
            Stage.TESTING: "Testing",
        }
        return names.get(self, self.name)

    @classmethod
    def from_string(cls, s: str) -> Optional['Stage']:
        """Parse stage from string."""
        s_upper = s.upper().replace("-", "_").replace(" ", "_")
        mapping = {
            "MAGTRAIN": cls.MAG_TRAIN,
            "MAG_TRAIN": cls.MAG_TRAIN,
            "MAGAZINE": cls.MAG_TRAIN,
            "FR1_30": cls.FR1_30,
            "FR130": cls.FR1_30,
            "FR1_10": cls.FR1_10,
            "FR110": cls.FR1_10,
            "FR5_10": cls.FR5_10,
            "FR510": cls.FR5_10,
            "TRAINED": cls.TRAINED,
            "TESTING": cls.TESTING,
            "TEST": cls.TESTING,
            "FR10_10": cls.TESTING,
            "FR1010": cls.TESTING,
        }
        return mapping.get(s_upper)

    def next_stage(self) -> Optional['Stage']:
        """Get the next stage in progression."""
        progression = [
            Stage.MAG_TRAIN,
            Stage.FR1_30,
            Stage.FR1_10,
            Stage.FR5_10,
            Stage.TRAINED,
            Stage.TESTING,
        ]
        try:
            idx = progression.index(self)
            if idx < len(progression) - 1:
                return progression[idx + 1]
        except ValueError:
            pass
        return None

    def prev_stage(self) -> Optional['Stage']:
        """Get the previous stage for regression."""
        progression = [
            Stage.MAG_TRAIN,
            Stage.FR1_30,
            Stage.FR1_10,
            Stage.FR5_10,
        ]
        try:
            idx = progression.index(self)
            if idx > 0:
                return progression[idx - 1]
        except ValueError:
            pass
        return None


class PassStatus:
    """Pass/fail status with support for partial passes."""
    PASS = "pass"           # Met all criteria (Green)
    FAIL = "fail"           # Failed all criteria (Red)
    PARTIAL = "partial"     # FR5-10: Met one criterion but not both (Yellow)


@dataclass
class SessionResult:
    """Result from a single training session (for tracker)."""
    date: str
    subject_id: str
    stage: Stage
    licks: int
    active_presses: int
    inactive_presses: int
    passed: bool
    filename: str = ""
    pass_status: str = PassStatus.FAIL
    day_in_stage: int = 1

    @property
    def lever_preference(self) -> float:
        """Calculate active lever preference ratio."""
        total = self.active_presses + self.inactive_presses
        if total == 0:
            return 0.0
        return self.active_presses / total


@dataclass
class AnimalState:
    """Current training state for a single animal."""
    subject_id: str
    cohort: str = ""
    current_stage: Stage = Stage.MAG_TRAIN
    stage_session_counts: Dict[str, int] = field(default_factory=dict)
    consecutive_passes: int = 0
    consecutive_fails: int = 0
    is_trained: bool = False
    test_day: int = 0
    history: List[SessionResult] = field(default_factory=list)

    def __post_init__(self):
        """Initialize stage session counts if empty."""
        if not self.stage_session_counts:
            self.stage_session_counts = {
                str(Stage.MAG_TRAIN): 0,
                str(Stage.FR1_30): 0,
                str(Stage.FR1_10): 0,
                str(Stage.FR5_10): 0,
            }

    def process_session(self, result: SessionResult) -> Dict[str, Any]:
        """
        Process a session result and update state.

        Returns dict with transition info:
        - advanced: bool
        - regressed: bool
        - from_stage: Stage
        - to_stage: Stage
        """
        transition = {
            "advanced": False,
            "regressed": False,
            "from_stage": self.current_stage,
            "to_stage": self.current_stage,
        }

        # Add to history
        self.history.append(result)

        # Handle testing phase
        if self.is_trained or self.current_stage == Stage.TESTING:
            self.test_day += 1
            self.current_stage = Stage.TESTING
            transition["to_stage"] = Stage.TESTING
            return transition

        # Increment session count for current stage
        stage_key = str(self.current_stage)
        self.stage_session_counts[stage_key] = self.stage_session_counts.get(stage_key, 0) + 1

        # Update consecutive counters based on pass/fail
        if result.passed:
            self.consecutive_passes += 1
            self.consecutive_fails = 0
        else:
            self.consecutive_fails += 1
            self.consecutive_passes = 0

        # Check for advancement
        if self._check_advancement():
            transition["advanced"] = True
            transition["to_stage"] = self.current_stage
            return transition

        # Check for regression
        if self._check_regression():
            transition["regressed"] = True
            transition["to_stage"] = self.current_stage
            return transition

        return transition

    def _check_advancement(self) -> bool:
        """Check if animal should advance to next stage."""
        passes_needed = self._get_passes_needed()

        if self.consecutive_passes >= passes_needed:
            next_stage = self.current_stage.next_stage()
            if next_stage:
                if next_stage == Stage.TRAINED:
                    self.is_trained = True
                    self.current_stage = Stage.TESTING
                    self.test_day = 0
                else:
                    self.current_stage = next_stage
                # Reset consecutive counters for new stage
                self.consecutive_passes = 0
                self.consecutive_fails = 0
                return True
        return False

    def _check_regression(self) -> bool:
        """Check if animal should regress to previous stage."""
        if self.consecutive_fails >= 3:
            prev_stage = self.current_stage.prev_stage()
            if prev_stage:
                self.current_stage = prev_stage
                # Reset consecutive counters, but NOT session counts
                self.consecutive_passes = 0
                self.consecutive_fails = 0
                return True
        return False

    def _get_passes_needed(self) -> int:
        """Get number of consecutive passes needed to advance from current stage."""
        if self.current_stage == Stage.MAG_TRAIN:
            return 1
        return 2  # FR1-30, FR1-10, FR5-10 all need 2 consecutive

    def get_status_text(self) -> str:
        """Get human-readable status text."""
        if self.is_trained or self.current_stage == Stage.TESTING:
            return f"Day {self.test_day}/7"

        passes_needed = self._get_passes_needed()

        if self.consecutive_passes > 0:
            remaining = passes_needed - self.consecutive_passes
            if remaining == 0:
                return "ADVANCING"
            return f"Need {remaining} more pass"

        if self.consecutive_fails >= 2:
            return "At risk"

        if self.consecutive_fails == 1:
            return "1 fail"

        return "Starting"

    def get_streak_text(self) -> str:
        """Get text describing current streak."""
        if self.is_trained or self.current_stage == Stage.TESTING:
            return f"Day {self.test_day}"

        if self.consecutive_passes > 0:
            return f"{self.consecutive_passes} pass"
        if self.consecutive_fails > 0:
            return f"{self.consecutive_fails} fail"
        return "-"

    def get_session_count(self) -> int:
        """Get total sessions at current stage."""
        if self.is_trained or self.current_stage == Stage.TESTING:
            return self.test_day
        return self.stage_session_counts.get(str(self.current_stage), 0)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "subject_id": self.subject_id,
            "cohort": self.cohort,
            "current_stage": str(self.current_stage),
            "stage_session_counts": self.stage_session_counts,
            "consecutive_passes": self.consecutive_passes,
            "consecutive_fails": self.consecutive_fails,
            "is_trained": self.is_trained,
            "test_day": self.test_day,
            "history": [
                {
                    "date": h.date,
                    "stage": str(h.stage),
                    "licks": h.licks,
                    "active_presses": h.active_presses,
                    "inactive_presses": h.inactive_presses,
                    "passed": h.passed,
                    "filename": h.filename,
                    "pass_status": h.pass_status,
                    "day_in_stage": h.day_in_stage,
                }
                for h in self.history
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AnimalState':
        """Deserialize from dictionary."""
        state = cls(
            subject_id=data["subject_id"],
            cohort=data.get("cohort", ""),
        )
        state.current_stage = Stage.from_string(data["current_stage"]) or Stage.MAG_TRAIN
        state.stage_session_counts = data.get("stage_session_counts", {})
        state.consecutive_passes = data.get("consecutive_passes", 0)
        state.consecutive_fails = data.get("consecutive_fails", 0)
        state.is_trained = data.get("is_trained", False)
        state.test_day = data.get("test_day", 0)

        for h in data.get("history", []):
            state.history.append(SessionResult(
                date=h["date"],
                subject_id=data["subject_id"],
                stage=Stage.from_string(h["stage"]) or Stage.MAG_TRAIN,
                licks=h["licks"],
                active_presses=h["active_presses"],
                inactive_presses=h["inactive_presses"],
                passed=h["passed"],
                filename=h.get("filename", ""),
                pass_status=h.get("pass_status", PassStatus.PASS if h["passed"] else PassStatus.FAIL),
                day_in_stage=h.get("day_in_stage", 1),
            ))

        return state
