@echo off
chcp 65001 >nul
echo =================================================
echo   正在啟動 catOS 筆電開發環境並開啟瀏覽器...
echo =================================================
setlocal
rem PowerShell 7 終端帶進來的 PSModulePath 會讓 Windows PowerShell 找不到內建指令，先清掉。
set "PSModulePath="
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-laptop-dev.ps1"
pause
