# Release verification - 2.1.1

Validated on Windows 11 x64 on 2026-10-23 with Python 3.13.11 and PyInstaller 6.19.0.

## Automated regression checks

`python -m unittest discover -s tests -v`: **39 tests passed**. The 2.1.1 update adds a release-archive check for LICENSE and LICENSING.md. The 38 runtime regression tests are unchanged from 2.1.0.

Coverage includes atomic storage, legacy migration, malformed/oversized import rejection, backups, shortcut conflicts, capture timeout/repeats, physical-key releases, left/right modifiers, expired sessions, ordered audio batches, unavailable-device backoff, temporary Windows startup registration/removal and failed tray-shutdown recovery. The startup integration test uses and removes a uniquely named temporary entry; the existing Volumaty startup entry is preserved.

## Real Windows audio check

The 2.1.0 runtime passed six test-owned silent-session checks: slider set to 40%, media callback up to 45%, down to 40%, mute, paused-key pass-through and worker shutdown. Runtime audio behavior is unchanged in the license-only 2.1.1 update.

## Independent review

For 2.1.0, a separate read-only reviewer identified four Important runtime cases. Each was reproduced with a failing regression and fixed: unsuccessful tray shutdown stopping the UI pump, modifier-dependent key names preventing release, capture of a previously held key leaving routing state, and expired first-session selection. The physical-key fix also covers left/right Ctrl sharing a scan code. The full suite passes with these fixes.

For 2.1.1, a separate read-only policy-consistency review checked LICENSE, the licensing guide, README, contribution guidance and request form against the owner's requirements. Two wording issues were corrected: non-Company organizations remain eligible under the default grant, and redistribution safeguards also apply by default to separately permitted distributions. Contributor ownership is retained; no broader relicensing permission is silently taken. This is not a legal enforceability opinion.

## Packaging checks

The EXE and portable ZIP include the project license, licensing guide and unchanged third-party notices. Before publication, archive inspection confirmed byte-for-byte matches for LICENSE and LICENSING.md inside the 2.1.1 EXE and ZIP, all published asset checksums matched, and packaged diagnostics confirmed version 2.1.1 with a frozen runtime. Background startup, second-launch reopening and mixer/settings layout were checked for the 2.1.0 runtime using an isolated profile. Existing settings and earlier desktop versions are preserved.

## Verification limits

Physical knob compatibility and startup after a fresh Windows sign-in require a local trial. Device reconnection is covered with simulated failures, not physical unplugging. No hosted CI run was performed; a template is included under `docs/workflows/`. The executable is unsigned. The custom license has not been reviewed by legal counsel.
