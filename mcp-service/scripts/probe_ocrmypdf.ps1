[Console]::InputEncoding = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
chcp 65001 > $null

$userScripts = Join-Path $env:APPDATA 'Python'
$ocrmypdfEnv = [Environment]::GetEnvironmentVariable('OCRMYPDF_PATH', 'User')
$ocrmypdfCandidates = @(
    $ocrmypdfEnv
    (Get-Command ocrmypdf -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue)
)

if (Test-Path -LiteralPath $userScripts) {
    $ocrmypdfCandidates += Get-ChildItem -Path $userScripts -Recurse -Filter ocrmypdf.exe -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty FullName
}

$tesseractCandidates = @(
    (Get-Command tesseract -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue)
    'C:\Program Files\Tesseract-OCR\tesseract.exe'
)

$ocrmypdfPath = $ocrmypdfCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
$tesseractPath = $tesseractCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1

$result = [ordered]@{
    OCRmyPDFFound = $null -ne $ocrmypdfPath
    OCRmyPDFPath = $ocrmypdfPath
    TesseractFound = $null -ne $tesseractPath
    TesseractPath = $tesseractPath
    UserOCRMYPDFPath = $ocrmypdfEnv
}

$result | ConvertTo-Json -Depth 3
