<#
.SYNOPSIS
    Manages the two project-local llama.cpp servers (chat and embeddings).

.DESCRIPTION
    For machines without Docker. Uses the prebuilt llama.cpp Windows release,
    dropped into .tools\llama, and GGUF files placed in models\llm and
    models\embeddings (see the header of this file for download steps).

    Two servers are started, matching CHAT_BASE_URL and EMBEDDING_BASE_URL in
    .env:

      chat       Qwen3-4B-Instruct-2507 Q4_K_M on the discrete GPU
      embeddings Qwen3-Embedding-0.6B Q8_0 on the CPU

    Each server's model alias is the configured model name, so /v1/models lists
    exactly what readiness and check-models expect.

    Chat runs on the GPU with a 4096-token context; that fits a 4 GB card
    together with the model and its KV cache. Embeddings stay on the CPU: the
    0.6B model does not need the GPU, and leaving it free avoids fighting the
    chat model for VRAM.

    To install the binaries and models by hand:

        mkdir .tools\llama
        curl.exe -L -o .tools\llama.zip https://github.com/ggml-org/llama.cpp/releases/download/b12233/llama-b12233-bin-win-vulkan-x64.zip
        powershell -Command "Expand-Archive .tools\llama.zip -DestinationPath .tools\llama -Force"
        curl.exe -L -o models\embeddings\Qwen3-Embedding-0.6B-Q8_0.gguf https://huggingface.co/Qwen/Qwen3-Embedding-0.6B-GGUF/resolve/main/Qwen3-Embedding-0.6B-Q8_0.gguf
        curl.exe -L -o models\llm\Qwen3-4B-Instruct-2507-Q4_K_M.gguf https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/main/Qwen3-4B-Instruct-2507-Q4_K_M.gguf

    The Vulkan build needs no CUDA toolkit; it uses the installed GPU driver.
    A CPU-only build of llama-server works too, just slower.

.PARAMETER Action
    start  - launch both servers and wait until /v1/models answers
    stop   - stop both servers (models stay on disk)
    status - report each server's URL and loaded model ids

.PARAMETER ChatContext
    Chat context size in tokens. Lower it if the GPU runs out of memory.

.PARAMETER Device
    GPU to use for chat, for example "Vulkan1". Defaults to the discrete GPU
    reported by llama-server --list-devices.

.EXAMPLE
    .\scripts\llama-local.ps1 -Action start
#>
[CmdletBinding()]
param(
    [ValidateSet("start", "stop", "status")]
    [string]$Action = "start",

    [int]$ChatContext = 4096,

    [string]$Device
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$bin = ".tools\llama"
$server = Join-Path $bin "llama-server.exe"
# Absolute, because llama-server resolves --log-file against its own directory.
$logDir = Join-Path $root ".tools\llama-logs"
$chatModelDir = "models\llm"
$embeddingModelDir = "models\embeddings"

if (-not (Test-Path $server)) {
    throw "llama.cpp is not installed at $bin. See the header of this script for the download steps."
}

function Get-FirstModel([string]$directory) {
    if (-not (Test-Path $directory)) { return $null }
    Get-ChildItem -Path $directory -Filter *.gguf -File |
        Sort-Object Name |
        Select-Object -First 1
}

# Keep URLs and aliases in sync with .env.
$chatUrl = "http://127.0.0.1:8080"
$embeddingUrl = "http://127.0.0.1:8081"
$chatAlias = "local-chat-model"
$embeddingAlias = "local-embedding-model"
$envFile = Join-Path $root ".env"
if (Test-Path $envFile) {
    foreach ($line in Get-Content $envFile) {
        if ($line -match '^\s*CHAT_BASE_URL\s*=\s*(\S+)') { $chatUrl = $Matches[1].TrimEnd("/") }
        if ($line -match '^\s*EMBEDDING_BASE_URL\s*=\s*(\S+)') { $embeddingUrl = $Matches[1].TrimEnd("/") }
        if ($line -match '^\s*CHAT_MODEL_NAME\s*=\s*(\S+)') { $chatAlias = $Matches[1] }
        if ($line -match '^\s*EMBEDDING_MODEL_NAME\s*=\s*(\S+)') { $embeddingAlias = $Matches[1] }
    }
}

function Get-Port([string]$url) {
    $uri = [System.Uri]$url
    if ($uri.Port -gt 0) { return $uri.Port }
    return 80
}

$chatPort = Get-Port $chatUrl
$embeddingPort = Get-Port $embeddingUrl

function Get-LlamaPid([string]$name) {
    $pidFile = Join-Path $logDir "$name.pid"
    if (-not (Test-Path $pidFile)) { return $null }
    $candidate = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    if (-not $candidate) { return $null }
    $process = Get-Process -Id ([int]$candidate) -ErrorAction SilentlyContinue
    # Verify the name, so a recycled pid never gets killed by mistake.
    if ($process -and $process.ProcessName -eq "llama-server") { return $process.Id }
    return $null
}

function Get-Models([string]$url) {
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $payload = Invoke-RestMethod -Uri "$url/v1/models" -TimeoutSec 3 -ErrorAction Stop
        return @($payload.data | ForEach-Object { $_.id })
    }
    catch {
        return $null
    }
    finally {
        $ErrorActionPreference = $previous
    }
}

function Wait-Models([string]$url, [string]$alias, [string]$logFile, [int]$seconds) {
    for ($attempt = 1; $attempt -le $seconds; $attempt++) {
        $models = Get-Models $url
        if ($models -and ($models -contains $alias)) { return $models }
        Start-Sleep -Seconds 1
    }
    throw "$url did not report model '$alias' within ${seconds}s; see $logFile."
}

function Resolve-ChatDevice {
    if ($Device) { return $Device }
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $lines = & (Resolve-Path $server).Path --list-devices 2>$null
    }
    finally {
        $ErrorActionPreference = $previous
    }
    # Prefer a discrete GPU over an Intel/AMD integrated one.
    $candidates = @()
    foreach ($line in $lines) {
        if ($line -match '^\s*(\S+):\s+(.+?)\s+\((\d+) MiB,\s*(\d+) MiB free\)') {
            $candidates += [pscustomobject]@{
                Id     = $Matches[1]
                Name   = $Matches[2]
                FreeMb = [int]$Matches[4]
                Integrated = ($Matches[2] -match 'Intel|Radeon\(TM\) Graphics|UHD')
            }
        }
    }
    $discrete = $candidates | Where-Object { -not $_.Integrated } | Sort-Object FreeMb -Descending
    $chosen = ($discrete | Select-Object -First 1)
    if ($chosen) { return $chosen.Id }
    $fallback = ($candidates | Sort-Object FreeMb -Descending | Select-Object -First 1)
    if ($fallback) { return $fallback.Id }
    return $null
}

function Start-Llama([string]$name, [string]$url, [string[]]$arguments, [string]$alias) {
    $logFile = Join-Path $logDir "$name.log"
    $pidFile = Join-Path $logDir "$name.pid"
    $models = Get-Models $url
    if ($models) {
        Write-Host "$name is already serving on $url ($($models -join ', '))." -ForegroundColor Yellow
        return
    }
    Remove-Item $logFile -ErrorAction SilentlyContinue
    # Start-Process joins -ArgumentList with spaces, so quote anything that has one
    # (model and log paths live under the repository folder, which may contain spaces).
    $quoted = $arguments | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }
    $process = Start-Process -FilePath (Resolve-Path $server).Path `
        -ArgumentList $quoted -WorkingDirectory (Resolve-Path $bin).Path `
        -WindowStyle Hidden -PassThru
    Set-Content -Path $pidFile -Value $process.Id -Encoding ascii
    Write-Host "$name starting (pid $($process.Id), log $logFile)..." -ForegroundColor Cyan
    $loaded = Wait-Models $url $alias $logFile 300
    Write-Host "$name is serving $($loaded -join ', ') on $url." -ForegroundColor Green
}

function Stop-Llama([string]$name, [string]$url) {
    $processId = Get-LlamaPid $name
    if ($processId) {
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped $name (pid $processId)." -ForegroundColor Green
    }
    else {
        Write-Host "$name is not running (no recorded pid)." -ForegroundColor Yellow
    }
    Remove-Item (Join-Path $logDir "$name.pid") -ErrorAction SilentlyContinue
    for ($attempt = 1; $attempt -le 20; $attempt++) {
        if (-not (Get-Models $url)) { return }
        Start-Sleep -Milliseconds 500
    }
    throw "$name still answers on $url after being stopped."
}

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$chatModel = Get-FirstModel $chatModelDir
$embeddingModel = Get-FirstModel $embeddingModelDir

switch ($Action) {
    "start" {
        if (-not $chatModel) {
            throw "No chat model in $chatModelDir. See the header of this script."
        }
        if (-not $embeddingModel) {
            throw "No embedding model in $embeddingModelDir. See the header of this script."
        }

        $gpu = Resolve-ChatDevice
        $gpuArgs = @()
        if ($gpu) {
            $gpuArgs = @("--device", $gpu)
            Write-Host "Chat model will use GPU device $gpu." -ForegroundColor Cyan
        }
        else {
            Write-Host "No GPU device reported; running the chat model on the CPU." -ForegroundColor Yellow
        }

        # Chat: as many layers on the GPU as fit, single slot, small context.
        $chatArgs = @(
            "--model", $chatModel.FullName,
            "--host", "127.0.0.1", "--port", "$chatPort",
            "--alias", $chatAlias,
            "--ctx-size", "$ChatContext",
            "--parallel", "1",
            "--flash-attn", "on",
            "--no-webui",
            "--log-file", (Join-Path $logDir "chat.log")
        ) + $gpuArgs
        if ($gpu) { $chatArgs += @("--n-gpu-layers", "99") }
        Start-Llama "chat" $chatUrl $chatArgs $chatAlias

        # Embeddings: CPU only, so the GPU stays available for chat.
        $embeddingArgs = @(
            "--model", $embeddingModel.FullName,
            "--host", "127.0.0.1", "--port", "$embeddingPort",
            "--alias", $embeddingAlias,
            "--embedding", "--pooling", "last",
            "--ctx-size", "2048", "--batch-size", "2048", "--ubatch-size", "2048",
            "--n-gpu-layers", "0",
            "--no-webui",
            "--log-file", (Join-Path $logDir "embedding.log")
        )
        Start-Llama "embedding" $embeddingUrl $embeddingArgs $embeddingAlias

        Write-Host "Models ready. Verify with: cd backend; ..\.venv\Scripts\python.exe -m app.cli check-models" -ForegroundColor Green
    }
    "stop" {
        Stop-Llama "chat" $chatUrl
        Stop-Llama "embedding" $embeddingUrl
    }
    "status" {
        foreach ($pair in @(@("chat", $chatUrl, $chatAlias), @("embedding", $embeddingUrl, $embeddingAlias))) {
            $name = $pair[0]
            $url = $pair[1]
            $alias = $pair[2]
            $models = Get-Models $url
            if ($models) {
                $suffix = if ($models -contains $alias) { "" } else { " (warning: alias '$alias' not listed)" }
                Write-Host "$($name.PadRight(10)) $url -> $($models -join ', ')$suffix" -ForegroundColor Green
            }
            else {
                Write-Host "$($name.PadRight(10)) $url -> not answering" -ForegroundColor Yellow
            }
        }
    }
}
