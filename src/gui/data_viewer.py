"""
Data viewer component for STAR Analyzer.
Displays imported sessions in a treeview table with filtering and detail view.
"""

from datetime import date
from tkinter import ttk, messagebox
from typing import List, Optional, Callable
import tkinter as tk

from core.data_models import MedPCSession


class SessionDetailDialog(tk.Toplevel):
    """Dialog showing full details of a single session."""

    def __init__(self, parent: tk.Tk, session: MedPCSession):
        super().__init__(parent)

        self.session = session
        self._setup_window()
        self._create_widgets()

    def _setup_window(self):
        """Configure the dialog window."""
        self.title(f'Session Details - Subject {self.session.subject}')
        self.geometry('700x500')
        self.transient(self.master)

        # Center on parent
        self.update_idletasks()
        x = self.master.winfo_x() + (self.master.winfo_width() - 700) // 2
        y = self.master.winfo_y() + (self.master.winfo_height() - 500) // 2
        self.geometry(f'+{x}+{y}')

    def _create_widgets(self):
        """Create dialog widgets."""
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Metadata tab
        meta_frame = ttk.Frame(notebook, padding=10)
        notebook.add(meta_frame, text='Metadata')
        self._create_metadata_tab(meta_frame)

        # Scalars tab
        scalars_frame = ttk.Frame(notebook, padding=10)
        notebook.add(scalars_frame, text='Counters')
        self._create_scalars_tab(scalars_frame)

        # Timestamps tab
        timestamps_frame = ttk.Frame(notebook, padding=10)
        notebook.add(timestamps_frame, text='Timestamps')
        self._create_timestamps_tab(timestamps_frame)

        # Warnings tab (if any)
        if self.session.warnings:
            warnings_frame = ttk.Frame(notebook, padding=10)
            notebook.add(warnings_frame, text='Warnings')
            self._create_warnings_tab(warnings_frame)

        # Close button
        ttk.Button(self, text='Close', command=self.destroy).pack(pady=(0, 10))

    def _create_metadata_tab(self, parent):
        """Create metadata display."""
        meta = self.session.metadata

        fields = [
            ('Subject', meta.subject),
            ('Date', meta.start_date.strftime('%Y-%m-%d')),
            ('Start Time', meta.start_time.strftime('%H:%M:%S')),
            ('End Time', meta.end_time.strftime('%H:%M:%S') if meta.end_time else 'N/A'),
            ('Experiment', meta.experiment),
            ('Group', meta.group),
            ('Box', str(meta.box)),
            ('MSN', meta.msn),
            ('File', str(meta.file_path)),
        ]

        for i, (label, value) in enumerate(fields):
            ttk.Label(parent, text=f'{label}:', font=('TkDefaultFont', 9, 'bold')).grid(
                row=i, column=0, sticky=tk.W, pady=2
            )
            ttk.Label(parent, text=value).grid(row=i, column=1, sticky=tk.W, padx=(10, 0), pady=2)

    def _create_scalars_tab(self, parent):
        """Create scalars display."""
        scalars = self.session.scalars

        # Calculate discrimination
        total_presses = scalars.active_lever_presses + scalars.inactive_lever_presses
        if total_presses > 0:
            discrimination = (scalars.active_lever_presses / total_presses) * 100
            discrimination_str = f'{discrimination:.1f}%'
        else:
            discrimination_str = 'N/A (no presses)'

        fields = [
            ('Active Lever Presses (A)', scalars.active_lever_presses),
            ('Inactive Lever Presses (B)', scalars.inactive_lever_presses),
            ('Discrimination Index', discrimination_str),
            ('', ''),  # Spacer
            ('Reinforcers (D)', scalars.reinforcers),
            ('Lick Onsets (E)', scalars.lick_onsets),
            ('Lick Offsets (F)', scalars.lick_offsets),
            ('Session Time (T)', f'{scalars.session_time:.2f} seconds'),
        ]

        for i, (label, value) in enumerate(fields):
            if label:  # Skip spacers
                ttk.Label(parent, text=f'{label}:', font=('TkDefaultFont', 9, 'bold')).grid(
                    row=i, column=0, sticky=tk.W, pady=2
                )
                ttk.Label(parent, text=str(value)).grid(row=i, column=1, sticky=tk.W, padx=(10, 0), pady=2)

    def _create_timestamps_tab(self, parent):
        """Create timestamps display with treeview."""
        ts = self.session.timestamps

        # Create treeview
        columns = ('active', 'inactive', 'reinforcer', 'lick_on', 'lick_off')
        tree = ttk.Treeview(parent, columns=columns, show='headings', height=15)

        tree.heading('active', text='Active (J)')
        tree.heading('inactive', text='Inactive (K)')
        tree.heading('reinforcer', text='Reinforcer (L)')
        tree.heading('lick_on', text='Lick On (N)')
        tree.heading('lick_off', text='Lick Off (O)')

        for col in columns:
            tree.column(col, width=100, anchor=tk.CENTER)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Find max length
        arrays = [
            ts.active_lever_timestamps,
            ts.inactive_lever_timestamps,
            ts.reinforcer_timestamps,
            ts.lick_onset_timestamps,
            ts.lick_offset_timestamps,
        ]
        max_len = max(len(arr) for arr in arrays) if arrays else 0

        # Populate rows
        for i in range(max_len):
            values = []
            for arr in arrays:
                if i < len(arr):
                    values.append(f'{arr[i]:.3f}')
                else:
                    values.append('')
            tree.insert('', tk.END, values=values)

    def _create_warnings_tab(self, parent):
        """Create warnings display."""
        text = tk.Text(parent, wrap=tk.WORD, height=15)
        text.pack(fill=tk.BOTH, expand=True)

        for warning in self.session.warnings:
            text.insert(tk.END, f'- {warning}\n')

        text.config(state=tk.DISABLED)


def calculate_discrimination(session: MedPCSession) -> float:
    """Calculate discrimination index (active / total presses * 100)."""
    total = session.scalars.active_lever_presses + session.scalars.inactive_lever_presses
    if total == 0:
        return 0.0
    return (session.scalars.active_lever_presses / total) * 100


class DataViewer(ttk.Frame):
    """Treeview table for displaying session data with multiple view modes."""

    # View modes
    VIEW_ALL = 'all'
    VIEW_BY_ANIMAL = 'animal'
    VIEW_BY_DAY = 'day'

    COLUMNS = [
        ('subject', 'Subject', 80),
        ('date', 'Date', 100),
        ('time', 'Time', 80),
        ('experiment', 'Experiment', 150),
        ('group', 'Group', 120),
        ('active', 'Active', 70),
        ('inactive', 'Inactive', 70),
        ('discrimination', 'Discrim %', 80),
        ('reinforcers', 'Reinforcers', 80),
        ('licks', 'Licks', 70),
        ('duration', 'Duration (s)', 90),
    ]

    def __init__(
        self,
        parent: tk.Widget,
        on_selection_change: Optional[Callable[[Optional[MedPCSession]], None]] = None,
    ):
        super().__init__(parent)

        self.sessions: List[MedPCSession] = []
        self.filtered_sessions: List[MedPCSession] = []
        self.on_selection_change = on_selection_change
        self.current_view = self.VIEW_ALL

        self._create_view_selector()
        self._create_filter_bar()
        self._create_treeview()

    def _create_view_selector(self):
        """Create view mode selector."""
        view_frame = ttk.LabelFrame(self, text='View Mode', padding=5)
        view_frame.pack(fill=tk.X, pady=(0, 5))

        self.view_var = tk.StringVar(value=self.VIEW_ALL)

        views = [
            (self.VIEW_ALL, 'All Sessions'),
            (self.VIEW_BY_ANIMAL, 'By Individual Animal'),
            (self.VIEW_BY_DAY, 'By Single Day'),
        ]

        for value, text in views:
            rb = ttk.Radiobutton(
                view_frame,
                text=text,
                value=value,
                variable=self.view_var,
                command=self._on_view_change,
            )
            rb.pack(side=tk.LEFT, padx=10)

    def _create_filter_bar(self):
        """Create filter controls."""
        filter_frame = ttk.Frame(self)
        filter_frame.pack(fill=tk.X, pady=(0, 5))

        # Subject filter
        ttk.Label(filter_frame, text='Subject:').pack(side=tk.LEFT)
        self.subject_var = tk.StringVar(value='All')
        self.subject_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.subject_var,
            values=['All'],
            width=10,
            state='readonly',
        )
        self.subject_combo.pack(side=tk.LEFT, padx=(5, 15))
        self.subject_combo.bind('<<ComboboxSelected>>', lambda e: self._apply_filters())

        # Date filter
        ttk.Label(filter_frame, text='Date:').pack(side=tk.LEFT)
        self.date_var = tk.StringVar(value='All')
        self.date_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.date_var,
            values=['All'],
            width=12,
            state='readonly',
        )
        self.date_combo.pack(side=tk.LEFT, padx=(5, 15))
        self.date_combo.bind('<<ComboboxSelected>>', lambda e: self._apply_filters())

        # Clear filters button
        ttk.Button(filter_frame, text='Clear Filters', command=self._clear_filters).pack(side=tk.LEFT)

        # Session count label
        self.count_var = tk.StringVar(value='No sessions')
        ttk.Label(filter_frame, textvariable=self.count_var).pack(side=tk.RIGHT)

    def _create_treeview(self):
        """Create the main treeview table."""
        # Create frame with scrollbars
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        # Create treeview
        columns = [col[0] for col in self.COLUMNS]
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings', selectmode='browse')

        # Configure columns
        for col_id, header, width in self.COLUMNS:
            self.tree.heading(col_id, text=header, command=lambda c=col_id: self._sort_by_column(c))
            self.tree.column(col_id, width=width, minwidth=50)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # Grid layout
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # Bindings
        self.tree.bind('<<TreeviewSelect>>', self._on_select)
        self.tree.bind('<Double-1>', self._on_double_click)

    def _on_view_change(self):
        """Handle view mode change."""
        new_view = self.view_var.get()
        self.current_view = new_view

        # Update filter visibility/state based on view
        if new_view == self.VIEW_BY_ANIMAL:
            # In "by animal" view, subject filter is primary selector
            self.subject_combo.config(state='readonly')
            self.date_combo.config(state='disabled')
            self.date_var.set('All')
            # If subject is 'All', select first subject
            if self.subject_var.get() == 'All' and len(self.subject_combo['values']) > 1:
                self.subject_var.set(self.subject_combo['values'][1])
        elif new_view == self.VIEW_BY_DAY:
            # In "by day" view, date filter is primary selector
            self.subject_combo.config(state='disabled')
            self.date_combo.config(state='readonly')
            self.subject_var.set('All')
            # If date is 'All', select first date
            if self.date_var.get() == 'All' and len(self.date_combo['values']) > 1:
                self.date_var.set(self.date_combo['values'][1])
        else:
            # All sessions view - both filters active
            self.subject_combo.config(state='readonly')
            self.date_combo.config(state='readonly')

        self._apply_filters()

    def set_sessions(self, sessions: List[MedPCSession]):
        """Set the sessions to display."""
        self.sessions = sessions
        self._update_filter_options()
        self._apply_filters()

    def clear(self):
        """Clear all sessions."""
        self.sessions = []
        self.filtered_sessions = []
        self._clear_tree()
        self._update_filter_options()
        self.count_var.set('No sessions')

    def get_selected_session(self) -> Optional[MedPCSession]:
        """Get the currently selected session."""
        selection = self.tree.selection()
        if not selection:
            return None

        # Find session by matching index
        idx = self.tree.index(selection[0])
        if 0 <= idx < len(self.filtered_sessions):
            return self.filtered_sessions[idx]
        return None

    def _update_filter_options(self):
        """Update filter combobox options based on loaded sessions."""
        # Get unique subjects (sort numerically if possible)
        subjects = sorted(
            set(s.subject for s in self.sessions),
            key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else x)
        )
        self.subject_combo['values'] = ['All'] + subjects

        # Get unique dates
        dates = sorted(set(s.date for s in self.sessions))
        date_strs = [d.strftime('%Y-%m-%d') for d in dates]
        self.date_combo['values'] = ['All'] + date_strs

    def _apply_filters(self):
        """Apply current filters and refresh display."""
        filtered = self.sessions

        # Subject filter
        subject = self.subject_var.get()
        if subject != 'All':
            filtered = [s for s in filtered if s.subject == subject]

        # Date filter
        date_str = self.date_var.get()
        if date_str != 'All':
            target_date = date.fromisoformat(date_str)
            filtered = [s for s in filtered if s.date == target_date]

        self.filtered_sessions = filtered
        self._refresh_tree()

    def _clear_filters(self):
        """Reset all filters."""
        self.view_var.set(self.VIEW_ALL)
        self.current_view = self.VIEW_ALL
        self.subject_combo.config(state='readonly')
        self.date_combo.config(state='readonly')
        self.subject_var.set('All')
        self.date_var.set('All')
        self._apply_filters()

    def _refresh_tree(self):
        """Refresh the treeview with filtered sessions."""
        self._clear_tree()

        for session in self.filtered_sessions:
            values = self._session_to_values(session)
            self.tree.insert('', tk.END, values=values)

        # Update count
        total = len(self.sessions)
        showing = len(self.filtered_sessions)

        # Customize count label based on view mode
        if self.current_view == self.VIEW_BY_ANIMAL:
            subject = self.subject_var.get()
            if subject != 'All':
                self.count_var.set(f'Subject {subject}: {showing} sessions')
            else:
                self.count_var.set(f'{showing} sessions')
        elif self.current_view == self.VIEW_BY_DAY:
            date_str = self.date_var.get()
            if date_str != 'All':
                self.count_var.set(f'{date_str}: {showing} sessions')
            else:
                self.count_var.set(f'{showing} sessions')
        else:
            if total == showing:
                self.count_var.set(f'{total} sessions')
            else:
                self.count_var.set(f'Showing {showing} of {total} sessions')

    def _clear_tree(self):
        """Remove all items from treeview."""
        for item in self.tree.get_children():
            self.tree.delete(item)

    def _session_to_values(self, session: MedPCSession) -> tuple:
        """Convert session to treeview values."""
        meta = session.metadata
        scalars = session.scalars
        total_licks = scalars.lick_onsets + scalars.lick_offsets

        # Calculate discrimination
        discrimination = calculate_discrimination(session)

        return (
            meta.subject,
            meta.start_date.strftime('%Y-%m-%d'),
            meta.start_time.strftime('%H:%M'),
            meta.experiment,
            meta.group,
            scalars.active_lever_presses,
            scalars.inactive_lever_presses,
            f'{discrimination:.1f}%',
            scalars.reinforcers,
            total_licks,
            f'{scalars.session_time:.1f}',
        )

    def _sort_by_column(self, column: str):
        """Sort treeview by the specified column."""
        # Get current sort direction
        current = self.tree.heading(column, 'text')
        reverse = not current.endswith(' v')

        # Sort filtered sessions
        def get_key(session: MedPCSession):
            values = self._session_to_values(session)
            col_idx = [c[0] for c in self.COLUMNS].index(column)
            val = values[col_idx]

            # Handle discrimination percentage
            if column == 'discrimination':
                try:
                    return (0, float(val.rstrip('%')))
                except (ValueError, AttributeError):
                    return (1, 0)

            # Try numeric sort
            try:
                return (0, float(val))
            except (ValueError, TypeError):
                return (1, str(val).lower())

        self.filtered_sessions.sort(key=get_key, reverse=reverse)

        # Update header indicator
        for col_id, header, _ in self.COLUMNS:
            self.tree.heading(col_id, text=header)

        indicator = ' v' if reverse else ' ^'
        col_header = next(h for c, h, _ in self.COLUMNS if c == column)
        self.tree.heading(column, text=col_header + indicator)

        self._refresh_tree()

    def _on_select(self, event):
        """Handle selection change."""
        if self.on_selection_change:
            session = self.get_selected_session()
            self.on_selection_change(session)

    def _on_double_click(self, event):
        """Handle double-click to show detail view."""
        session = self.get_selected_session()
        if session:
            SessionDetailDialog(self.winfo_toplevel(), session)
