Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead('frontend/catos-frontend-redesign-v1.zip')
$entries = $zip.Entries | Select-Object -ExpandProperty FullName
$bad = $entries | Where-Object { $_ -match 'node_modules|\.git|\.env|\.db|\.sqlite|\.key|\.pem' }
Write-Host "Total entries in zip: $($entries.Count)"
Write-Host "Bad/Sensitive entries in zip: $($bad.Count)"
if ($bad.Count -gt 0) {
    Write-Host "Found bad entries:"
    $bad | ForEach-Object { Write-Host " - $_" }
} else {
    Write-Host "Verification PASSED: Zip is clean of node_modules, git, DB, env and keys."
}
$zip.Dispose()
