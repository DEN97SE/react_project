$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Filter = 'Проект Шины (*.xasm)|*.xasm'
$dialog.Title = 'Выберите Opera_PC_39_fixed.xasm'
if ($dialog.ShowDialog() -ne 'OK') { return }
$source = $dialog.FileName
$expected = 'AC71691544E0509DB4D2EFCC345AA7202B7DA1366D62A1BA8326EA038494F593'
if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $expected) {
    throw 'Выберите именно Opera_PC_39_fixed.xasm из предыдущего исправления.'
}
$b64 = @'
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
'@
$packed = [IO.MemoryStream]::new([Convert]::FromBase64String($b64))
$gzip = [IO.Compression.GZipStream]::new($packed,[IO.Compression.CompressionMode]::Decompress)
$plain = [IO.MemoryStream]::new()
try { $gzip.CopyTo($plain); $server = $plain.ToArray() }
finally { $gzip.Dispose(); $packed.Dispose(); $plain.Dispose() }
$sha = [Security.Cryptography.SHA256]::Create()
try { $actual = [BitConverter]::ToString($sha.ComputeHash($server)).Replace('-','') }
finally { $sha.Dispose() }
if ($actual -ne '716C2443F5DF3929E368CF905A40AEC55E26D5C8D2DE1B70FBBF2DC9EEFFA384') { throw 'Текст скопирован не полностью.' }

$target = Join-Path ([IO.Path]::GetDirectoryName($source)) 'Opera_PC_40.xasm'
if (Test-Path -LiteralPath $target) { throw 'Opera_PC_40.xasm уже существует. Переименуйте его перед повтором.' }
$inputZip = [IO.Compression.ZipFile]::OpenRead($source)
try {
    $file = [IO.File]::Create($target)
    try {
        $outputZip = [IO.Compression.ZipArchive]::new($file,[IO.Compression.ZipArchiveMode]::Create,$true,[Text.Encoding]::UTF8)
        try {
            foreach ($entry in $inputZip.Entries) {
                if ($entry.FullName.EndsWith('/КлючиРегистрацииМагазинов.yaml')) { continue }
                $newEntry = $outputZip.CreateEntry($entry.FullName,[IO.Compression.CompressionLevel]::Optimal)
                $destination = $newEntry.Open()
                try {
                    if ($entry.FullName.EndsWith('/InfoBases.xbsl')) {
                        $destination.Write($server,0,$server.Length)
                    } elseif ($entry.FullName -eq 'Assembly.yaml') {
                        $reader = [IO.StreamReader]::new($entry.Open(),[Text.Encoding]::UTF8)
                        try { $text = $reader.ReadToEnd().Replace('Version: 1.0-39','Version: 1.0-40') }
                        finally { $reader.Dispose() }
                        $data = [Text.Encoding]::UTF8.GetBytes($text)
                        $destination.Write($data,0,$data.Length)
                    } else {
                        $content = $entry.Open()
                        try { $content.CopyTo($destination) } finally { $content.Dispose() }
                    }
                } finally { $destination.Dispose() }
            }
        } finally { $outputZip.Dispose() }
    } finally { $file.Dispose() }
} finally { $inputZip.Dispose() }
Write-Host ('READY: ' + $target)
