$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
    python -m PyInstaller --noconfirm --clean Volumaty.spec
    if ($LASTEXITCODE -ne 0) { throw 'EXE build failed.' }
    python scripts\package_release.py
    if ($LASTEXITCODE -ne 0) { throw 'Release packaging failed.' }
    Write-Host 'Ready: EXE, portable ZIP and SHA256SUMS.txt in dist\'
} finally {
    Pop-Location
}
