[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [switch]$Rebuild,
    [ValidateRange(5, 300)][int]$TimeoutSeconds = 40
)

# One command for the whole app: create the virtual environment, install the pinned
# requirements, build the React UI when it is missing or stale, then run CatOS on
# http://127.0.0.1:8770/ in this window. Ctrl+C stops it.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$ui = Join-Path $root 'frontend\cat-os-vite'
$url = 'http://127.0.0.1:8770'
$server = $null

function Get-Json($path) {
    try { Invoke-RestMethod -Uri "$url$path" -TimeoutSec 2 } catch { $null }
}

function Test-PortOccupied {
    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Parse('127.0.0.1'), 8770)
    $listener.Server.ExclusiveAddressUse = $true
    try { $listener.Start(); return $false } catch { return $true } finally { $listener.Stop() }
}

function Find-Python {
    foreach ($candidate in @(@('py', '-3'), @('python'), @('python3'))) {
        if (-not (Get-Command $candidate[0] -ErrorAction SilentlyContinue)) { continue }
        $rest = @($candidate | Select-Object -Skip 1)
        try {
            $found = & $candidate[0] @rest -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        } catch { continue }
        if ($LASTEXITCODE -eq 0 -and $found -and [version]$found -ge [version]'3.11') { return , $candidate }
    }
    throw 'Python 3.11 or newer was not found. Install it from https://www.python.org/downloads/ and run this again.'
}

try {
    # 1. Python environment
    $venvPython = Join-Path $root '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $venvPython)) {
        $python = Find-Python
        $rest = @($python | Select-Object -Skip 1)
        Write-Host 'Creating .venv ...'
        & $python[0] @rest -m venv (Join-Path $root '.venv')
        if ($LASTEXITCODE -ne 0) { throw "python -m venv failed: $LASTEXITCODE" }
    }
    $stamp = Join-Path $root '.venv\.catos-requirements'
    $wanted = ((Get-FileHash (Join-Path $root 'requirements-http.txt')).Hash +
        (Get-FileHash (Join-Path $root 'requirements-research.txt')).Hash)
    if (-not (Test-Path -LiteralPath $stamp) -or (Get-Content -LiteralPath $stamp -Raw).Trim() -ne $wanted) {
        Write-Host 'Installing Python requirements ...'
        & $venvPython -m pip install --disable-pip-version-check -q -r (Join-Path $root 'requirements-http.txt')
        if ($LASTEXITCODE -ne 0) { throw "pip install failed: $LASTEXITCODE" }
        Set-Content -LiteralPath $stamp -Value $wanted -Encoding ascii
    }

    # 2. React UI: build when missing, or when a source file is newer than the build
    $index = Join-Path $ui 'dist\index.html'
    $needsBuild = $Rebuild -or -not (Test-Path -LiteralPath $index)
    if (-not $needsBuild) {
        $built = (Get-Item -LiteralPath $index).LastWriteTimeUtc
        $sources = @(Get-ChildItem -LiteralPath (Join-Path $ui 'src') -Recurse -File)
        foreach ($name in 'index.html', 'package.json', 'package-lock.json', 'vite.config.ts') {
            $sources += Get-Item -LiteralPath (Join-Path $ui $name)
        }
        $needsBuild = [bool]($sources | Where-Object { $_.LastWriteTimeUtc -gt $built } | Select-Object -First 1)
    }
    if ($needsBuild) {
        if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
            throw 'The UI is not built yet and Node.js (npm) was not found. Install Node.js 18 or newer from https://nodejs.org/ and run this again.'
        }
        Push-Location -LiteralPath $ui
        try {
            if (-not (Test-Path -LiteralPath 'node_modules')) {
                Write-Host 'Installing UI packages (npm ci) ...'
                & npm.cmd ci
                if ($LASTEXITCODE -ne 0) { throw "npm ci failed: $LASTEXITCODE" }
            }
            Write-Host 'Building the UI ...'
            & npm.cmd run build
            if ($LASTEXITCODE -ne 0) { throw "npm run build failed: $LASTEXITCODE" }
        } finally { Pop-Location }
    }

    # 3. Server: reuse a CatOS from this checkout, never stop an unknown port owner
    $running = Get-Json '/api/research/version'
    if ($running) {
        if (-not [string]::Equals([string]$running.workspace, $root, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Port 8770 is serving another CatOS checkout ($($running.workspace)). It was not stopped."
        }
        Write-Host "CatOS is already running: $url/"
        if ($running.restart_required) { Write-Warning 'Its source changed since it started; stop it and run this again to load the update.' }
        if (-not $NoBrowser) { Start-Process "$url/" }
        exit 0
    }
    if (Test-PortOccupied) { throw 'Port 8770 is in use by another program. It was not stopped.' }

    $server = Start-Process -FilePath $venvPython -ArgumentList @('-B', '-m', 'catos.workspace_api') `
        -WorkingDirectory $root -NoNewWindow -PassThru
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $ready = $null
    do {
        $server.Refresh()
        if ($server.HasExited) { throw "CatOS exited during startup: $($server.ExitCode)" }
        $ready = Get-Json '/api/workspace/version'
        if ($ready) { break }
        Start-Sleep -Milliseconds 300
    } while ([DateTime]::UtcNow -lt $deadline)
    if (-not $ready) { throw 'CatOS did not become ready in time.' }
    Write-Host "CatOS ready: $url/   (Ctrl+C to stop)"
    if (-not $NoBrowser) { Start-Process "$url/" }
    $server.WaitForExit()
    exit $server.ExitCode
} catch {
    Write-Error $_ -ErrorAction Continue
    exit 1
} finally {
    if ($server) {
        $server.Refresh()
        if (-not $server.HasExited) { Stop-Process -Id $server.Id -ErrorAction SilentlyContinue }
    }
}
