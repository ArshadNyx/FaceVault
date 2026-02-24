<#
.SYNOPSIS
    Installs or uninstalls Face Unlock application to run at Windows startup.

.DESCRIPTION
    This script creates a scheduled task that launches the Face Unlock application
    when the user logs in to Windows.

.PARAMETER Uninstall
    Removes the startup task instead of creating it.

.PARAMETER Silent
    Runs without user prompts.

.EXAMPLE
    .\install_startup.ps1
    Installs Face Unlock to run at startup.

.EXAMPLE
    .\install_startup.ps1 -Uninstall
    Removes Face Unlock from startup.

.NOTES
    Requires Administrator privileges.
#>

param(
    [switch]$Uninstall,
    [switch]$Silent
)

# Configuration
$TaskName = "FaceUnlock"
$TaskDescription = "Face Unlock Desktop Application - Authenticates user via facial recognition"
$AppPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$BatchFile = Join-Path $AppPath "run_face_unlock.bat"

# Check if running as administrator
function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# Main script
if (-not (Test-Administrator)) {
    Write-Host "Error: This script requires Administrator privileges." -ForegroundColor Red
    Write-Host "Please right-click and select 'Run as Administrator'." -ForegroundColor Yellow
    exit 1
}

if ($Uninstall) {
    # Uninstall mode
    Write-Host "Removing Face Unlock from startup..." -ForegroundColor Yellow
    
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    
    if ($task) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$(-not $Silent)
        Write-Host "Face Unlock has been removed from startup." -ForegroundColor Green
    } else {
        Write-Host "Face Unlock startup task not found." -ForegroundColor Yellow
    }
} else {
    # Install mode
    Write-Host "Installing Face Unlock to run at startup..." -ForegroundColor Yellow
    
    # Check if batch file exists
    if (-not (Test-Path $BatchFile)) {
        Write-Host "Error: Batch file not found at: $BatchFile" -ForegroundColor Red
        exit 1
    }
    
    # Remove existing task if present
    $existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existingTask) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }
    
    # Create scheduled task
    $action = New-ScheduledTaskAction -Execute $BatchFile -WorkingDirectory $AppPath
    $trigger = New-ScheduledTaskTrigger -AtLogon
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -RunOnlyIfNetworkAvailable:$false `
        -ExecutionTimeLimit 0
    
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
    
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Description $TaskDescription
    
    Write-Host ""
    Write-Host "Face Unlock has been installed successfully!" -ForegroundColor Green
    Write-Host "It will run automatically when you log in to Windows." -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To start it now, run: $BatchFile" -ForegroundColor White
}

Write-Host ""
Write-Host "Press any key to exit..." -ForegroundColor Gray
if (-not $Silent) {
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}
