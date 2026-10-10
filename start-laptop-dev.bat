@echo off
chcp 65001 >nul
echo =================================================
echo   正在啟動 catOS 筆電開發環境並開啟瀏覽器...
echo =================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-laptop-dev.ps1"
pause
