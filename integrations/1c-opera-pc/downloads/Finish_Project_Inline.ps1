$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
if ($null -eq $patch -or [string]::IsNullOrWhiteSpace($out) -or -not (Test-Path -LiteralPath $out)) {
    throw 'Run this in the same PowerShell window as the previous block.'
}
$zip = [System.IO.Compression.ZipFile]::Open($out,[System.IO.Compression.ZipArchiveMode]::Update)
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
