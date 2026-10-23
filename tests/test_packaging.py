"""Release archives must carry the same licensing terms as the source."""
import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile


class PackagingLicenseTests(unittest.TestCase):
    def test_portable_archive_contains_project_license_and_guide(self):
        script = Path(__file__).resolve().parents[1] / 'scripts/package_release.py'
        spec = importlib.util.spec_from_file_location('volumaty_packaging', script)
        packaging = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(packaging)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'dist').mkdir()
            (root / 'dist/Volumaty.exe').write_bytes(b'test executable')
            names = ['README.md', 'CHANGELOG.md', 'THIRD_PARTY_NOTICES.md',
                     'RELEASE_NOTES.md', 'VERIFICATION.md', 'LICENSE', 'LICENSING.md']
            for name in names:
                (root / name).write_text('Contents of ' + name, encoding='utf-8')
            with patch.object(packaging, 'ROOT', root), contextlib.redirect_stdout(io.StringIO()):
                packaging.main()
            archive = root / f'dist/Volumaty-{packaging.__version__}-windows-x64.zip'
            with zipfile.ZipFile(archive) as output:
                self.assertIn('LICENSE', output.namelist())
                self.assertEqual(output.read('LICENSE').decode(), 'Contents of LICENSE')
                self.assertIn('LICENSING.md', output.namelist())


if __name__ == '__main__':
    unittest.main()
