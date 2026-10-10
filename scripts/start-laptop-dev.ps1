# start-laptop-dev.ps1
# 自動檢查依賴、啟動 8890 (React) 與 8899 (Vue)，並自動在瀏覽器開啟指定分頁：
# 1. http://127.0.0.1:8899/#/
# 2. http://127.0.0.1:8890/#/review

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "   catOS 筆電一鍵自動啟動與雙端頁面開啟腳本" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

# 0. 檢查並安裝 node_modules (若為全新 clone)
$reactDir = Join-Path $projectRoot "frontend\cat-os-vite"
$vueDir = Join-Path $projectRoot "frontend\redesign-v2-return"

if (-not (Test-Path (Join-Path $reactDir "node_modules"))) {
    Write-Host "[0/4] 偵測到 React 前端未安裝依賴，正在執行 npm install..." -ForegroundColor Yellow
    Start-Process -FilePath "npm.cmd" -ArgumentList "install" -WorkingDirectory $reactDir -Wait -NoNewWindow
}

if (-not (Test-Path (Join-Path $vueDir "node_modules"))) {
    Write-Host "[0/4] 偵測到 Vue 前端未安裝依賴，正在執行 npm install..." -ForegroundColor Yellow
    Start-Process -FilePath "npm.cmd" -ArgumentList "install" -WorkingDirectory $vueDir -Wait -NoNewWindow
}

# 1. 檢查並啟動 8890 (React / cat-os-vite)
$port8890 = Get-NetTCPConnection -LocalPort 8890 -ErrorAction SilentlyContinue
if (-not $port8890) {
    Write-Host "[1/4] 啟動 8890 React 前端服務..." -ForegroundColor Yellow
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", "cd '$reactDir'; npm run dev -- --port 8890 --host 127.0.0.1" -WindowStyle Minimized
} else {
    Write-Host "[1/4] 8890 服務已在運行中。" -ForegroundColor Green
}

# 2. 檢查並啟動 8899 (Vue / redesign-v2-return)
$port8899 = Get-NetTCPConnection -LocalPort 8899 -ErrorAction SilentlyContinue
if (-not $port8899) {
    Write-Host "[2/4] 啟動 8899 Vue 前端服務..." -ForegroundColor Yellow
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", "cd '$vueDir'; npm run dev -- --port 8899 --host 127.0.0.1" -WindowStyle Minimized
} else {
    Write-Host "[2/4] 8899 服務已在運行中。" -ForegroundColor Green
}

# 3. 等候服務連線就緒 (最多等待 15 秒)
Write-Host "[3/4] 等候 8890 與 8899 服務就緒..." -ForegroundColor Cyan
$timeout = 15
$ready8890 = $false
$ready8899 = $false

for ($i = 0; $i -lt $timeout; $i++) {
    if (-not $ready8890) {
        $conn8890 = Get-NetTCPConnection -LocalPort 8890 -ErrorAction SilentlyContinue
        if ($conn8890) { $ready8890 = $true }
    }
    if (-not $ready8899) {
        $conn8899 = Get-NetTCPConnection -LocalPort 8899 -ErrorAction SilentlyContinue
        if ($conn8899) { $ready8899 = $true }
    }
    if ($ready8890 -and $ready8899) {
        break
    }
    Start-Sleep -Seconds 1
}

# 4. 自動在預設瀏覽器開啟兩個指定網址
Write-Host "[4/4] 自動開啟瀏覽器分頁：" -ForegroundColor Cyan
Write-Host "  -> http://127.0.0.1:8899/#/" -ForegroundColor White
Write-Host "  -> http://127.0.0.1:8890/#/review" -ForegroundColor White

Start-Process "http://127.0.0.1:8899/#/"
Start-Process "http://127.0.0.1:8890/#/review"

Write-Host "`n✓ 服務已成功啟動並自動開啟瀏覽器分頁！" -ForegroundColor Green
