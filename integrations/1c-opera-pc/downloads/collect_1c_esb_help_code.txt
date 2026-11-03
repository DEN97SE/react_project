# Collect documentation pages into one UTF-8 TXT. GET requests only.
# Default source: the local help server provided by the user.
# Public alternative: https://1cmycloud.com/console/help/esb/10.0/docs/
$DocsRoot = [Uri]'http://program58:9090/docs/help/'
$DesktopPath = [Environment]::GetFolderPath('Desktop')
$OutputPath = Join-Path $DesktopPath '1C_ESB_help_for_review.txt'
$PageLimit = 30
$Encoding = New-Object System.Text.UTF8Encoding($true)
$Writer = New-Object System.IO.StreamWriter($OutputPath, $false, $Encoding)
$PendingPages = New-Object 'System.Collections.Generic.Queue[string]'
$SeenPages = New-Object 'System.Collections.Generic.HashSet[string]'
$PendingPages.Enqueue(([Uri]::new($DocsRoot, 'topics/about-1c-esb/')).AbsoluteUri)
$PendingPages.Enqueue(([Uri]::new($DocsRoot, 'topics/amqp-connection/')).AbsoluteUri)
$PendingPages.Enqueue(([Uri]::new($DocsRoot, 'topics/message-transformation/')).AbsoluteUri)
$PendingPages.Enqueue($DocsRoot.AbsoluteUri)
$UsefulLinks = '(?i)amqp|integration|information|participant|group|message|routing|queue|token|access|system|doc20033|doc00115|doc20006|интеграц|информацион|участник|групп|сообщен|маршрут|очеред|ключ|токен'
$FetchedPages = 0
try {
    $Writer.WriteLine('1C ESB documentation export. Source: ' + $DocsRoot.AbsoluteUri)
    $Writer.WriteLine('HTML is preserved as text for analysis. No application settings were changed.')
    while (($PendingPages.Count -gt 0) -and ($FetchedPages -lt $PageLimit)) {
        $CurrentUrl = $PendingPages.Dequeue()
        if (-not $SeenPages.Add($CurrentUrl)) { continue }
        $FetchedPages++
        Write-Host ('Reading ' + $FetchedPages + ': ' + $CurrentUrl)
        $Writer.WriteLine("`r`n===== PAGE: " + $CurrentUrl + " =====`r`n")
        try {
            $Response = Invoke-WebRequest -Uri $CurrentUrl -UseBasicParsing -TimeoutSec 20 -ErrorAction Stop
            $Html = [string]$Response.Content
            $Writer.WriteLine('HTTP status: ' + [string]$Response.StatusCode)
            $Writer.WriteLine($Html)
            $Links = [regex]::Matches($Html, '(?is)<a\b[^>]*href\s*=\s*["''](?<url>[^"'']+)["''][^>]*>(?<label>.*?)</a>')
            foreach ($Link in $Links) {
                $Href = [System.Net.WebUtility]::HtmlDecode($Link.Groups['url'].Value)
                if (($Href -match '^(#|javascript:|mailto:)') -or (($Href + ' ' + $Link.Groups['label'].Value) -notmatch $UsefulLinks)) { continue }
                try {
                    $Resolved = [Uri]::new([Uri]$CurrentUrl, $Href)
                    $WithoutFragment = $Resolved.GetLeftPart([UriPartial]::Path)
                    if (($Resolved.Scheme -ne $DocsRoot.Scheme) -or ($Resolved.Authority -ne $DocsRoot.Authority)) { continue }
                    if (-not $Resolved.AbsolutePath.StartsWith($DocsRoot.AbsolutePath, [StringComparison]::OrdinalIgnoreCase)) { continue }
                    if ($Resolved.AbsolutePath -match '(?i)\.(js|css|png|jpg|jpeg|svg|ico|woff|zip|pdf)$') { continue }
                    if (-not $SeenPages.Contains($WithoutFragment)) { $PendingPages.Enqueue($WithoutFragment) }
                } catch {
                    $Writer.WriteLine('Link not resolved: ' + $Href)
                }
            }
        } catch {
            $Writer.WriteLine('READ ERROR: ' + $_.Exception.Message)
        }
        $Writer.Flush()
    }
} finally {
    $Writer.Dispose()
}
Write-Host ('Finished. File: ' + $OutputPath)
Write-Host 'Attach this TXT file to the chat. It contains documentation pages only.'
