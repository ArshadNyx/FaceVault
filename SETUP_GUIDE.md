# Face Unlock Desktop Application - Complete Setup Guide

This guide will walk you through installing, setting up, and configuring the Face Unlock application to run automatically at Windows startup.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [First-Time Setup](#first-time-setup)
4. [Running the Application](#running-the-application)
5. [Auto-Start Configuration](#auto-start-configuration)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before installing, ensure you have:

- **Windows 10 or 11**
- **Python 3.8 - 3.11** (Python 3.10 recommended)
- **Webcam** (built-in or external)
- **Administrator access** (for auto-start setup)

### Check Python Installation

Open Command Prompt or PowerShell and run:

```powershell
python --version
```

You should see something like `Python 3.10.x`. If Python is not installed:

1. Download from https://www.python.org/downloads/
2. **Important**: Check "Add Python to PATH" during installation
3. Restart your computer after installation

---

## Installation

### Step 1: Open PowerShell as Administrator

1. Press `Win + X`
2. Select "Windows PowerShell (Admin)" or "Terminal (Admin)"

### Step 2: Navigate to the Project Directory

```powershell
cd "C:\Users\Rasel\Desktop\New folder"
```

### Step 3: Create a Virtual Environment

```powershell
# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1
```

If you get an execution policy error, run:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then try activating again:

```powershell
.\venv\Scripts\Activate.ps1
```

### Step 4: Install Dependencies

```powershell
# Upgrade pip
python -m pip install --upgrade pip

# Install required packages
pip install -r requirements.txt
```

### Step 5: Verify Installation

```powershell
python -c "import cv2; print('OpenCV:', cv2.__version__)"
python -c "import numpy; print('NumPy:', numpy.__version__)"
```

---

## First-Time Setup

### Step 1: Run the Application

```powershell
cd "C:\Users\Rasel\Desktop\New folder"
.\venv\Scripts\Activate.ps1
python main_gui.py
```

### Step 2: Register Your Face

1. Go to the **Registration** tab
2. Click **Start Camera**
3. Position your face in the camera view
4. Click **Capture Face**
5. Enter a username (e.g., your Windows username)
6. Click **Register Face**

### Step 3: Test Authentication

1. Go to the **Authentication** tab
2. Click **Start Camera**
3. Verify that your face is recognized

---

## Running the Application

### Method 1: Using PowerShell

```powershell
cd "C:\Users\Rasel\Desktop\New folder"
.\venv\Scripts\Activate.ps1
python main_gui.py
```

### Method 2: Using the Batch File

Double-click `run_face_unlock.bat` (created below)

### Method 3: Using Desktop Shortcut

A shortcut can be created on your desktop for easy access.

---

## Auto-Start Configuration

To make Face Unlock run automatically when Windows starts:

### Option 1: Using the Startup Folder (Recommended)

1. Create a startup batch file (instructions below)
2. Press `Win + R`, type `shell:startup`, press Enter
3. Copy the batch file shortcut to this folder

### Option 2: Using Task Scheduler (More Control)

1. Open Task Scheduler (`Win + R`, type `taskschd.msc`)
2. Click "Create Basic Task"
3. Name: "Face Unlock"
4. Trigger: "When the computer starts"
5. Action: "Start a program"
6. Browse to your batch file
7. Finish

---

## Creating Startup Files

The following files will be created automatically:

1. `run_face_unlock.bat` - Batch file to run the application
2. `install_startup.ps1` - PowerShell script to install auto-start

### To Install Auto-Start:

1. Open PowerShell as Administrator
2. Run:

```powershell
cd "C:\Users\Rasel\Desktop\New folder"
.\install_startup.ps1
```

### To Uninstall Auto-Start:

```powershell
cd "C:\Users\Rasel\Desktop\New folder"
.\install_startup.ps1 -Uninstall
```

---

## Troubleshooting

### Camera Not Working

1. Check if another application is using the camera
2. Try a different camera index in Settings (0, 1, or 2)
3. Check Windows privacy settings:
   - Settings → Privacy → Camera
   - Enable "Allow apps to access your camera"

### Face Not Detected

1. Ensure good lighting
2. Face the camera directly
3. Remove glasses/hats if necessary
4. Adjust the matching threshold in Settings

### Import Errors

If you see `ModuleNotFoundError`:

```powershell
# Make sure virtual environment is activated
.\venv\Scripts\Activate.ps1

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Application Won't Start at Boot

1. Check if the batch file path is correct
2. Verify Task Scheduler task is enabled
3. Check Windows Defender isn't blocking the script

### Reset Application Data

To reset all registered faces:

```powershell
# Delete the face_data folder
Remove-Item -Recurse -Force .\face_data\
```

The application will create a fresh database on next run.

---

## File Structure

```
C:\Users\Rasel\Desktop\New folder\
├── main_gui.py              # Main application
├── face_registration.py     # Registration module
├── face_authentication.py   # Authentication module
├── secure_storage.py        # Secure storage utility
├── windows_unlock.py        # Windows unlock functionality
├── requirements.txt         # Dependencies
├── run_face_unlock.bat      # Startup batch file
├── install_startup.ps1      # Auto-start installer
├── venv\                    # Virtual environment
└── face_data\               # Encrypted face data
    ├── encodings.enc
    ├── key.bin
    └── salt.bin
```

---

## Security Notes

1. **Face data is encrypted** using Fernet symmetric encryption
2. **Data is stored locally** - no cloud transmission
3. **Windows password** (if used for auto-unlock) is encrypted separately
4. **Keep your system secure** - this is a convenience feature, not a replacement for strong passwords

---

## Support

For issues or questions:

1. Check the Troubleshooting section above
2. Verify all dependencies are installed correctly
3. Check the README.md for additional information