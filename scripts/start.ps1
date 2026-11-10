<#
.SYNOPSIS
    Starts Rika's API, and optionally the Celery worker.

.PARAMETER WithWorker
    Also launch a Celery worker in a separate window.

.PARAMETER NoInfrastructure
    Skip docker compose (already running, or managed elsewhere).

.EXAMPLE
    .\scripts\start.ps1 -WithWorker
#>
[CmdletBinding()]
param(
    [switch]$WithWorker,
    [switch]$NoInfrastructure
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

Write-Host "API:      http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Docs:     http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host "Health:   http://127.0.0.1:8000/health/ready" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop." -ForegroundColor DarkGray

& $py -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
