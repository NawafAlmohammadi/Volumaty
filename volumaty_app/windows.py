"""Windows startup registration, shortcuts and per-profile single instance."""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import winreg

RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
APPROVED_KEY = r'Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run'


def launch_command(background=False, frozen=None, executable=None, script=None):
    frozen = getattr(sys, 'frozen', False) if frozen is None else frozen
    executable = str(executable or sys.executable)
    script = str(script or Path(__file__).resolve().parents[1] / 'volumaty.py')
    if not frozen:
        pythonw = Path(executable).with_name('pythonw.exe')
        if pythonw.exists():
            executable = str(pythonw)
    args = [executable] if frozen else [executable, script]
    if background:
        args.append('--background')
    return subprocess.list2cmdline(args)


@dataclass
class StartupStatus:
    registered: bool
    matches: bool
    blocked: bool
    command: str = ''


class StartupService:
    def __init__(self, name='Volumaty', command=None):
        self.name = name
        self.command = command or launch_command(background=True)

    def status(self):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                value = winreg.QueryValueEx(key, self.name)[0]
        except FileNotFoundError:
            return StartupStatus(False, False, False)
        blocked = False
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APPROVED_KEY) as key:
                data = winreg.QueryValueEx(key, self.name)[0]
                blocked = isinstance(data, bytes) and len(data) >= 4 and int.from_bytes(data[:4], 'little') in (3, 7)
        except FileNotFoundError:
            pass
        return StartupStatus(True, value == self.command, blocked, value)

    def set_enabled(self, enabled):
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                if len(self.command) > 260:
                    raise ValueError('Startup command is too long. Move Volumaty to a shorter path.')
                winreg.SetValueEx(key, self.name, 0, winreg.REG_SZ, self.command)
            else:
                try:
                    winreg.DeleteValue(key, self.name)
                except FileNotFoundError:
                    pass
        state = self.status()
        if enabled and not state.matches:
            raise OSError('Windows did not retain the startup command.')
        return state


def create_shortcut(destination):
    import pythoncom
    from win32com.client import Dispatch
    pythoncom.CoInitialize()
    try:
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortcut(str(destination))
        # Shortcut fields are assigned directly through COM, never interpolated into a shell.
        frozen = getattr(sys, 'frozen', False)
        target = Path(sys.executable)
        if not frozen and target.with_name('pythonw.exe').exists():
            target = target.with_name('pythonw.exe')
        script = Path(__file__).resolve().parents[1] / 'volumaty.py'
        shortcut.TargetPath = str(target)
        shortcut.Arguments = '' if frozen else subprocess.list2cmdline([str(script)])
        shortcut.WorkingDirectory = str(target.parent if frozen else script.parent)
        shortcut.Description = 'Volumaty — per-app volume control'
        shortcut.Save()
        if not Path(destination).exists():
            raise OSError('Windows could not create the shortcut.')
    finally:
        pythoncom.CoUninitialize()


def desktop_path():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                       r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders') as key:
        return Path(os.path.expandvars(winreg.QueryValueEx(key, 'Desktop')[0]))


class SingleInstance:
    def __init__(self, profile):
        import win32api
        import win32event
        self.api, self.events = win32api, win32event
        suffix = hashlib.sha256(str(Path(profile).resolve()).lower().encode()).hexdigest()[:20]
        self.mutex = win32event.CreateMutex(None, False, 'Local\\VolumatyMutex-' + suffix)
        already = win32api.GetLastError() == 183
        self.show_event = win32event.CreateEvent(None, False, False, 'Local\\VolumatyShow-' + suffix)
        self.owner = not already
        if already:
            win32event.SetEvent(self.show_event)

    def requested_show(self):
        return self.events.WaitForSingleObject(self.show_event, 0) == self.events.WAIT_OBJECT_0

    def close(self):
        self.api.CloseHandle(self.show_event)
        self.api.CloseHandle(self.mutex)
