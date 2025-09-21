param(
  [Parameter(Mandatory = $true)]
  [string]$Cities,  # e.g. "seattle,portland"
  [string]$RepoRoot = ".",
  [string]$VenvPath = ".\.venv\Scripts\python.exe",
  [string]$ProfileJson = "luma-bot\profile.json",
  [int]$MaxPerCity = 0,   # 0 = unlimited
  [switch]$Headless
)

# Ensure we run from repo root (so relative paths match)
Set-Location -Path $RepoRoot

# Build arg list
$py = $VenvPath
$script = "luma-bot\register_events.py"

$argList = @("--cities", $Cities, "--profile-json", $ProfileJson)
if ($MaxPerCity -gt 0) {
  $argList += @("--max-per-city", "$MaxPerCity")
}
if ($Headless) {
  $argList += "--headless"
}

Write-Host "[RUN] $py $script $($argList -join ' ')"
& $py $script @argList
if ($LASTEXITCODE -ne 0) {
  Write-Host "[ERROR] Bot exited with code $LASTEXITCODE"
  exit $LASTEXITCODE
}

# For Windows Task Scheduler, point the action to powershell.exe and set Arguments to something like:
# -ExecutionPolicy Bypass -File "C:\path\to\repo\scripts\run-luma-bot.ps1" -Cities "seattle,portland" -RepoRoot "C:\path\to\repo" -VenvPath "C:\path\to\repo\.venv\Scripts\python.exe" -Headless
