<#
.SYNOPSIS
    Builds Rika into a versioned release bundle.

.DESCRIPTION
    Runs the Next.js production build (which also typechecks) and writes
    dist\rika-<version>.zip containing the backend, the built UI, the scripts,
    Compose file and documentation.

    The virtual environment, node_modules and the GGUF models are not packaged:
    a bundle is prepared for another machine with scripts\setup.ps1.

.PARAMETER Output
    Destination zip. Defaults to dist\rika-<version>.zip.

.PARAMETER SkipBuild
    Reuse an existing frontend build instead of running npm run build.

.EXAMPLE
    .\scripts\package.ps1
#>
[CmdletBinding()]
param(
    [string]$Output = "",
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$py = Join-Path $root ".venv\Scripts\python.exe"
$frontend = Join-Path $root "frontend"

if (-not (Test-Path $py)) {
    throw "Virtual environment missing. Run .\scripts\setup.ps1 first."
}
if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    throw "Frontend dependencies missing. Run: cd frontend; npm install"
}

$version = (& $py -c "import sys; sys.path.insert(0, 'backend'); from app import __version__; print(__version__)").Trim()
if (-not $version) {
    throw "Could not read the Rika version from backend\app\__init__.py."
}

if (-not $SkipBuild) {
    Write-Host "Building the frontend (npm run build)..." -ForegroundColor Cyan
    Push-Location $frontend
    try {
        & npm run build
        if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
    }
    finally {
        Pop-Location
    }
}
elseif (-not (Test-Path (Join-Path $frontend ".next"))) {
    throw "No frontend build found in frontend\.next; run without -SkipBuild."
}

$staging = Join-Path $root ".tools\package\rika-$version"
if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
New-Item -ItemType Directory -Path $staging -Force | Out-Null

foreach ($directory in @("backend", "scripts", "docker", "docs")) {
    Copy-Item (Join-Path $root $directory) (Join-Path $staging $directory) -Recurse -Force
}

# The UI is copied piecewise: node_modules is deep enough that removing it
# afterwards fails silently, and the receiver installs its own.
$frontendStaging = Join-Path $staging "frontend"
New-Item -ItemType Directory -Path $frontendStaging -Force | Out-Null
Get-ChildItem (Join-Path $root "frontend") -File |
    Copy-Item -Destination $frontendStaging -Force
foreach ($item in @("src", "public", ".next")) {
    $source = Join-Path $root "frontend\$item"
    if (Test-Path $source) {
        Copy-Item $source (Join-Path $frontendStaging $item) -Recurse -Force
    }
}

# .next/dev is the dev server's output and .next/cache is rebuilt on demand;
# only the production build belongs in a release.
foreach ($unused in @("dev", "cache")) {
    $path = Join-Path $frontendStaging ".next\$unused"
    if (Test-Path $path) {
        Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue
    }
}
foreach ($file in @("README.md", ".env.example", ".gitignore", "docker-compose.yml")) {
    Copy-Item (Join-Path $root $file) (Join-Path $staging $file) -Force
}

# Caches are rebuilt locally; the built .next output is kept so the bundle can
# be served without running the build again.
Get-ChildItem -Path $staging -Recurse -Directory -Force |
    Where-Object { $_.Name -in @("__pycache__", ".pytest_cache", "node_modules") } |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $staging "frontend\.next\cache") -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $staging "backend\tests") -Recurse -Force -ErrorAction SilentlyContinue

if (-not $Output) {
    $Output = Join-Path $root "dist\rika-$version.zip"
}
$outputDirectory = Split-Path -Parent $Output
New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
if (Test-Path $Output) { Remove-Item $Output -Force }

Compress-Archive -Path (Join-Path $staging "*") -DestinationPath $Output -CompressionLevel Optimal

$size = (Get-Item $Output).Length / 1MB
$files = (Get-ChildItem $staging -Recurse -File).Count
Write-Host ("Release {0}: {1} files, {2:N1} MB -> {3}" -f $version, $files, $size, $Output) -ForegroundColor Green
