param(
  [Parameter(Mandatory = $true)] [string]$Cities,
  [string]$RepoRoot = ".",
  [string]$VenvPath = ".\.venv\Scripts\python.exe",
  [string]$ProfileJson = "luma_bot\profile.json",
  [int]$MaxPerCity = 0,
  [switch]$Headless,
  [switch]$SetupFirst   # <— add this
)

Set-Location -Path $RepoRoot

if ($SetupFirst) {
  $setupArgs = @("--cities", $Cities)
  if ($MaxPerCity -gt 0) { $setupArgs += @("--max-per-city", "$MaxPerCity") }
  # NOTE: setup script performs the handoff to register_events for you.
  & $VenvPath "luma_bot\setup_driver_session.py" @setupArgs
  exit $LASTEXITCODE
}

# normal direct run
$argList = @("--cities", $Cities, "--profile-json", $ProfileJson)
if ($MaxPerCity -gt 0) { $argList += @("--max-per-city", "$MaxPerCity") }
if ($Headless) { $argList += "--headless" }
& $VenvPath "luma_bot\register_events.py" @argList
exit $LASTEXITCODE

# Usage example:
# # first time (does interactive logins, then runs the bot)
# powershell -ExecutionPolicy Bypass -File .\luma_bot\run_luma_bot.ps1 -Cities "seattle" -SetupFirst

# # later (headless)
# powershell -ExecutionPolicy Bypass -File .\luma_bot\run_luma_bot.ps1 -Cities "seattle,portland" -Headless
