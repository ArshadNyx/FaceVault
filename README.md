# Face Unlock Desktop Application

A Python-based desktop application that uses facial recognition for user authentication. This system allows users to log in using their face instead of a password.

## Quick Start

### Option 1: Automatic Setup (Recommended)

1. Open PowerShell as Administrator
2. Navigate to the project folder:
   ```powershell
   cd "C:\Users\Rasel\Desktop\New folder"
   ```
3. Run the setup script:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   .\setup.ps1
   ```

### Option 2: Manual Setup

1. Open PowerShell and navigate to the project folder
2. Create virtual environment:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
3. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
4. Run the application:
   ```powershell
   python main_gui.py
   ```

## Features

- **Real-time Face Detection**: Captures live video from webcam and detects faces in real-time
- **Face Registration**: Register new users by capturing their facial features
- **Face Authentication**: Authenticate users by comparing live camera input with stored encodings
- **Secure Storage**: Facial encodings are encrypted and stored securely using Fernet symmetric encryption
- **User-friendly GUI**: Clean and intuitive graphical interface built with Tkinter
- **Windows Integration**: Optional auto-start when Windows logs in

## Requirements

- **Windows 10 or 11**
- **Python 3.8 - 3.11** (Python 3.10 recommended)
- **Webcam** (built-in or external)

## Installation Files

| File | Purpose |
|------|---------|
| `setup.ps1` | Complete automatic setup |
| `run_face_unlock.bat` | Launch the application |
| `install_startup.ps1` | Install/remove auto-start |
| `create_shortcut.ps1` | Create desktop shortcut |

## Usage

### Register Your Face

1. Run the application (`run_face_unlock.bat` or `python main_gui.py`)
2. Go to the **Registration** tab
3. Click **Start Camera**
4. Position your face in the camera view
5. Click **Capture Face**
6. Enter a username
7. Click **Register Face**

### Authenticate

1. Go to the **Authentication** tab
2. Click **Start Camera**
3. Position your registered face in the camera view
4. The system will automatically recognize you

### Auto-Start Configuration

To run Face Unlock automatically when Windows starts:

```powershell
# Run as Administrator
.\install_startup.ps1
```

To remove auto-start:

```powershell
.\install_startup.ps1 -Uninstall
```

### Create Desktop Shortcut

```powershell
.\create_shortcut.ps1
```

## Project Structure

```
C:\Users\Rasel\Desktop\New folder\
├── main_gui.py              # Main GUI application
├── face_registration.py     # Face registration module
├── face_authentication.py   # Face authentication module
├── secure_storage.py        # Secure storage utility
├── windows_unlock.py        # Windows unlock functionality
├── requirements.txt         # Dependencies
├── setup.ps1               # Automatic setup script
├── run_face_unlock.bat     # Application launcher
├── install_startup.ps1     # Auto-start installer
├── create_shortcut.ps1     # Desktop shortcut creator
├── SETUP_GUIDE.md          # Detailed setup guide
├── README.md               # This file
├── venv\                   # Virtual environment (created by setup)
├── face_data\              # Encrypted face data
└── models\                 # ML models
```

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

```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### PowerShell Execution Policy Error

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## Security Notes

1. **Face data is encrypted** using Fernet symmetric encryption
2. **Data is stored locally** - no cloud transmission
3. **Windows password** (if used for auto-unlock) is encrypted separately
4. **Keep your system secure** - this is a convenience feature, not a replacement for strong passwords

## Detailed Documentation

See [SETUP_GUIDE.md](SETUP_GUIDE.md) for complete installation and configuration instructions.

## License

This project is for educational purposes. Feel free to use and modify as needed.

---

Made with Python and OpenCV