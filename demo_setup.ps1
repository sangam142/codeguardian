# Laptop bootstrap for the CodeGuardian demo.
#
#     .\demo_setup.ps1                 # check + install + seed
#     .\demo_setup.ps1 -Token ghp_xxx  # also write .env
#
# Run from the project root. Idempotent: safe to run repeatedly.

param(
    [string]$Token = "",
    [string]$Secret = "demo-secret-2026"
)

$ErrorActionPreference = "Continue"
Write-Host "`n=== CodeGuardian demo setup ===`n" -ForegroundColor Cyan

# --- 1. prerequisites -------------------------------------------------------
$py = (python --version 2>&1)
Write-Host "python : $py"
if ($py -notmatch "3\.(1[0-9]|[2-9][0-9])") {
    Write-Host "  ! needs Python 3.10+ (the code uses `X | Y` union syntax)" -ForegroundColor Red
}
foreach ($c in @("node", "git", "gh")) {
    $p = Get-Command $c -ErrorAction SilentlyContinue
    if ($p) { Write-Host "$c".PadRight(7) ": $($p.Source)" }
    else { Write-Host "$c".PadRight(7) ": NOT FOUND" -ForegroundColor Yellow }
}

# --- 2. dependencies --------------------------------------------------------
Write-Host "`n-- installing dependencies (slow on a fresh machine) --" -ForegroundColor Cyan
pip install -r requirements.txt

# --- 3. .env ----------------------------------------------------------------
Write-Host "`n-- .env --" -ForegroundColor Cyan
if (-not (Test-Path .env)) { Copy-Item .env.example .env; Write-Host "created .env from .env.example" }
if ($Token) {
    $lines = Get-Content .env
    $seenSecret = $false; $seenToken = $false
    $out = $lines | ForEach-Object {
        if ($_ -match '^GITHUB_WEBHOOK_SECRET=') { $script:seenSecret = $true; "GITHUB_WEBHOOK_SECRET=$Secret" }
        elseif ($_ -match '^GITHUB_TOKEN=') { $script:seenToken = $true; "GITHUB_TOKEN=$Token" }
        else { $_ }
    }
    if (-not $seenSecret) { $out += "GITHUB_WEBHOOK_SECRET=$Secret" }
    if (-not $seenToken) { $out += "GITHUB_TOKEN=$Token" }
    [System.IO.File]::WriteAllLines((Resolve-Path .env), $out)
    Write-Host "wrote GITHUB_WEBHOOK_SECRET and GITHUB_TOKEN"
} else {
    Write-Host "no -Token given; set GITHUB_WEBHOOK_SECRET / GITHUB_TOKEN by hand for the live-PR demo"
}

# --- 4. verify --------------------------------------------------------------
Write-Host "`n-- tests --" -ForegroundColor Cyan
python -m pytest -q

Write-Host "`n-- config (booleans only, never values) --" -ForegroundColor Cyan
python -c "from app.config import settings; print('  secret set:', bool(settings.github_webhook_secret)); print('  token set :', bool(settings.github_token)); print('  llm       :', settings.llm_enabled); print('  rag off   :', settings.rag_disabled)"

Write-Host "`n-- pipeline smoke test --" -ForegroundColor Cyan
python -m app.harness sample_good_code --no-history | Select-Object -First 3
python -m app.harness sample_vulnerable_code --no-history | Select-Object -First 3

# --- 5. seed the dashboard --------------------------------------------------
# data/ is gitignored, so a fresh clone has an empty dashboard. Seed it unless
# history.db was copied over from another machine.
Write-Host "`n-- dashboard history --" -ForegroundColor Cyan
if (Test-Path data\history.db) {
    Write-Host "data\history.db already present - leaving it alone"
} else {
    Write-Host "seeding data\history.db (no --no-history, so these get recorded)"
    python -m app.harness sample_good_code       | Out-Null
    python -m app.harness sample_vulnerable_code | Out-Null
    python -m app.harness sample_good_code       | Out-Null
    python -m app.harness app                    | Out-Null
    Write-Host "seeded 4 reviews"
}

Write-Host "`n=== done ===" -ForegroundColor Green
Write-Host @"

Next:
  1. python -m uvicorn app.main:app --reload
  2. npx smee-client --url <YOUR_SMEE_URL> --target http://localhost:8000/webhook
  3. gh api repos/sangam142/codeguardian-demo/hooks/<HOOK_ID>/pings -X POST
  4. Only ONE machine may run smee-client at a time.
"@
