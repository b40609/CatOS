[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [switch]$CheckOnly,
    [ValidateRange(1, 120)][int]$TimeoutSeconds = 20
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$reactDir = [IO.Path]::GetFullPath((Join-Path $projectRoot 'frontend\cat-os-vite'))
$url = 'http://127.0.0.1:8890'
$ownedProcess = $null

function Get-FrontendIdentity {
    try {
        Invoke-RestMethod -Uri "$url/__catos/frontend" -TimeoutSec 2
    } catch { return $null }
}

function Test-Identity($identity) {
    return $identity -and $identity.contract -eq 'catos.frontend.v1' -and
        [string]::Equals($reactDir.TrimEnd('\'), [string]$identity.root.TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase)
}

function Test-PortOccupied {
    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Parse('127.0.0.1'), 8890)
    $listener.Server.ExclusiveAddressUse = $true
    try { $listener.Start(); return $false } catch { return $true } finally { $listener.Stop() }
}

try {
    $identity = Get-FrontendIdentity
    if (-not (Test-Identity $identity)) {
        if (Test-PortOccupied) { throw 'Port 8890 has an unknown owner or a different checkout. It was not stopped.' }
        if ($CheckOnly) { throw 'CatOS frontend is not running.' }
        $node = (Get-Command node.exe -ErrorAction Stop).Source
        $npm = (Get-Command npm.cmd -ErrorAction Stop).Source
        $viteCli = Join-Path $reactDir 'node_modules\vite\bin\vite.js'
        if (-not (Test-Path -LiteralPath $viteCli)) {
            Push-Location $reactDir
            try {
                & $npm ci
                if ($LASTEXITCODE -ne 0) { throw "npm ci failed: $LASTEXITCODE" }
            } finally { Pop-Location }
        }
        $logRoot = Join-Path $projectRoot 'outputs\dev-frontend'
        New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
        $stamp = [Guid]::NewGuid().ToString('N')
        $ownedProcess = Start-Process -FilePath $node -ArgumentList @("`"$viteCli`"") -WorkingDirectory $reactDir -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logRoot "$stamp.stdout.log") -RedirectStandardError (Join-Path $logRoot "$stamp.stderr.log")
        $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
        do {
            $identity = Get-FrontendIdentity
            if (Test-Identity $identity) { break }
            $ownedProcess.Refresh()
            if ($ownedProcess.HasExited) { throw "Vite exited: $($ownedProcess.ExitCode). See outputs/dev-frontend." }
            Start-Sleep -Milliseconds 250
        } while ([DateTime]::UtcNow -lt $deadline)
        if (-not (Test-Identity $identity)) { throw 'Frontend readiness timeout. Browser was not opened.' }
    }
    $page = Invoke-WebRequest -UseBasicParsing -Uri "$url/" -TimeoutSec 3
    if ($page.StatusCode -ne 200 -or $page.Content -notmatch 'id="root"') { throw 'Frontend HTML is not ready.' }
    Write-Host "CatOS frontend ready: $url/#/ | root=$reactDir"
    try {
        $backend = Invoke-RestMethod -Uri 'http://127.0.0.1:8770/api/research/version' -TimeoutSec 2
        if ($backend.mode -ne 'local_research_synthetic' -or
            -not [string]::Equals([string]$backend.workspace, $projectRoot, [StringComparison]::OrdinalIgnoreCase) -or
            $backend.restart_required) { throw 'Backend identity/source mismatch.' }
        Write-Host 'Research backend: ready (local synthetic research only).'
    } catch { Write-Warning 'Research backend: unavailable or identity/source mismatch; frontend readiness does not imply backend readiness.' }
    if (-not $NoBrowser -and -not $CheckOnly) { Start-Process "$url/#/" }
    exit 0
} catch {
    if ($ownedProcess) {
        $ownedProcess.Refresh()
        if (-not $ownedProcess.HasExited) { Stop-Process -Id $ownedProcess.Id -ErrorAction SilentlyContinue }
    }
    Write-Error $_ -ErrorAction Continue
    exit 1
}
