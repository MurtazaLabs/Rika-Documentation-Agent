<#
.SYNOPSIS
    Restores a Rika database backup produced by backup.ps1.

.DESCRIPTION
    The dump contains DROP statements, so it replaces the current schema.
    Stop the API first: .\scripts\stop.ps1 -KeepInfrastructure

.PARAMETER BackupFile
    Path to the .sql dump to restore.

.PARAMETER User
    Database role used for psql.

.PARAMETER Database
    Target database name.

.PARAMETER Force
    Skip the interactive confirmation.

.EXAMPLE
    .\scripts\restore.ps1 -BackupFile storage\backups\rika-20260101-120000.sql
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile,
    [string]$User = "rika",
    [string]$Database = "rika",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$resolved = Resolve-Path -Path $BackupFile -ErrorAction SilentlyContinue
if (-not $resolved) {
    throw "Backup file not found: $BackupFile"
}
$path = $resolved.Path

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is required to reach the PostgreSQL container."
}

if (-not $Force) {
    Write-Warning "This replaces the contents of database '$Database'."
    $answer = Read-Host "Type YES to continue"
    if ($answer -ne "YES") {
        Write-Host "Aborted."
        exit 1
    }
}

cmd /c "docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U $User -d $Database < `"$path`""
if ($LASTEXITCODE -ne 0) {
    throw "Restore failed; the database may be partially restored. Review the output above."
}

Write-Host "Restored $path into '$Database'." -ForegroundColor Green
