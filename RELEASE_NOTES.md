# Volumaty 2.1.0

Your keyboard knob. Your apps. Your sound.

Volumaty is a Windows per-app volume mixer with global keyboard shortcuts, a dark desktop interface and system-tray controls. This release improves audio reliability and adds portable settings backups.

## What's new

- Export/import from **Settings → Backup & restore**.
- Automatic pre-import backups, shortcut-conflict validation and protection against malformed files.
- Batched audio controls during fast knob turns.
- Healthy sessions remain controllable when another session disappears.
- Stale levels clear when the output device is unavailable; the worker retries automatically.
- Shortcut capture consumes held-key repeats until release and recognizes Windows media scan codes.

## Downloads

- **Volumaty.exe** — standalone Windows x64 application; Python is not required.
- **Volumaty-2.1.0-windows-x64.zip** — EXE, documentation and dependency license texts.
- **SHA256SUMS.txt** — SHA-256 hashes for release assets.

Place the EXE in a permanent folder. Enable **Run Volumaty at sign-in** in Settings for quiet startup. If you move the app, choose **Update startup path**.

Existing settings remain in `%APPDATA%\Volumaty`. This executable is unsigned. Knobs must emit standard Windows volume media keys. Audio control covers the current default output device.

See [CHANGELOG.md](https://github.com/NawafAlmohammadi/Volumaty/blob/main/CHANGELOG.md) and the verification report for coverage and limitations.
