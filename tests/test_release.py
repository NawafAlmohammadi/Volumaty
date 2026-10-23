"""Regressions for the 2.1 reliability and settings-transfer release."""
import unittest
import json
from pathlib import Path
import tempfile
from queue import Queue, Empty
from types import SimpleNamespace
from unittest.mock import Mock, patch
from volumaty_app.audio import AudioWorker, apply_action
from volumaty_app.keyboard_service import KeyboardService
from volumaty_app.models import Settings, Slot, KeyRouter
from volumaty_app.config import ConfigStore


class Volume:
    def __init__(self, value=.5, muted=False, broken=False):
        self.value, self.muted, self.broken = value, muted, broken

    def GetMasterVolume(self):
        if self.broken:
            raise OSError('Audio session expired')
        return self.value

    def SetMasterVolume(self, value, context):
        self.value = value

    def GetMute(self):
        if self.broken:
            raise OSError('Audio session expired')
        return self.muted

    def SetMute(self, muted, context):
        if self.broken:
            raise OSError('Audio session expired')
        self.muted = muted


class AudioReliabilityTests(unittest.TestCase):
    def test_single_session_controls_choose_first_healthy_session(self):
        good = Volume(.4)
        worker = AudioWorker(Queue())
        with patch.object(worker, '_sessions', return_value={'music.exe': ('Music.exe', [Volume(broken=True), good])}):
            worker._process_batch([('Music.exe', False, 'up', .05)])
            self.assertAlmostEqual(good.value, .45)
            worker._process_batch([('Music.exe', False, 'set', .2)])
            self.assertAlmostEqual(good.value, .2)
            worker._process_batch([('Music.exe', False, 'mute', .05)])
            self.assertTrue(good.muted)

    def test_stale_session_does_not_block_volume_on_healthy_session(self):
        good = Volume(.5)
        apply_action([Volume(broken=True), good], 'up', .05)
        self.assertAlmostEqual(good.value, .55)

    def test_stale_first_session_does_not_block_consistent_mute(self):
        good = Volume(muted=False)
        apply_action([Volume(broken=True), good, Volume(muted=True)], 'mute')
        self.assertTrue(good.muted)

    def test_batch_enumerates_once_and_preserves_tick_order(self):
        good = Volume(.98)
        worker = AudioWorker(Queue())
        with patch.object(worker, '_sessions', return_value={'music.exe': ('Music.exe', [good])}) as sessions:
            snapshot = worker._process_batch([('Music.exe', True, 'up', .05),
                                              ('Music.exe', True, 'down', .05)])
        self.assertEqual(sessions.call_count, 1)
        self.assertAlmostEqual(good.value, .95)
        self.assertAlmostEqual(snapshot['music.exe']['volume'], .95)

    def test_snapshot_ignores_expired_interface(self):
        from volumaty_app.audio import build_snapshot
        snapshot = build_snapshot({'gone.exe': ('Gone.exe', [Volume(broken=True)]),
                                   'music.exe': ('Music.exe', [Volume(broken=True), Volume(.4)])})
        self.assertNotIn('gone.exe', snapshot)
        self.assertAlmostEqual(snapshot['music.exe']['volume'], .4)
        self.assertEqual(snapshot['music.exe']['sessions'], 1)

    def test_device_failure_clears_snapshot_and_retries_with_backoff(self):
        messages = Queue()
        worker = AudioWorker(messages)
        clock = [0.0]

        class Commands:
            def get(self, timeout):
                clock[0] += timeout
                raise Empty

            def get_nowait(self):
                raise Empty

        class Stopping:
            def is_set(self):
                return clock[0] > 2.3

        worker.commands, worker.stopping = Commands(), Stopping()
        with patch('volumaty_app.audio.time.monotonic', side_effect=lambda: clock[0]):
            with patch.object(worker, '_sessions', side_effect=OSError('Device disconnected')) as sessions:
                with self.assertLogs('volumaty_app.audio', level='ERROR'):
                    worker._run()
        events = list(messages.queue)
        self.assertIn(('audio', {}), events)
        self.assertEqual(sessions.call_count, 2)


class CaptureRepeatTests(unittest.TestCase):
    def test_capture_of_an_already_held_mute_key_clears_routing_state_on_release(self):
        audio = Mock()
        service = KeyboardService(audio, Queue())
        service.configure(Settings(slots=[Slot(app='Music.exe', key_mute='f9')]))
        down = SimpleNamespace(name='f9', scan_code=67, event_type='down')
        service._event(down)
        self.assertEqual(audio.submit.call_count, 1)
        service.begin_capture(('slot', 'key_mute'))
        service._event(down)
        service._event(SimpleNamespace(name='f9', scan_code=67, event_type='up'))
        service._event(down)
        self.assertEqual(audio.submit.call_count, 2)

    def test_capture_understands_windows_media_scan_codes(self):
        messages = Queue()
        service = KeyboardService(None, messages)
        service.begin_capture(('slot', 'key_up'))
        self.assertFalse(service._event(SimpleNamespace(name='unknown', scan_code=-175, event_type='down')))
        self.assertEqual(messages.get_nowait(), ('capture', (('slot', 'key_up'), 'volume up')))

    def test_captured_key_repeat_never_triggers_action_until_release(self):
        class Audio:
            def __init__(self):
                self.commands = []

            def submit(self, *args):
                self.commands.append(args)

        audio = Audio()
        service = KeyboardService(audio, Queue())
        slot = Slot(app='Music.exe', key_up='f8')
        service.configure(Settings(slots=[slot]))
        service.begin_capture(('slot', 'key_up'))
        event = SimpleNamespace(name='f8', scan_code=66, event_type='down')
        self.assertFalse(service._event(event))
        self.assertFalse(service._event(event))
        self.assertEqual(audio.commands, [])
        self.assertFalse(service._event(SimpleNamespace(name='f8', scan_code=66, event_type='up')))
        self.assertFalse(service._event(event))
        self.assertEqual(len(audio.commands), 1)


class SettingsTransferTests(unittest.TestCase):
    def test_roundtrip_preserves_bindings_and_backs_up_previous_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory) / 'profile')
            original = Settings(step=3)
            store.save(original)
            transferred = Settings(slots=[Slot(app='Music.exe', knob=True, key_up='ctrl+f8')], step=7)
            exported = Path(directory) / 'export.json'
            store.export_settings(transferred, exported)
            restored = store.import_settings(exported)
            self.assertEqual(restored.to_dict(), transferred.to_dict())
            self.assertEqual(store.load().step, 7)
            backups = list(store.directory.glob('settings-before-import-*.json'))
            self.assertEqual(len(backups), 1)
            self.assertEqual(json.loads(backups[0].read_text())['step'], 3)

    def test_rejects_invalid_import_without_modifying_current_file(self):
        invalid = [[], {'schema_version': 99, 'slots': []}, {'schema_version': 2, 'slots': 'wrong'},
                   {'schema_version': 2, 'slots': [{'app': 'C:\\private\\Music.exe'}]},
                   {'schema_version': 2, 'slots': [], 'step': 0},
                   {'schema_version': 2, 'slots': [], 'close_to_tray': 'yes'},
                   {'schema_version': 2, 'slots': [{'app': 'Music.exe', 'knob': 'false'}]},
                   {'schema_version': 2, 'slots': [{'key_up': 'ctrl'}]},
                   {'schema_version': 2, 'slots': [None]},
                   {'schema_version': 2, 'slots': [{}] * 51}]
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(directory)
            store.save(Settings(step=3))
            original = store.path.read_bytes()
            source = Path(directory) / 'import.json'
            for data in invalid:
                with self.subTest(data=data):
                    source.write_text(json.dumps(data))
                    with self.assertRaises(ValueError):
                        store.import_settings(source)
                    self.assertEqual(store.path.read_bytes(), original)
            self.assertFalse(list(store.directory.glob('settings-before-import-*.json')))

    def test_rejects_duplicate_shortcuts_even_if_modifier_order_differs(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(directory)
            source = Path(directory) / 'import.json'
            source.write_text(json.dumps({'schema_version': 2, 'slots': [
                {'app': 'Music.exe', 'key_up': 'shift+ctrl+f8'},
                {'app': 'Chat.exe', 'key_down': 'ctrl+shift+f8'}]}))
            with self.assertRaisesRegex(ValueError, 'shortcut'):
                store.import_settings(source)
            self.assertFalse(store.path.exists())

    def test_rejects_oversized_input(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(directory)
            source = Path(directory) / 'large.json'
            source.write_bytes(b' ' * (1_048_576 + 1))
            with self.assertRaisesRegex(ValueError, 'large'):
                store.import_settings(source)

    def test_failed_import_keeps_current_file_and_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(directory)
            store.save(Settings(step=3))
            source = Path(directory) / 'import.json'
            source.write_text(json.dumps(Settings(step=9).to_dict()))
            with patch('volumaty_app.config.os.replace', side_effect=OSError('disk failure')):
                with self.assertRaises(OSError):
                    store.import_settings(source)
            self.assertEqual(store.load().step, 3)
            self.assertEqual(len(list(store.directory.glob('settings-before-import-*.json'))), 1)

    def test_legacy_export_can_be_imported(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(directory)
            source = Path(directory) / 'legacy.json'
            source.write_text(json.dumps({'slots': [{'app': 'Music.exe', 'knob': True}]}))
            settings = store.import_settings(source)
            self.assertEqual(settings.slots[0].app, 'Music.exe')
            self.assertTrue(settings.slots[0].knob)


class PhysicalKeyTests(unittest.TestCase):
    def test_release_after_shift_changes_name_but_clears_physical_key(self):
        router = KeyRouter()
        router.configure(Settings(slots=[Slot(app='Music.exe', key_mute='shift+!')]))
        router.route('shift', 42, True)
        self.assertTrue(router.route('!', 2, True)[0])
        router.route('shift', 42, False)
        self.assertEqual(router.route('1', 2, False), ([], True))
        router.route('shift', 42, True)
        self.assertTrue(router.route('!', 2, True)[0])

    def test_real_windows_left_and_right_control_share_scan_code(self):
        router = KeyRouter()
        router.route('ctrl', 29, True)
        router.route('right ctrl', 29, True)
        router.route('ctrl', 29, False)
        self.assertEqual(router.held_modifiers, {'ctrl'})


class LifecycleTests(unittest.TestCase):
    def test_failed_tray_quit_keeps_pumping_and_can_show_window(self):
        from volumaty_app.ui import VolumatyWindow
        fake = SimpleNamespace(quitting=False, save_settings=lambda: False,
                               keyboard=SimpleNamespace(check_timeout=lambda: None),
                               instance=SimpleNamespace(requested_show=lambda: False),
                               messages=Queue(), after=Mock(), show_window=Mock())
        fake.quit_app = lambda: VolumatyWindow.quit_app(fake)
        fake.pump = lambda: VolumatyWindow.pump(fake)
        fake.messages.put(('quit', None))
        fake.messages.put(('show', None))
        fake.pump()
        self.assertFalse(fake.quitting)
        self.assertTrue(fake.messages.empty())
        fake.after.assert_called_once()
        self.assertTrue(fake.show_window.called)


if __name__ == '__main__':
    unittest.main()
