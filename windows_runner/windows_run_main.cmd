@echo off
REM Lets you double-click from Explorer. Pass args through to the PS script.
powershell -ExecutionPolicy Bypass -File "%~dp0windows_run_main.ps1" %*

@REM Usage examples (PowerShell or Run dialog):
@REM Default: .\windows_run_main.ps1
@REM With area only: .\windows_run_main.ps1 atlanta
@REM With both args: .\windows_run_main.ps1 atlanta --send_emails
@REM Or just double-click windows_run_main.cmd (you can also create a Desktop shortcut).