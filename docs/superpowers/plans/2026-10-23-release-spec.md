# Volumaty 2.1 release scope

Publish the user's Windows per-app keyboard-knob mixer to their GitHub account with English interface, documentation and release notes. Retain the existing 2.0 desktop folder and user settings.

Improvements: batch queued audio commands to reduce repeated COM enumeration; isolate disappearing sessions and clear stale UI state when audio is unavailable; export/import validated settings with automatic rollback backup; prevent a captured key's auto-repeat from triggering its newly assigned action. Keep the dark UI, per-app slots, tray, startup registration and single-instance behavior.

Do not add online telemetry, automatic updates, administrator requirements, or unrelated game code. Do not publish local settings, diagnostics, logs, absolute user paths or synced project files. Build a single Windows EXE and publish a downloadable GitHub Release. Public repository name: Volumaty, unless an existing matching repository dictates otherwise.
