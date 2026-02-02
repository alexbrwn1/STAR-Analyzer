# STAR Analyzer V3

A desktop application for parsing and analyzing Med-PC IV data files from STAR (Structured Tracking of Alcohol Reinforcement) rodent operant self-administration experiments.

## What It Does

STAR Analyzer helps behavioral neuroscience researchers:

1. **Import Med-PC data** - Automatically discovers and parses Med-PC IV output files from a folder
2. **Visualize sessions** - Generate raster plots showing lever presses, licks, and reinforcer deliveries over time
3. **Track training progress** - Monitor each animal's progression through STAR training stages with pass/fail criteria
4. **Export to Excel** - Create formatted spreadsheets with all session data organized by subject

## Features

### Raster Plots Tab
- View timestamped behavioral events (active/inactive lever presses, licks, reinforcers)
- Color-coded pass/fail badges on each plot
- Sipper access periods highlighted
- 100-lick criterion line for quick visual assessment
- Scrollable view for multiple sessions
- Filter by subject
- Save plots as PNG or PDF

### Progress Tracker Tab
- Day-by-day grid showing all animals' training progression
- Color-coded cells: Green = Pass, Yellow = Partial, Red = Fail
- Next day setup panel showing what stage each animal should run
- Individual animal history with detailed session metrics

### Excel Export
- "All Sessions" sheet with complete dataset
- Separate sheet for each subject
- Includes: Date, Time, Stage, Lever Presses, Licks, Reinforcers, Discrimination %, Pass/Fail

---

## Installation

### Prerequisites

You need Python 3.10 or newer installed on your computer.

To check your Python version, open a terminal/command prompt and run:
```
python --version
```

### Step 1: Download the Application

Download or clone the STAR Analyzer V3 folder to your computer.

### Step 2: Install Required Packages

Open a terminal/command prompt, navigate to the STAR Analyzer V3 folder, and run:

```
pip install matplotlib openpyxl pandas
```

**What these packages do:**

| Package | Purpose |
|---------|---------|
| `matplotlib` | Creates the raster plot visualizations |
| `openpyxl` | Writes formatted Excel (.xlsx) files |
| `pandas` | Data manipulation library (used for data processing) |

These are all well-established, trusted Python packages from the Python Package Index (PyPI).

### Step 3: Verify Installation

Run the application to verify everything is installed correctly:

```
cd "STAR Analyzer V3/src"
python main.py
```

The application window should open.

---

## How to Use

### Importing Data

1. Click **Import Data** button (or press `Ctrl+I`)
2. Browse to select a folder containing Med-PC data files
3. The application will scan for files recursively (including subfolders)
4. Wait for the progress bar to complete
5. Your data will appear in both the Raster Plots and Progress Tracker tabs

**Supported file formats:**
- Standard Med-PC IV output files (no extension or various extensions)
- Files are identified by their internal structure, not filename

**Recommended folder structure:**
```
My Cohort/
├── Day 1/
│   ├── Subject1_data
│   ├── Subject2_data
│   └── Subject3_data
├── Day 2/
│   └── ...
```

### Viewing Raster Plots

1. Go to the **Raster Plots** tab
2. Use the **Subject** dropdown to filter by animal (or select "All")
3. Click sessions in the list to select them (Ctrl+click for multiple)
4. Use **Select All** / **Select None** buttons for quick selection
5. Scroll the plot area with your mouse wheel to view all plots

### Tracking Progress

1. Go to the **Progress Tracker** tab
2. The **Next Day Setup** panel shows what stage each animal should run tomorrow
3. The **Training Progress** grid shows day-by-day pass/fail status
4. Use the **Individual Training History** dropdown to see detailed metrics for one animal

### Exporting Data

1. Click **Export Stats** button (or press `Ctrl+E`)
2. Choose a location and filename for your Excel file
3. The exported file will contain:
   - **All Sessions** sheet: Complete dataset
   - **Subject 1**, **Subject 2**, etc.: Per-animal sheets

### Saving Plots

1. With plots displayed, click **Save Plots**
2. Choose PNG (for images) or PDF (for documents)
3. All currently displayed plots will be saved to the file

---

## STAR Training Stages

The application automatically detects these training stages from the MSN (program name) field:

| Stage | Description | Pass Criteria |
|-------|-------------|---------------|
| Mag Train | Magazine training | ≥100 licks (1 pass to advance) |
| FR1-30 | Fixed ratio 1, 30 min | ≥100 licks (2 consecutive passes) |
| FR1-10 | Fixed ratio 1, 10 min | ≥100 licks (2 consecutive passes) |
| FR5-10 | Fixed ratio 5, 10 min | ≥100 licks AND ≥70% discrimination (2 consecutive passes) |
| FR10-10 | Testing phase | 7 days total |

**Regression rule:** 3 consecutive failures returns the animal to the previous stage.

---

## Troubleshooting

### "No Med-PC data files found"
- Ensure your files are actual Med-PC output files (check they contain "Start Date:", "Subject:", etc.)
- Try selecting the parent folder if files are in subfolders

### Import errors
- Check that files aren't corrupted or incomplete
- The application will skip files it can't parse and show a count of skipped files

### Plots not displaying
- Ensure you have sessions selected in the list
- Try clicking "Refresh Plots" from the View menu

### Application won't start
- Verify Python is installed: `python --version`
- Verify packages are installed: `pip list | grep matplotlib`
- Check for error messages in the terminal

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+I` | Open Import Dialog |
| `Ctrl+E` | Export to Excel |
| `Alt+F4` | Exit Application |

---

## Data Privacy

This application runs entirely on your local computer. No data is sent to the internet. All processing happens locally using only the files you select.

---

## Support

For issues or questions, contact the developer or open an issue in the project repository.
