import json
from pathlib import Path
from queue import Queue
import tempfile
import unittest
from unittest.mock import patch

from volumaty_app.audio import apply_action
from volumaty_app.config import ConfigStore
from volumaty_app.models import Settings, Slot, KeyRouter, normalize_combo, shortcut_conflict
from volumaty_app.keyboard_service import KeyboardService
from volumaty_app.windows import launch_command, StartupService


class Volume:
    def __init__(self, value, muted=False):
        self.value, self.muted = value, muted

    def GetMasterVolume(self):
        return self.value

    def SetMasterVolume(self, value, context):
        self.value = value

    def GetMute(self):
        return self.muted

    def SetMute(self, value, context):
        self.muted = bool(value)


class AudioTests(unittest.TestCase):
    def test_clamp_and_all_sessions(self):
        volumes = [Volume(.98), Volume(.10)]
        apply_action(volumes, 'up', .05)
        self.assertEqual([v.value for v in volumes], [1, .15000000000000002])
        apply_action(volumes, 'down', .2)
        self.assertEqual([v.value for v in volumes], [.8, 0])
        apply_action(volumes, 'set', .35)
        self.assertEqual([v.value for v in volumes], [.35, .35])

    def test_mute_synchronizes_mixed_sessions(self):
        volumes = [Volume(.5, False), Volume(.4, True)]
        apply_action(volumes, 'mute')
        self.assertTrue(all(v.muted for v in volumes))
        apply_action(volumes, 'mute')
        self.assertFalse(any(v.muted for v in volumes))

    def test_closed_app_is_noop(self):
        apply_action([], 'up')


class ConfigTests(unittest.TestCase):
    def test_migrate_without_overwriting_original(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(directory)
            old = Path(directory) / 'volumaty_config.json'
            legacy = json.dumps({'slots': [{'app': 'Discord.exe', 'knob': True, 'all_sessions': False, 'key_up': 'shift+ctrl+f8'}]})
            old.write_text(legacy)
            data = store.load()
            self.assertEqual(data.slots[0].key_up, 'ctrl+shift+f8')
            self.assertFalse(data.slots[0].all_sessions)
            store.save(data)
            self.assertEqual(old.read_text(), legacy)
            self.assertTrue(store.load().slots[0].knob)
            self.assertFalse(list(Path(directory).glob('*.tmp')))

    def test_corrupt_config_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(directory)
            store.path.write_text('{broken')
            with self.assertLogs('volumaty_app.config', level='ERROR'):
                settings = store.load()
            self.assertTrue(store.notice)
            store.save(settings)
            backup = list(Path(directory).glob('settings-corrupt-*.json'))
            self.assertEqual(len(backup), 1)
            self.assertEqual(backup[0].read_text(), '{broken')

    def test_invalid_and_empty_data(self):
        settings = Settings.from_dict({'step': None, 'slots': 'invalid'})
        self.assertEqual(settings.step, 5)
        self.assertEqual(settings.slots, [])
        settings = Settings.from_dict({'step': 999, 'slots': [{'app': 'No apps found'}, {'id': 'same'}, {'id': 'same'}]})
        self.assertEqual(settings.step, 20)
        self.assertEqual(settings.slots[0].app, '')
        self.assertEqual(len({s.id for s in settings.slots}), 3)

    def test_atomic_failure_keeps_original(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(directory)
            store.save(Settings(step=4))
            with patch('volumaty_app.config.os.replace', side_effect=OSError('disk failed')):
                with self.assertRaises(OSError):
                    store.save(Settings(step=7))
            self.assertEqual(store.load().step, 4)
            self.assertFalse(list(Path(directory).glob('*.tmp')))


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(slots=[Slot(app='Discord.exe', knob=True, key_up='ctrl+f8', key_mute='f9'),
                                        Slot(app='Music.exe', knob=True)])
        self.router = KeyRouter()
        self.router.configure(self.settings)

    def test_knob_fans_out_and_consumes_release(self):
        actions, consumed = self.router.route('volume up', -175, True)
        self.assertTrue(consumed)
        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[0], ('Discord.exe', True, 'up'))
        self.assertEqual(self.router.route('volume up', -175, False), ([], True))

    def test_unassigned_media_keys_pass_through(self):
        self.router.configure(Settings(slots=[]))
        self.assertEqual(self.router.route('volume up', -175, True), ([], False))
        self.assertEqual(self.router.route('volume down', -174, False), ([], False))

    def test_duplicate_app_knob_routes_once(self):
        self.router.configure(Settings(slots=[Slot(app='Discord.exe', knob=True, all_sessions=False),
                                              Slot(app='discord.exe', knob=True, all_sessions=True)]))
        actions, consumed = self.router.route('volume up', -175, True)
        self.assertTrue(consumed)
        self.assertEqual(actions, [('discord.exe', True, 'up')])

    def test_exact_modifiers_and_repeat_volume(self):
        self.router.route('left ctrl', 29, True)
        expected = ([('Discord.exe', True, 'up')], True)
        self.assertEqual(self.router.route('f8', 66, True), expected)
        self.assertEqual(self.router.route('f8', 66, True), expected)
        self.router.route('shift', 42, True)
        self.assertEqual(self.router.route('f8', 66, True), ([], False))

    def test_mute_does_not_repeat(self):
        self.assertEqual(len(self.router.route('f9', 67, True)[0]), 1)
        self.assertEqual(self.router.route('f9', 67, True), ([], True))
        self.router.route('f9', 67, False)
        self.assertEqual(len(self.router.route('f9', 67, True)[0]), 1)

    def test_two_control_keys_keep_modifier_held(self):
        self.router.route('left ctrl', 29, True)
        self.router.route('right ctrl', 29, True)
        self.router.route('left ctrl', 29, False)
        self.assertEqual(self.router.held_modifiers, {'ctrl'})

    def test_paused_controls_pass_through(self):
        self.router.paused = True
        self.assertEqual(self.router.route('volume up', -175, True), ([], False))

    def test_duplicate_shortcut_rejected(self):
        owner = shortcut_conflict(self.settings, self.settings.slots[1].id, 'key_down', 'ctrl+f8')
        self.assertEqual(owner, 'Discord.exe')
        self.assertIsNone(shortcut_conflict(self.settings, self.settings.slots[0].id, 'key_up', 'ctrl+f8'))
        self.assertEqual(normalize_combo('alt+left ctrl+f7'), 'ctrl+alt+f7')


class CaptureTests(unittest.TestCase):
    def test_timeout_returns_to_normal_routing(self):
        messages = Queue()
        service = KeyboardService(None, messages)
        service.begin_capture(('slot', 'key_up'))
        with patch('volumaty_app.keyboard_service.time.monotonic', return_value=service.capture[1] + 1):
            service.check_timeout()
        self.assertIsNone(service.capture)
        self.assertEqual(messages.get_nowait(), ('capture', (('slot', 'key_up'), None)))

    def test_escape_cancels_and_release_is_consumed(self):
        from types import SimpleNamespace
        messages = Queue()
        service = KeyboardService(None, messages)
        service.begin_capture(('slot', 'key_up'))
        self.assertFalse(service._event(SimpleNamespace(name='esc', scan_code=1, event_type='down')))
        self.assertIsNone(service.capture)
        self.assertFalse(service._event(SimpleNamespace(name='esc', scan_code=1, event_type='up')))
        self.assertEqual(messages.get_nowait()[1][1], None)


class StartupTests(unittest.TestCase):
    def test_frozen_command_quotes_space_and_background(self):
        command = launch_command(True, True, r'C:\My Apps\Volumaty.exe')
        self.assertEqual(command, '"C:\\My Apps\\Volumaty.exe" --background')

    def test_source_command_includes_interpreter_and_script(self):
        with patch('volumaty_app.windows.Path.exists', return_value=False):
            command = launch_command(True, False, r'C:\Python\python.exe', r'C:\My App\volumaty.py')
        self.assertEqual(command, 'C:\\Python\\python.exe "C:\\My App\\volumaty.py" --background')

    def test_registration_roundtrip_uses_temporary_name(self):
        # Never touch the user's real Volumaty entry.
        import uuid
        service = StartupService('Volumaty-Test-' + uuid.uuid4().hex, '"C:\\Test App\\Volumaty.exe" --background')
        try:
            self.assertFalse(service.status().registered)
            self.assertTrue(service.set_enabled(True).matches)
            self.assertFalse(service.set_enabled(False).registered)
        finally:
            service.set_enabled(False)


if __name__ == '__main__':
    unittest.main()
