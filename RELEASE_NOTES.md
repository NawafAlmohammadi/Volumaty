# Volumaty 2.1.1

Your keyboard knob. Your apps. Your sound.

Volumaty is a Windows per-app volume mixer with global keyboard shortcuts, a dark desktop interface and system-tray controls. This release adds explicit project licensing and embeds the license in the downloadable packages. Runtime behavior is unchanged from 2.1.0.

## What's new

- Added the **Volumaty Community License 1.0**, a custom source-available license.
- Use, modification and free sharing are permitted for eligible non-Company users under LICENSE.
- **Every Company requires prior written permission for use or development, regardless of size, including internal use.**
- **Selling the original or a modified version, paid access, paid services and inclusion in a paid product require prior written permission for everyone.**
- Added [a licensing-request form](https://github.com/NawafAlmohammadi/Volumaty/issues/new?template=licensing_request.yml). Opening a request is not permission; approval must be explicit and written.
- Included LICENSE and LICENSING.md in the portable ZIP and embedded them in the EXE. Third-party components retain their own terms.

## Downloads

- **Volumaty.exe** — standalone Windows x64 application; Python is not required.
- **Volumaty-2.1.1-windows-x64.zip** — EXE, project license, documentation and dependency license texts.
- **SHA256SUMS.txt** — SHA-256 hashes for release assets.

Place the EXE in a permanent folder. Enable **Run Volumaty at sign-in** in Settings for quiet startup. If you move the app, choose **Update startup path**.

Existing settings remain in `%APPDATA%\Volumaty`. This executable is unsigned. Knobs must emit standard Windows volume media keys. Audio control covers the current default output device.

See [CHANGELOG.md](https://github.com/NawafAlmohammadi/Volumaty/blob/main/CHANGELOG.md) and the verification report for coverage and limitations.
