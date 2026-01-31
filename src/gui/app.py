"""
Main application window for STAR Analyzer.
"""

import json
from pathlib import Path
from tkinter import ttk, filedialog, messagebox
from typing import Optional
import tkinter as tk

from core.data_models import MedPCSession, Cohort
from core.exporters import ExcelExporter
from gui.import_dialog import ImportDialog, ImportResult
from gui.data_viewer import DataViewer


class ConfigManager:
    """Manages application configuration (last folder, etc.)."""

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            # Use user's app data directory
            app_data = Path.home() / '.star_analyzer'
            app_data.mkdir(exist_ok=True)
            config_path = app_data / 'config.json'

        self.config_path = config_path
        self._config = self._load()

    def _load(self) -> dict:
        """Load config from file."""
        if self.config_path.exists():
            try:
                return json.loads(self.config_path.read_text())
            except (json.JSONDecodeError, IOError):
                pass
        return {}

    def _save(self):
        """Save config to file."""
        try:
            self.config_path.write_text(json.dumps(self._config, indent=2))
        except IOError:
            pass

    @property
    def last_import_path(self) -> Optional[Path]:
        """Get last import folder path."""
        path_str = self._config.get('last_import_path')
        if path_str:
            return Path(path_str)
        return None

    @last_import_path.setter
    def last_import_path(self, value: Path):
        """Set last import folder path."""
        self._config['last_import_path'] = str(value)
        self._save()


class StarAnalyzerApp(tk.Tk):
    """Main application window."""

    def __init__(self):
        super().__init__()

        self.config_manager = ConfigManager()
        self.current_cohort: Optional[Cohort] = None

        self._setup_window()
        self._create_menu()
        self._create_toolbar()
        self._create_main_content()
        self._create_statusbar()

    def _setup_window(self):
        """Configure the main window."""
        self.title('STAR Analyzer - Data Parser')
        self.geometry('1100x600')
        self.minsize(800, 400)

        # Set window icon if available
        icon_path = Path(__file__).parent.parent.parent / 'resources' / 'icon.ico'
        if icon_path.exists():
            try:
                self.iconbitmap(icon_path)
            except tk.TclError:
                pass

    def _create_menu(self):
        """Create the menu bar."""
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label='File', menu=file_menu)
        file_menu.add_command(label='Import Data...', command=self._open_import_dialog, accelerator='Ctrl+I')
        file_menu.add_separator()
        file_menu.add_command(label='Export to Excel...', command=self._export_excel, accelerator='Ctrl+E')
        file_menu.add_separator()
        file_menu.add_command(label='Exit', command=self.quit, accelerator='Alt+F4')

        # Bind keyboard shortcuts
        self.bind('<Control-i>', lambda e: self._open_import_dialog())
        self.bind('<Control-e>', lambda e: self._export_excel())

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label='View', menu=view_menu)
        view_menu.add_command(label='Clear Filters', command=self._clear_filters)
        view_menu.add_separator()
        view_menu.add_command(label='Session Details', command=self._show_selected_details)

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

        self.export_btn = ttk.Button(toolbar, text='Export Excel', command=self._export_excel, state=tk.DISABLED)
        self.export_btn.pack(side=tk.LEFT, padx=2)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)

        self.clear_btn = ttk.Button(toolbar, text='Clear Data', command=self._clear_data, state=tk.DISABLED)
        self.clear_btn.pack(side=tk.LEFT, padx=2)

    def _create_main_content(self):
        """Create the main content area."""
        # Main frame
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Data viewer
        self.data_viewer = DataViewer(main_frame, on_selection_change=self._on_selection_change)
        self.data_viewer.pack(fill=tk.BOTH, expand=True)

    def _create_statusbar(self):
        """Create the status bar."""
        statusbar = ttk.Frame(self, padding=(5, 2))
        statusbar.pack(fill=tk.X, side=tk.BOTTOM)

        self.status_var = tk.StringVar(value='Ready. Click "Import Data" to begin.')
        ttk.Label(statusbar, textvariable=self.status_var).pack(side=tk.LEFT)

        # Selection info
        self.selection_var = tk.StringVar(value='')
        ttk.Label(statusbar, textvariable=self.selection_var).pack(side=tk.RIGHT)

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

        # Create cohort
        self.current_cohort = Cohort(
            name=result.source_path.name if result.source_path else 'Imported Data',
            sessions=result.sessions,
            source_path=result.source_path,
        )

        # Update viewer
        self.data_viewer.set_sessions(result.sessions)

        # Update UI state
        self.export_btn.config(state=tk.NORMAL)
        self.clear_btn.config(state=tk.NORMAL)

        # Status message
        status = f'Imported {result.success_count} sessions from {result.source_path.name}'
        if result.error_count > 0:
            status += f' ({result.error_count} files skipped)'
        self.status_var.set(status)

        # Show summary with warnings if any
        warning_sessions = [s for s in result.sessions if s.has_warnings]
        if warning_sessions or result.error_count > 0:
            self._show_import_summary(result, warning_sessions)

    def _show_import_summary(self, result: ImportResult, warning_sessions):
        """Show import summary dialog."""
        lines = [f'Successfully imported: {result.success_count} sessions']

        if result.error_count > 0:
            lines.append(f'Failed to parse: {result.error_count} files')
            lines.append('')
            lines.append('Failed files:')
            for path, error in result.errors[:10]:  # Show first 10
                lines.append(f'  - {path.name}: {error}')
            if len(result.errors) > 10:
                lines.append(f'  ... and {len(result.errors) - 10} more')

        if warning_sessions:
            lines.append('')
            lines.append(f'Sessions with warnings: {len(warning_sessions)}')
            lines.append('(Double-click a session to view warnings)')

        messagebox.showinfo('Import Summary', '\n'.join(lines), parent=self)

    def _export_excel(self):
        """Export current data to Excel."""
        if not self.current_cohort or not self.current_cohort.sessions:
            messagebox.showwarning('No Data', 'No data to export. Import data first.', parent=self)
            return

        # Get save path
        default_name = f'{self.current_cohort.name}_export.xlsx'
        file_path = filedialog.asksaveasfilename(
            parent=self,
            title='Export to Excel',
            defaultextension='.xlsx',
            filetypes=[('Excel files', '*.xlsx'), ('All files', '*.*')],
            initialfile=default_name,
        )

        if not file_path:
            return

        try:
            exporter = ExcelExporter()
            exporter.export_cohort(
                self.current_cohort,
                Path(file_path),
                include_timestamps=True,
            )
            self.status_var.set(f'Exported to {Path(file_path).name}')
            messagebox.showinfo('Export Complete', f'Data exported to:\n{file_path}', parent=self)
        except Exception as e:
            messagebox.showerror('Export Error', f'Failed to export: {e}', parent=self)

    def _clear_data(self):
        """Clear all loaded data."""
        if not self.current_cohort:
            return

        if messagebox.askyesno('Clear Data', 'Clear all imported data?', parent=self):
            self.current_cohort = None
            self.data_viewer.clear()
            self.export_btn.config(state=tk.DISABLED)
            self.clear_btn.config(state=tk.DISABLED)
            self.status_var.set('Data cleared. Click "Import Data" to begin.')
            self.selection_var.set('')

    def _clear_filters(self):
        """Clear all filters in data viewer."""
        self.data_viewer._clear_filters()

    def _show_selected_details(self):
        """Show details for selected session."""
        session = self.data_viewer.get_selected_session()
        if session:
            from .data_viewer import SessionDetailDialog
            SessionDetailDialog(self, session)
        else:
            messagebox.showinfo('No Selection', 'Select a session first.', parent=self)

    def _on_selection_change(self, session: Optional[MedPCSession]):
        """Handle selection change in data viewer."""
        if session:
            self.selection_var.set(f'Selected: Subject {session.subject}, {session.date}')
        else:
            self.selection_var.set('')

    def _show_about(self):
        """Show about dialog."""
        about_text = """STAR Analyzer - Data Parser

Version 1.0

A tool for parsing and analyzing Med-PC IV data files from STAR rodent operant self-administration experiments.

Developed for behavioral neuroscience research."""

        messagebox.showinfo('About STAR Analyzer', about_text, parent=self)


def run():
    """Run the application."""
    app = StarAnalyzerApp()
    app.mainloop()
