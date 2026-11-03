$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

function Read-EntryText($Entry) {
    $reader = [IO.StreamReader]::new($Entry.Open(),[Text.Encoding]::UTF8)
    try { $reader.ReadToEnd() } finally { $reader.Dispose() }
}
function Text-Hash([string]$Text) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try { [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Text))).Replace('-','') }
    finally { $sha.Dispose() }
}
$b64 = @'
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
'@
$packed = [IO.MemoryStream]::new([Convert]::FromBase64String($b64))
$gzip = [IO.Compression.GZipStream]::new($packed,[IO.Compression.CompressionMode]::Decompress)
$reader = [IO.StreamReader]::new($gzip,[Text.Encoding]::UTF8)
try { $patch = $reader.ReadToEnd() | ConvertFrom-Json }
finally { $reader.Dispose(); $packed.Dispose() }

$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Filter = 'Проект Шины (*.xasm)|*.xasm'
$dialog.Title = 'Выберите Opera_PC_40.xasm'
if ($dialog.ShowDialog() -ne 'OK') { return }
$source = $dialog.FileName
$target = Join-Path ([IO.Path]::GetDirectoryName($source)) 'Opera_PC_41.xasm'
if (Test-Path -LiteralPath $target) { throw 'Файл Opera_PC_41.xasm уже есть. Переименуйте его перед повтором.' }
$prefix = 'Komandor/Opera_PC/Основной/'
$inputZip = [IO.Compression.ZipFile]::OpenRead($source)
try {
    $entry = $inputZip.GetEntry($prefix + 'InfoBases.xbsl')
    if ($null -eq $entry) { throw 'В выбранном проекте нет InfoBases.xbsl.' }
    $server = Read-EntryText $entry
    if ((Text-Hash $server) -ne '716C2443F5DF3929E368CF905A40AEC55E26D5C8D2DE1B70FBBF2DC9EEFFA384') {
        throw 'Выберите исходный Opera_PC_40.xasm из предыдущего шага.'
    }
    foreach ($edit in $patch.edits) {
        if (-not $server.Contains([string]$edit.old)) { throw 'Не найден фрагмент для исправления.' }
        $server = $server.Replace([string]$edit.old,[string]$edit.new)
    }
    if ((Text-Hash $server) -ne '108820855CE84CEBD8F6DD87A2844B12A0A3E72734E0A5DA82B1EA5F6E3C3B87') { throw 'Текст исправления повреждён.' }
    $assembly = Read-EntryText ($inputZip.GetEntry('Assembly.yaml'))
    if (-not $assembly.Contains('Version: 1.0-40')) { throw 'Нужна версия проекта 1.0-40.' }
    $assembly = $assembly.Replace('Version: 1.0-40','Version: 1.0-41')
    $file = [IO.File]::Create($target)
    try {
        $outputZip = [IO.Compression.ZipArchive]::new($file,[IO.Compression.ZipArchiveMode]::Create,$true,[Text.Encoding]::UTF8)
        try {
            foreach ($entry in $inputZip.Entries) {
                $newEntry = $outputZip.CreateEntry($entry.FullName,[IO.Compression.CompressionLevel]::Optimal)
                $destination = $newEntry.Open()
                try {
                    if ($entry.FullName -eq ($prefix + 'InfoBases.xbsl')) {
                        $bytes = [Text.Encoding]::UTF8.GetBytes($server)
                        $destination.Write($bytes,0,$bytes.Length)
                    } elseif ($entry.FullName -eq 'Assembly.yaml') {
                        $bytes = [Text.Encoding]::UTF8.GetBytes($assembly)
                        $destination.Write($bytes,0,$bytes.Length)
                    } else {
                        $content = $entry.Open()
                        try { $content.CopyTo($destination) } finally { $content.Dispose() }
                    }
                } finally { $destination.Dispose() }
            }
            foreach ($item in $patch.files.PSObject.Properties) {
                $newEntry = $outputZip.CreateEntry($prefix + $item.Name,[IO.Compression.CompressionLevel]::Optimal)
                $destination = $newEntry.Open()
                try {
                    $bytes = [Text.Encoding]::UTF8.GetBytes([string]$item.Value)
                    $destination.Write($bytes,0,$bytes.Length)
                } finally { $destination.Dispose() }
            }
        } finally { $outputZip.Dispose() }
    } finally { $file.Dispose() }
} finally { $inputZip.Dispose() }
Write-Host ('READY: ' + $target)
