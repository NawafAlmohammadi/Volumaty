# Volumaty 2.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a tested, improved Volumaty release with English documentation and a downloadable Windows EXE.

**Architecture:** Continue with a Tk main thread, queued global keyboard callbacks and one COM audio worker. Add validated settings transfer in the persistence layer and batch audio work in the existing worker; keep Windows integration isolated.

**Tech Stack:** Python 3.13, CustomTkinter, pycaw, keyboard, pystray, PyInstaller, unittest, GitHub CLI.

**Spec:** docs/superpowers/plans/2026-10-23-release-spec.md

## Global Constraints

- English interface, documentation and release notes.
- Preserve the existing 2.0 desktop folder and user settings.
- No telemetry, automatic updates, administrator requirement or unrelated game code.
- Never publish local settings, diagnostics, logs or absolute user paths.
- Target Windows 10/11 x64; deliver a single EXE.

## Review Focus

- Broken audio sessions must not stop healthy sessions or leave stale card levels.
- Fast knob turns must preserve tick ordering without per-tick enumeration.
- Imports must reject unsupported schemas, malformed slots and duplicate shortcuts before changing settings.
- Failed settings import/save must preserve current data and the pre-import backup.
- A captured key held down must stay consumed until release, including media-key scan-code aliases.

### Task 1: Audio and capture reliability

**Files:** Modify `volumaty_app/audio.py`, `volumaty_app/keyboard_service.py`; create `tests/test_release.py`.
**Interfaces:** AudioWorker continues consuming `(app, all_sessions, action, value)` commands and emitting `('audio', snapshot)`; add `_process_batch(commands)` and `build_snapshot(grouped)` for deterministic tests. KeyboardService keeps its public interface.

- [ ] Write failing tests for healthy sessions surviving stale ones, one enumeration per batch, ordered tick processing, and capture repeat suppression.
- [ ] Run `python -m unittest discover -s tests -v`; verify failures describe the missing behavior.
- [ ] Implement minimal session isolation, batching and capture release tracking; publish an empty snapshot when device enumeration fails.
- [ ] Run the full suite and the silent audio integration check.
- [ ] Commit the independently tested change.

### Task 2: Validated settings transfer

**Files:** Modify `volumaty_app/config.py`, `volumaty_app/ui.py`; extend `tests/test_release.py`.
**Interfaces:** `ConfigStore.export_settings(settings, destination)` writes portable JSON atomically; `ConfigStore.import_settings(source)` validates, backs up current persisted settings, saves and returns Settings. The UI replaces settings only after import succeeds.

- [ ] Write failing roundtrip, invalid-schema, duplicate-shortcut, oversized-file and failed-save tests.
- [ ] Run the tests and confirm expected failures.
- [ ] Implement strict import validation and atomic export; add English Import/Export controls and update the live hook after successful import.
- [ ] Run the suite and visually check both pages and transfer controls in an isolated profile.
- [ ] Commit the change.

### Task 3: Publishable release

**Files:** Update version, README, workflow and build script; add changelog, release notes, verification report, attribution and issue templates.

- [ ] Prepare English repository materials and GitHub Actions build plus tag-release job.
- [ ] Build EXE; run packaged diagnostics, quiet start, second-launch and UI checks.
- [ ] Run the final full tests and obtain read-only review from a fresh reviewer; address consequential findings with regression tests.
- [ ] Inspect tracked files for local data and validate archive contents.
- [ ] Publish repository and v2.1.0 release after authenticated GitHub access is available; verify source and downloadable assets.

## Progress

- Baseline: 20 tests passed on 2026-10-23. Isolated release checkout imported from 2.0; old desktop copy is unchanged.
- Authorization: user explicitly requested development and GitHub publication. Continue inline; no additional plan approval is needed. Requesting-code-review supplies the final review subagent requirement.
- Task 1 complete: all 26 baseline/reliability tests and six live silent-audio checks passed before settings transfer implementation.
- Task 2 complete: 33 tests passed after settings transfer; implementation committed at 687ae1d.
- Final independent review found four Important runtime issues: failed tray-save shutdown, name-changing physical key releases, capture of an already-held key, and stale first session in single-session mode. Each was reproduced by a failing regression, fixed in 14b1423, and verified in the green 38-test suite. The same physical-key identity fix also corrects the left/right Ctrl case reported as Minor.
- Review boundaries: packaging/publication are verified by the implementer; physical keyboard compatibility and next-sign-in startup remain local-user trials. Source tests simulate device disconnection; live audio checks use a test-owned silent session.
- Publication: the user explicitly approved a public repository. Publish source and the locally verified EXE using the existing GitHub authorization. Keep the hosted build/release workflow as an inactive template under docs/workflows because the additional workflow authorization is not complete.
