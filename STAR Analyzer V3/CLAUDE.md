# STAR Analyzer V3 - Developer Reference

This document is intended for AI assistants and developers making future code changes.

## Project Overview

STAR Analyzer V3 is a desktop application for analyzing Med-PC IV data files from STAR (Structured Tracking of Alcohol Reinforcement) rodent operant experiments. It combines functionality from two previous versions:

- **V1**: Complete functionality with raster plots and progress tracking, but messy code and CustomTkinter dependency
- **V2**: Clean architecture with standard ttk widgets, but limited features

V3 uses V2's clean architecture with V1's complete functionality, all in standard tkinter/ttk.

## Architecture

```
STAR Analyzer V3/
├── src/
│   ├── main.py                 # Entry point - just calls gui.app.run()
│   ├── core/                   # GUI-independent business logic
│   │   ├── data_models.py      # Dataclasses: Stage, PassStatus, SessionResult, AnimalState, MedPCSession
│   │   ├── parser.py           # MedPC file parsing, protocol detection
│   │   ├── file_discovery.py   # Recursive file scanning with pattern matching
│   │   ├── tracker.py          # CohortTracker, check_pass_criteria(), progression logic
│   │   ├── plotting.py         # Matplotlib raster plots with pass/fail badges
│   │   ├── exporters.py        # Excel export with multi-sheet support
│   │   └── session_manager.py  # Central data layer with observer callbacks
│   └── gui/                    # tkinter/ttk GUI layer
│       ├── app.py              # Main window, two-tab interface
│       ├── config.py           # ConfigManager for persisting user settings
│       ├── import_dialog.py    # Thread-safe import with progress bar
│       └── tracker_view.py     # DayByDayTable, NextDaySetupPanel, SubjectHistoryPanel
```

## Key Files and Their Origins

| File | Source | Description |
|------|--------|-------------|
| `core/data_models.py` | V2 + V1 | V2's dataclasses extended with V1's Stage enum, PassStatus, AnimalState, SessionResult |
| `core/parser.py` | V2 + V1 | V2's regex parser + V1's `detect_training_stage()` and `extract_protocol_info()` |
| `core/tracker.py` | V1 | CohortTracker class, `check_pass_criteria()`, date parsing helpers |
| `core/plotting.py` | V1 | Raster plot generation with pass/fail badges, sipper periods, 100-lick line |
| `core/session_manager.py` | New | Central data layer combining parsed sessions and tracker state |
| `core/exporters.py` | New | Multi-sheet Excel export using openpyxl |
| `gui/app.py` | V2 + New | V2's ttk structure with scrollable plots and TrackerView integration |
| `gui/import_dialog.py` | V2 | Thread-safe import using queue.Queue pattern |
| `gui/tracker_view.py` | V1 | Ported from CustomTkinter to standard ttk - DayByDayTable canvas grid |
| `gui/config.py` | V2 | JSON config persistence for last folder, window geometry |

## Data Flow

```
User imports folder
    │
    ▼
ImportDialog discovers files (file_discovery.py)
    │
    ▼
Parser creates MedPCSession objects (parser.py)
    │
    ▼
SessionManager.load_folder()
    ├─► Stores ParsedSession objects (for plotting)
    └─► Builds CohortTracker state (for tracking)
    │
    ▼
SessionManager._notify_data_changed()
    ├─► app.py._on_data_changed() → updates raster plots
    └─► TrackerView._on_data_changed() → updates DayByDayTable
```

## Important Classes

### ParsedSession (session_manager.py:36-111)
Wrapper around MedPCSession with quick-access attributes for GUI display:
- `subject_id`, `date`, `stage`, `stage_name`
- `licks`, `active_presses`, `inactive_presses`, `reinforcers`
- `passed`, `pass_status`
- `raw_data` property for plotting compatibility

### SessionManager (session_manager.py:114-424)
Central data layer with observer pattern:
- `load_folder(path)` - parses files, builds tracker state, notifies callbacks
- `get_all_sessions()` - returns List[ParsedSession]
- `get_tracker()` - returns CohortTracker
- `add_data_changed_callback(fn)` - register for data change notifications

### CohortTracker (tracker.py)
Tracks animal progression through training stages:
- `animals: Dict[str, AnimalState]` - keyed by subject ID
- `get_all_animals()` - returns sorted list of AnimalState

### AnimalState (data_models.py)
Per-animal state machine:
- `current_stage: Stage`
- `consecutive_passes`, `consecutive_fails`
- `history: List[SessionResult]`
- `process_session(result)` - updates state based on pass/fail

## Pass Criteria (tracker.py)

| Stage | Lick Requirement | Discrimination | Passes to Advance |
|-------|------------------|----------------|-------------------|
| MAG_TRAIN | ≥100 | - | 1 |
| FR1_30 | ≥100 | - | 2 consecutive |
| FR1_10 | ≥100 | - | 2 consecutive |
| FR5_10 | ≥100 | ≥70% | 2 consecutive |
| TESTING | Always passes | - | 7 days total |

- 3 consecutive failures → regression to previous stage
- "Partial" pass = met one FR5-10 criterion but not both (yellow badge)

## GUI Components

### Raster Plots Tab (app.py)
- Left panel: Subject filter dropdown, session listbox with multi-select
- Right panel: Scrollable canvas containing matplotlib figure
- Mouse wheel scrolling bound to canvas and figure widget

### Progress Tracker Tab (tracker_view.py)
- **NextDaySetupPanel**: Table showing next session for each animal
- **DayByDayTable**: Canvas-drawn grid with color-coded pass/fail cells
- **SubjectHistoryPanel**: Dropdown + detailed history table for one animal

### Scrollable Plot Implementation (app.py:175-213)
```python
self.plot_canvas = tk.Canvas(...)  # Outer scrollable canvas
self.plot_interior = ttk.Frame(self.plot_canvas)  # Inner frame for matplotlib
self.plot_canvas.create_window((0, 0), window=self.plot_interior, anchor='nw')
# Mouse wheel bindings on canvas, interior, and matplotlib widget
```

## Excel Export (exporters.py)

ExcelExporter creates multi-sheet workbooks:
- Sheet 1: "All Sessions" - all data sorted by subject then date
- Sheet 2+: "Subject N" - per-subject filtered data

Columns: Subject, Date, Time, Experiment, Stage, Active, Inactive, Licks, Reinforcers, Discrim%, Duration, Pass, MSN

## Thread Safety

Import operations run in background thread (import_dialog.py):
- `_run_import()` runs in daemon thread
- Uses `queue.Queue` for thread-safe UI updates
- Main thread polls queue with `after(50, _process_queue)`

## Common Modifications

### Adding a new training stage
1. Add to `Stage` enum in `data_models.py`
2. Add detection pattern in `parser.py:detect_training_stage()`
3. Add pass criteria in `tracker.py:check_pass_criteria()`
4. Add display name in `session_manager.py:_parse_session()`
5. Add short name in `tracker_view.py:_short_stage_name()`

### Adding a new export column
1. Add to `COLUMNS` list in `exporters.py`
2. Add value to return list in `_session_to_row()`

### Adding a new tracker panel
1. Create class in `tracker_view.py` extending `ttk.Frame` or `ttk.LabelFrame`
2. Instantiate in `TrackerView._create_widgets()`
3. Update in `TrackerView._update_display()`

## Dependencies

- **matplotlib**: Raster plot generation (TkAgg backend)
- **openpyxl**: Excel file creation with formatting
- **pandas**: Not currently used, but available for future data manipulation
- Standard library: tkinter, threading, queue, dataclasses, pathlib, re, json

## Testing

Mock data location: `STAR Analyzer V1/Mock Cohort 1 Data by Day/`
- Contains 11 days of data for 3 subjects
- Covers all training stages from MAG_TRAIN through FR10-10 testing
