"""Global hook with bounded capture and no Tk/COM calls on hook threads."""
import logging
import threading
import time
from .models import KeyRouter, normalize_key, MODIFIERS

log = logging.getLogger(__name__)


class KeyboardService:
    def __init__(self, audio, messages):
        self.audio, self.messages = audio, messages
        self.router = KeyRouter()
        self.lock = threading.RLock()
        self.capture = None
        self.capture_keys = set()
        self.step = 0.05
        self.hook = None
        self.keyboard = None

    def configure(self, settings):
        with self.lock:
            self.router.configure(settings)
            self.step = settings.step / 100

    def start(self):
        import keyboard
        self.keyboard = keyboard
        try:
            self.hook = keyboard.hook(self._event, suppress=True)
            self.messages.put(('keyboard', True))
        except Exception:
            log.exception('Could not install keyboard hook')
            self.messages.put(('keyboard', False))

    def pause(self, paused):
        with self.lock:
            self.router.paused = paused

    def begin_capture(self, token):
        with self.lock:
            self.capture = (token, time.monotonic() + 12)

    def cancel_capture(self):
        with self.lock:
            self.capture = None

    def check_timeout(self):
        with self.lock:
            if self.capture and time.monotonic() > self.capture[1]:
                token = self.capture[0]
                self.capture = None
                self.messages.put(('capture', (token, None)))

    def _event(self, event):
        try:
            with self.lock:
                name = normalize_key(event.name, event.scan_code)
                down = event.event_type == 'down'
                identity = event.scan_code
                if identity in self.capture_keys:
                    if not down:
                        self.capture_keys.discard(identity)
                        self.router.route(event.name, event.scan_code, False)
                    return False
                if self.capture:
                    token = self.capture[0]
                    # Keep modifier state correct while capture bypasses routing.
                    if name in MODIFIERS:
                        self.router.route(event.name, event.scan_code, down)
                        return True
                    if down:
                        self.capture_keys.add(identity)
                        self.capture = None
                        combo = '+'.join([m for m in MODIFIERS if m in self.router.held_modifiers] + [name])
                        self.messages.put(('capture', (token, None if name == 'esc' else combo)))
                    return False
                actions, consumed = self.router.route(event.name, event.scan_code, down)
                for app, all_sessions, action in actions:
                    self.audio.submit(app, all_sessions, action, self.step)
                return not consumed
        except Exception:
            log.exception('Keyboard callback failed')
            return True

    def stop(self):
        self.cancel_capture()
        if self.hook is not None:
            self.keyboard.unhook(self.hook)
            self.hook = None
