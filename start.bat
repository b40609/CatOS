@echo off
rem CatOS: set up on first run, then open http://127.0.0.1:8770/
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1" %*
if errorlevel 1 pause
