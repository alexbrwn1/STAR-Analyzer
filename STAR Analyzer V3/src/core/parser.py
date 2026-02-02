"""
Med-PC IV file parser for STAR experiments.
Merges V2's class structure with V1's protocol detection.
"""

import re
from datetime import datetime, date, time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union

from .data_models import (
    SessionMetadata,
    ScalarVariables,
    TimestampArrays,
    ProtocolInfo,
    MedPCSession,
    ParseWarning,
    Stage,
)


class ParseError(Exception):
    """Raised when a file cannot be parsed."""
    pass


class MedPCParser:
    """Parser for Med-PC IV data files from STAR experiments."""

    # Header field patterns
    HEADER_PATTERNS = {
        'file': re.compile(r'^File:\s*(.+)$', re.IGNORECASE),
        'start_date': re.compile(r'^Start Date:\s*(\d{2}/\d{2}/\d{2})$', re.IGNORECASE),
        'end_date': re.compile(r'^End Date:\s*(\d{2}/\d{2}/\d{2})$', re.IGNORECASE),
        'subject': re.compile(r'^Subject:\s*(.+)$', re.IGNORECASE),
        'experiment': re.compile(r'^Experiment:\s*(.+)$', re.IGNORECASE),
        'group': re.compile(r'^Group:\s*(.+)$', re.IGNORECASE),
        'box': re.compile(r'^Box:\s*(\d+)$', re.IGNORECASE),
        'start_time': re.compile(r'^Start Time:\s*(\d{1,2}:\d{2}:\d{2})$', re.IGNORECASE),
        'end_time': re.compile(r'^End Time:\s*(\d{1,2}:\d{2}:\d{2})$', re.IGNORECASE),
        'msn': re.compile(r'^MSN:\s*(.+)$', re.IGNORECASE),
    }

    # Scalar variable pattern: "A:       3.000"
    SCALAR_PATTERN = re.compile(r'^([A-Z]):\s+([\d.]+)\s*$')

    # Array header pattern: "J:"
    ARRAY_HEADER_PATTERN = re.compile(r'^([A-Z]):\s*$')

    # Array data row pattern: "     0:   8.540  44.830  76.830  0.000  0.000"
    ARRAY_ROW_PATTERN = re.compile(r'^\s*\d+:\s*([\d.\s]+)$')

    # Variable mappings
    SCALAR_MAP = {
        'A': 'active_lever_presses',
        'B': 'inactive_lever_presses',
        'C': 'lick_count',
        'D': 'reinforcers',
        'E': 'lick_onsets',
        'F': 'lick_offsets',
        'T': 'session_time',
    }

    ARRAY_MAP = {
        'J': 'active_lever_timestamps',
        'K': 'inactive_lever_timestamps',
        'L': 'reinforcer_timestamps',
        'N': 'lick_onset_timestamps',
        'O': 'lick_offset_timestamps',
    }

    def __init__(self):
        self.warnings: List[ParseWarning] = []

    def parse_file(self, file_path: Path) -> MedPCSession:
        """
        Parse a Med-PC data file and return a MedPCSession object.

        Args:
            file_path: Path to the Med-PC data file

        Returns:
            MedPCSession containing all parsed data

        Raises:
            ParseError: If the file cannot be parsed
        """
        self.warnings = []

        # Read file content
        content = self._read_file(file_path)
        lines = content.splitlines()

        # Parse header
        header = self._parse_header(lines, file_path)

        # Parse variables (scalars and arrays)
        scalars, arrays = self._parse_variables(lines)

        # Extract protocol info from MSN
        protocol = extract_protocol_info(header.msn)

        # Create session object
        session = MedPCSession(
            metadata=header,
            scalars=scalars,
            timestamps=arrays,
            protocol=protocol,
            warnings=self.warnings.copy(),
        )

        # Validate array lengths
        validation_warnings = session.validate_array_lengths()
        session.warnings.extend(validation_warnings)

        return session

    def _read_file(self, file_path: Path) -> str:
        """Read file with encoding fallback."""
        encodings = ['utf-8', 'latin-1', 'cp1252']

        for encoding in encodings:
            try:
                return file_path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue

        raise ParseError(f"Could not decode file with any supported encoding: {file_path}")

    def _parse_header(self, lines: List[str], file_path: Path) -> SessionMetadata:
        """Parse header lines and extract metadata."""
        header_data: Dict[str, str] = {}

        # Parse first ~20 lines for header fields
        for line in lines[:20]:
            line = line.strip()
            if not line:
                continue

            for field_name, pattern in self.HEADER_PATTERNS.items():
                match = pattern.match(line)
                if match:
                    header_data[field_name] = match.group(1).strip()
                    break

        # Validate required fields
        required = ['subject', 'start_date', 'start_time', 'experiment', 'group', 'box', 'msn']
        missing = [f for f in required if f not in header_data]
        if missing:
            self.warnings.append(ParseWarning(
                f"Missing header fields: {', '.join(missing)}"
            ))

        # Parse date
        try:
            start_date = datetime.strptime(
                header_data.get('start_date', '01/01/00'), '%m/%d/%y'
            ).date()
        except ValueError:
            self.warnings.append(ParseWarning("Could not parse start date"))
            start_date = date(2000, 1, 1)

        # Parse times
        try:
            start_time = datetime.strptime(
                header_data.get('start_time', '00:00:00'), '%H:%M:%S'
            ).time()
        except ValueError:
            self.warnings.append(ParseWarning("Could not parse start time"))
            start_time = time(0, 0, 0)

        end_time = None
        if 'end_time' in header_data:
            try:
                end_time = datetime.strptime(header_data['end_time'], '%H:%M:%S').time()
            except ValueError:
                self.warnings.append(ParseWarning("Could not parse end time"))

        # Parse box number
        try:
            box = int(header_data.get('box', '0'))
        except ValueError:
            self.warnings.append(ParseWarning("Could not parse box number"))
            box = 0

        return SessionMetadata(
            file_path=file_path,
            subject=header_data.get('subject', 'Unknown'),
            start_date=start_date,
            start_time=start_time,
            end_time=end_time,
            experiment=header_data.get('experiment', 'Unknown'),
            group=header_data.get('group', 'Unknown'),
            box=box,
            msn=header_data.get('msn', 'Unknown'),
        )

    def _parse_variables(self, lines: List[str]) -> Tuple[ScalarVariables, TimestampArrays]:
        """Parse scalar variables and timestamp arrays."""
        scalars = ScalarVariables()
        arrays = TimestampArrays()

        current_array: Optional[str] = None
        array_values: List[float] = []

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Check for array header (e.g., "J:")
            array_match = self.ARRAY_HEADER_PATTERN.match(line_stripped)
            if array_match:
                # Save previous array if any
                if current_array and current_array in self.ARRAY_MAP:
                    self._set_array(arrays, current_array, array_values)

                current_array = array_match.group(1)
                array_values = []
                continue

            # Check for array data row
            row_match = self.ARRAY_ROW_PATTERN.match(line)
            if row_match and current_array:
                values_str = row_match.group(1)
                values = self._parse_array_row(values_str)
                array_values.extend(values)
                continue

            # Check for scalar variable (e.g., "A:       3.000")
            scalar_match = self.SCALAR_PATTERN.match(line_stripped)
            if scalar_match:
                # Save previous array if transitioning out
                if current_array and current_array in self.ARRAY_MAP:
                    self._set_array(arrays, current_array, array_values)
                    current_array = None
                    array_values = []

                var_name = scalar_match.group(1)
                var_value = scalar_match.group(2)
                self._set_scalar(scalars, var_name, var_value)

        # Save final array if any
        if current_array and current_array in self.ARRAY_MAP:
            self._set_array(arrays, current_array, array_values)

        return scalars, arrays

    def _parse_array_row(self, values_str: str) -> List[float]:
        """Parse space-separated values from an array row."""
        values = []
        for part in values_str.split():
            try:
                values.append(float(part))
            except ValueError:
                continue
        return values

    def _set_scalar(self, scalars: ScalarVariables, var_name: str, value_str: str) -> None:
        """Set a scalar variable value."""
        if var_name not in self.SCALAR_MAP:
            return

        attr_name = self.SCALAR_MAP[var_name]
        try:
            value = float(value_str)
            if attr_name == 'session_time':
                setattr(scalars, attr_name, value)
            else:
                setattr(scalars, attr_name, int(value))
        except ValueError:
            self.warnings.append(ParseWarning(
                f"Could not parse value: {value_str}",
                variable=var_name
            ))

    def _set_array(self, arrays: TimestampArrays, var_name: str, values: List[float]) -> None:
        """Set an array variable, trimming trailing zeros."""
        if var_name not in self.ARRAY_MAP:
            return

        attr_name = self.ARRAY_MAP[var_name]

        # Trim trailing zeros (Med-PC padding)
        trimmed = self._trim_trailing_zeros(values)

        setattr(arrays, attr_name, trimmed)

    def _trim_trailing_zeros(self, values: List[float]) -> List[float]:
        """Remove trailing zeros from array (Med-PC pads arrays with zeros)."""
        if not values:
            return values

        # Find last non-zero value
        last_nonzero = -1
        for i in range(len(values) - 1, -1, -1):
            if values[i] != 0.0:
                last_nonzero = i
                break

        if last_nonzero == -1:
            # All zeros - return empty list
            return []

        return values[:last_nonzero + 1]


# =============================================================================
# Protocol Info Extraction (from V1)
# =============================================================================

def extract_protocol_info(msn: str) -> ProtocolInfo:
    """
    Parse MSN (protocol) string to extract experimental parameters.

    Expected MSN format examples:
    - "FR5_LEFT_10s" -> FR5 schedule, left active lever, 10s sipper
    - "FR1_RIGHT_30s" -> FR1 schedule, right active lever, 30s sipper
    - "SIPPER_FR3_L_10SEC" -> FR3 schedule, left active, 10s sipper
    - "01_LEFT_STAR_Acq_FR1_30s_NoCap" -> FR1, left, 30s

    Args:
        msn: The MSN protocol string

    Returns:
        ProtocolInfo with extracted parameters
    """
    msn_upper = msn.upper()

    # Extract active lever side
    active_lever = None
    if 'LEFT' in msn_upper or '_L_' in msn_upper or msn_upper.endswith('_L'):
        active_lever = 'LEFT'
    elif 'RIGHT' in msn_upper or '_R_' in msn_upper or msn_upper.endswith('_R'):
        active_lever = 'RIGHT'

    # Extract FR schedule
    fr_schedule = None
    fr_match = re.search(r'FR\s*(\d+)', msn_upper)
    if fr_match:
        fr_schedule = int(fr_match.group(1))

    # Extract sipper duration
    sipper_duration = None
    # Try patterns like "10s", "10sec", "30S", "30SEC"
    duration_match = re.search(r'(\d+)\s*(?:S|SEC)\b', msn_upper)
    if duration_match:
        sipper_duration = int(duration_match.group(1))
    else:
        # Try pattern like "FR10-10" where second number is duration
        fr_duration_match = re.search(r'FR\d+[-_](\d+)', msn_upper)
        if fr_duration_match:
            sipper_duration = int(fr_duration_match.group(1))

    return ProtocolInfo(
        active_lever=active_lever,
        fr_schedule=fr_schedule,
        sipper_duration=sipper_duration
    )


def detect_training_stage(msn: str) -> Optional[Stage]:
    """
    Detect training stage from MSN protocol string.

    Returns one of:
    - Stage.MAG_TRAIN - Magazine training
    - Stage.FR1_30 - FR1 with 30s sipper
    - Stage.FR1_10 - FR1 with 10s sipper
    - Stage.FR5_10 - FR5 with 10s sipper
    - Stage.TESTING - FR10 with 10s sipper (testing)
    - None if stage cannot be determined

    Args:
        msn: The MSN protocol string from MedPC file

    Returns:
        Stage enum or None
    """
    msn_upper = msn.upper()

    # Check for magazine training
    if any(x in msn_upper for x in ["MAG", "MAGAZINE"]):
        return Stage.MAG_TRAIN

    # Extract protocol info
    protocol = extract_protocol_info(msn)
    fr = protocol.fr_schedule
    duration = protocol.sipper_duration

    if fr is None:
        return None

    # Map FR + duration to stage
    if fr == 10 and duration == 10:
        return Stage.TESTING
    elif fr == 5 and duration == 10:
        return Stage.FR5_10
    elif fr == 1:
        if duration == 30:
            return Stage.FR1_30
        elif duration == 10:
            return Stage.FR1_10

    # Try to infer from common naming patterns
    if "FR1" in msn_upper:
        if "30" in msn_upper:
            return Stage.FR1_30
        elif "10" in msn_upper:
            return Stage.FR1_10
    elif "FR5" in msn_upper and "10" in msn_upper:
        return Stage.FR5_10
    elif "FR10" in msn_upper and "10" in msn_upper:
        return Stage.TESTING

    return None


def get_session_display_name(session: MedPCSession) -> str:
    """Generate a display name for a session based on its metadata."""
    subject = session.metadata.subject
    date_str = session.metadata.start_date.strftime("%Y-%m-%d")
    time_str = session.metadata.start_time.strftime("%H:%M")

    return f"{date_str} {time_str} - Subject {subject}"


# =============================================================================
# Convenience Functions
# =============================================================================

def parse_medpc_file(file_path: Union[str, Path]) -> MedPCSession:
    """
    Convenience function to parse a single Med-PC file.

    Args:
        file_path: Path to the Med-PC data file

    Returns:
        MedPCSession containing all parsed data
    """
    parser = MedPCParser()
    return parser.parse_file(Path(file_path))


def parse_multiple_files(filepaths: List[Union[str, Path]]) -> List[MedPCSession]:
    """
    Parse multiple MedPC data files.

    Args:
        filepaths: List of paths to MedPC data files

    Returns:
        List of parsed MedPCSession objects
    """
    parser = MedPCParser()
    results = []
    for filepath in filepaths:
        try:
            session = parser.parse_file(Path(filepath))
            results.append(session)
        except Exception as e:
            print(f"Error parsing {filepath}: {e}")
    return results
