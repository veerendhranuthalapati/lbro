# LBRO — Push to GitHub
# Run this once from the lbro folder to wipe the remote and push all new code.
# Right-click → "Run with PowerShell"

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$REPO_URL = "https://github.com/veerendhranuthalapati/lbro.git"
$BRANCH   = "main"

Write-Host ""
Write-Host "=== LBRO GitHub Push ===" -ForegroundColor Cyan
Write-Host "Remote : $REPO_URL"
Write-Host "Branch : $BRANCH"
Write-Host ""

# Move into the script's own directory (works when launched via right-click)
Set-Location $PSScriptRoot

# ── 1. Initialize git if needed ────────────────────────────────────────────────
if (-not (Test-Path ".git")) {
    Write-Host "[1/6] git init..." -ForegroundColor Yellow
    git init -b $BRANCH
} else {
    Write-Host "[1/6] Git already initialized, skipping init." -ForegroundColor Green
}

# ── 2. Configure remote ────────────────────────────────────────────────────────
Write-Host "[2/6] Setting remote 'origin'..." -ForegroundColor Yellow
$remotes = git remote 2>$null
if ($remotes -contains "origin") {
    git remote set-url origin $REPO_URL
} else {
    git remote add origin $REPO_URL
}

# ── 3. Stage everything ────────────────────────────────────────────────────────
Write-Host "[3/6] Staging all files..." -ForegroundColor Yellow
git add -A

# ── 4. Commit ─────────────────────────────────────────────────────────────────
Write-Host "[4/6] Creating commit..." -ForegroundColor Yellow
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm"
git commit -m "feat: complete LBRO monorepo v2 — $timestamp" --allow-empty

# ── 5. Force-push (replaces old repo content) ─────────────────────────────────
Write-Host "[5/6] Force-pushing to $BRANCH..." -ForegroundColor Yellow
Write-Host "      (GitHub may prompt for your username/token)" -ForegroundColor DarkGray
git push --force origin $BRANCH

# ── 6. Done ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[6/6] Done!" -ForegroundColor Green
Write-Host "      https://github.com/veerendhranuthalapati/lbro" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press any key to close..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
