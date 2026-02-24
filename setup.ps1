<#
.SYNOPSIS
    Complete setup script for Face Unlock Desktop Application.

.DESCRIPTION
    This script performs the complete setup:
    1. Creates virtual environment
    2. Installs all dependencies
    3. Verifies installation
    4. Optionally installs auto-start

.EXAMPLE
    .\setup.ps1
    Runs the complete setup process.
#>

param(
    [switch]$SkipVenv,
    [switch]$InstallStartup
)

# Colors for output
function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "    [OK] $Message" -ForegroundColor Green
}

function Write-Error-Msg {
    param([string]$Message)
    Write-Host "    [ERROR] $Message" -ForegroundColor Red
}

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host @"

===============================================
   Face Unlock Desktop Application Setup
===============================================

"@ -ForegroundColor Yellow

# Step 1: Check Python
Write-Step "Checking Python installation..."
try {
    $pythonVersion = python --version 2>&1
    Write-Success "Python found: $pythonVersion"
} catch {
    Write-Error-Msg "Python not found. Please install Python 3.8-3.11 from python.org"
    exit 1
}

# Step 2: Create virtual environment
if (-not $SkipVenv) {
    Write-Step "Creating virtual environment..."
    
    if (Test-Path ".\venv") {
        Write-Host "    Virtual environment already exists. Skipping..." -ForegroundColor Yellow
    } else {
        python -m venv venv
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Virtual environment created"
        } else {
            Write-Error-Msg "Failed to create virtual environment"
            exit 1
        }
    }
} else {
    Write-Host "    Skipping virtual environment creation" -ForegroundColor Yellow
}

# Step 3: Activate virtual environment
Write-Step "Activating virtual environment..."
try {
    .\venv\Scripts\Activate.ps1
    Write-Success "Virtual environment activated"
} catch {
    Write-Error-Msg "Failed to activate virtual environment"
    Write-Host "    Trying to set execution policy..." -ForegroundColor Yellow
    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
    .\venv\Scripts\Activate.ps1
    Write-Success "Virtual environment activated"
}

# Step 4: Upgrade pip
Write-Step "Upgrading pip..."
python -m pip install --upgrade pip --quiet
Write-Success "Pip upgraded"

# Step 5: Install dependencies
Write-Step "Installing dependencies..."
pip install -r requirements.txt --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Success "Dependencies installed"
} else {
    Write-Error-Msg "Failed to install dependencies"
    Write-Host "    Trying with --user flag..." -ForegroundColor Yellow
    pip install -r requirements.txt --user
}

# Step 6: Verify installation
Write-Step "Verifying installation..."

$packages = @("cv2", "numpy", "PIL", "cryptography")
$allOk = $true

foreach ($pkg in $packages) {
    try {
        if ($pkg -eq "cv2") {
            python -c "import cv2" 2>$null
        } elseif ($pkg -eq "PIL") {
            python -c "from PIL import Image" 2>$null
        } else {
            python -c "import $pkg" 2>$null
        }
        Write-Success "$pkg installed correctly"
    } catch {
        Write-Error-Msg "$pkg not installed correctly"
        $allOk = $false
    }
}

# Step 7: Create necessary directories
Write-Step "Creating application directories..."
if (-not (Test-Path ".\face_data")) {
    New-Item -ItemType Directory -Path ".\face_data" -Force | Out-Null
    Write-Success "Created face_data directory"
} else {
    Write-Success "face_data directory exists"
}

if (-not (Test-Path ".\models")) {
    New-Item -ItemType Directory -Path ".\models" -Force | Out-Null
    Write-Success "Created models directory"
} else {
    Write-Success "models directory exists"
}

# Step 8: Optional - Install startup
if ($InstallStartup) {
    Write-Step "Installing auto-start..."
    if (Test-Path ".\install_startup.ps1") {
        powershell -ExecutionPolicy Bypass -File ".\install_startup.ps1" -Silent
        Write-Success "Auto-start installed"
    } else {
        Write-Error-Msg "install_startup.ps1 not found"
    }
}

# Final summary
Write-Host @"

===============================================
            Setup Complete!
===============================================

"@ -ForegroundColor Green

if ($allOk) {
    Write-Host "All dependencies installed successfully!" -ForegroundColor Green
} else {
    Write-Host "Some dependencies may have issues. Check the output above." -ForegroundColor Yellow
}

Write-Host @"

To run the application:
  1. Double-click 'run_face_unlock.bat'
  OR
  2. Run in PowerShell:
     .\venv\Scripts\Activate.ps1
     python main_gui.py

To install auto-start (run as Administrator):
  .\install_startup.ps1

"@ -ForegroundColor Cyan

Write-Host "Press any key to exit..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
