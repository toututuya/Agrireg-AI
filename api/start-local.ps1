$envFile = Join-Path $PSScriptRoot '.env.local'

if (-not (Test-Path -LiteralPath $envFile)) {
    throw 'Missing api/.env.local. Copy .env.example and fill in local values first.'
}

foreach ($line in Get-Content -LiteralPath $envFile) {
    $entry = $line.Trim()
    if (-not $entry -or $entry.StartsWith('#')) { continue }
    $parts = $entry.Split('=', 2)
    if ($parts.Count -eq 2) {
        Set-Item -Path ("Env:" + $parts[0].Trim()) -Value $parts[1].Trim()
    }
}

& mvn spring-boot:run
