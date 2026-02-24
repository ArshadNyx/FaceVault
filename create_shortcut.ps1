<#
.SYNOPSIS
    Creates a desktop shortcut for Face Unlock application.

.DESCRIPTION
    This script creates a desktop shortcut that launches the Face Unlock application.

.EXAMPLE
    .\create_shortcut.ps1
    Creates a desktop shortcut.
#>

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $DesktopPath "Face Unlock.lnk"
$BatchFile = Join-Path $ScriptDir "run_face_unlock.bat"
$IconPath = Join-Path $ScriptDir "icon.ico"

# Create shortcut
$WScriptShell = New-Object -ComObject WScript.Shell
$Shortcut = $WScriptShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $BatchFile
$Shortcut.WorkingDirectory = $ScriptDir
$Shortcut.Description = "Face Unlock Desktop Application"
$Shortcut.WindowStyle = 1

# Set icon if exists
if (Test-Path $IconPath) {
    $Shortcut.IconLocation = $IconPath
}

$Shortcut.Save()

Write-Host "Desktop shortcut created: $ShortcutPath" -ForegroundColor Green
Write-Host "You can now launch Face Unlock from your desktop!" -ForegroundColor Cyan
