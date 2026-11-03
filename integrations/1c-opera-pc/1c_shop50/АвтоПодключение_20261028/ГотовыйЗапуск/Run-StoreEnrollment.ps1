# Run on the CENTRAL Windows computer with 1C COMConnector installed.
# Preview is the default. -Apply enables server registration and writes 1C settings.
# Administrative ESB credentials stay on this computer; they are never passed to shop databases.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$RegistryCsv,
    [Parameter(Mandatory=$true)][Uri]$RegistrationUri,
    [string]$OperaServiceAddress = '',
    [string]$PcServiceAddress = '',
    [string]$OperaRecipient = 'BackendOpera',
    [string]$PcRecipient = 'Backend_PC',
    [string]$CacheDirectory = (Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'AstorEsbEnrollment'),
    [switch]$Apply
)
$ErrorActionPreference = 'Stop'

function ConvertFrom-ProtectedText([Security.SecureString]$Value) {
    $Pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Value)
    try { [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Pointer) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Pointer) }
}
function Quote-ConnectionValue([string]$Value) { '"' + $Value.Replace('"','""') + '"' }
function Request-Token([string]$ClientId, [string]$ClientSecret) {
    $Basic = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($ClientId + ':' + $ClientSecret))
    $Token = Invoke-RestMethod -Uri $TokenUri -Method Post -Headers @{Authorization=('Basic '+$Basic)} `
        -ContentType 'application/x-www-form-urlencoded' -Body 'grant_type=client_credentials' -TimeoutSec 30
    if ([string]::IsNullOrWhiteSpace([string]$Token.id_token)) { throw 'Token response incomplete' }
    return [string]$Token.id_token
}

$Rows = @(Import-Csv -LiteralPath $RegistryCsv -Encoding UTF8)
if ($Rows.Count -eq 0) { throw 'Registry is empty' }
$UniqueStores = @{}
$UniqueDatabases = @{}
foreach ($Row in $Rows) {
    foreach ($Field in @('StoreId','Name','Server','Ref')) {
        if ([string]::IsNullOrWhiteSpace([string]$Row.$Field)) { throw ('Missing column/value: '+$Field) }
    }
    $Guid = ([Guid]::Parse($Row.StoreId)).ToString()
    if ($Guid -eq [Guid]::Empty.ToString()) { throw 'Empty store UUID' }
    if ($UniqueStores.ContainsKey($Guid)) { throw 'Duplicate store UUID in registry' }
    $UniqueStores[$Guid] = $true
    $DatabaseKey = $Row.Server.ToLowerInvariant() + '/' + $Row.Ref.ToLowerInvariant()
    if ($UniqueDatabases.ContainsKey($DatabaseKey)) { throw 'Database appears more than once' }
    $UniqueDatabases[$DatabaseKey] = $true
    $Row.StoreId = $Guid
}
if (-not (Test-Path -LiteralPath $CacheDirectory)) {
    New-Item -ItemType Directory -Path $CacheDirectory | Out-Null
}
$DbCredential = Get-Credential -Message '1C database administrator for this batch (Data administration right required)'
$DbPassword = $DbCredential.GetNetworkCredential().Password
$TokenUri = [Uri]::new($RegistrationUri.GetLeftPart([UriPartial]::Authority) + '/auth/oidc/token')
$BootstrapClientId = ''
$BootstrapSecret = $null
$BootstrapToken = ''
$BootstrapTokenTime = [DateTime]::MinValue
if ($Apply) {
    $BootstrapClientId = Read-Host 'ESB administrative API client ID (kept on this computer)'
    $BootstrapSecret = Read-Host 'ESB administrative API client secret' -AsSecureString
}
$Connector = New-Object -ComObject 'V83.COMConnector'
$Report = New-Object 'System.Collections.Generic.List[object]'
$ToVerify = New-Object 'System.Collections.Generic.List[object]'

foreach ($Row in $Rows) {
    $Connection = $null
    $Stage = 'CONNECT'
    $Result = [pscustomobject]@{StoreId=$Row.StoreId;Name=$Row.Name;Status='';Stage='';HttpStatus='';SettingsVerified=$false;CredentialsVerified=$false}
    try {
        $ConnectionString = 'Srvr='+(Quote-ConnectionValue $Row.Server)+';Ref='+(Quote-ConnectionValue $Row.Ref)+
            ';Usr='+(Quote-ConnectionValue $DbCredential.UserName)+';Pwd='+(Quote-ConnectionValue $DbPassword)+';'
        $Connection = $Connector.Connect($ConnectionString)
        $ConnectionString = $null
        $Stage = 'PREFLIGHT'
        $State = ([string]$Connection.'КХ_ПолучитьДанныеРегистрацииШины'()) | ConvertFrom-Json
        if ([string]$State.store_id -ne $Row.StoreId) { throw 'Store UUID mismatch' }
        if (-not $State.services_present) { throw 'Integration services missing' }
        if (((-not $State.opera_address_ready) -and [string]::IsNullOrWhiteSpace($OperaServiceAddress)) -or
            ((-not $State.pc_address_ready) -and [string]::IsNullOrWhiteSpace($PcServiceAddress))) {
            throw 'Service addresses must be supplied for an unconfigured database'
        }
        $CachePath = Join-Path $CacheDirectory ($Row.StoreId+'.json.dpapi')
        if (-not $State.can_apply) {
            if ($Apply -and (Test-Path -LiteralPath $CachePath)) {
                $CachedSecure = Get-Content -LiteralPath $CachePath -Raw | ConvertTo-SecureString
                $CachedJson = ConvertFrom-ProtectedText $CachedSecure
                $Cached = $CachedJson | ConvertFrom-Json
                if ([string]$Cached.'Код' -eq $Row.StoreId) {
                    $Verified = ([string]$Connection.'КХ_ПроверитьЗаписьРегистрацииШины'(
                        $Row.StoreId,[string]$Cached.clientid,$OperaServiceAddress,$PcServiceAddress)) | ConvertFrom-Json
                    if ($Verified.settings_verified -and (-not $Verified.error)) {
                        $Result.Status='ALREADY_CONFIGURED';$Result.SettingsVerified=$true
                    }
                }
                $CachedJson=$null;$Cached=$null;$CachedSecure=$null
            }
            if (-not $Result.Status) { $Result.Status='BLOCKED_EXISTING_QUEUE_OR_SOURCE' }
            continue
        }
        if (-not $Apply) { $Result.Status='READY_PREVIEW';continue }

        $Stage = 'REGISTRATION'
        if (Test-Path -LiteralPath $CachePath) {
            $CachedSecure = Get-Content -LiteralPath $CachePath -Raw | ConvertTo-SecureString
            $RegistrationJson = ConvertFrom-ProtectedText $CachedSecure
            $Registration = $RegistrationJson | ConvertFrom-Json
        } else {
            if (([DateTime]::UtcNow-$BootstrapTokenTime).TotalMinutes -ge 45) {
                $AdminSecret = ConvertFrom-ProtectedText $BootstrapSecret
                try { $BootstrapToken = Request-Token $BootstrapClientId $AdminSecret }
                finally { $AdminSecret=$null }
                $BootstrapTokenTime=[DateTime]::UtcNow
            }
            $Body = @{'Код'=$Row.StoreId;'Наименование'=$Row.Name;'Описание'='Source database: Opera and PC'} | ConvertTo-Json -Compress
            $Registration = Invoke-RestMethod -Uri $RegistrationUri -Method Post `
                -Headers @{Authorization=('Bearer '+$BootstrapToken);Accept='application/json'} `
                -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($Body)) -TimeoutSec 60
            if ($Registration -is [string]) { $Registration = $Registration | ConvertFrom-Json }
            $RegistrationJson = $Registration | ConvertTo-Json -Depth 6 -Compress
        }
        if ([string]$Registration.'Код' -ne $Row.StoreId -or
            [string]::IsNullOrWhiteSpace([string]$Registration.clientid) -or
            [string]::IsNullOrWhiteSpace([string]$Registration.clientsecret)) { throw 'Registration response incomplete' }
        if (-not (Test-Path -LiteralPath $CachePath)) {
            $Protected = ConvertTo-SecureString -String $RegistrationJson -AsPlainText -Force | ConvertFrom-SecureString
            $Temporary = $CachePath+'.tmp'
            [IO.File]::WriteAllText($Temporary,$Protected,[Text.Encoding]::UTF8)
            Move-Item -LiteralPath $Temporary -Destination $CachePath
        }
        $Stage='VERIFY_CREDENTIALS'
        $UnusedTicket = Request-Token ([string]$Registration.clientid) ([string]$Registration.clientsecret)
        $UnusedTicket=$null
        $Result.CredentialsVerified=$true
        $Stage='APPLY'
        $Applied = ([string]$Connection.'КХ_ПрименитьРегистрациюШины'(
            $RegistrationJson,$Row.StoreId,$OperaServiceAddress,$PcServiceAddress,$OperaRecipient,$PcRecipient)) | ConvertFrom-Json
        if ($Applied.error -or (-not $Applied.applied)) { throw 'Settings application incomplete' }
        $Result.Status='APPLIED_PENDING_SETTINGS_VERIFY'
        $ToVerify.Add([pscustomobject]@{Row=$Row;Result=$Result;ClientId=[string]$Registration.clientid})
    } catch {
        $Result.Status='ERROR'
        if ($null -ne $_.Exception.Response) {
            try {$Result.HttpStatus=[string][int]$_.Exception.Response.StatusCode} catch {}
        }
        # Do not output exceptions, HTTP bodies or COM parameters: they may contain secrets.
    } finally {
        $Result.Stage=$Stage
        $Report.Add($Result)
        Write-Host ($Row.StoreId+' '+$Result.Status+' ['+$Stage+'] HTTP='+$Result.HttpStatus)
        if ($null -ne $Connection) { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($Connection) }
        $Registration=$null;$RegistrationJson=$null;$CachedSecure=$null
    }
}
if ($ToVerify.Count -gt 0) {
    Write-Host 'Waiting 21 seconds once for the platform settings cache, then verifying saved settings.'
    Start-Sleep -Seconds 21
    foreach ($Item in $ToVerify) {
        $Connection=$null
        try {
            $ConnectionString='Srvr='+(Quote-ConnectionValue $Item.Row.Server)+';Ref='+(Quote-ConnectionValue $Item.Row.Ref)+
                ';Usr='+(Quote-ConnectionValue $DbCredential.UserName)+';Pwd='+(Quote-ConnectionValue $DbPassword)+';'
            $Connection=$Connector.Connect($ConnectionString);$ConnectionString=$null
            $Verified=([string]$Connection.'КХ_ПроверитьЗаписьРегистрацииШины'(
                $Item.Row.StoreId,$Item.ClientId,$OperaServiceAddress,$PcServiceAddress)) | ConvertFrom-Json
            $Item.Result.SettingsVerified=([bool]$Verified.settings_verified -and (-not [bool]$Verified.error))
            $Item.Result.Status=if ($Item.Result.SettingsVerified) {'SETTINGS_VERIFIED_DELIVERY_NOT_TESTED'} else {'SETTINGS_VERIFY_FAILED'}
        } catch { $Item.Result.Status='SETTINGS_VERIFY_FAILED' }
        finally {
            if ($null -ne $Connection) { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($Connection) }
        }
    }
}
$ReportPath=Join-Path $CacheDirectory ('results-'+[DateTime]::Now.ToString('yyyyMMdd-HHmmss')+'.csv')
$Report | Export-Csv -LiteralPath $ReportPath -NoTypeInformation -Encoding UTF8
[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($Connector)
$DbPassword=$null;$BootstrapToken=$null;$BootstrapSecret=$null
Write-Host ('Report: '+$ReportPath)
Write-Host 'Saved settings and token authentication are separate from shop-to-bus delivery and application ACK.'
