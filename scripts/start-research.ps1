$ErrorActionPreference = 'Stop'
$researchRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $researchRoot
try {
    python -B -m catos.research_api --port 8770
    $researchExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $researchExitCode
