[Console]::InputEncoding = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
chcp 65001 > $null

$fineCmd = 'C:\Program Files (x86)\ABBYY FineReader 15\FineCmd.exe'
$fineReader = 'C:\Program Files (x86)\ABBYY FineReader 15\FineReaderOCR.exe'
$progId = 'ABBYY.FineReader15.OCR.Application'

[pscustomobject]@{
    FineCmdExists = Test-Path $fineCmd
    FineReaderExists = Test-Path $fineReader
    OcrProgIdExists = Test-Path "Registry::HKEY_CLASSES_ROOT\$progId"
}
