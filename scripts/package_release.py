"""Package only publishable files and dependency notices, never local data."""
import hashlib
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from volumaty_app import __version__


def main():
    destination = ROOT / 'dist'
    executable = destination / 'Volumaty.exe'
    if not executable.is_file():
        raise SystemExit('Build dist/Volumaty.exe before packaging a release.')
    archive = destination / f'Volumaty-{__version__}-windows-x64.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as output:
        output.write(executable, executable.name)
        for name in ('README.md', 'CHANGELOG.md', 'THIRD_PARTY_NOTICES.md', 'RELEASE_NOTES.md', 'VERIFICATION.md', 'LICENSE', 'LICENSING.md'):
            output.write(ROOT / name, name)
        for directory in ('licenses', 'docs/images'):
            for path in sorted((ROOT / directory).rglob('*')):
                if path.is_file():
                    output.write(path, path.relative_to(ROOT).as_posix())
    lines = [hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + path.name
             for path in (executable, archive)]
    (destination / 'SHA256SUMS.txt').write_text('\n'.join(lines) + '\n', encoding='ascii')
    for path in (archive, destination / 'SHA256SUMS.txt'):
        print(f'Packaged {path.name}')


if __name__ == '__main__':
    main()
