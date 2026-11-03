$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms

$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Filter = '1C ESB project (*.xasm)|*.xasm'
$dialog.Title = 'Выберите Opera_PC_39_e1490c.xasm'
if ($dialog.ShowDialog() -ne 'OK') { return }
$source = $dialog.FileName

$expected = '5E65A71049FBD142CC2C489C590C063966DB9F33A98910372D378A1FDDEB0D69'
if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $expected) {
    throw 'Выбран другой файл. Нужен именно присланный Opera_PC_39_e1490c.xasm.'
}

$bytes = [IO.File]::ReadAllBytes($source)
$flags = @(6,764,1667,2820,3826,5006,5206,5487,5863,6163,6450,6542,6994,
           11738,11828,11919,12010,12098,12186,12296,12406,12524,12642,
           12756,12862,12968)
foreach ($position in $flags) {
    $bytes[$position] = $bytes[$position] -band 0xF7
}
$bytes[6452] = 8
$bytes[12758] = 8

$target = Join-Path ([IO.Path]::GetDirectoryName($source)) 'Opera_PC_39_fixed.xasm'
[IO.File]::WriteAllBytes($target, $bytes)
$expectedResult = 'AC71691544E0509DB4D2EFCC345AA7202B7DA1366D62A1BA8326EA038494F593'
if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $expectedResult) {
    throw 'Контрольная сумма результата не совпала.'
}
Write-Host ('READY: ' + $target)
