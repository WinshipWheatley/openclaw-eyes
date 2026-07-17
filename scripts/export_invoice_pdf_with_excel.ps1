param(
    [Parameter(Mandatory = $true)][string]$InputPath,
    [Parameter(Mandatory = $true)][string]$SheetName,
    [Parameter(Mandatory = $true)][string]$OutputPath
)

$ErrorActionPreference = "Stop"
$excel = $null
$workbook = $null
$worksheet = $null
$result = [ordered]@{
    status = "FAILED"
    error_code = "EXCEL_PDF_EXPORT_FAILED"
    excel_version = ""
}

try {
    if (-not (Test-Path -LiteralPath $InputPath -PathType Leaf)) {
        throw "SOURCE_WORKBOOK_MISSING"
    }
    if (Test-Path -LiteralPath $OutputPath) {
        throw "PDF_OUTPUT_ALREADY_EXISTS"
    }

    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $excel.AskToUpdateLinks = $false
    $excel.EnableEvents = $false
    $excel.AutomationSecurity = 3
    $result.excel_version = [string]$excel.Version
    $workbook = $excel.Workbooks.Open($InputPath, 0, $true)
    if ($workbook.HasVBProject) {
        throw "MACROS_PRESENT"
    }
    $links = $workbook.LinkSources(1)
    if ($null -ne $links) {
        throw "EXTERNAL_LINKS_PRESENT"
    }
    $worksheet = $workbook.Worksheets.Item($SheetName)
    $worksheet.ExportAsFixedFormat(0, $OutputPath)
    if (-not (Test-Path -LiteralPath $OutputPath -PathType Leaf)) {
        throw "PDF_OUTPUT_MISSING"
    }
    if ((Get-Item -LiteralPath $OutputPath).Length -eq 0) {
        throw "PDF_ZERO_BYTE"
    }
    $result.status = "PDF_EXPORTED"
    $result.error_code = ""
}
catch {
    $message = [string]$_.Exception.Message
    if ($message -match "^[A-Z][A-Z0-9_]+$") {
        $result.error_code = $message
    }
}
finally {
    if ($null -ne $worksheet) {
        try { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($worksheet) } catch {}
    }
    if ($null -ne $workbook) {
        try { $workbook.Close($false) } catch {}
        try { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($workbook) } catch {}
    }
    if ($null -ne $excel) {
        try { $excel.Quit() } catch {}
        try { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($excel) } catch {}
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

$result | ConvertTo-Json -Compress
if ($result.status -eq "FAILED") { exit 1 }
