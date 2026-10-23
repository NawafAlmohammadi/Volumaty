"""Lifecycle, diagnostics, logging and CLI."""
import argparse
from dataclasses import asdict
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from queue import Queue
import sys
from .config import ConfigStore
from .windows import StartupService, SingleInstance, launch_command
from . import __version__


def diagnose(store):
    import pythoncom
    from pycaw.pycaw import AudioUtilities
    pythoncom.CoInitialize()
    try:
        sessions = []
        for session in AudioUtilities.GetAllSessions():
            if session.Process:
                sessions.append({'process': session.Process.name(),
                                 'volume': round(session.SimpleAudioVolume.GetMasterVolume(), 4),
                                 'muted': bool(session.SimpleAudioVolume.GetMute())})
        return {'version': __version__, 'packaged': bool(getattr(sys, 'frozen', False)),
                'settings_path': str(store.path), 'startup': asdict(StartupService().status()),
                'expected_startup_command': launch_command(True), 'audio_sessions': sessions}
    finally:
        pythoncom.CoUninitialize()


def main():
    parser = argparse.ArgumentParser(description='Volumaty — per-app volume control for Windows')
    parser.add_argument('--background', action='store_true', help='Start in the system tray')
    parser.add_argument('--data-dir', type=Path, help='Use an isolated profile (startup/shortcuts disabled)')
    parser.add_argument('--diagnose', type=Path, metavar='JSON_FILE', help='Write diagnostics without starting the UI')
    parser.add_argument('--version', action='version', version=f'Volumaty {__version__}')
    args = parser.parse_args()
    if sys.platform != 'win32':
        parser.error('Volumaty requires Windows 10 or Windows 11.')
    store = ConfigStore(args.data_dir)
    store.directory.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(store.directory / 'volumaty.log', maxBytes=512_000, backupCount=2, encoding='utf-8')
    logging.basicConfig(level=logging.INFO, handlers=[handler],
                        format='%(asctime)s %(levelname)s %(name)s %(message)s')
    log = logging.getLogger(__name__)
    if args.diagnose:
        args.diagnose.write_text(json.dumps(diagnose(store), indent=2), encoding='utf-8')
        return
    instance = SingleInstance(store.directory)
    if not instance.owner:
        instance.close()
        return
    audio = keyboard = window = None
    try:
        from .audio import AudioWorker
        from .keyboard_service import KeyboardService
        from .ui import VolumatyWindow
        settings = store.load()
        messages = Queue()
        audio = AudioWorker(messages)
        keyboard = KeyboardService(audio, messages)
        keyboard.configure(settings)
        window = VolumatyWindow(store, settings, audio, keyboard, messages, StartupService(), instance,
                                background=args.background, isolated=bool(args.data_dir))
        audio.start()
        keyboard.start()
        log.info('Volumaty %s started (packaged=%s)', __version__, bool(getattr(sys, 'frozen', False)))
        window.mainloop()
    except Exception:
        log.exception('Volumaty could not start')
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, f'Volumaty could not start.\nDetails: {store.directory / "volumaty.log"}', 'Volumaty', 0x10)
        raise
    finally:
        if keyboard:
            keyboard.stop()
        if audio and audio.thread.is_alive():
            audio.stop()
        if window and window.tray:
            window.tray.stop()
        instance.close()
