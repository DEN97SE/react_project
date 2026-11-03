$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$d = New-Object System.Windows.Forms.OpenFileDialog
$d.Title = 'Select original Opera_PC 1.0-38.xasm'
$d.Filter = '1C project (*.xasm)|*.xasm'
if ($d.ShowDialog() -ne 'OK') { throw 'Cancelled' }
if ((Get-FileHash -LiteralPath $d.FileName -Algorithm SHA256).Hash.ToLowerInvariant() -ne '767e07127a67b42636f286dedabc999023dea3103b97a494c98e7384bc20af6d') {
    throw 'Select the original Opera_PC 1.0-38.xasm uploaded to this chat.'
}
$b64 = @'
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
'@
$bytes = [Convert]::FromBase64String($b64)
$sha = [Security.Cryptography.SHA256]::Create()
try { $hash = ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-','').ToLowerInvariant() }
finally { $sha.Dispose() }
if ($hash -ne '25c73b522c314a150fca50995f5370d881567e3900fe9f5ed01236269c5dbcff') { throw 'Text was copied incompletely' }
$memory = [IO.MemoryStream]::new($bytes)
$gzip = [IO.Compression.GZipStream]::new($memory,[IO.Compression.CompressionMode]::Decompress)
$reader = [IO.StreamReader]::new($gzip,[Text.Encoding]::UTF8)
try { $patch = $reader.ReadToEnd() | ConvertFrom-Json }
finally { $reader.Dispose() }
$out = Join-Path ([Environment]::GetFolderPath('Desktop')) ('Opera_PC_39_'+[Guid]::NewGuid().ToString('N').Substring(0,6)+'.xasm')
Copy-Item -LiteralPath $d.FileName -Destination $out
$zip = [IO.Compression.ZipFile]::Open($out,[IO.Compression.ZipArchiveMode]::Update)
try {
    foreach ($p in $patch.PSObject.Properties) {
        $name = 'Komandor/Opera_PC/Основной/' + $p.Name
        $old = $zip.GetEntry($name)
        if ($old) { $old.Delete() }
        $entry = $zip.CreateEntry($name)
        $writer = [IO.StreamWriter]::new($entry.Open(),[Text.UTF8Encoding]::new($false))
        try { $writer.Write([string]$p.Value) } finally { $writer.Dispose() }
    }
    $entry = $zip.GetEntry('Assembly.yaml')
    $reader = [IO.StreamReader]::new($entry.Open(),[Text.Encoding]::UTF8)
    try { $assembly = $reader.ReadToEnd() } finally { $reader.Dispose() }
    $entry.Delete()
    $entry = $zip.CreateEntry('Assembly.yaml')
    $writer = [IO.StreamWriter]::new($entry.Open(),[Text.UTF8Encoding]::new($false))
    try { $writer.Write($assembly.Replace('Version: 1.0-38','Version: 1.0-39')) } finally { $writer.Dispose() }
} finally { $zip.Dispose() }
Write-Host ('READY: ' + $out)
