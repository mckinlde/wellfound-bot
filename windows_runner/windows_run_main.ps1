param(
  [string]$AreaSet = "atlanta",
  [string]$SendEmails = "--send_emails",
  [string]$ScriptPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host ("[INFO] Starting scraper at {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))

# Resolve repo root and default entry script
$RunnerDir   = $PSScriptRoot
$ProjectRoot = Split-Path $RunnerDir -Parent
Set-Location -Path $ProjectRoot

# Prefer the venv's python if present, else 'python' or 'python3'
$VenvPy = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (Test-Path $VenvPy) {
  $pythonCmd = $VenvPy
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
  $pythonCmd = "python"
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
  $pythonCmd = "python3"
} else {
  throw "[ERROR] Python 3 not found on PATH."
}

# Default entry script at repo root unless -ScriptPath provided
if (-not $ScriptPath) { $ScriptPath = Join-Path $ProjectRoot "main.py" }
$ScriptPath = Resolve-Path -Path $ScriptPath -ErrorAction SilentlyContinue
if (-not $ScriptPath) { throw "[ERROR] Entry script not found. Pass -ScriptPath .\path\to\script.py" }

# Clean problematic env vars that can cause 'platform independent libraries <prefix>'
Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue

# Optional env discovery
if (-not $env:GECKODRIVER_PATH) {
  $localGecko = Join-Path $RunnerDir "bin\geckodriver.exe"
  if (Test-Path $localGecko) { $env:GECKODRIVER_PATH = $localGecko }
}
if (-not $env:FIREFOX_BIN) {
  try {
    $ffReg = Get-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\firefox.exe" -ErrorAction Stop
    $ff = $ffReg."(Default)"; if ($ff -and (Test-Path $ff)) { $env:FIREFOX_BIN = $ff }
  } catch { }
  if (-not $env:FIREFOX_BIN) {
    $ffStd = "C:\Program Files\Mozilla Firefox\firefox.exe"
    if (Test-Path $ffStd) { $env:FIREFOX_BIN = $ffStd }
  }
}

Write-Host ("[INFO] project root: {0}" -f $ProjectRoot)
Write-Host ("[INFO] entry script: {0}" -f $ScriptPath)
Write-Host ("[INFO] area_set: {0}" -f $AreaSet)
Write-Host ("[INFO] email flag: {0}" -f $SendEmails)
if ($env:GECKODRIVER_PATH) { Write-Host ("[INFO] geckodriver: {0}" -f $env:GECKODRIVER_PATH) }
if ($env:FIREFOX_BIN)     { Write-Host ("[INFO] firefox:     {0}" -f $env:FIREFOX_BIN) }

try {
  $cmd = '{0} "{1}" "{2}" {3}' -f $pythonCmd, $ScriptPath, $AreaSet, $SendEmails
  Write-Host ("[INFO] running: {0}" -f $cmd)
  & $pythonCmd $ScriptPath $AreaSet $SendEmails
  if ($LASTEXITCODE -ne 0) { throw ("[ERROR] Python exited with code {0}" -f $LASTEXITCODE) }
  Write-Host ("[INFO] Scraper finished at {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
}
finally {
  Write-Host ("[WARN] Cleanup triggered at {0}: no-op" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
}
