<#
.SYNOPSIS
    Manages the project-local Redis server.

.DESCRIPTION
    For machines without Docker. Redis has no conda-forge/Windows build, so this
    uses the portable MSYS2 build from redis-windows: a zip, no installer, no
    service and no admin rights. Everything lives in .tools\; delete that folder
    to remove it.

        curl.exe -L -o .tools\redis.zip https://github.com/redis-windows/redis-windows/releases/download/8.10.3/Redis-8.10.3-Windows-x64-msys2.zip
        powershell -Command "Expand-Archive .tools\redis.zip -DestinationPath .tools"
        Move-Item .tools\Redis-8.10.3-Windows-x64-msys2 .tools\redis

    The configuration is written on start: loopback only, append-only persistence
    in .tools\redis-data (matching the Compose service), port taken from
    REDIS_URL.

.PARAMETER Action
    start  - write the config, start the server and wait for PING
    stop   - SHUTDOWN the server (data is flushed first)
    status - report whether it answers PING

.EXAMPLE
    .\scripts\redis-local.ps1 -Action start
#>
[CmdletBinding()]
param(
    [ValidateSet("start", "stop", "status")]
    [string]$Action = "start"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$bin = ".tools\redis"
$server = Join-Path $bin "redis-server.exe"
$cli = Join-Path $bin "redis-cli.exe"
$conf = Join-Path $bin "redis.local.conf"
$data = ".tools\redis-data"

if (-not (Test-Path $server)) {
    throw "Redis is not installed at $bin. See the header of this script for the download steps."
}

# Keep the port in sync with REDIS_URL in .env.
$port = 6379
$envFile = Join-Path $root ".env"
if (Test-Path $envFile) {
    foreach ($line in Get-Content $envFile) {
        if ($line -match '^\s*REDIS_URL\s*=\s*redis://(?:[^@/]*@)?[^:/]+:(\d+)') {
            $port = [int]$Matches[1]
        }
    }
}

function Test-Redis {
    # redis-cli writes "Could not connect" to stderr, which PowerShell turns into
    # a terminating error under the script's ErrorActionPreference; probe quietly.
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $reply = & $cli -h 127.0.0.1 -p $port ping 2>$null
        return ($LASTEXITCODE -eq 0 -and "$reply".Trim() -eq "PONG")
    }
    finally {
        $ErrorActionPreference = $previous
    }
}

switch ($Action) {
    "start" {
        if (Test-Redis) {
            Write-Host "Redis is already answering PING on 127.0.0.1:$port." -ForegroundColor Yellow
            return
        }
        New-Item -ItemType Directory -Force -Path $data | Out-Null
        $configText = @"
# Rika local development Redis (portable build, loopback only).
# Written by scripts\redis-local.ps1; the working directory is .tools\redis-data,
# so "dir ." keeps the AOF/RDB files there.
bind 127.0.0.1
port $port
protected-mode yes

dir .
logfile ./redis.log
loglevel notice
databases 16

# The Celery broker must survive a restart, so keep persistence on.
appendonly yes
appendfsync everysec
save 60 1
"@
        Set-Content -Path $conf -Value $configText -Encoding ascii

        # Detached, so the server outlives the terminal that started it.
        Start-Process -FilePath (Resolve-Path $server).Path -ArgumentList "..\redis\redis.local.conf" `
            -WorkingDirectory (Resolve-Path $data).Path -WindowStyle Hidden | Out-Null

        for ($attempt = 1; $attempt -le 60; $attempt++) {
            if (Test-Redis) { break }
            Start-Sleep -Milliseconds 500
        }
        if (-not (Test-Redis)) {
            throw "Redis did not answer PING within 30s; see .tools\redis-data\redis.log."
        }
        Write-Host "Redis is answering PING on 127.0.0.1:$port (data in $data)." -ForegroundColor Green
    }
    "stop" {
        if (-not (Test-Redis)) {
            Write-Host "Redis is not running on 127.0.0.1:$port." -ForegroundColor Yellow
            return
        }
        & $cli -h 127.0.0.1 -p $port shutdown | Out-Null
        for ($attempt = 1; $attempt -le 60; $attempt++) {
            if (-not (Test-Redis)) { break }
            Start-Sleep -Milliseconds 500
        }
        if (Test-Redis) {
            throw "Redis did not shut down; check .tools\redis-data\redis.log."
        }
        Write-Host "Redis stopped." -ForegroundColor Green
    }
    "status" {
        if (Test-Redis) {
            $version = (& $cli -h 127.0.0.1 -p $port --raw info server 2>$null) |
                Where-Object { $_ -like "redis_version:*" } | Select-Object -First 1
            Write-Host "Redis $($version -replace 'redis_version:', '') is answering PING on 127.0.0.1:$port." -ForegroundColor Green
        }
        else {
            Write-Host "Redis is not answering PING on 127.0.0.1:$port." -ForegroundColor Yellow
        }
    }
}
