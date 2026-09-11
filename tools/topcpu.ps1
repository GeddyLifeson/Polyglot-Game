$a = @{}; Get-Process | ForEach-Object { $a[$_.Id] = $_.CPU }
Start-Sleep -Seconds 4
Get-Process | ForEach-Object {
  if ($a.ContainsKey($_.Id) -and $_.CPU -ne $null) {
    $d = $_.CPU - $a[$_.Id]
    if ($d -gt 0.2) { [pscustomobject]@{ Name = $_.Name; Id = $_.Id; CorePct = [math]::Round($d / 4 * 100 / 16, 1) } }
  }
} | Sort-Object CorePct -Descending | Select-Object -First 10 | Format-Table -AutoSize
