@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0backup-published-cloud-forecast.ps1"
if errorlevel 1 (
  echo.
  echo Backup failed. Read the error above.
  pause
)
