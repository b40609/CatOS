# start-laptop-dev.ps1
# 自動檢查依賴、啟動 8890 React 前端 (cat-os-vite)，並自動在瀏覽器開啟：
# http://127.0.0.1:8890/#/ (CatOS 唯一正式前端)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $scriptDir) {
    $scriptDir = Join-Path (Get-Location) "scripts"
}
$projectRoot = Split-Path -Parent $scriptDir

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "   CatOS 筆電一鍵自動啟動前端 (8890 React)" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

$reactDir = Join-Path $projectRoot "frontend\cat-os-vite"

# 0. 檢查並安裝 node_modules (若為全新環境)
if (-not (Test-Path (Join-Path $reactDir "node_modules"))) {
    Write-Host "[1/3] 偵測到 React 前端未安裝依賴，正在執行 npm install..." -ForegroundColor Yellow
    Start-Process -FilePath "npm.cmd" -ArgumentList "install" -WorkingDirectory $reactDir -Wait -NoNewWindow
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
if (-not $port8890) {
    Write-Host "[2/3] 啟動 8890 React 前端服務..." -ForegroundColor Yellow
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", "npm.cmd run dev" -WorkingDirectory $reactDir -WindowStyle Minimized
} else {
    Write-Host "[2/3] 8890 服務已在運行中。" -ForegroundColor Green
}

# 2. 等候服務連線就緒 (最多等待 15 秒)
Write-Host "[3/3] 檢查 8890 服務連線..." -ForegroundColor Cyan
$timeout = 15
$ready8890 = Test-PortOpen 8890

for ($i = 0; $i -lt $timeout; $i++) {
    if (-not $ready8890) {
        $ready8890 = Test-PortOpen 8890
    }
    if ($ready8890) {
        break
    }
    Start-Sleep -Seconds 1
}

# 3. 自動在預設瀏覽器開啟唯一正式前端
Write-Host "`n開啟 CatOS 前端網址：" -ForegroundColor Cyan
Write-Host "  -> http://127.0.0.1:8890/#/ (React 主儀表盤)" -ForegroundColor White

Start-Process "http://127.0.0.1:8890/#/"

Write-Host "`n✓ 8890 服務就緒並已開啟瀏覽器！" -ForegroundColor Green
