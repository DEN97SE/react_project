# Administrative pilot from the central computer. No changes to 1C databases.
# Without -Register: health only. With -Register: creates/reuses one participant and checks repeat stability.
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
    if ($Health.version -ne 'opera-pc-enrollment-1') {throw 'Unexpected API version'}
    Write-Host 'PASS: endpoint version and administrative access'
    if ($Register) {
        if ($StoreId -eq [Guid]::Empty) {throw 'Store UUID is required for registration'}
        if ([string]::IsNullOrWhiteSpace($StoreName)) {$StoreName=$StoreId.ToString()}
        $Body=@{'Код'=$StoreId.ToString();'Наименование'=$StoreName;'Описание'='Enrollment API pilot'}|ConvertTo-Json -Compress
        $Stage='REGISTER'
        $First=Invoke-RestMethod -Uri $RegistrationUri -Method Post -Headers $Headers `
            -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($Body)) -TimeoutSec 60
        if ($First -is [string]) {$First=$First|ConvertFrom-Json}
        if ($First.'Код' -ne $StoreId.ToString() -or (-not $First.clientid) -or (-not $First.clientsecret)) {throw 'Incomplete response'}
        if (-not(Test-Path -LiteralPath $CacheDirectory)) {New-Item -ItemType Directory -Path $CacheDirectory|Out-Null}
        $Path=Join-Path $CacheDirectory ($StoreId.ToString()+'.json.dpapi')
        if (Test-Path -LiteralPath $Path) {
            $OldSecure=Get-Content -LiteralPath $Path -Raw|ConvertTo-SecureString
            $Old=(Unprotect $OldSecure)|ConvertFrom-Json
            if ($Old.clientid -ne $First.clientid -or $Old.clientsecret -ne $First.clientsecret) {throw 'Cache conflict; do not overwrite'}
            $Old=$null;$OldSecure=$null
        } else {
            $Protected=ConvertTo-SecureString -String ($First|ConvertTo-Json -Depth 6 -Compress) -AsPlainText -Force|ConvertFrom-SecureString
            [IO.File]::WriteAllText($Path,$Protected,[Text.Encoding]::UTF8)
        }
        Write-Host 'PASS: registration response saved in local DPAPI cache'
        $Stage='REPEAT'
        $Second=Invoke-RestMethod -Uri $RegistrationUri -Method Post -Headers $Headers `
            -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($Body)) -TimeoutSec 60
        if ($Second -is [string]) {$Second=$Second|ConvertFrom-Json}
        if ($First.'Код' -ne $Second.'Код' -or $First.clientid -ne $Second.clientid -or $First.clientsecret -ne $Second.clientsecret) {
            throw 'Repeated registration changed credentials'
        }
        Write-Host 'PASS: repeat returned the same credentials'
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
