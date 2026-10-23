# Changelog

## 2.1.1 — 2026-10-23

- Added the custom Volumaty Community License 1.0 and an English licensing guide.
- Company use/development, regardless of Company size, requires prior written permission; selling original or modified software or charging for access also requires permission.
- Added a licensing-request issue form and clarified the third-party license boundary.
- Bundled the project license in both the EXE and portable ZIP, with an archive regression check.
- No audio, keyboard, startup or settings behavior changed from 2.1.0.

## 2.1.0 — 2026-10-23

### Added

- Export and import app cards, shortcuts and preferences from Settings.
- Validation of imported formats, process names, preferences and shortcut conflicts.
- Automatic pre-import backups and preservation of current settings on save failure.
- English documentation, issue templates, build automation and downloadable release assets.

### Improved

- Process queued audio controls in batches with one session enumeration per batch.
- Keep healthy sessions working when another session expires.
- Clear stale card levels and retry with a delay when the output device becomes unavailable.
- Suppress auto-repeat of a captured key until it is released.
- Recognize Windows media scan codes consistently during capture and routing.

## 2.0.0 — 2026-10-09

- Rebuilt the original single-file application into focused audio, keyboard, Windows, persistence and UI modules.
- Added the dark mixer, sliders, live status, automatic saving, tray controls and single-instance behavior.
- Fixed source startup commands to include the Python interpreter and support quiet startup.
