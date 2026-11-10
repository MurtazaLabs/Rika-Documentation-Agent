<#
.SYNOPSIS
    Applies Rika's database migrations.

.PARAMETER Revision
    Target revision; defaults to "head".

.PARAMETER Downgrade
    Step back to the given revision instead of upgrading. Requires -Revision.

.EXAMPLE
    .\scripts\migrate.ps1

.EXAMPLE
    .\scripts\migrate.ps1 -Revision 0001 -Downgrade
#>
[CmdletBinding()]
param(
    [string]$Revision = "head",
    [switch]$Downgrade
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    throw "Virtual environment missing. Run .\scripts\setup.ps1 first."
}

$action = "upgrade"
$target = $Revision
if ($Downgrade) {
    $action = "downgrade"
    if (-not $PSBoundParameters.ContainsKey("Revision")) {
        throw "-Downgrade needs an explicit -Revision (use 'base' to remove all tables)."
    }
}

Push-Location (Join-Path $root "backend")
try {
    & $py -m alembic $action $target
    if ($LASTEXITCODE -ne 0) {
        throw "alembic $action $target failed. Is PostgreSQL running?"
    }
}
finally {
    Pop-Location
}

Write-Host "Database is at revision: $(if ($Downgrade) { $target } else { 'head' })" -ForegroundColor Green
