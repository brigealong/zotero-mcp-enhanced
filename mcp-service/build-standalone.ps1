[Console]::InputEncoding = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
chcp 65001 > $null

$ErrorActionPreference = "Stop"

$serviceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$distDir = Join-Path $serviceRoot "dist"
$buildDir = Join-Path $serviceRoot "build"
$buildVenv = Join-Path $buildDir ".build-venv"
$venvPython = Join-Path $buildVenv "Scripts\\python.exe"
$entryScript = Join-Path $serviceRoot "standalone_entry.py"
$outputExe = Join-Path $distDir "zotero-mcp-enhanced-service.exe"

Push-Location $serviceRoot
try {
    if (-not (Test-Path -LiteralPath $venvPython)) {
        Write-Output "Creating isolated build virtual environment..."
        python -m venv $buildVenv
    }

    Write-Output "Installing standalone build dependencies into isolated environment..."
    & $venvPython -m pip install -e ".[build]"

    if (-not (Test-Path -LiteralPath $distDir)) {
        New-Item -ItemType Directory -Path $distDir | Out-Null
    }

    & $venvPython -m PyInstaller `
        --noconfirm `
        --clean `
        --onefile `
        --name "zotero-mcp-enhanced-service" `
        --paths "src" `
        --distpath $distDir `
        --workpath (Join-Path $buildDir "pyinstaller") `
        --specpath $buildDir `
        $entryScript

    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $outputExe)) {
        throw "Standalone build failed. Expected executable not found: $outputExe"
    }

    Write-Output "Built standalone MCP service: $outputExe"
}
finally {
    Pop-Location
}
