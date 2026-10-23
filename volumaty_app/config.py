"""Atomic persistence, legacy migration and recoverable malformed settings."""
import json
import logging
import os
from pathlib import Path
import tempfile
from datetime import datetime
from .models import Settings, KEY_FIELDS, normalize_combo

log = logging.getLogger(__name__)


class ConfigStore:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory else Path(os.environ.get('APPDATA', Path.home())) / 'Volumaty'
        self.path = self.directory / 'settings.json'
        self.notice = ''

    def load(self):
        legacy = self.directory / 'volumaty_config.json'
        path = self.path if self.path.exists() else legacy
        if not path.exists():
            return Settings()
        try:
            return Settings.from_dict(json.loads(path.read_text(encoding='utf-8-sig')))
        except (ValueError, OSError) as exc:
            log.exception('Settings could not be read')
            self.notice = 'Settings could not be read. A backup was kept; defaults are loaded.'
            if path == self.path:
                backup = path.with_name(f'settings-corrupt-{datetime.now():%Y%m%d-%H%M%S-%f}.json')
                try:
                    backup.write_bytes(path.read_bytes())
                except OSError:
                    log.exception('Could not back up malformed settings')
                    raise OSError('Cannot back up settings; the original will not be overwritten.') from exc
            return Settings()

    def save(self, settings):
        self._write_atomic(settings.to_dict(), self.path)

    @staticmethod
    def _write_atomic(data, destination):
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=destination.parent,
                                             suffix='.tmp', delete=False) as handle:
                temp = Path(handle.name)
                json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, destination)
        finally:
            if temp and temp.exists():
                temp.unlink()

    def export_settings(self, settings, destination):
        """Export only portable configuration; no paths, registry or diagnostics."""
        self._write_atomic(settings.to_dict(), destination)

    def import_settings(self, source):
        source = Path(source)
        # Read at most the limit even if a file grows after the initial stat.
        with source.open('rb') as handle:
            contents = handle.read(1_048_577)
        if len(contents) > 1_048_576:
            raise ValueError('Settings file is too large (maximum 1 MB).')
        data = json.loads(contents.decode('utf-8-sig'))
        settings = validate_import(data)
        self.directory.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            backup = self.directory / f'settings-before-import-{datetime.now():%Y%m%d-%H%M%S-%f}.json'
            backup.write_bytes(self.path.read_bytes())
        self.save(settings)
        return settings


def validate_import(data):
    """Reject destructive/ambiguous input before any persistent change."""
    if not isinstance(data, dict):
        raise ValueError('Expected a Volumaty settings object.')
    version = data.get('schema_version', 1)
    if type(version) is not int or version not in (1, 2):
        raise ValueError('This settings format is not supported by this version of Volumaty.')
    slots = data.get('slots')
    if not isinstance(slots, list) or len(slots) > 50:
        raise ValueError('Expected a list containing at most 50 app cards.')
    step = data.get('step', 5)
    if type(step) is not int or not 1 <= step <= 20:
        raise ValueError('Volume step must be an integer between 1 and 20.')
    if type(data.get('close_to_tray', True)) is not bool:
        raise ValueError('Close-to-tray must be true or false.')
    shortcuts = set()
    for slot in slots:
        if not isinstance(slot, dict):
            raise ValueError('Each app card must be an object.')
        app = slot.get('app', '')
        if (not isinstance(app, str) or len(app) > 255 or
                (app and (not app.lower().endswith('.exe') or any(c in app for c in '\\/:*?"<>|\x00\r\n')))):
            raise ValueError('App names must be process names such as Discord.exe, without a folder path.')
        for flag in ('knob', 'all_sessions'):
            if type(slot.get(flag, False)) is not bool:
                raise ValueError(f'{flag} must be true or false.')
        for field in KEY_FIELDS:
            combo = slot.get(field, '')
            if not isinstance(combo, str) or len(combo) > 100 or (combo and not normalize_combo(combo)):
                raise ValueError('Invalid keyboard shortcut in settings.')
            normalized = normalize_combo(combo)
            if normalized:
                if normalized in shortcuts:
                    raise ValueError('A keyboard shortcut is assigned more than once.')
                shortcuts.add(normalized)
    return Settings.from_dict(data)
