# LBRO compose smoke — evidence log (session 3)
$ErrorActionPreference = "Continue"
$log = Join-Path $PSScriptRoot "..\lbro-run-scratch\compose_smoke_full.txt"
function Log($msg) { "$(Get-Date -Format o) $msg" | Tee-Object -FilePath $log -Append }

Log "=== compose smoke start ==="
$ready = curl.exe -s -o NUL -w "%{http_code}" http://localhost:8000/health/ready
Log "health/ready HTTP $ready"
$ui = curl.exe -s -o NUL -w "%{http_code}" http://localhost:3000/
Log "ui HTTP $ui"

$loginJson = Join-Path $env:TEMP "lbro-login.json"
'{"email":"admin@lbro.local","password":"Admin123!"}' | Set-Content -Path $loginJson -Encoding utf8 -NoNewline
$login = curl.exe -s -w "`nHTTP:%{http_code}" -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" --data-binary "@$loginJson"
Log "admin login tail: $($login.Substring([Math]::Max(0,$login.Length-80)))"

Log "=== partial smoke (full lifecycle TODO in RUNBOOK) ==="
