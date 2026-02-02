"""
Main application window for STAR Analyzer V3.
Two-tab interface with Raster Plots and Progress Tracker.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import Optional, List

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from gui.config import ConfigManager
from gui.import_dialog import ImportDialog, ImportResult
from gui.tracker_view import TrackerView
from core.session_manager import SessionManager, ParsedSession
from core.plotting import create_multi_raster_plot, COLORS
from core.tracker import generate_next_day_report
from core.exporters import ExcelExporter


class StarAnalyzerApp(tk.Tk):
    """Main application window with two tabs."""

    def __init__(self):
        super().__init__()

        self.config_manager = ConfigManager()
        self.session_manager = SessionManager()

        # Register for data changes
        self.session_manager.add_data_changed_callback(self._on_data_changed)

        self._setup_window()
        self._create_menu()
        self._create_toolbar()
        self._create_main_content()
        self._create_statusbar()

    def _setup_window(self):
        """Configure the main window."""
        self.title('STAR Analyzer V3')
        self.geometry('1200x700')
        self.minsize(900, 500)

        # Restore geometry if saved
        if self.config_manager.window_geometry:
            try:
                self.geometry(self.config_manager.window_geometry)
            except tk.TclError:
                pass

        # Save geometry on close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_menu(self):
        """Create the menu bar."""
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label='File', menu=file_menu)
        file_menu.add_command(label='Import Data...', command=self._open_import_dialog, accelerator='Ctrl+I')
        file_menu.add_separator()
        file_menu.add_command(label='Export Statistics...', command=self._export_stats, accelerator='Ctrl+E')
        file_menu.add_command(label='Save Plots...', command=self._save_plots)
        file_menu.add_separator()
        file_menu.add_command(label='Exit', command=self._on_close, accelerator='Alt+F4')

        # Bind keyboard shortcuts
        self.bind('<Control-i>', lambda e: self._open_import_dialog())
        self.bind('<Control-e>', lambda e: self._export_stats())

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label='View', menu=view_menu)
        view_menu.add_command(label='Clear Data', command=self._clear_data)
        view_menu.add_separator()
        view_menu.add_command(label='Refresh Plots', command=self._refresh_plots)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label='Help', menu=help_menu)
        help_menu.add_command(label='About', command=self._show_about)

    def _create_toolbar(self):
        """Create the toolbar."""
        toolbar = ttk.Frame(self, padding=(5, 2))
        toolbar.pack(fill=tk.X)

        self.import_btn = ttk.Button(toolbar, text='Import Data', command=self._open_import_dialog)
        self.import_btn.pack(side=tk.LEFT, padx=2)

        self.export_btn = ttk.Button(toolbar, text='Export Stats', command=self._export_stats, state=tk.DISABLED)
        self.export_btn.pack(side=tk.LEFT, padx=2)

        self.save_plot_btn = ttk.Button(toolbar, text='Save Plots', command=self._save_plots, state=tk.DISABLED)
        self.save_plot_btn.pack(side=tk.LEFT, padx=2)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)

        self.clear_btn = ttk.Button(toolbar, text='Clear Data', command=self._clear_data, state=tk.DISABLED)
        self.clear_btn.pack(side=tk.LEFT, padx=2)

    def _create_main_content(self):
        """Create the main content area with tabs."""
        # Notebook for tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Tab 1: Raster Plots
        self.raster_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.raster_frame, text='Raster Plots')
        self._create_raster_tab()

        # Tab 2: Progress Tracker
        self.tracker_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.tracker_frame, text='Progress Tracker')
        self._create_tracker_tab()

    def _create_raster_tab(self):
        """Create the raster plots tab."""
        # Paned window for left panel (file list) and right panel (plots)
        paned = ttk.PanedWindow(self.raster_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Left panel - file list with filter
        left_frame = ttk.Frame(paned, padding=5)
        paned.add(left_frame, weight=1)

        # Subject filter
        filter_frame = ttk.Frame(left_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(filter_frame, text='Subject:').pack(side=tk.LEFT)
        self.subject_filter_var = tk.StringVar(value='All')
        self.subject_filter = ttk.Combobox(filter_frame, textvariable=self.subject_filter_var,
                                            state='readonly', width=12)
        self.subject_filter['values'] = ['All']
        self.subject_filter.pack(side=tk.LEFT, padx=5)
        self.subject_filter.bind('<<ComboboxSelected>>', self._on_filter_changed)

        # Session count label
        self.session_count_var = tk.StringVar(value='0 sessions')
        ttk.Label(filter_frame, textvariable=self.session_count_var).pack(side=tk.RIGHT)

        # File list with checkboxes
        list_frame = ttk.LabelFrame(left_frame, text='Sessions', padding=5)
        list_frame.pack(fill=tk.BOTH, expand=True)

        # Listbox with scrollbar
        list_container = ttk.Frame(list_frame)
        list_container.pack(fill=tk.BOTH, expand=True)

        self.session_listbox = tk.Listbox(list_container, selectmode=tk.EXTENDED,
                                           exportselection=False)
        scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL,
                                   command=self.session_listbox.yview)
        self.session_listbox.config(yscrollcommand=scrollbar.set)

        self.session_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.session_listbox.bind('<<ListboxSelect>>', self._on_selection_changed)

        # Select all/none buttons
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Button(btn_frame, text='Select All', command=self._select_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text='Select None', command=self._select_none).pack(side=tk.LEFT, padx=2)

        # Right panel - scrollable plot display
        right_frame = ttk.Frame(paned, padding=5)
        paned.add(right_frame, weight=3)

        # Create scrollable container for plots
        self.plot_canvas = tk.Canvas(right_frame, bg='#f0f0f0', highlightthickness=0)
        self.plot_scrollbar = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.plot_canvas.yview)
        self.plot_canvas.configure(yscrollcommand=self.plot_scrollbar.set)

        self.plot_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.plot_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Create interior frame for the matplotlib figure
        self.plot_interior = ttk.Frame(self.plot_canvas)
        self.plot_canvas_window = self.plot_canvas.create_window((0, 0), window=self.plot_interior, anchor='nw')

        # Bind mouse wheel for scrolling
        self.plot_canvas.bind('<MouseWheel>', self._on_plot_mousewheel)
        self.plot_interior.bind('<MouseWheel>', self._on_plot_mousewheel)

        # Update scroll region when interior frame resizes
        self.plot_interior.bind('<Configure>', self._on_plot_interior_configure)
        self.plot_canvas.bind('<Configure>', self._on_plot_canvas_configure)

        # Initial empty plot
        self._create_empty_plot()

    def _on_plot_mousewheel(self, event):
        """Handle mouse wheel scrolling on plot canvas."""
        self.plot_canvas.yview_scroll(-1 * (event.delta // 120), 'units')

    def _on_plot_interior_configure(self, event=None):
        """Update scroll region when plot interior changes size."""
        self.plot_canvas.configure(scrollregion=self.plot_canvas.bbox('all'))

    def _on_plot_canvas_configure(self, event=None):
        """Update interior width when canvas is resized."""
        canvas_width = event.width if event else self.plot_canvas.winfo_width()
        self.plot_canvas.itemconfig(self.plot_canvas_window, width=canvas_width)

    def _create_tracker_tab(self):
        """Create the progress tracker tab with full TrackerView."""
        self.tracker_view = TrackerView(self.tracker_frame, session_manager=self.session_manager)
        self.tracker_view.pack(fill=tk.BOTH, expand=True)

    def _create_empty_plot(self):
        """Create an empty placeholder plot."""
        fig, ax = plt.subplots(figsize=(10, 6), facecolor=COLORS['background'])
        ax.text(0.5, 0.5, 'Import data to view raster plots',
                ha='center', va='center', fontsize=14, color='gray')
        ax.set_xticks([])
        ax.set_yticks([])
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.spines['left'].set_visible(False)

        self._display_figure(fig)

    def _display_figure(self, fig):
        """Display a matplotlib figure in the scrollable plot container."""
        # Clear existing widgets in the interior frame
        for widget in self.plot_interior.winfo_children():
            widget.destroy()

        # Create matplotlib canvas inside the interior frame
        canvas = FigureCanvasTkAgg(fig, master=self.plot_interior)
        canvas.draw()

        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack(fill=tk.BOTH, expand=True)

        # Bind mouse wheel to the matplotlib canvas widget too
        canvas_widget.bind('<MouseWheel>', self._on_plot_mousewheel)

        # Update interior frame size based on figure
        fig_height = int(fig.get_figheight() * fig.dpi)
        fig_width = int(fig.get_figwidth() * fig.dpi)
        self.plot_interior.configure(height=fig_height, width=fig_width)

        # Reset scroll position to top
        self.plot_canvas.yview_moveto(0)

        self._current_figure = fig

    def _create_statusbar(self):
        """Create the status bar."""
        statusbar = ttk.Frame(self, padding=(5, 2))
        statusbar.pack(fill=tk.X, side=tk.BOTTOM)

        self.status_var = tk.StringVar(value='Ready. Click "Import Data" to begin.')
        ttk.Label(statusbar, textvariable=self.status_var).pack(side=tk.LEFT)

        self.selection_var = tk.StringVar(value='')
        ttk.Label(statusbar, textvariable=self.selection_var).pack(side=tk.RIGHT)

    # =============================================================================
    # Event Handlers
    # =============================================================================

    def _on_data_changed(self):
        """Handle data change notification from session manager."""
        self._update_subject_filter()
        self._update_session_list()
        self._update_tracker_view()
        self._update_ui_state()

    def _on_filter_changed(self, event=None):
        """Handle subject filter change."""
        self._update_session_list()

    def _on_selection_changed(self, event=None):
        """Handle session list selection change."""
        self._update_plots()
        self._update_selection_status()

    def _on_close(self):
        """Handle window close."""
        # Save window geometry
        self.config_manager.window_geometry = self.geometry()

        # Close any open plots
        plt.close('all')

        self.destroy()

    # =============================================================================
    # UI Updates
    # =============================================================================

    def _update_subject_filter(self):
        """Update subject filter dropdown."""
        subjects = self.session_manager.get_all_subjects()
        self.subject_filter['values'] = ['All'] + subjects
        self.subject_filter_var.set('All')

    def _update_session_list(self):
        """Update the session listbox."""
        self.session_listbox.delete(0, tk.END)

        subject_filter = self.subject_filter_var.get()
        sessions = self.session_manager.get_all_sessions()

        if subject_filter != 'All':
            sessions = [s for s in sessions if s.subject_id == subject_filter]

        for session in sessions:
            # Format: "Subject 1 | FR1-30 | Day 3 | Pass"
            status = "Pass" if session.passed else "Fail"
            if session.pass_status == 'partial':
                status = "Partial"
            label = f"{session.subject_id} | {session.stage_name} | Day {session.day_in_cohort} | {status}"
            self.session_listbox.insert(tk.END, label)

        self.session_count_var.set(f'{len(sessions)} sessions')

        # Select all by default
        if sessions:
            self.session_listbox.select_set(0, tk.END)
            self._update_plots()

    def _update_plots(self):
        """Update the raster plots based on selection."""
        selection = self.session_listbox.curselection()
        if not selection:
            self._create_empty_plot()
            return

        # Get filtered session list
        subject_filter = self.subject_filter_var.get()
        sessions = self.session_manager.get_all_sessions()
        if subject_filter != 'All':
            sessions = [s for s in sessions if s.subject_id == subject_filter]

        # Get selected sessions
        selected_sessions = [sessions[i] for i in selection if i < len(sessions)]

        if not selected_sessions:
            self._create_empty_plot()
            return

        # Get raw data and pass statuses
        data_list = [s.raw_data for s in selected_sessions]
        pass_statuses = [{'passed': s.passed, 'pass_status': s.pass_status} for s in selected_sessions]

        # Create multi-plot
        try:
            fig, axes = create_multi_raster_plot(data_list, pass_statuses=pass_statuses)
            self._display_figure(fig)
        except Exception as e:
            print(f"Error creating plots: {e}")
            self._create_empty_plot()

    def _update_tracker_view(self):
        """Update the progress tracker view."""
        self.tracker_view.refresh()

    def _update_selection_status(self):
        """Update status bar with selection info."""
        selection = self.session_listbox.curselection()
        if selection:
            self.selection_var.set(f'{len(selection)} session(s) selected')
        else:
            self.selection_var.set('')

    def _update_ui_state(self):
        """Update button states based on data availability."""
        has_data = self.session_manager.has_data()

        state = tk.NORMAL if has_data else tk.DISABLED
        self.export_btn.config(state=state)
        self.save_plot_btn.config(state=state)
        self.clear_btn.config(state=state)

        if has_data:
            count = self.session_manager.get_session_count()
            subjects = self.session_manager.get_subject_count()
            self.status_var.set(f'Loaded {count} sessions from {subjects} subject(s)')

    # =============================================================================
    # Actions
    # =============================================================================

    def _open_import_dialog(self):
        """Open the import dialog."""
        initial_path = self.config_manager.last_import_path
        ImportDialog(self, initial_path=initial_path, on_complete=self._on_import_complete)

    def _on_import_complete(self, result: ImportResult):
        """Handle import completion."""
        if result.success_count == 0:
            return

        # Save last path
        if result.source_path:
            self.config_manager.last_import_path = result.source_path

        # Load into session manager (this triggers _on_data_changed)
        count = self.session_manager.load_folder(str(result.source_path))

        # Show summary if there were errors
        if result.error_count > 0:
            messagebox.showinfo(
                'Import Summary',
                f'Imported {count} sessions.\n{result.error_count} files could not be parsed.',
                parent=self
            )

    def _export_stats(self):
        """Export statistics to Excel with multi-sheet format."""
        if not self.session_manager.has_data():
            messagebox.showwarning('No Data', 'No data to export.', parent=self)
            return

        # Get save path
        folder_name = self.session_manager.folder_path.name if self.session_manager.folder_path else 'export'
        default_name = f'{folder_name}_stats.xlsx'

        file_path = filedialog.asksaveasfilename(
            parent=self,
            title='Export Statistics',
            defaultextension='.xlsx',
            filetypes=[('Excel files', '*.xlsx'), ('All files', '*.*')],
            initialfile=default_name,
        )

        if not file_path:
            return

        try:
            # Export using ExcelExporter
            exporter = ExcelExporter()
            sessions = self.session_manager.get_all_sessions()
            exporter.export_sessions(sessions, Path(file_path))

            self.status_var.set(f'Exported to {Path(file_path).name}')
            messagebox.showinfo(
                'Export Complete',
                f'Data exported to:\n{file_path}\n\nSheets:\n- All Sessions\n- Per-subject tabs',
                parent=self
            )
        except Exception as e:
            messagebox.showerror('Export Error', f'Failed to export: {e}', parent=self)

    def _save_plots(self):
        """Save current plots to file."""
        if not hasattr(self, '_current_figure') or self._current_figure is None:
            messagebox.showwarning('No Plots', 'No plots to save.', parent=self)
            return

        file_path = filedialog.asksaveasfilename(
            parent=self,
            title='Save Plots',
            defaultextension='.png',
            filetypes=[('PNG files', '*.png'), ('PDF files', '*.pdf'), ('All files', '*.*')],
            initialfile='raster_plots.png',
        )

        if not file_path:
            return

        try:
            self._current_figure.savefig(file_path, dpi=150, bbox_inches='tight',
                                          facecolor=COLORS['background'])
            self.status_var.set(f'Saved plots to {Path(file_path).name}')
        except Exception as e:
            messagebox.showerror('Save Error', f'Failed to save: {e}', parent=self)

    def _clear_data(self):
        """Clear all loaded data."""
        if not self.session_manager.has_data():
            return

        if messagebox.askyesno('Clear Data', 'Clear all imported data?', parent=self):
            self.session_manager.clear()
            self._create_empty_plot()
            self.status_var.set('Data cleared. Click "Import Data" to begin.')

    def _refresh_plots(self):
        """Refresh the current plots."""
        self._update_plots()

    def _select_all(self):
        """Select all sessions in the list."""
        self.session_listbox.select_set(0, tk.END)
        self._update_plots()

    def _select_none(self):
        """Deselect all sessions."""
        self.session_listbox.selection_clear(0, tk.END)
        self._update_plots()

    def _show_about(self):
        """Show about dialog."""
        about_text = """STAR Analyzer V3

A tool for analyzing Med-PC IV data files from STAR (Structured Tracking of Alcohol Reinforcement) experiments.

Features:
- Data parsing and organization
- Progress tracking through training phases
- Raster plot visualization

Developed for behavioral neuroscience research."""

        messagebox.showinfo('About STAR Analyzer', about_text, parent=self)


def run():
    """Run the application."""
    app = StarAnalyzerApp()
    app.mainloop()


if __name__ == '__main__':
    run()
