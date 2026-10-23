"""One worker owns all COM audio objects; only plain data crosses threads."""
import logging
from queue import Queue, Empty, Full
import threading
import time

log = logging.getLogger(__name__)


def apply_action(interfaces, action, value=0.05):
    """Keep sessions in sync for mute, and clamp volume to the valid range."""
    if not interfaces:
        return
    muted = None
    if action == 'mute':
        for volume in interfaces:
            try:
                muted = not bool(volume.GetMute())
                break
            except Exception:
                log.debug('Expired mute source', exc_info=True)
        if muted is None:
            return
    for volume in interfaces:
        try:
            if action == 'mute':
                volume.SetMute(muted, None)
            else:
                current = volume.GetMasterVolume()
                target = value if action == 'set' else current + (value if action == 'up' else -value)
                volume.SetMasterVolume(max(0.0, min(1.0, target)), None)
        except Exception:
            # Windows can invalidate one session between enumeration and use.
            log.debug('Audio session expired during control', exc_info=True)


def build_snapshot(grouped):
    snapshot = {}
    for name, (original, interfaces) in grouped.items():
        states = []
        for volume in interfaces:
            try:
                states.append((volume.GetMasterVolume(), bool(volume.GetMute())))
            except Exception:
                log.debug('Audio session expired during polling', exc_info=True)
        if states:
            snapshot[name] = {'name': original, 'volume': states[0][0],
                              'muted': states[0][1], 'sessions': len(states)}
    return snapshot


class AudioWorker:
    def __init__(self, messages):
        self.messages = messages
        self.commands = Queue(maxsize=512)
        self.stopping = threading.Event()
        self.thread = threading.Thread(target=self._run, name='VolumatyAudio', daemon=True)

    def start(self):
        self.thread.start()

    def submit(self, app, all_sessions, action, value=0.05):
        try:
            self.commands.put_nowait((app, all_sessions, action, value))
        except Full:
            log.warning('Audio queue full; dropped an action')

    def refresh(self):
        self.submit('', True, 'refresh')

    def stop(self):
        self.stopping.set()
        self.thread.join(timeout=3)

    @staticmethod
    def _sessions():
        from pycaw.pycaw import AudioUtilities
        grouped = {}
        for session in AudioUtilities.GetAllSessions():
            try:
                if session.Process:
                    name = session.Process.name()
                    grouped.setdefault(name.lower(), (name, []))[1].append(session.SimpleAudioVolume)
            except Exception:
                log.debug('Audio session disappeared during refresh', exc_info=True)
        return grouped

    def _process_batch(self, commands):
        """Enumerate once per batch; retain tick order and clamp each tick."""
        grouped = self._sessions()
        for app, all_sessions, action, value in commands:
            if action == 'refresh':
                continue
            interfaces = grouped.get(app.lower(), ('', []))[1]
            if not all_sessions:
                usable = []
                for interface in interfaces:
                    try:
                        interface.GetMasterVolume()
                        interface.GetMute()
                        usable = [interface]
                        break
                    except Exception:
                        log.debug('Skipping expired single-session target', exc_info=True)
                interfaces = usable
            apply_action(interfaces, action, value)
        return build_snapshot(grouped)

    def _run(self):
        import pythoncom
        pythoncom.CoInitialize()
        next_poll = 0
        last_error = None
        retry_after = 0
        try:
            while not self.stopping.is_set():
                try:
                    command = self.commands.get(timeout=0.1)
                except Empty:
                    command = None
                batch = [command] if command else []
                for _ in range(63):
                    try:
                        batch.append(self.commands.get_nowait())
                    except Empty:
                        break
                # Discard controls during an outage so old ticks never replay on reconnect.
                if time.monotonic() < retry_after:
                    continue
                try:
                    if batch or time.monotonic() >= next_poll:
                        snapshot = self._process_batch(batch)
                        self.messages.put(('audio', snapshot))
                        next_poll = time.monotonic() + 0.8
                        last_error = None
                except Exception as exc:
                    if str(exc) != last_error:
                        log.exception('Windows audio operation failed')
                        self.messages.put(('audio', {}))
                        self.messages.put(('error', 'Audio unavailable. Check your output device; Volumaty will retry.'))
                        last_error = str(exc)
                    retry_after = next_poll = time.monotonic() + 2
        finally:
            pythoncom.CoUninitialize()
