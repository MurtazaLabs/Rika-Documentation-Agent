<#
.SYNOPSIS
    Prepares the Rika development environment on Windows.

.DESCRIPTION
    Checks Python, creates .venv, installs backend dependencies, creates .env
    from .env.example, creates storage folders, starts the database and applies
    migrations.

    PostgreSQL and Redis come from Docker Compose when Docker is available.
    Otherwise the portable services in .tools\ are started instead (see
    scripts\postgres-local.ps1 and scripts\redis-local.ps1).

.PARAMETER PythonExe
    Python interpreter to build the virtual environment with.

.PARAMETER SkipInfrastructure
    Do not run docker compose up or migrations.

.EXAMPLE
    .\scripts\setup.ps1
#>
[CmdletBinding()]
param(
    [string]$PythonExe = "python",
    [switch]$SkipInfrastructure
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "[1/6] Checking Python" -ForegroundColor Cyan
$version = (& $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
if (-not $version) {
    throw "Python was not found. Install Python 3.10 or newer and re-run setup."
}
$parts = $version.Split(".")
if ([int]$parts[0] -lt 3 -or ([int]$parts[0] -eq 3 -and [int]$parts[1] -lt 10)) {
    throw "Python 3.10 or newer is required; found $version."
}
Write-Host "      Python $version"

Write-Host "[2/6] Creating virtual environment (.venv)" -ForegroundColor Cyan
$venv = Join-Path $root ".venv"
if (-not (Test-Path $venv)) {
    & $PythonExe -m venv $venv
}
$py = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $py)) {
    throw "Virtual environment creation failed: $py is missing."
}

Write-Host "[3/6] Installing backend dependencies" -ForegroundColor Cyan
& $py -m pip install --upgrade pip --quiet
& $py -m pip install -r (Join-Path $root "backend\requirements.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Dependency installation failed."
}

Write-Host "[4/6] Preparing .env and storage" -ForegroundColor Cyan
$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $root ".env.example") $envFile
    Write-Host "      Created .env - change POSTGRES_PASSWORD and DATABASE_URL together."
}
else {
    Write-Host "      .env already exists; left untouched."
}
foreach ($name in @("uploads", "extracted", "temp", "backups")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $root "storage\$name") | Out-Null
}

Write-Host "[5/6] Starting infrastructure" -ForegroundColor Cyan
$dockerAvailable = $null -ne (Get-Command docker -ErrorAction SilentlyContinue)
$localPostgres = Test-Path (Join-Path $root ".tools\pgdata\PG_VERSION")
$localRedis = Test-Path (Join-Path $root ".tools\redis\redis-server.exe")
$databaseReady = $false
if ($SkipInfrastructure) {
    Write-Host "      Skipped (-SkipInfrastructure)."
}
elseif ($dockerAvailable) {
    & docker compose up -d
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose up failed. Is Docker Desktop running?"
    }

    Write-Host "      Waiting for PostgreSQL to accept connections..."
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        & docker compose exec -T postgres pg_isready -U rika -d rika *> $null
        if ($LASTEXITCODE -eq 0) { $databaseReady = $true; break }
        Start-Sleep -Seconds 2
    }
    if (-not $databaseReady) {
        Write-Warning "PostgreSQL did not become ready; skipping migrations."
    }
}
else {
    if ($localPostgres) {
        Write-Host "      Docker not found; starting the project-local PostgreSQL cluster."
        try {
            & (Join-Path $PSScriptRoot "postgres-local.ps1") -Action start
            $databaseReady = $true
        }
        catch {
            Write-Warning "The local PostgreSQL cluster did not start: $($_.Exception.Message)"
        }
    }
    if ($localRedis) {
        Write-Host "      Starting the project-local Redis server."
        try {
            & (Join-Path $PSScriptRoot "redis-local.ps1") -Action start
        }
        catch {
            Write-Warning "The local Redis server did not start: $($_.Exception.Message)"
        }
    }
    $localLlama = Test-Path (Join-Path $root ".tools\llama\llama-server.exe")
    $localModels = Test-Path (Join-Path $root "models\llm")
    if ($localLlama -and $localModels) {
        Write-Host "      Starting the project-local llama.cpp servers."
        try {
            & (Join-Path $PSScriptRoot "llama-local.ps1") -Action start
        }
        catch {
            Write-Warning "The local model servers did not start: $($_.Exception.Message)"
        }
    }
    if (-not $localPostgres -and -not $localRedis) {
        Write-Warning "No local infrastructure found. Install Docker Desktop and run 'docker compose up -d', or follow the README's portable PostgreSQL + Redis setup."
    }
}

Write-Host "[6/6] Applying database migrations" -ForegroundColor Cyan
if ($SkipInfrastructure -or -not $databaseReady) {
    Write-Host "      Skipped. Apply them later with: .\scripts\migrate.ps1"
}
else {
    Push-Location (Join-Path $root "backend")
    try {
        & $py -m alembic upgrade head
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Migrations failed. Once PostgreSQL is up, run: .\scripts\migrate.ps1"
        }
    }
    finally {
        Pop-Location
    }
}

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Start the API with:  .\scripts\start.ps1 -WithWorker"
Write-Host "Verify models with:  cd backend; ..\.venv\Scripts\python.exe -m app.cli check-models"
