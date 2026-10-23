# Release verification â€” 2.1.0

Validated on Windows 11 x64 on 2026-10-23, with Python 3.13.11 and PyInstaller 6.19.0.

## Automated regression checks

`python -m unittest discover -s tests -v` â€” **38 tests passed**.

Coverage includes settings migration and atomic replacement, backup/recovery, malformed/oversized import rejection, shortcut conflicts, capture timeout/repeats, physical-key release order, left/right modifiers, expired audio sessions, ordered batches, unavailable-device backoff, Windows startup command construction and temporary registration/removal, and failed tray-shutdown recovery.

The Windows startup integration test uses a unique temporary Run entry and removes it. It does not alter the existing Volumaty startup entry.

## Real Windows audio check

`python tests/windows_audio_smoke.py` â€” six checks passed: slider set to 40%, media-key callback up to 45%, down to 40%, mute, paused-key pass-through and worker shutdown. The test creates a silent session in its own process and restores its state before exit.

## Independent review

A separate read-only reviewer examined the runtime and tests. Four Important findings were reproduced with failing regressions and fixed: unsuccessful tray shutdown stopping the UI pump, modifier-dependent key names preventing release, capture of a previously held key leaving routing state behind, and an expired first session in single-session mode. The physical-key fix also handles left/right Ctrl sharing a Windows scan code. The complete suite passed after the fix pass.

## Packaged application

- Single-file Windows EXE built successfully.
- Packaged diagnostics reported version 2.1.0, a frozen runtime and working audio-session access.
- Background startup showed no main window.
- A second launch reopened one existing mixer window.
- UI checks used a separate settings profile; regular user settings and the older desktop release were preserved.

## Limits of verification

Physical knob compatibility and startup after a fresh Windows sign-in require a local-user trial. Device reconnection is covered with controlled simulated failures, not physical device unplugging. No hosted CI run was performed for this release; a build/release workflow template is included under `docs/workflows/`. The executable is unsigned.
