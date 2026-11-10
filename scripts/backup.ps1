<#
.SYNOPSIS
    Backs up the Rika PostgreSQL database.

.DESCRIPTION
    Writes a plain-SQL dump (with DROP statements, so it is safe to restore
    over an existing database) to storage\backups. Uploaded project files live
    under storage\ and should be copied separately.

.PARAMETER User
    Database role used for pg_dump.

.PARAMETER Database
    Database name to dump.

.EXAMPLE
    .\scripts\backup.ps1
#>
[CmdletBinding()]
param(
    [string]$User = "rika",
    [string]$Database = "rika"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is required to reach the PostgreSQL container."
}

$target = Join-Path $root "storage\backups"
New-Item -ItemType Directory -Force -Path $target | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$file = Join-Path $target "rika-$stamp.sql"

# cmd.exe keeps the dump byte-exact; PowerShell redirection would re-encode it.
cmd /c "docker compose exec -T postgres pg_dump -U $User -d $Database --clean --if-exists --no-owner --no-privileges > `"$file`""
if ($LASTEXITCODE -ne 0) {
    throw "pg_dump failed. Is the postgres container running?"
}

$size = [math]::Round((Get-Item $file).Length / 1KB, 1)
Write-Host "Backup written: $file ($size KB)" -ForegroundColor Green
Write-Host "Reminder: copy the storage\ folder for uploaded files." -ForegroundColor DarkGray
