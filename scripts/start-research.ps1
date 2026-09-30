$ErrorActionPreference = 'Stop'
$researchRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $researchRoot
try {
    python -B -m catos.workspace_api
    $researchExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $researchExitCode
