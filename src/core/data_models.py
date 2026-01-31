"""
Data models for STAR Analyzer.
Dataclasses representing parsed Med-PC IV session data.
"""

from dataclasses import dataclass, field
from datetime import datetime, date, time
from pathlib import Path
from typing import List, Optional


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
