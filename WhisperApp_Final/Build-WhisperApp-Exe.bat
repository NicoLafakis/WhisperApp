@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Build-WhisperApp-Exe.ps1"
if errorlevel 1 (
  echo.
  echo Build failed. See build.log in this folder.
  pause
)
