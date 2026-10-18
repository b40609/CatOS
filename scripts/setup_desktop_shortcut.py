import os
import subprocess
import base64

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
script_path = os.path.join(current_dir, "start-laptop-dev.ps1")

desktop = os.path.expanduser("~/Desktop")

# Remove any old/garbled files
for f in os.listdir(desktop):
    if f.startswith("CatOS") and (f.endswith(".bat") or f.endswith(".lnk")):
        try:
            os.remove(os.path.join(desktop, f))
        except Exception:
            pass

lnk_name = "CatOS \u7db2\u9801\u4e00\u9375\u555f\u52d5.lnk"  # CatOS 網頁一鍵啟動.lnk
lnk_path = os.path.join(desktop, lnk_name)

# PowerShell script to create .lnk with dynamic paths
ps_script = f"""
$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut('{lnk_path}')
$shortcut.TargetPath = 'powershell.exe'
$shortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Minimized -File "{script_path}"'
$shortcut.WorkingDirectory = '{project_root}'
$shortcut.Description = 'CatOS Web Dev Launcher'
$shortcut.IconLocation = 'shell32.dll,220'
$shortcut.Save()
"""

encoded_ps = base64.b64encode(ps_script.encode("utf-16le")).decode("ascii")
subprocess.run(["powershell", "-NoProfile", "-EncodedCommand", encoded_ps], check=True)
print(f"Successfully created: {lnk_path}")

# Also create a .bat file with dynamic script path
bat_name = "CatOS \u7db2\u9801\u4e00\u9375\u555f\u52d5.bat"
bat_path = os.path.join(desktop, bat_name)
bat_content = f"""@echo off
chcp 65001 >nul
echo 正在啟動 catOS 前端服務並開啟瀏覽器畫面...
powershell -NoProfile -ExecutionPolicy Bypass -File "{script_path}"
"""
with open(bat_path, "w", encoding="utf-8-sig") as f:
    f.write(bat_content)
print(f"Successfully created: {bat_path}")
