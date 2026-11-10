<#
.SYNOPSIS
    Stops the Rika API, Celery workers and Docker infrastructure.

.DESCRIPTION
    Only targets the API listening on port 8000 and python processes whose
    command line runs celery, so nothing else on the machine is touched.

.PARAMETER KeepInfrastructure
    Leave PostgreSQL and Redis running.
#>
[CmdletBinding()]
param(
    [switch]$KeepInfrastructure
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$listeners = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($listeners) {
    $listeners | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object {
        Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped API process $_"
    }
}
else {
    Write-Host "No process is listening on port 8000."
}

Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and $_.CommandLine -like "*celery*" } |
    ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped Celery worker $($_.ProcessId)"
    }

if (-not $KeepInfrastructure) {
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        & docker compose stop
        Write-Host "Infrastructure stopped (data volumes preserved)."
    }
    else {
        $stopped = $false
        if (Test-Path (Join-Path $root ".tools\llama\llama-server.exe")) {
            & (Join-Path $PSScriptRoot "llama-local.ps1") -Action stop
            $stopped = $true
        }
        if (Test-Path (Join-Path $root ".tools\redis\redis-server.exe")) {
            & (Join-Path $PSScriptRoot "redis-local.ps1") -Action stop
            $stopped = $true
        }
        if (Test-Path (Join-Path $root ".tools\pgdata\PG_VERSION")) {
            & (Join-Path $PSScriptRoot "postgres-local.ps1") -Action stop
            $stopped = $true
        }
        if ($stopped) {
            Write-Host "Local infrastructure stopped (data preserved in .tools)."
        }
    }
}
