# Administrative pilot from the central computer. No changes to 1C databases.
# Without -Register: health only. With -Register: creates one participant or reads its local cache; checks that repeated POST is rejected.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][Uri]$RegistrationUri,
    [Guid]$StoreId = [Guid]::Empty,
    [string]$StoreName = '',
    [string]$CacheDirectory = (Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'AstorEsbEnrollment'),
    [switch]$Register
)
$ErrorActionPreference='Stop'
$ClientId=Read-Host 'ESB administrative API client ID'
$Secret=Read-Host 'ESB administrative API client secret' -AsSecureString
$AuthUri=[Uri]::new($RegistrationUri.GetLeftPart([UriPartial]::Authority)+'/auth/oidc/token')
function Unprotect([Security.SecureString]$Value) {
    $Pointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($Value)
    try {[Runtime.InteropServices.Marshal]::PtrToStringBSTR($Pointer)}
    finally {[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Pointer)}
}
function Token([string]$Id,[string]$Password) {
    $Basic=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Id+':'+$Password))
    $Reply=Invoke-RestMethod -Uri $AuthUri -Method Post -Headers @{Authorization=('Basic '+$Basic)} `
        -ContentType 'application/x-www-form-urlencoded' -Body 'grant_type=client_credentials' -TimeoutSec 30
    if (-not $Reply.id_token) {throw 'Token response incomplete'}
    return [string]$Reply.id_token
}
$Stage='ADMIN_AUTH'
try {
    $Plain=Unprotect $Secret
    try {$Ticket=Token $ClientId $Plain} finally {$Plain=$null}
    $Headers=@{Authorization=('Bearer '+$Ticket);Accept='application/json'}
    $Stage='HEALTH'
    $HealthUri=[Uri]::new($RegistrationUri,'./health')
    $Health=Invoke-RestMethod -Uri $HealthUri -Headers $Headers -TimeoutSec 30
    if ($Health -is [string]) {$Health=$Health|ConvertFrom-Json}
    if ($Health.version -ne 'opera-pc-enrollment-2') {throw 'Unexpected API version'}
    Write-Host 'PASS: endpoint version and administrative access'
    if ($Register) {
        if ($StoreId -eq [Guid]::Empty) {throw 'Store UUID is required for registration'}
        if ([string]::IsNullOrWhiteSpace($StoreName)) {$StoreName=$StoreId.ToString()}
        $Body=@{'Код'=$StoreId.ToString();'Наименование'=$StoreName;'Описание'='Enrollment API pilot'}|ConvertTo-Json -Compress
        $Stage='REGISTER'
        if (-not(Test-Path -LiteralPath $CacheDirectory)) {New-Item -ItemType Directory -Path $CacheDirectory|Out-Null}
        $Path=Join-Path $CacheDirectory ($StoreId.ToString()+'.json.dpapi')
        if (Test-Path -LiteralPath $Path) {
            $OldSecure=Get-Content -LiteralPath $Path -Raw|ConvertTo-SecureString
            $First=(Unprotect $OldSecure)|ConvertFrom-Json
            $OldSecure=$null
        } else {
            $First=Invoke-RestMethod -Uri $RegistrationUri -Method Post -Headers $Headers `
                -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($Body)) -TimeoutSec 60
            if ($First -is [string]) {$First=$First|ConvertFrom-Json}
            if ($First.'Код' -ne $StoreId.ToString() -or (-not $First.clientid) -or (-not $First.clientsecret)) {throw 'Incomplete response'}
            $Protected=ConvertTo-SecureString -String ($First|ConvertTo-Json -Depth 6 -Compress) -AsPlainText -Force|ConvertFrom-SecureString
            $Temporary=$Path+'.tmp'
            [IO.File]::WriteAllText($Temporary,$Protected,[Text.Encoding]::UTF8)
            Move-Item -LiteralPath $Temporary -Destination $Path
        }
        if ($First.'Код' -ne $StoreId.ToString() -or (-not $First.clientid) -or (-not $First.clientsecret)) {throw 'Invalid local cache'}
        Write-Host 'PASS: registration credentials available in local DPAPI cache'
        $Stage='REPEAT'
        $RepeatRejected=$false
        try {
            $Unexpected=Invoke-RestMethod -Uri $RegistrationUri -Method Post -Headers $Headers `
                -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($Body)) -TimeoutSec 60
            $Unexpected=$null
        } catch {
            if ($null -eq $_.Exception.Response -or [int]$_.Exception.Response.StatusCode -ne 409) {throw}
            $RepeatRejected=$true
        }
        if (-not $RepeatRejected) {throw 'Repeated registration should return HTTP 409'}
        Write-Host 'PASS: repeat rejected with HTTP 409; credentials were not reissued'
        $Stage='STORE_AUTH'
        $UnusedTicket=Token ([string]$First.clientid) ([string]$First.clientsecret)
        $UnusedTicket=$null
        Write-Host 'PASS: issued credentials authenticate at the ESB token endpoint'
        Write-Host 'Verify both group memberships in ESB. No 1C database settings were changed by this test.'
    }
} catch {
    $HttpStatus=''
    if ($null -ne $_.Exception.Response) {
        try {$HttpStatus=[string][int]$_.Exception.Response.StatusCode} catch {}
    }
    Write-Host ('FAILED at '+$Stage+' HTTP='+$HttpStatus+'. Do not post credentials or raw HTTP response bodies.')
    exit 1
} finally {$Ticket=$null;$Headers=$null;$Secret=$null;$First=$null;$Second=$null}
