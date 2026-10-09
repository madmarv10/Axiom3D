# Runs the headless Blender smoke test. Exit 0 = headless Blender works.
# Finds Blender via $env:BLENDER_PATH, then default install locations.

$ErrorActionPreference = "Stop"

$blender = $env:BLENDER_PATH
if (-not $blender) {
    $candidates = Get-ChildItem "C:\Program Files\Blender Foundation\Blender *\blender.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending
    if ($candidates) { $blender = $candidates[0].FullName }
}
if (-not $blender -or -not (Test-Path $blender)) {
    Write-Error "Blender not found. Set BLENDER_PATH to blender.exe."
    exit 1
}

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$smoke = Join-Path $repoRoot "blender\tests\smoke.py"

Write-Host "Using: $blender"
& $blender --background --factory-startup --python $smoke
exit $LASTEXITCODE