# Mata o vite orfao na porta 8080 (PID via netstat) - encerramento limpo.
$line = netstat -ano | Select-String ':8080\s.*LISTENING'
if ($line) {
  $parts = ($line -split '\s+') | Where-Object { $_ -ne '' }
  $procId = [int]$parts[-1]
  Write-Output "Encerrando PID $procId..."
  $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
  if ($p) {
    $null = $p.CloseMainWindow()
    Start-Sleep -Seconds 2
    if (Get-Process -Id $procId -ErrorAction SilentlyContinue) {
      Write-Output "Processo ainda vivo apos CloseMainWindow - usando Stop-Process."
      Stop-Process -Id $procId -Force
    } else {
      Write-Output "Processo encerrado via CloseMainWindow."
    }
  }
} else {
  Write-Output "Nada escutando na 8080."
}
Start-Sleep -Seconds 1
$resto = netstat -ano | Select-String ':8080\s.*LISTENING'
if ($resto) { Write-Output "AINDA OCUPADA: $resto" } else { Write-Output "PORTA 8080 LIVRE" }
