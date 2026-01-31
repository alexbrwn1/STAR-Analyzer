"""
Import dialog for STAR Analyzer.
Provides folder selection and progress tracking during import.
"""

import threading
import queue
from pathlib import Path
from tkinter import ttk, filedialog, messagebox
from typing import Callable, List, Optional
import tkinter as tk

from core.file_discovery import discover_medpc_files
from core.parser import MedPCParser, ParseError
from core.data_models import MedPCSession


class ImportResult:
    """Result of an import operation."""

    def __init__(self):
        self.sessions: List[MedPCSession] = []
        self.errors: List[tuple] = []  # (file_path, error_message)
        self.source_path: Optional[Path] = None

    @property
    def success_count(self) -> int:
        return len(self.sessions)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def total_files(self) -> int:
        return self.success_count + self.error_count


class ImportDialog(tk.Toplevel):
    """Dialog for importing Med-PC data files."""

    def __init__(
        self,
        parent: tk.Tk,
        initial_path: Optional[Path] = None,
        on_complete: Optional[Callable[[ImportResult], None]] = None,
    ):
        super().__init__(parent)

        self.parent = parent
        self.initial_path = initial_path
        self.on_complete = on_complete
        self.result = ImportResult()
        self._import_thread: Optional[threading.Thread] = None
        self._cancel_requested = False
        self._message_queue = queue.Queue()

        self._setup_window()
        self._create_widgets()
        self._process_queue()

    def _setup_window(self):
        """Configure the dialog window."""
        self.title('Import Data')
        self.geometry('550x220')
        self.resizable(False, False)
        self.transient(self.parent)
        self.grab_set()

        # Center on parent
        self.update_idletasks()
        x = self.parent.winfo_x() + (self.parent.winfo_width() - 550) // 2
        y = self.parent.winfo_y() + (self.parent.winfo_height() - 220) // 2
        self.geometry(f'+{x}+{y}')

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _create_widgets(self):
        """Create dialog widgets."""
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Folder selection
        folder_frame = ttk.LabelFrame(main_frame, text='Select Folder', padding=10)
        folder_frame.pack(fill=tk.X, pady=(0, 10))

        self.path_var = tk.StringVar(value=str(self.initial_path) if self.initial_path else '')
        self.path_entry = ttk.Entry(folder_frame, textvariable=self.path_var, width=55)
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        self.browse_btn = ttk.Button(folder_frame, text='Browse...', command=self._browse_folder)
        self.browse_btn.pack(side=tk.RIGHT)

        # Progress section
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=10)

        self.status_var = tk.StringVar(value='Select a folder to import')
        self.status_label = ttk.Label(progress_frame, textvariable=self.status_var)
        self.status_label.pack(anchor=tk.W)

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100,
            mode='determinate',
        )
        self.progress_bar.pack(fill=tk.X, pady=5)

        self.detail_var = tk.StringVar(value='')
        self.detail_label = ttk.Label(progress_frame, textvariable=self.detail_var, foreground='gray')
        self.detail_label.pack(anchor=tk.W)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        self.import_btn = ttk.Button(button_frame, text='Import', command=self._start_import)
        self.import_btn.pack(side=tk.RIGHT, padx=(5, 0))

        self.cancel_btn = ttk.Button(button_frame, text='Cancel', command=self._cancel)
        self.cancel_btn.pack(side=tk.RIGHT)

    def _browse_folder(self):
        """Open folder browser dialog."""
        initial_dir = self.path_var.get() or str(Path.home())
        if initial_dir and Path(initial_dir).exists():
            pass
        else:
            initial_dir = str(Path.home())

        folder = filedialog.askdirectory(
            parent=self,
            initialdir=initial_dir,
            title='Select folder containing Med-PC data files',
        )
        if folder:
            self.path_var.set(folder)

    def _start_import(self):
        """Start the import process in a background thread."""
        folder_path = self.path_var.get().strip()
        if not folder_path:
            messagebox.showwarning('No Folder', 'Please select a folder to import.', parent=self)
            return

        path = Path(folder_path)
        if not path.exists():
            messagebox.showerror('Invalid Path', f'Path does not exist:\n{folder_path}', parent=self)
            return

        if not path.is_dir():
            messagebox.showerror('Invalid Folder', 'The selected path is not a valid folder.', parent=self)
            return

        # Disable controls during import
        self.import_btn.config(state=tk.DISABLED)
        self.browse_btn.config(state=tk.DISABLED)
        self.path_entry.config(state=tk.DISABLED)
        self._cancel_requested = False

        # Reset result
        self.result = ImportResult()
        self.result.source_path = path

        # Start import in background thread
        self._import_thread = threading.Thread(target=self._run_import, args=(path,), daemon=True)
        self._import_thread.start()

    def _run_import(self, folder_path: Path):
        """Run the import process (called in background thread)."""
        try:
            # Discover files
            self._queue_update('status', 'Scanning for data files...')
            files = discover_medpc_files(folder_path, recursive=True)

            if not files:
                self._queue_update('status', 'No Med-PC data files found in folder')
                self._queue_update('complete', False)
                return

            total = len(files)
            self._queue_update('status', f'Found {total} files. Parsing...')

            # Parse files
            parser = MedPCParser()
            for i, file_path in enumerate(files):
                if self._cancel_requested:
                    self._queue_update('status', 'Import cancelled')
                    self._queue_update('complete', False)
                    return

                # Update progress
                progress = ((i + 1) / total) * 100
                self._queue_update('progress', progress)
                self._queue_update('detail', f'Parsing: {file_path.name}')

                try:
                    session = parser.parse_file(file_path)
                    self.result.sessions.append(session)
                except ParseError as e:
                    self.result.errors.append((file_path, str(e)))
                except Exception as e:
                    self.result.errors.append((file_path, f'Unexpected error: {e}'))

            # Final status
            status = f'Imported {self.result.success_count} sessions'
            if self.result.error_count > 0:
                status += f', {self.result.error_count} files skipped'
            self._queue_update('status', status)
            self._queue_update('progress', 100)
            self._queue_update('detail', '')
            self._queue_update('complete', True)

        except Exception as e:
            self._queue_update('status', f'Error: {e}')
            self._queue_update('complete', False)

    def _queue_update(self, msg_type: str, value):
        """Queue a UI update from background thread."""
        self._message_queue.put((msg_type, value))

    def _process_queue(self):
        """Process queued messages from background thread."""
        try:
            while True:
                msg_type, value = self._message_queue.get_nowait()

                if msg_type == 'status':
                    self.status_var.set(value)
                elif msg_type == 'progress':
                    self.progress_var.set(value)
                elif msg_type == 'detail':
                    self.detail_var.set(value)
                elif msg_type == 'complete':
                    self._handle_complete(value)

        except queue.Empty:
            pass

        # Continue processing queue
        if self.winfo_exists():
            self.after(50, self._process_queue)

    def _handle_complete(self, success: bool):
        """Handle import completion."""
        self.import_btn.config(state=tk.NORMAL)
        self.browse_btn.config(state=tk.NORMAL)
        self.path_entry.config(state=tk.NORMAL)

        if success and self.result.success_count > 0:
            # Call callback with result
            if self.on_complete:
                self.on_complete(self.result)
            self.destroy()
        elif not self._cancel_requested:
            if self.result.error_count > 0 and self.result.success_count == 0:
                messagebox.showwarning(
                    'Import Failed',
                    f'All {self.result.error_count} files failed to parse.',
                    parent=self,
                )

    def _cancel(self):
        """Cancel the import or close dialog."""
        if self._import_thread and self._import_thread.is_alive():
            self._cancel_requested = True
        else:
            self.destroy()
