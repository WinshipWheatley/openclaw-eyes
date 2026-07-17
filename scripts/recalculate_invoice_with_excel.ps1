param(
    [Parameter(Mandatory = $true)][string]$InputPath,
    [Parameter(Mandatory = $true)][string]$OutputPath,
    [int]$TimeoutSeconds = 120
)

$ErrorActionPreference = "Stop"
$excel = $null
$workbook = $null
$result = [ordered]@{
    status = "FAILED"
    error_code = "EXCEL_RECALC_FAILED"
    excel_version = ""
    excel_build = ""
    calculation_state = "unknown"
    reopen_count = 0
}

try {
    if (-not (Test-Path -LiteralPath $InputPath -PathType Leaf)) {
        throw "SOURCE_WORKBOOK_MISSING"
    }
    if (Test-Path -LiteralPath $OutputPath) {
        throw "RECALC_OUTPUT_ALREADY_EXISTS"
    }

    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $excel.AskToUpdateLinks = $false
    $excel.EnableEvents = $false
    $excel.AutomationSecurity = 3
    $result.excel_version = [string]$excel.Version
    $result.excel_build = [string]$excel.Build

    $workbook = $excel.Workbooks.Open($InputPath, 0, $true)
    if ($workbook.HasVBProject) {
        throw "MACROS_PRESENT"
    }
    $links = $workbook.LinkSources(1)
    if ($null -ne $links) {
        throw "EXTERNAL_LINKS_PRESENT"
    }

    $excel.Calculation = -4105
    $excel.CalculateFullRebuild()
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([int]$excel.CalculationState -ne 0) {
        if ([DateTime]::UtcNow -ge $deadline) {
            throw "CALCULATION_TIMEOUT"
        }
        Start-Sleep -Milliseconds 100
    }
    $result.calculation_state = "xlDone"
    $workbook.SaveAs($OutputPath, 51)
    $workbook.Close($false)
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($workbook)
    $workbook = $null

    for ($index = 0; $index -lt 2; $index++) {
        $check = $excel.Workbooks.Open($OutputPath, 0, $true)
        try {
            if ($check.HasVBProject) {
                throw "MACROS_PRESENT_AFTER_SAVE"
            }
            $savedLinks = $check.LinkSources(1)
            if ($null -ne $savedLinks) {
                throw "EXTERNAL_LINKS_PRESENT_AFTER_SAVE"
            }
            $result.reopen_count = $result.reopen_count + 1
        }
        finally {
            $check.Close($false)
            [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($check)
        }
    }
    $result.status = "RECALCULATED"
    $result.error_code = ""
}
catch {
    $message = [string]$_.Exception.Message
    if ($message -match "^[A-Z][A-Z0-9_]+$") {
        $result.error_code = $message
    }
}
finally {
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
