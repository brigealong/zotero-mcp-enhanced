[Console]::InputEncoding = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
chcp 65001 > $null

$ErrorActionPreference = "Stop"

$pluginRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$distDir = Join-Path $pluginRoot "dist"
$zipPath = Join-Path $distDir "zotero-mcp-enhanced.zip"
$outputPath = Join-Path $distDir "zotero-mcp-enhanced.xpi"

if (-not (Test-Path -LiteralPath $distDir)) {
    New-Item -ItemType Directory -Path $distDir | Out-Null
}

if (Test-Path -LiteralPath $outputPath) {
    Remove-Item -LiteralPath $outputPath -Force
}

if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

$packageItems = @(
    "bootstrap.js",
    "manifest.json",
    "prefs.js",
    "content",
    "locale"
) | ForEach-Object { Join-Path $pluginRoot $_ }

Compress-Archive -Path $packageItems -DestinationPath $zipPath -CompressionLevel Optimal
Move-Item -LiteralPath $zipPath -Destination $outputPath

Write-Output "Built plugin package: $outputPath"
