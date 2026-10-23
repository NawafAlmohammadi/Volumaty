# Reproducible Windows single-file build, no administrator manifest.
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = Path(SPECPATH)
datas = collect_data_files('customtkinter') + [(str(root / 'assets' / 'icon.ico'), 'assets')]
datas += [(str(root / 'licenses'), 'licenses'), (str(root / 'THIRD_PARTY_NOTICES.md'), '.')]
hidden = collect_submodules('pycaw') + ['pystray._win32', 'win32timezone', 'win32com.client', 'pythoncom']
a = Analysis([str(root / 'volumaty.py')], pathex=[str(root)], binaries=[], datas=datas,
             hiddenimports=hidden, hookspath=[], hooksconfig={}, runtime_hooks=[],
             excludes=['matplotlib', 'numpy', 'pandas', 'scipy', 'IPython', 'pytest'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='Volumaty', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          disable_windowed_traceback=False, icon=str(root / 'assets' / 'icon.ico'))
