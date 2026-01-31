"""
Med-PC IV file parser for STAR experiments.
Parses data files and extracts session metadata, scalar variables, and timestamp arrays.
"""

import re
from datetime import datetime, date, time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .data_models import (
    SessionMetadata,
    ScalarVariables,
    TimestampArrays,
    MedPCSession,
    ParseWarning,
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

        # Create session object
        session = MedPCSession(
            metadata=header,
            scalars=scalars,
            timestamps=arrays,
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

        # Parse first ~15 lines for header fields
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


def parse_medpc_file(file_path: Path) -> MedPCSession:
    """
    Convenience function to parse a single Med-PC file.

    Args:
        file_path: Path to the Med-PC data file

    Returns:
        MedPCSession containing all parsed data
    """
    parser = MedPCParser()
    return parser.parse_file(file_path)
