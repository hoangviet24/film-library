<#
.SYNOPSIS
    Builds Fluent Media Player standalone distribution and Inno Setup Windows installer.
#>
$ErrorActionPreference = "Stop"
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "Building Fluent Media Player (PyInstaller + Inno Setup)" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan

python build_release.py $args
if ($LASTEXITCODE -ne 0) {
    Write-Error "Build failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}
Write-Host "[SUCCESS] Build completed successfully." -ForegroundColor Green
