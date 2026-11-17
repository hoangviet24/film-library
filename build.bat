@echo off
setlocal
echo =======================================================
echo Building Fluent Media Player (PyInstaller + Inno Setup)
echo =======================================================
python build_release.py %*
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Build failed with exit code %ERRORLEVEL%
    exit /b %ERRORLEVEL%
)
echo [SUCCESS] Build completed successfully.
exit /b 0
