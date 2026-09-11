# Exports locally-trusted root certificates that intercept TLS (Norton and friends) as PEM, so Python
# environments on this machine can append them to their certifi bundle and reach HTTPS hosts.
$certs = Get-ChildItem Cert:\LocalMachine\Root, Cert:\CurrentUser\Root | Where-Object { $_.Subject -match 'Norton|Symantec|NortonLifeLock|Gen Digital' }
$certs | ForEach-Object { Write-Output $_.Subject }
$out = ''
foreach ($c in $certs) {
  $b64 = [Convert]::ToBase64String($c.RawData, 'InsertLineBreaks')
  $out += "-----BEGIN CERTIFICATE-----`n$b64`n-----END CERTIFICATE-----`n"
}
[IO.File]::WriteAllText('C:\Users\imarl\polyglot_game\models\local_roots.pem', $out)
Write-Output ("wrote " + $out.Length + " chars")
