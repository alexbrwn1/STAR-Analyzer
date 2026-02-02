"""
Progress Tracker GUI components for STAR Analyzer V3.
Ported from V1's CustomTkinter implementation to standard ttk.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import Optional, List, Dict, TYPE_CHECKING
import re

from core.data_models import Stage, PassStatus, AnimalState, SessionResult
from core.tracker import CohortTracker, generate_next_day_report

if TYPE_CHECKING:
    from core.session_manager import SessionManager


# Colors for pass status: (background_fill, text_color)
STATUS_COLORS = {
    PassStatus.PASS: ("#90EE90", "#228B22"),      # Light green / Dark green
    PassStatus.PARTIAL: ("#FFFF99", "#B8860B"),   # Light yellow / Dark goldenrod
    PassStatus.FAIL: ("#FFB6C1", "#DC143C"),      # Light pink / Crimson
}


def _short_stage_name(stage: Stage) -> str:
    """Get shortened program name for display."""
    names = {
        Stage.MAG_TRAIN: "Mag Train",
        Stage.FR1_30: "FR1-30",
        Stage.FR1_10: "FR1-10",
        Stage.FR5_10: "FR5-10",
        Stage.TESTING: "FR10-10",
        Stage.TRAINED: "FR10-10",
    }
    return names.get(stage, str(stage))


def _next_session_info(animal: AnimalState) -> tuple:
    """Return (program_name, day_number) for the animal's next session."""
    if animal.is_trained or animal.current_stage == Stage.TESTING:
        if animal.test_day >= 7:
            return ("Complete", "")
        return ("FR10-10", animal.test_day + 1)

    stage = animal.current_stage
    day_count = sum(1 for s in animal.history if s.stage == stage)
    return (_short_stage_name(stage), day_count + 1)


# =============================================================================
# DayByDayTable - Canvas-drawn grid showing day-by-day progression
# =============================================================================

class DayByDayTable(ttk.Frame):
    """Scrollable table showing day-by-day progression for all animals.

    Uses direct Canvas drawing for pixel-perfect grid alignment.
    """

    # Cell dimensions (pixels)
    ID_COL_WIDTH = 80
    PROG_WIDTH = 65
    DAY_WIDTH = 35
    PROGRESS_WIDTH = 55
    DAY_GROUP_WIDTH = PROG_WIDTH + DAY_WIDTH + PROGRESS_WIDTH   # 155
    NEXT_DAY_WIDTH = PROG_WIDTH + DAY_WIDTH                     # 100

    HEADER_ROW1_HEIGHT = 25
    HEADER_ROW2_HEIGHT = 22
    HEADER_HEIGHT = HEADER_ROW1_HEIGHT + HEADER_ROW2_HEIGHT     # 47
    DATA_ROW_HEIGHT = 28

    # Drawing colours
    HEADER_BG = "#D9D9D9"
    HEADER_TEXT = "#000000"
    GRID_COLOR = "#AAAAAA"
    DATA_BG = "#FFFFFF"
    DATA_TEXT = "#000000"

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.canvas = tk.Canvas(self, bg="white", highlightthickness=0)
        self.h_scrollbar = ttk.Scrollbar(
            self, orient="horizontal", command=self.canvas.xview
        )
        self.v_scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview
        )
        self.canvas.configure(
            xscrollcommand=self.h_scrollbar.set,
            yscrollcommand=self.v_scrollbar.set,
        )

        # Layout
        self.h_scrollbar.pack(side="bottom", fill="x")
        self.v_scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        # Mouse wheel bindings
        self._wheel_bound = False
        self.canvas.bind("<Enter>", self._on_enter)
        self.canvas.bind("<Leave>", self._on_leave)

    def _on_enter(self, event):
        if not self._wheel_bound:
            self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
            self.canvas.bind_all("<Shift-MouseWheel>", self._on_shift_mousewheel)
            self._wheel_bound = True

    def _on_leave(self, event):
        if self._wheel_bound:
            self.canvas.unbind_all("<MouseWheel>")
            self.canvas.unbind_all("<Shift-MouseWheel>")
            self._wheel_bound = False

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_shift_mousewheel(self, event):
        self.canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")

    def _draw_cell(self, x, y, w, h, text, bg, fg, bold=False, font_size=10):
        """Draw a rectangle cell with centred text."""
        self.canvas.create_rectangle(
            x, y, x + w, y + h, fill=bg, outline=self.GRID_COLOR
        )
        weight = "bold" if bold else "normal"
        self.canvas.create_text(
            x + w // 2, y + h // 2,
            text=text, fill=fg,
            font=("Segoe UI", font_size, weight),
        )

    def populate(self, animals: List[AnimalState]):
        """Redraw the entire grid from scratch."""
        self.canvas.delete("all")

        if not animals:
            return

        max_days = max(len(a.history) for a in animals)

        total_width = (
            self.ID_COL_WIDTH
            + max_days * self.DAY_GROUP_WIDTH
            + self.NEXT_DAY_WIDTH
        )
        total_height = self.HEADER_HEIGHT + len(animals) * self.DATA_ROW_HEIGHT

        # Header row 1 - "Animal ID" spans both header rows
        self._draw_cell(
            0, 0, self.ID_COL_WIDTH, self.HEADER_HEIGHT,
            "Animal ID", self.HEADER_BG, self.HEADER_TEXT, bold=True, font_size=10,
        )

        for day_num in range(1, max_days + 1):
            x = self.ID_COL_WIDTH + (day_num - 1) * self.DAY_GROUP_WIDTH
            self._draw_cell(
                x, 0, self.DAY_GROUP_WIDTH, self.HEADER_ROW1_HEIGHT,
                f"Day {day_num}", self.HEADER_BG, self.HEADER_TEXT,
                bold=True, font_size=10,
            )

        # Next-day header (Day N+1)
        nx = self.ID_COL_WIDTH + max_days * self.DAY_GROUP_WIDTH
        self._draw_cell(
            nx, 0, self.NEXT_DAY_WIDTH, self.HEADER_ROW1_HEIGHT,
            f"Day {max_days + 1}", self.HEADER_BG, self.HEADER_TEXT,
            bold=True, font_size=10,
        )

        # Header row 2 (sub-headers)
        y2 = self.HEADER_ROW1_HEIGHT

        for day_num in range(1, max_days + 1):
            x = self.ID_COL_WIDTH + (day_num - 1) * self.DAY_GROUP_WIDTH
            self._draw_cell(
                x, y2, self.PROG_WIDTH, self.HEADER_ROW2_HEIGHT,
                "Program", self.HEADER_BG, self.HEADER_TEXT, font_size=9,
            )
            self._draw_cell(
                x + self.PROG_WIDTH, y2, self.DAY_WIDTH, self.HEADER_ROW2_HEIGHT,
                "Day", self.HEADER_BG, self.HEADER_TEXT, font_size=9,
            )
            self._draw_cell(
                x + self.PROG_WIDTH + self.DAY_WIDTH, y2,
                self.PROGRESS_WIDTH, self.HEADER_ROW2_HEIGHT,
                "Progress?", self.HEADER_BG, self.HEADER_TEXT, font_size=9,
            )

        # Next-day sub-headers (no Progress column)
        self._draw_cell(
            nx, y2, self.PROG_WIDTH, self.HEADER_ROW2_HEIGHT,
            "Program", self.HEADER_BG, self.HEADER_TEXT, font_size=9,
        )
        self._draw_cell(
            nx + self.PROG_WIDTH, y2, self.DAY_WIDTH, self.HEADER_ROW2_HEIGHT,
            "Day", self.HEADER_BG, self.HEADER_TEXT, font_size=9,
        )

        # Data rows
        for row_idx, animal in enumerate(animals):
            y = self.HEADER_HEIGHT + row_idx * self.DATA_ROW_HEIGHT

            # Animal ID
            self._draw_cell(
                0, y, self.ID_COL_WIDTH, self.DATA_ROW_HEIGHT,
                str(animal.subject_id), self.DATA_BG, self.DATA_TEXT,
                bold=True, font_size=10,
            )

            for day_idx in range(max_days):
                x = self.ID_COL_WIDTH + day_idx * self.DAY_GROUP_WIDTH

                if day_idx < len(animal.history):
                    session = animal.history[day_idx]

                    # Program
                    self._draw_cell(
                        x, y, self.PROG_WIDTH, self.DATA_ROW_HEIGHT,
                        _short_stage_name(session.stage),
                        self.DATA_BG, self.DATA_TEXT, font_size=10,
                    )
                    # Day in stage
                    self._draw_cell(
                        x + self.PROG_WIDTH, y,
                        self.DAY_WIDTH, self.DATA_ROW_HEIGHT,
                        str(session.day_in_stage),
                        self.DATA_BG, self.DATA_TEXT, font_size=10,
                    )
                    # Progress (colour-coded)
                    status_text = "Yes" if session.passed else "No"
                    colors = STATUS_COLORS.get(
                        session.pass_status, STATUS_COLORS[PassStatus.FAIL]
                    )
                    self._draw_cell(
                        x + self.PROG_WIDTH + self.DAY_WIDTH, y,
                        self.PROGRESS_WIDTH, self.DATA_ROW_HEIGHT,
                        status_text, colors[0], colors[1],
                        bold=True, font_size=10,
                    )
                else:
                    # Empty cells for days not yet completed
                    self._draw_cell(
                        x, y, self.PROG_WIDTH, self.DATA_ROW_HEIGHT,
                        "", self.DATA_BG, self.DATA_TEXT,
                    )
                    self._draw_cell(
                        x + self.PROG_WIDTH, y,
                        self.DAY_WIDTH, self.DATA_ROW_HEIGHT,
                        "", self.DATA_BG, self.DATA_TEXT,
                    )
                    self._draw_cell(
                        x + self.PROG_WIDTH + self.DAY_WIDTH, y,
                        self.PROGRESS_WIDTH, self.DATA_ROW_HEIGHT,
                        "", self.DATA_BG, self.DATA_TEXT,
                    )

            # Next-day column (Program + Day only)
            next_program, next_day = _next_session_info(animal)
            self._draw_cell(
                nx, y, self.PROG_WIDTH, self.DATA_ROW_HEIGHT,
                next_program, self.DATA_BG, self.DATA_TEXT, font_size=10,
            )
            self._draw_cell(
                nx + self.PROG_WIDTH, y, self.DAY_WIDTH, self.DATA_ROW_HEIGHT,
                str(next_day) if next_day != "" else "",
                self.DATA_BG, self.DATA_TEXT, font_size=10,
            )

        # Set scroll region to full drawing area
        self.canvas.configure(scrollregion=(0, 0, total_width, total_height))


# =============================================================================
# NextDaySetupPanel - Table showing next session for each animal
# =============================================================================

class NextDaySetupPanel(ttk.LabelFrame):
    """Panel showing the next day setup as a simple table."""

    def __init__(self, master, **kwargs):
        super().__init__(master, text="NEXT DAY SETUP", **kwargs)

        # Cohort day label
        self.cohort_day_var = tk.StringVar(value="Cohort Day --")
        ttk.Label(self, textvariable=self.cohort_day_var,
                  font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', padx=10, pady=5)

        # Treeview for setup table
        columns = ('Animal ID', 'Session', 'Session Day')
        self.tree = ttk.Treeview(self, columns=columns, show='headings', height=6)

        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100, anchor=tk.CENTER)

        self.tree.pack(fill=tk.X, padx=10, pady=(0, 10))

    def update_report(self, animals: List[AnimalState], cohort_day: int):
        """Update the display with next day setup data."""
        self.cohort_day_var.set(f"Cohort Day {cohort_day}")

        # Clear existing rows
        self.tree.delete(*self.tree.get_children())

        # Add rows for each animal
        for animal in animals:
            session_name, session_day = _next_session_info(animal)
            self.tree.insert('', tk.END, values=(
                animal.subject_id,
                session_name,
                str(session_day) if session_day != "" else ""
            ))


# =============================================================================
# SubjectHistoryPanel - Detailed history for one animal
# =============================================================================

class SubjectHistoryPanel(ttk.LabelFrame):
    """Panel showing detailed training history for one animal."""

    def __init__(self, master, **kwargs):
        super().__init__(master, text="INDIVIDUAL TRAINING HISTORY", **kwargs)

        # Header bar with subject dropdown
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(header_frame, text="Subject:").pack(side=tk.LEFT)

        self.subject_var = tk.StringVar(value="Select Subject")
        self.subject_dropdown = ttk.Combobox(header_frame, textvariable=self.subject_var,
                                              state='readonly', width=15)
        self.subject_dropdown['values'] = ["Select Subject"]
        self.subject_dropdown.pack(side=tk.LEFT, padx=5)
        self.subject_dropdown.bind('<<ComboboxSelected>>', self._on_dropdown_change)

        # Summary label
        self.summary_var = tk.StringVar(value="")
        ttk.Label(header_frame, textvariable=self.summary_var).pack(side=tk.RIGHT)

        # Treeview for history
        columns = ('Day', 'Date', 'Program', 'Day#', 'Licks', 'Active', 'Inactive', 'Discrim%', 'Progress')
        self.tree = ttk.Treeview(self, columns=columns, show='headings', height=8)

        for col in columns:
            self.tree.heading(col, text=col)
            width = 60 if col not in ('Date', 'Program', 'Progress') else 80
            self.tree.column(col, width=width, anchor=tk.CENTER)

        # Scrollbar
        scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=(0, 10))
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=(0, 10))

        # Internal state
        self._animals_map: Dict[str, AnimalState] = {}

    def set_animals(self, animals: List[AnimalState]):
        """Populate the dropdown and auto-select the first subject."""
        self._animals_map = {a.subject_id: a for a in animals}
        subject_ids = [a.subject_id for a in animals]

        if subject_ids:
            self.subject_dropdown['values'] = subject_ids
            self.subject_dropdown['state'] = 'readonly'
            self.subject_var.set(subject_ids[0])
            self.update_animal(self._animals_map[subject_ids[0]])
        else:
            self.subject_dropdown['values'] = ["No subjects"]
            self.subject_dropdown['state'] = 'disabled'
            self.subject_var.set("No subjects")
            self._clear_table()
            self.summary_var.set("")

    def update_animal(self, animal: AnimalState):
        """Rebuild the detail table for animal."""
        # Summary
        info = f"Current Stage: {animal.current_stage}"
        if animal.is_trained or animal.current_stage == Stage.TESTING:
            info += f"  |  Test Day: {animal.test_day}/7"
        else:
            info += (
                f"  |  Passes: {animal.consecutive_passes}"
                f"  |  Fails: {animal.consecutive_fails}"
            )
        self.summary_var.set(info)

        # Rebuild table
        self._clear_table()

        for i, session in enumerate(animal.history):
            total_presses = session.active_presses + session.inactive_presses
            discrim = (
                f"{session.lever_preference * 100:.0f}%"
                if total_presses > 0 else "-"
            )
            progress_text = "Yes" if session.passed else "No"

            self.tree.insert('', tk.END, values=(
                i + 1,
                session.date or "-",
                _short_stage_name(session.stage),
                session.day_in_stage,
                session.licks,
                session.active_presses,
                session.inactive_presses,
                discrim,
                progress_text
            ))

    def _on_dropdown_change(self, event):
        animal = self._animals_map.get(self.subject_var.get())
        if animal:
            self.update_animal(animal)

    def _clear_table(self):
        self.tree.delete(*self.tree.get_children())


# =============================================================================
# TrackerView - Main Progress Tracker view combining all components
# =============================================================================

class TrackerView(ttk.Frame):
    """Main Progress Tracker view panel."""

    def __init__(self, master, session_manager: Optional['SessionManager'] = None, **kwargs):
        super().__init__(master, **kwargs)

        self.session_manager = session_manager

        self._create_widgets()

        # Register callback for data changes from SessionManager
        if self.session_manager:
            self.session_manager.add_data_changed_callback(self._on_data_changed)

    def _on_data_changed(self):
        """Handle data change from SessionManager."""
        self._update_display()

    def _create_widgets(self):
        """Create all widgets."""
        # Control bar
        control_frame = ttk.Frame(self)
        control_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(control_frame, text="Cohort:", font=('TkDefaultFont', 10, 'bold')).pack(side=tk.LEFT)

        self.cohort_var = tk.StringVar(value="(Load folder to see data)")
        ttk.Label(control_frame, textvariable=self.cohort_var).pack(side=tk.LEFT, padx=10)

        self.refresh_btn = ttk.Button(control_frame, text="Refresh", command=self._refresh, state=tk.DISABLED)
        self.refresh_btn.pack(side=tk.RIGHT)

        # Next day setup panel
        self.next_day_panel = NextDaySetupPanel(self)
        self.next_day_panel.pack(fill=tk.X, padx=10, pady=5)

        # Training Progress section (day-by-day table)
        progress_frame = ttk.LabelFrame(self, text="TRAINING PROGRESS")
        progress_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Legend
        legend_frame = ttk.Frame(progress_frame)
        legend_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(legend_frame, text="Legend:", font=('TkDefaultFont', 9, 'bold')).pack(side=tk.LEFT)

        # Pass legend
        pass_label = tk.Label(legend_frame, text=" Yes ", bg=STATUS_COLORS[PassStatus.PASS][0],
                               fg=STATUS_COLORS[PassStatus.PASS][1], font=('TkDefaultFont', 9, 'bold'))
        pass_label.pack(side=tk.LEFT, padx=(10, 2))
        ttk.Label(legend_frame, text="= Pass").pack(side=tk.LEFT, padx=(0, 15))

        # Partial legend
        partial_label = tk.Label(legend_frame, text=" No ", bg=STATUS_COLORS[PassStatus.PARTIAL][0],
                                  fg=STATUS_COLORS[PassStatus.PARTIAL][1], font=('TkDefaultFont', 9, 'bold'))
        partial_label.pack(side=tk.LEFT, padx=2)
        ttk.Label(legend_frame, text="= Partial").pack(side=tk.LEFT, padx=(0, 15))

        # Fail legend
        fail_label = tk.Label(legend_frame, text=" No ", bg=STATUS_COLORS[PassStatus.FAIL][0],
                               fg=STATUS_COLORS[PassStatus.FAIL][1], font=('TkDefaultFont', 9, 'bold'))
        fail_label.pack(side=tk.LEFT, padx=2)
        ttk.Label(legend_frame, text="= Fail").pack(side=tk.LEFT)

        # Day-by-day table
        self.day_table = DayByDayTable(progress_frame)
        self.day_table.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Subject history panel
        self.subject_history_panel = SubjectHistoryPanel(self)
        self.subject_history_panel.pack(fill=tk.X, padx=10, pady=5)

        # Bottom info label
        self.info_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.info_var).pack(anchor='e', padx=10, pady=5)

    def _refresh(self):
        """Refresh data from current folder."""
        if self.session_manager and self.session_manager.folder_path:
            try:
                self.session_manager.load_folder(str(self.session_manager.folder_path))
            except Exception as e:
                messagebox.showerror("Refresh Error", f"Failed to refresh data:\n{e}")

    def _update_display(self):
        """Update all display elements with current tracker data."""
        tracker = self.session_manager.get_tracker() if self.session_manager else None
        if not tracker:
            return

        # Update cohort name
        self.cohort_var.set(tracker.cohort_name or "(Unnamed)")

        # Update day-by-day table and next day panel
        animals = tracker.get_all_animals()
        self.day_table.populate(animals)

        # Determine cohort day (max history length + 1)
        max_days = max((len(a.history) for a in animals), default=0)
        cohort_day = max_days + 1

        # Update next day panel with animal list and cohort day
        self.next_day_panel.update_report(animals, cohort_day)

        # Update embedded subject history panel
        self.subject_history_panel.set_animals(animals)

        # Enable refresh button
        self.refresh_btn['state'] = tk.NORMAL

        # Update info label
        self.info_var.set(f"Loaded {len(animals)} animals")

    def refresh(self):
        """Public method to refresh the tracker view."""
        self._update_display()
