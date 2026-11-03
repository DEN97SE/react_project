# Read-only check based on the API example supplied with the integration documents.
# Run on the 1C application server. No messages are sent.
# {{ semidockij - 22.10.2026 - Проверка авторизации и списка каналов Шины
$busBaseUrl = 'http://program58:9090'
$busApplication = 'Opera-PC'
$busReportLines = New-Object 'System.Collections.Generic.List[string]'
$busReportPath = Join-Path $env:TEMP '1c_bus_diagnostic.txt'
$busStage = 'INITIALIZATION'
$busCredential = $null
$busPair = $null
$busBasic = $null
$busTokenResponse = $null
$busTokenBody = $null
$busToken = $null
$busStageResponse = $null

function Write-BusDiagnostic {
    param([string]$Line)
    $busReportLines.Add($Line)
    Write-Host $Line
}

try {
    Write-BusDiagnostic ('Server: ' + $env:COMPUTERNAME)
    Write-BusDiagnostic ('Application: ' + $busBaseUrl + '/applications/' + $busApplication)

    # The user name is the client key entered in Astor's external service settings.
    # The password is its client secret; Get-Credential masks the password.
    $busCredential = Get-Credential -Message 'Enter the SAME external-service client key and secret as in ASTOR (not your Windows or 1C database login).'
    if ($null -eq $busCredential) {
        throw 'Credential entry cancelled.'
    }

    # Disable HTTP proxy only for this PowerShell process and restore it in finally.
    $busPreviousProxy = [System.Net.WebRequest]::DefaultWebProxy
    [System.Net.WebRequest]::DefaultWebProxy = $null

    $busStage = 'TOKEN'
    $busPair = $busCredential.UserName + ':' + $busCredential.GetNetworkCredential().Password
    $busBasic = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($busPair))
    $busStageResponse = Invoke-WebRequest -UseBasicParsing -Method Post `
        -Uri ($busBaseUrl + '/auth/oidc/token') `
        -Headers @{ Authorization = 'Basic ' + $busBasic } `
        -ContentType 'application/x-www-form-urlencoded' `
        -Body 'grant_type=client_credentials' -TimeoutSec 20 -ErrorAction Stop
    $busTokenResponse = $busStageResponse
    Write-BusDiagnostic ('TOKEN HTTP: ' + [int]$busTokenResponse.StatusCode)
    $busTokenBody = $busTokenResponse.Content | ConvertFrom-Json -ErrorAction Stop
    $busToken = $busTokenBody.id_token
    if ([string]::IsNullOrWhiteSpace([string]$busToken)) {
        throw 'No id_token in the response. Token values are intentionally omitted.'
    }

    $busStage = 'CHANNELS'
    $busStageResponse = Invoke-WebRequest -UseBasicParsing -Method Get `
        -Uri ($busBaseUrl + '/applications/' + $busApplication + '/sys/esb/runtime/channels') `
        -Headers @{ Authorization = 'Bearer ' + $busToken } `
        -TimeoutSec 20 -ErrorAction Stop
    Write-BusDiagnostic ('CHANNELS HTTP: ' + [int]$busStageResponse.StatusCode)
    $busChannelBody = $busStageResponse.Content | ConvertFrom-Json -ErrorAction Stop
    $busItems = @($busChannelBody.items | Where-Object { $null -ne $_ })
    Write-BusDiagnostic ('CHANNEL COUNT: ' + $busItems.Count)
    if ($busItems.Count -gt 0) {
        $busTable = $busItems | Select-Object channel, destination | Format-Table -AutoSize | Out-String -Width 260
        Write-BusDiagnostic $busTable.TrimEnd()
    }
    Write-BusDiagnostic 'FINISHED: API check only. Message delivery has not been tested.'
}
catch {
    Write-BusDiagnostic ('FAILED STAGE: ' + $busStage)
    if ($null -ne $_.Exception.Response) {
        Write-BusDiagnostic ('FAILED HTTP: ' + [int]$_.Exception.Response.StatusCode)
    }
    # Do not print request headers, credentials, token responses, or stack variables.
    Write-BusDiagnostic ('ERROR: ' + $_.Exception.Message)
}
finally {
    if (Test-Path variable:busPreviousProxy) {
        [System.Net.WebRequest]::DefaultWebProxy = $busPreviousProxy
    }
    $busPair = $null
    $busBasic = $null
    $busToken = $null
    $busTokenBody = $null
    $busTokenResponse = $null
    $busStageResponse = $null
    $busCredential = $null
    $busReportLines | Set-Content -LiteralPath $busReportPath -Encoding UTF8
    Write-Host ('Report: ' + $busReportPath)
}
# }} semidockij - 22.10.2026
