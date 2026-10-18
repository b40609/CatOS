# start-laptop-dev.ps1
# 自動檢查依賴、啟動 8890 (React) 與 8899 (Vue)，並自動在瀏覽器開啟指定分頁：
# 1. http://127.0.0.1:8890/#/ (React 主儀表盤)
# 2. http://127.0.0.1:8899/#/ (Vue 3 對照)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $scriptDir) {
    $scriptDir = Join-Path (Get-Location) "scripts"
}
$projectRoot = Split-Path -Parent $scriptDir

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "   catOS 筆電一鍵自動啟動與多端頁面開啟腳本" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

$reactDir = Join-Path $projectRoot "frontend\cat-os-vite"
$vueDir = Join-Path $projectRoot "frontend\redesign-v2-return"

# 0. 檢查並安裝 node_modules (若為全新環境)
if (-not (Test-Path (Join-Path $reactDir "node_modules"))) {
    Write-Host "[0/4] 偵測到 React 前端未安裝依賴，正在執行 npm install..." -ForegroundColor Yellow
    Start-Process -FilePath "npm.cmd" -ArgumentList "install" -WorkingDirectory $reactDir -Wait -NoNewWindow
}

if (-not (Test-Path (Join-Path $vueDir "node_modules"))) {
    Write-Host "[0/4] 偵測到 Vue 前端未安裝依賴，正在執行 npm install..." -ForegroundColor Yellow
    Start-Process -FilePath "npm.cmd" -ArgumentList "install" -WorkingDirectory $vueDir -Wait -NoNewWindow
}

function Test-PortOpen ($port) {
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $iar = $tcp.BeginConnect("127.0.0.1", $port, $null, $null)
        $wait = $iar.AsyncWaitHandle.WaitOne(400, $false)
        if ($wait -and $tcp.Connected) {
            $tcp.EndConnect($iar)
            $tcp.Close()
            return $true
        }
        $tcp.Close()
        return $false
    } catch {
        return $false
    }
}

# 1. 檢查並啟動 8890 (React / cat-os-vite)
$port8890 = Test-PortOpen 8890
$started8890 = $false
if (-not $port8890) {
    Write-Host "[1/4] 啟動 8890 React 前端服務..." -ForegroundColor Yellow
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", "npm.cmd run dev" -WorkingDirectory $reactDir -WindowStyle Minimized
    $started8890 = $true
} else {
    Write-Host "[1/4] 8890 服務已在運行中。" -ForegroundColor Green
}

# 2. 檢查並啟動 8899 (Vue / redesign-v2-return)
$port8899 = Test-PortOpen 8899
$started8899 = $false
if (-not $port8899) {
    Write-Host "[2/4] 啟動 8899 Vue 前端服務..." -ForegroundColor Yellow
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", "npm.cmd run dev" -WorkingDirectory $vueDir -WindowStyle Minimized
    $started8899 = $true
} else {
    Write-Host "[2/4] 8899 服務已在運行中。" -ForegroundColor Green
}

# 3. 等候服務連線就緒 (若剛啟動，最多等待 15 秒)
Write-Host "[3/4] 檢查 8890 與 8899 服務連線..." -ForegroundColor Cyan
$timeout = 15
$ready8890 = Test-PortOpen 8890
$ready8899 = Test-PortOpen 8899

for ($i = 0; $i -lt $timeout; $i++) {
    if (-not $ready8890) {
        $ready8890 = Test-PortOpen 8890
    }
    if (-not $ready8899) {
        $ready8899 = Test-PortOpen 8899
    }
    if ($ready8890 -and $ready8899) {
        break
    }
    Start-Sleep -Seconds 1
}

# 4. 自動在預設瀏覽器開啟指定網址
Write-Host "[4/4] 開啟瀏覽器對照分頁：" -ForegroundColor Cyan
Write-Host "  -> http://127.0.0.1:8890/#/ (React 主儀表盤)" -ForegroundColor White
Write-Host "  -> http://127.0.0.1:8899/#/ (Vue 3 對照)" -ForegroundColor White

Start-Process "http://127.0.0.1:8890/#/"
Start-Process "http://127.0.0.1:8899/#/"

Write-Host "`n✓ 服務就緒並已開啟瀏覽器分頁！" -ForegroundColor Green
