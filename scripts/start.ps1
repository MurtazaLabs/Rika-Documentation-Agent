<#
.SYNOPSIS
    Starts Rika's API, and optionally the Celery worker.

.PARAMETER WithWorker
    Also launch a Celery worker in a separate window.

.PARAMETER WithFrontend
    Also launch the Next.js UI in a separate window (http://127.0.0.1:3000).

.PARAMETER NoInfrastructure
    Skip docker compose (already running, or managed elsewhere).

.PARAMETER Production
    Serve the production build instead of the dev servers: uvicorn without
    --reload and ``npm run start`` (run scripts\package.ps1 first).

.EXAMPLE
    .\scripts\start.ps1 -WithWorker -WithFrontend

.EXAMPLE
    .\scripts\start.ps1 -Production -WithWorker -WithFrontend
#>
[CmdletBinding()]
param(
    [switch]$WithWorker,
    [switch]$WithFrontend,
    [switch]$NoInfrastructure,
    [switch]$Production
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    throw "Virtual environment missing. Run .\scripts\setup.ps1 first."
}

if (-not $NoInfrastructure) {
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        & docker compose up -d
        if ($LASTEXITCODE -ne 0) { Write-Warning "docker compose up failed; continuing." }
    }
    else {
        $started = $false
        if (Test-Path (Join-Path $root ".tools\pgdata\PG_VERSION")) {
            & (Join-Path $PSScriptRoot "postgres-local.ps1") -Action start
            $started = $true
        }
        if (Test-Path (Join-Path $root ".tools\redis\redis-server.exe")) {
            & (Join-Path $PSScriptRoot "redis-local.ps1") -Action start
            $started = $true
        }
        $llama = Join-Path $root ".tools\llama\llama-server.exe"
        $models = (Test-Path (Join-Path $root "models\llm")) -and
            (Get-ChildItem (Join-Path $root "models\llm") -Filter *.gguf -ErrorAction SilentlyContinue)
        if ((Test-Path $llama) -and $models) {
            & (Join-Path $PSScriptRoot "llama-local.ps1") -Action start
        }
        elseif (Test-Path $llama) {
            Write-Warning "llama.cpp found but no model in models\llm; see scripts\llama-local.ps1."
        }
        if (-not $started) {
            Write-Warning "Docker not found; expecting PostgreSQL and Redis to be running already."
        }
    }
}

if ($WithWorker) {
    Start-Process -FilePath $py `
        -ArgumentList "-m", "celery", "-A", "app.workers.celery_app", "worker", "--loglevel=INFO" `
        -WorkingDirectory (Join-Path $root "backend")
    Write-Host "Celery worker started in a separate window." -ForegroundColor Cyan
}

if ($WithFrontend) {
    $frontend = Join-Path $root "frontend"
    if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
        Write-Warning "Frontend dependencies missing. Run: cd frontend; npm install"
    }
    elseif (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        Write-Warning "npm not found. Install Node.js 20+ to run the UI."
    }
    else {
        $script = if ($Production) { "start" } else { "dev" }
        if ($Production -and -not (Test-Path (Join-Path $frontend ".next"))) {
            Write-Warning "No production build found. Run .\scripts\package.ps1 first."
        }
        # cmd /c keeps npm.cmd resolvable from a detached window.
        Start-Process -FilePath "cmd.exe" `
            -ArgumentList "/c npm run $script" `
            -WorkingDirectory $frontend
        Write-Host "Next.js UI started in a separate window." -ForegroundColor Cyan
    }
}

Write-Host "API:      http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Docs:     http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host "Health:   http://127.0.0.1:8000/health/ready" -ForegroundColor Green
if ($WithFrontend) {
    Write-Host "UI:       http://127.0.0.1:3000" -ForegroundColor Green
}
if ($Production) {
    Write-Host "Mode:     production (no reload, built UI)" -ForegroundColor DarkGray
    & $py -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
}
else {
    & $py -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
}
