# STAR Analyzer V2 - Project Reference

## Overview

A Python + Tkinter desktop application for parsing and analyzing Med-PC IV data files from STAR (rodent operant self-administration) experiments. Designed for behavioral neuroscience research.

---

## Technology Stack

- **Python 3.8+** with Tkinter (built-in GUI)
- **openpyxl** for Excel export (.xlsx)
- **PyInstaller** for standalone .exe packaging
- Target size: 20-35 MB executable

---

## Project Structure

```
STAR_Analyzer_V2/
├── src/
│   ├── main.py                    # Entry point
│   ├── core/                      # GUI-independent logic
│   │   ├── __init__.py
│   │   ├── parser.py              # Med-PC file parser
│   │   ├── data_models.py         # Dataclasses (Session, Cohort, etc.)
│   │   ├── file_discovery.py      # File/folder scanning
│   │   └── exporters.py           # Excel export (.xlsx)
│   └── gui/                       # Tkinter components
│       ├── __init__.py
│       ├── app.py                 # Main window
│       ├── import_dialog.py       # Folder selection + progress
│       └── data_viewer.py         # Treeview table display
├── resources/                     # (for icon.ico if added)
├── requirements.txt               # openpyxl, pyinstaller
├── build.spec                     # PyInstaller config
├── test_parser.py                 # Parser verification tests
└── test_export.py                 # Export verification tests
```

---

## Data File Format (Med-PC IV)

**Filename pattern:** `!YYYY-MM-DD_HHhMMm.Subject #`

**Structure:**
```
File: C:\MED-PC IV\DATA\...
Start Date: 01/26/26
Subject: 1
Experiment: FR1-30 Day 1
Group: Mock Cohort 1
Box: 1
MSN: 01_LEFT_STAR_Acq_FR1_30s_NoCap
A:       3.000          <- Scalar variables
...
J:                      <- Array header
     0:   8.540  44.830  76.830  0.000  0.000   <- 5-column data rows
```

---

## Key Variables Parsed

| Variable | Type    | Array | Description                     |
|----------|---------|-------|---------------------------------|
| A        | Counter | J     | Active lever presses            |
| B        | Counter | K     | Inactive lever presses          |
| D        | Counter | L     | Reinforcers (sipper extensions) |
| E        | Counter | N     | Lick onsets                     |
| F        | Counter | O     | Lick offsets                    |
| T        | Timer   | -     | Session duration (seconds)      |

---

## Core Data Models

```python
@dataclass
class SessionMetadata:
    file_path, subject, start_date, start_time, end_time
    experiment, group, box, msn

@dataclass
class ScalarVariables:
    active_lever_presses (A), inactive_lever_presses (B)
    reinforcers (D), lick_onsets (E), lick_offsets (F)
    session_time (T)

@dataclass
class TimestampArrays:
    active_lever_timestamps (J), inactive_lever_timestamps (K)
    reinforcer_timestamps (L), lick_onset_timestamps (N), lick_offset_timestamps (O)

@dataclass
class MedPCSession:
    metadata, scalars, timestamps

@dataclass
class Cohort:
    name, sessions[], source_path
```

---

## Implementation Status

### Completed Features (Phase 1)

1. **Core Parser** (`parser.py`)
   - Parses Med-PC IV files with header metadata extraction
   - Handles scalar variables (A, B, D, E, F, T)
   - Handles timestamp arrays (J, K, L, N, O) in 5-column format
   - Automatic trimming of trailing zeros (Med-PC padding)
   - Validation that array lengths match counter values
   - UTF-8 encoding with latin-1/cp1252 fallback

2. **File Discovery** (`file_discovery.py`)
   - Scans folders recursively for Med-PC files
   - Matches filename pattern `!YYYY-MM-DD_HHhMMm.Subject #`

3. **Excel Export** (`exporters.py`)
   - Summary sheet with all session data
   - Optional timestamp sheets per session
   - Proper formatting and column widths
   - **Discrimination %** column: `(active presses / total presses) * 100`

4. **GUI Application**
   - Import dialog with progress bar and background threading
   - Data viewer with sortable columns
   - **Three view modes:**
     - **All Sessions** - Every session on its own row
     - **By Subject** - Filter to show one animal's sessions
     - **By Date** - Filter to show all sessions from one day
   - Session detail dialog (double-click to view)
   - Path memory (remembers last import folder in `~/.star_analyzer/config.json`)
   - Export to Excel functionality

5. **PyInstaller Build** (`build.spec`)
   - Configured for single-file Windows executable
   - UPX compression enabled
   - No console window (GUI app)

---

## Running the Application

### Development
```bash
cd "STAR Analyzer V2"
pip install -r requirements.txt
python src/main.py
```

### Build Executable
```bash
pip install pyinstaller
pyinstaller build.spec
# Output: dist/STAR_Analyzer.exe
```

### Run Tests
```bash
python test_parser.py    # Parser verification
python test_export.py    # Export verification
```

---

## Verified Results

- Parsed all 33 test files from Mock Cohort 1 with 0 errors
- All counter values match array lengths (A/J, B/K, D/L, E/N, F/O)
- Excel export produces valid .xlsx files
- GUI launches and runs correctly

---

## Key Files Reference

- **Sample data:** `Mock Cohort 1 Data by Day/Day 2/!2026-01-26_13h25m.Subject 1`
- **Variable definitions:** `STAR Code for MedPC/01_LEFT_STAR_Acq_FR1_30s_NoCap.txt`

---

## Modularity for Future Tools

The `core/` module is completely independent of the GUI. Future analysis tools can import directly:

```python
from star_analyzer.core.parser import parse_medpc_file
from star_analyzer.core.data_models import MedPCSession

session = parse_medpc_file(Path("data/file.txt"))
lick_times = session.timestamps.lick_onset_timestamps
```

---

## Pending/Future Features

*Add new feature requests here as they are discussed:*

1. *(placeholder for next feature)*

---

## Bug Fixes Applied

1. **Import Dialog Threading** - Fixed callback issues by using a message queue pattern for thread-safe UI updates
2. **View Modes** - Added three view modes (All Sessions, By Subject, By Date) as requested
3. **Discrimination Index** - Added calculation: `(active presses / total presses) * 100`

---

## Session History

- **Initial Implementation:** Core parser, file discovery, Excel export, full GUI
- **Bug Fix:** Import dialog wasn't loading data due to threading issues
- **Feature Add:** Three view modes + discrimination index

---

*Last updated: 2026-01-28*
