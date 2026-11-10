<#
.SYNOPSIS
    Manages the project-local PostgreSQL + pgvector cluster.

.DESCRIPTION
    For machines without Docker. The cluster lives entirely inside .tools\:
    no service, no admin rights and no system-wide install. Delete .tools\ to
    remove it.

    The binaries come from conda-forge (postgresql 16 + pgvector), installed
    with micromamba:

        .tools\micromamba.exe create -y -r .tools\mamba-root -p .tools\postgres -c conda-forge "postgresql=16" pgvector

    conda-forge only publishes the pgvector extension for Windows against
    PostgreSQL 16, hence the version. The schema itself is identical on 16 and
    17, which is what docker-compose.yml runs.

.PARAMETER Action
    init   - create the data directory (.tools\pgdata) and the rika database
    start  - start the server on 127.0.0.1:5432
    stop   - stop it
    status - report whether it is running and accepting connections

.EXAMPLE
    .\scripts\postgres-local.ps1 -Action start
#>
[CmdletBinding()]
param(
    [ValidateSet("init", "start", "stop", "status")]
    [string]$Action = "start"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$bin = ".tools\postgres\Library\bin"
$data = ".tools\pgdata"
$log = ".tools\pgdata\server.log"

foreach ($exe in @("pg_ctl.exe", "pg_isready.exe")) {
    if (-not (Test-Path (Join-Path $bin $exe))) {
        throw "PostgreSQL is not installed at $bin. See the header of this script for the install command."
    }
}
$pgCtl = Join-Path $bin "pg_ctl.exe"
$pgIsReady = Join-Path $bin "pg_isready.exe"

# Credentials must match DATABASE_URL in .env (defaults mirror .env.example).
$password = "change-me"
$dbUser = "rika"
$dbName = "rika"
$envFile = Join-Path $root ".env"
if (Test-Path $envFile) {
    foreach ($line in Get-Content $envFile) {
        if ($line -match '^\s*POSTGRES_PASSWORD\s*=\s*(.+?)\s*$') { $password = $Matches[1] }
        elseif ($line -match '^\s*POSTGRES_USER\s*=\s*(.+?)\s*$') { $dbUser = $Matches[1] }
        elseif ($line -match '^\s*POSTGRES_DB\s*=\s*(.+?)\s*$') { $dbName = $Matches[1] }
    }
}

function Test-Ready {
    & $pgIsReady -h 127.0.0.1 -p 5432 -U $dbUser -d $dbName *> $null
    return $LASTEXITCODE -eq 0
}

switch ($Action) {
    "init" {
        if (Test-Path (Join-Path $data "PG_VERSION")) {
            Write-Host "Cluster already initialised at $data; nothing to do." -ForegroundColor Yellow
            return
        }
        New-Item -ItemType Directory -Force -Path $data | Out-Null
        $pwFile = ".tools\.pgpw"
        Set-Content -Path $pwFile -Value $password -NoNewline -Encoding ascii
        try {
            & (Join-Path $bin "initdb.exe") -D $data -U $dbUser --pwfile=$pwFile `
                --auth-local=trust --auth-host=scram-sha-256 --encoding=UTF8 --locale=C
            if ($LASTEXITCODE -ne 0) { throw "initdb failed." }
        }
        finally {
            Remove-Item $pwFile -ErrorAction SilentlyContinue
        }
        Add-Content -Path (Join-Path $data "postgresql.conf") -Value @"

# Rika local development cluster (project-local, loopback only)
listen_addresses = '127.0.0.1'
port = 5432
log_timezone = 'UTC'
timezone = 'UTC'
"@
        Write-Host "Data directory created. Start it with: .\scripts\postgres-local.ps1 -Action start" -ForegroundColor Green
    }
    "start" {
        if (-not (Test-Path (Join-Path $data "PG_VERSION"))) {
            throw "No cluster at $data. Run: .\scripts\postgres-local.ps1 -Action init"
        }
        if (Test-Ready) {
            Write-Host "PostgreSQL is already accepting connections on 127.0.0.1:5432." -ForegroundColor Yellow
            return
        }
        # Started in its own hidden process so the server outlives this terminal,
        # then waited for (relative paths keep spaces out of the argument list).
        $pgCtlFull = (Resolve-Path $pgCtl).Path
        Start-Process -FilePath $pgCtlFull -ArgumentList @("-D", $data, "-l", $log, "start") `
            -WorkingDirectory $root -WindowStyle Hidden | Out-Null
        for ($attempt = 1; $attempt -le 120; $attempt++) {
            if (Test-Ready) { break }
            Start-Sleep -Seconds 1
        }
        if (-not (Test-Ready)) { throw "PostgreSQL did not accept connections within 120s; see $log." }
        Write-Host "PostgreSQL is accepting connections on 127.0.0.1:5432." -ForegroundColor Green

        $env:PGPASSWORD = $password
        $env:PGGSSENCMODE = "disable"
        & (Join-Path $bin "psql.exe") -w -h 127.0.0.1 -U $dbUser -d postgres -tAc `
            "SELECT 1 FROM pg_database WHERE datname = '$dbName'" 2>$null | ForEach-Object { $existing = $_.Trim() }
        if ($existing -ne "1") {
            & (Join-Path $bin "createdb.exe") -h 127.0.0.1 -U $dbUser $dbName
            if ($LASTEXITCODE -ne 0) { throw "Could not create the $dbName database." }
            Write-Host "Created database '$dbName'." -ForegroundColor Green
        }
        Remove-Item Env:\PGPASSWORD, Env:\PGGSSENCMODE -ErrorAction SilentlyContinue
    }
    "stop" {
        & $pgCtl -D $data -m fast -w -t 120 stop
        if ($LASTEXITCODE -ne 0) { throw "PostgreSQL did not stop; see $log." }
        Write-Host "PostgreSQL stopped." -ForegroundColor Green
    }
    "status" {
        & $pgCtl -D $data status
        if (Test-Ready) {
            Write-Host "Accepting connections on 127.0.0.1:5432." -ForegroundColor Green
        }
        else {
            Write-Host "Not accepting connections." -ForegroundColor Yellow
        }
    }
}
