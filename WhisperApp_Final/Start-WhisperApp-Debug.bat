@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-WhisperApp.ps1"
if errorlevel 1 (
  echo.
  echo WhisperApp launcher failed. See startup.log in this folder.
  pause
)
