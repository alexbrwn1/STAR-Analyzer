"""
File discovery for Med-PC data files.
Scans folders to find valid STAR experiment data files.
"""

import re
from pathlib import Path
from typing import List, Iterator, Optional


# Filename pattern: !YYYY-MM-DD_HHhMMm.Subject #
# Examples: !2026-01-26_13h25m.Subject 1
MEDPC_FILENAME_PATTERN = re.compile(
    r'^!(\d{4})-(\d{2})-(\d{2})_(\d{2})h(\d{2})m\.Subject\s*(\d+)$'
)

# Extensions to skip (non-MedPC files)
SKIP_EXTENSIONS = {'.md', '.xlsx', '.csv', '.xls', '.json', '.py', '.bat', '.pyw', '.txt', '.log'}


def is_medpc_file(file_path: Path) -> bool:
    """
    Check if a file appears to be a Med-PC data file.

    Uses filename pattern matching as primary check.

    Args:
        file_path: Path to check

    Returns:
        True if file matches Med-PC naming pattern
    """
    if not file_path.is_file():
        return False

    # Skip known non-data extensions
    if file_path.suffix.lower() in SKIP_EXTENSIONS:
        return False

    # Check filename pattern
    return MEDPC_FILENAME_PATTERN.match(file_path.name) is not None


def discover_medpc_files(folder_path: Path, recursive: bool = True) -> List[Path]:
    """
    Find all Med-PC data files in a folder.

    Args:
        folder_path: Root folder to search
        recursive: If True, search subdirectories

    Returns:
        List of paths to Med-PC data files, sorted by path
    """
    files = list(scan_folder_recursive(folder_path) if recursive else scan_folder(folder_path))
    return sorted(files)


def scan_folder(folder_path: Path) -> Iterator[Path]:
    """
    Scan a single folder (non-recursive) for Med-PC files.

    Args:
        folder_path: Folder to scan

    Yields:
        Paths to Med-PC data files
    """
    if not folder_path.is_dir():
        return

    for item in folder_path.iterdir():
        if is_medpc_file(item):
            yield item


def scan_folder_recursive(folder_path: Path) -> Iterator[Path]:
    """
    Recursively scan a folder tree for Med-PC files.

    Args:
        folder_path: Root folder to scan

    Yields:
        Paths to Med-PC data files
    """
    if not folder_path.is_dir():
        return

    for item in folder_path.rglob('*'):
        if is_medpc_file(item):
            yield item


def extract_filename_info(file_path: Path) -> Optional[dict]:
    """
    Extract date/time/subject info from Med-PC filename.

    Args:
        file_path: Path to Med-PC file

    Returns:
        Dict with year, month, day, hour, minute, subject_number
        or None if filename doesn't match pattern
    """
    match = MEDPC_FILENAME_PATTERN.match(file_path.name)
    if not match:
        return None

    return {
        'year': int(match.group(1)),
        'month': int(match.group(2)),
        'day': int(match.group(3)),
        'hour': int(match.group(4)),
        'minute': int(match.group(5)),
        'subject_number': int(match.group(6)),
    }


def group_files_by_folder(files: List[Path]) -> dict:
    """
    Group files by their parent folder.

    Args:
        files: List of file paths

    Returns:
        Dict mapping folder path to list of files
    """
    groups = {}
    for f in files:
        parent = f.parent
        if parent not in groups:
            groups[parent] = []
        groups[parent].append(f)
    return groups


def group_files_by_subject(files: List[Path]) -> dict:
    """
    Group files by subject number (from filename).

    Args:
        files: List of file paths

    Returns:
        Dict mapping subject number (str) to list of files
    """
    groups = {}
    for f in files:
        info = extract_filename_info(f)
        if info:
            subject = str(info['subject_number'])
            if subject not in groups:
                groups[subject] = []
            groups[subject].append(f)
    return groups


def group_files_by_date(files: List[Path]) -> dict:
    """
    Group files by date (from filename).

    Args:
        files: List of file paths

    Returns:
        Dict mapping date string (YYYY-MM-DD) to list of files
    """
    groups = {}
    for f in files:
        info = extract_filename_info(f)
        if info:
            date_str = f"{info['year']}-{info['month']:02d}-{info['day']:02d}"
            if date_str not in groups:
                groups[date_str] = []
            groups[date_str].append(f)
    return groups
