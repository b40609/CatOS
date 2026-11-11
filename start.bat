@echo off
rem CatOS: set up on first run, then open http://127.0.0.1:8770/
setlocal
rem When started from a PowerShell 7 terminal, the inherited PSModulePath makes Windows
rem PowerShell load incompatible modules (built-in cmdlets go missing). Clear it here.
set "PSModulePath="
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1" %*
if errorlevel 1 pause
