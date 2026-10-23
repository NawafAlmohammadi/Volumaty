"""Manual integration check: manipulates only this process's silent audio session.

Run on Windows outside constrained environments: python tests/windows_audio_smoke.py
"""
import json
import os
from pathlib import Path
from queue import Queue, Empty
import sys
import tempfile
import time
import wave
import winsound

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from volumaty_app.audio import AudioWorker
from volumaty_app.keyboard_service import KeyboardService
from volumaty_app.models import Settings, Slot


def main():
    import pythoncom
    from pycaw.pycaw import AudioUtilities
    from types import SimpleNamespace
    pythoncom.CoInitialize()
    report = {}
    worker = None
    original = []
    with tempfile.TemporaryDirectory() as directory:
        wav = Path(directory) / 'silence.wav'
        with wave.open(str(wav), 'wb') as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(44100)
            output.writeframes(b'\x00\x00' * 44100)
        winsound.PlaySound(str(wav), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)
        try:
            deadline = time.monotonic() + 8
            sessions = []
            while not sessions and time.monotonic() < deadline:
                sessions = [s for s in AudioUtilities.GetAllSessions() if s.ProcessId == os.getpid()]
                time.sleep(.1)
            assert sessions, 'Test audio session did not appear'
            process_name = sessions[0].Process.name()
            original = [(s.SimpleAudioVolume, s.SimpleAudioVolume.GetMasterVolume(), s.SimpleAudioVolume.GetMute()) for s in sessions]
            worker = AudioWorker(Queue())
            worker.start()

            def wait_for_volume(value):
                deadline = time.monotonic() + 6
                while time.monotonic() < deadline:
                    if all(abs(s.SimpleAudioVolume.GetMasterVolume() - value) < .01 for s in sessions):
                        return
                    time.sleep(.05)
                raise AssertionError(f'Test session volume did not reach {value}')

            worker.submit(process_name, True, 'set', .40)
            wait_for_volume(.40)
            report['slider_set_40_percent'] = True
            service = KeyboardService(worker, Queue())
            service.configure(Settings(slots=[Slot(app=process_name, knob=True)]))
            assert service._event(SimpleNamespace(name='volume up', scan_code=-175, event_type='down')) is False
            service._event(SimpleNamespace(name='volume up', scan_code=-175, event_type='up'))
            wait_for_volume(.45)
            report['media_key_callback_to_audio_worker_45_percent'] = True
            service._event(SimpleNamespace(name='volume down', scan_code=-174, event_type='down'))
            service._event(SimpleNamespace(name='volume down', scan_code=-174, event_type='up'))
            wait_for_volume(.40)
            report['media_key_down_40_percent'] = True
            worker.submit(process_name, True, 'mute')
            deadline = time.monotonic() + 6
            while time.monotonic() < deadline and not sessions[0].SimpleAudioVolume.GetMute():
                time.sleep(.05)
            assert sessions[0].SimpleAudioVolume.GetMute(), 'Mute did not apply'
            report['mute'] = True
            service.pause(True)
            assert service._event(SimpleNamespace(name='volume up', scan_code=-175, event_type='down')) is True
            service._event(SimpleNamespace(name='volume up', scan_code=-175, event_type='up'))
            report['paused_media_pass_through'] = True
            worker.stop()
            report['worker_shutdown'] = not worker.thread.is_alive()
        finally:
            if worker and worker.thread.is_alive():
                worker.stop()
            for interface, volume, muted in original:
                interface.SetMasterVolume(volume, None)
                interface.SetMute(muted, None)
            winsound.PlaySound(None, 0)
            pythoncom.CoUninitialize()
    destination = Path('test-results')
    destination.mkdir(exist_ok=True)
    (destination / 'audio-smoke.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
