# Contributing

Read [LICENSE](LICENSE) and [LICENSING.md](LICENSING.md) first. Individuals may modify and contribute in their own capacity under that license. Any Company or contributor acting on behalf of a Company needs prior written permission, regardless of Company size or whether copies will be sold. Contributions do not transfer your ownership; they are offered under the repository license unless a separate written agreement says otherwise. Discuss any separate commercial licensing needs with the owner before submitting material you cannot license accordingly.

Develop on Windows with Python 3.13. Follow the README setup and use `--data-dir .test-profile` for UI work.

Before opening a pull request:

1. Add a regression test for behavior changes.
2. Run `python -m unittest discover -s tests -v`.
3. Run `python tests/windows_audio_smoke.py` for audio changes on a machine with a working output device.
4. Run `./build.ps1` and verify the packaged EXE.
5. Check mixer/settings layouts, tray startup, shutdown and second-launch behavior.

Keep Tk operations on the main thread. COM audio objects belong to the audio worker; pass ordinary data between threads. Keyboard callbacks must enqueue actions and return promptly.

Do not commit personal settings, diagnostics, logs, credentials, local build artifacts or private paths. Sanitize screenshots and reports before including them in an issue. Use English for repository documentation and interface text.
