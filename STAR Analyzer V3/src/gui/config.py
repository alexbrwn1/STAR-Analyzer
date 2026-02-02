"""
Configuration manager for STAR Analyzer V3.
Persists user settings like last import folder.
"""

import json
from pathlib import Path
from typing import Optional


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

    @property
    def window_geometry(self) -> Optional[str]:
        """Get saved window geometry."""
        return self._config.get('window_geometry')

    @window_geometry.setter
    def window_geometry(self, value: str):
        """Set window geometry."""
        self._config['window_geometry'] = value
        self._save()
