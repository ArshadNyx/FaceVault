"""
Face Unlock Desktop Application - Modern GUI
A clean and user-friendly facial recognition authentication system.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageDraw
import cv2
import numpy as np
import threading
from typing import Optional, List, Dict
from datetime import datetime
import json
import os
import winsound  # For sound notifications on Windows

from face_registration import FaceRegistration
from face_authentication import FaceAuthentication, AuthenticationResult
from secure_storage import get_storage


# Modern Color Scheme
COLORS = {
    'primary': '#2196F3',
    'primary_dark': '#1976D2',
    'primary_light': '#BBDEFB',
    'secondary': '#607D8B',
    'success': '#4CAF50',
    'success_dark': '#388E3C',
    'warning': '#FF9800',
    'error': '#F44336',
    'error_dark': '#D32F2F',
    'background': '#FAFAFA',
    'surface': '#FFFFFF',
    'text_primary': '#212121',
    'text_secondary': '#757575',
    'divider': '#BDBDBD',
    'card_bg': '#FFFFFF',
    'shadow': '#E0E0E0',
    # Dark mode colors
    'dark_bg': '#121212',
    'dark_surface': '#1E1E1E',
    'dark_card': '#2D2D2D',
    'dark_text': '#E0E0E0',
    'dark_text_secondary': '#A0A0A0',
}


class ModernButton(tk.Canvas):
    """A modern styled button with hover effects."""
    
    def __init__(self, parent, text, command=None, width=200, height=45,
                 bg_color=None, text_color='white', corner_radius=8, 
                 icon=None, **kwargs):
        super().__init__(parent, width=width, height=height, 
                        highlightthickness=0, bg=parent['bg'], **kwargs)
        
        self.command = command
        self.text = text
        self.width = width
        self.height = height
        self.bg_color = bg_color or COLORS['primary']
        self.text_color = text_color
        self.corner_radius = corner_radius
        self.icon = icon
        self.hover = False
        self.enabled = True
        
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
        self.bind('<Button-1>', self._on_click)
        
        self._draw()
    
    def _draw(self):
        self.delete('all')
        if not self.enabled:
            color = COLORS['divider']
        else:
            color = self._darken_color(self.bg_color) if self.hover else self.bg_color
        
        self._create_rounded_rect(2, 2, self.width-2, self.height-2, 
                                  self.corner_radius, fill=color, outline='')
        
        self.create_text(self.width//2, self.height//2, text=self.text,
                        fill=self.text_color if self.enabled else COLORS['text_secondary'],
                        font=('Segoe UI', 11, 'bold'))
    
    def _create_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        points = [
            x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
        ]
        return self.create_polygon(points, smooth=True, **kwargs)
    
    def _darken_color(self, hex_color, factor=0.85):
        hex_color = hex_color.lstrip('#')
        r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:], 16)
        r, g, b = int(r * factor), int(g * factor), int(b * factor)
        return f'#{r:02x}{g:02x}{b:02x}'
    
    def _on_enter(self, event):
        if self.enabled:
            self.hover = True
            self._draw()
    
    def _on_leave(self, event):
        self.hover = False
        self._draw()
    
    def _on_click(self, event):
        if self.enabled and self.command:
            self.command()
    
    def set_enabled(self, enabled):
        self.enabled = enabled
        self._draw()


class ModernCard(tk.Frame):
    """A modern card-style container."""
    
    def __init__(self, parent, title='', dark_mode=False, **kwargs):
        bg = COLORS['dark_card'] if dark_mode else COLORS['card_bg']
        super().__init__(parent, bg=bg, **kwargs)
        
        self.dark_mode = dark_mode
        self.config(highlightbackground=COLORS['shadow'] if not dark_mode else COLORS['dark_surface'],
                   highlightthickness=1, padx=20, pady=15)
        
        if title:
            title_frame = tk.Frame(self, bg=bg)
            title_frame.pack(fill='x', pady=(0, 15))
            
            text_color = COLORS['dark_text'] if dark_mode else COLORS['text_primary']
            tk.Label(title_frame, text=title, font=('Segoe UI', 14, 'bold'),
                    bg=bg, fg=text_color).pack(side='left')
            
            divider_color = COLORS['dark_surface'] if dark_mode else COLORS['divider']
            divider = tk.Frame(self, height=1, bg=divider_color)
            divider.pack(fill='x', pady=(0, 15))


class FaceUnlockApp:
    """Main application class with modern UI and practical features."""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Face Unlock")
        self.root.geometry("1100x750")
        self.root.minsize(900, 650)
        
        # Settings
        self.dark_mode = tk.BooleanVar(value=False)
        self.sound_enabled = tk.BooleanVar(value=True)
        self.auto_lock = tk.BooleanVar(value=False)
        self.auto_lock_timeout = tk.IntVar(value=30)  # seconds
        self.show_confidence = tk.BooleanVar(value=True)
        
        # Load settings
        self._load_settings()
        
        # Apply theme
        self._apply_theme()
        
        # Initialize modules
        self.registration = FaceRegistration()
        self.authentication = FaceAuthentication()
        self.storage = get_storage()
        
        # State variables
        self.is_camera_running = False
        self.current_frame: Optional[np.ndarray] = None
        self.camera_thread: Optional[threading.Thread] = None
        self.stop_camera_flag = False
        self.captured_frame: Optional[np.ndarray] = None
        self.lock_timer = None
        self.is_locked = False
        self.last_auth_time = None
        
        # Build UI
        self._build_ui()
        
        # Center window
        self._center_window()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Start auto-lock timer if enabled
        if self.auto_lock.get():
            self._reset_lock_timer()
    
    def _load_settings(self):
        """Load user settings from file."""
        settings_file = 'settings.json'
        if os.path.exists(settings_file):
            try:
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                    self.dark_mode.set(settings.get('dark_mode', False))
                    self.sound_enabled.set(settings.get('sound_enabled', True))
                    self.auto_lock.set(settings.get('auto_lock', False))
                    self.auto_lock_timeout.set(settings.get('auto_lock_timeout', 30))
                    self.show_confidence.set(settings.get('show_confidence', True))
            except:
                pass
    
    def _save_settings(self):
        """Save user settings to file."""
        settings = {
            'dark_mode': self.dark_mode.get(),
            'sound_enabled': self.sound_enabled.get(),
            'auto_lock': self.auto_lock.get(),
            'auto_lock_timeout': self.auto_lock_timeout.get(),
            'show_confidence': self.show_confidence.get()
        }
        with open('settings.json', 'w') as f:
            json.dump(settings, f, indent=2)
    
    def _apply_theme(self):
        """Apply the current theme (light/dark)."""
        if self.dark_mode.get():
            self.root.configure(bg=COLORS['dark_bg'])
        else:
            self.root.configure(bg=COLORS['background'])
    
    def _build_ui(self):
        """Build the main user interface."""
        # Main container
        self.main_container = tk.Frame(self.root, 
                                        bg=COLORS['dark_bg'] if self.dark_mode.get() else COLORS['background'])
        self.main_container.pack(fill='both', expand=True, padx=30, pady=20)
        
        # Header
        self._build_header()
        
        # Notebook (tabs)
        style = ttk.Style()
        style.theme_use('clam')
        
        bg_color = COLORS['dark_surface'] if self.dark_mode.get() else COLORS['background']
        card_bg = COLORS['dark_card'] if self.dark_mode.get() else COLORS['card_bg']
        text_color = COLORS['dark_text'] if self.dark_mode.get() else COLORS['text_primary']
        
        style.configure('Modern.TNotebook', background=bg_color, borderwidth=0)
        style.configure('Modern.TNotebook.Tab',
                       background=card_bg,
                       foreground=COLORS['dark_text_secondary'] if self.dark_mode.get() else COLORS['text_secondary'],
                       padding=[25, 12],
                       font=('Segoe UI', 11))
        style.map('Modern.TNotebook.Tab',
                 background=[('selected', COLORS['primary'])],
                 foreground=[('selected', 'white')])
        
        self.notebook = ttk.Notebook(self.main_container, style='Modern.TNotebook')
        self.notebook.pack(fill='both', expand=True, pady=(20, 0))
        
        # Create tabs
        self.auth_frame = tk.Frame(self.notebook, bg=bg_color)
        self.reg_frame = tk.Frame(self.notebook, bg=bg_color)
        self.settings_frame = tk.Frame(self.notebook, bg=bg_color)
        
        self.notebook.add(self.auth_frame, text='  🔐 Authentication  ')
        self.notebook.add(self.reg_frame, text='  👤 Registration  ')
        self.notebook.add(self.settings_frame, text='  ⚙️ Settings  ')
        
        # Build tab contents
        self._build_auth_tab()
        self._build_registration_tab()
        self._build_settings_tab()
    
    def _build_header(self):
        """Build the header section."""
        bg = COLORS['dark_bg'] if self.dark_mode.get() else COLORS['background']
        text_color = COLORS['dark_text'] if self.dark_mode.get() else COLORS['text_primary']
        
        header = tk.Frame(self.main_container, bg=bg)
        header.pack(fill='x', pady=(0, 10))
        
        # Left side - Title
        left_frame = tk.Frame(header, bg=bg)
        left_frame.pack(side='left')
        
        title_label = tk.Label(left_frame, text="Face Unlock",
                              font=('Segoe UI', 28, 'bold'),
                              bg=bg, fg=COLORS['primary'])
        title_label.pack(anchor='w')
        
        subtitle_label = tk.Label(left_frame,
                                  text="Facial recognition authentication system",
                                  font=('Segoe UI', 11),
                                  bg=bg, fg=COLORS['dark_text_secondary'] if self.dark_mode.get() else COLORS['text_secondary'])
        subtitle_label.pack(anchor='w')
        
        # Right side - Status and controls
        right_frame = tk.Frame(header, bg=bg)
        right_frame.pack(side='right', pady=10)
        

        
        # Status indicator
        self.status_indicator = tk.Label(right_frame, text="● Ready",
                                         font=('Segoe UI', 10),
                                         bg=bg, fg=COLORS['success'])
        self.status_indicator.pack(side='right', padx=10)
    
    def _build_auth_tab(self):
        """Build the authentication tab."""
        bg = COLORS['dark_bg'] if self.dark_mode.get() else COLORS['background']
        card_bg = COLORS['dark_card'] if self.dark_mode.get() else COLORS['card_bg']
        text_color = COLORS['dark_text'] if self.dark_mode.get() else COLORS['text_primary']
        
        container = tk.Frame(self.auth_frame, bg=bg)
        container.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Left side - Video feed
        left_panel = ModernCard(container, title='📷 Camera Feed', dark_mode=self.dark_mode.get())
        left_panel.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        self.auth_video_frame = tk.Frame(left_panel, bg='#1a1a2e', width=640, height=480)
        self.auth_video_frame.pack(pady=10)
        self.auth_video_frame.pack_propagate(False)
        
        self._show_placeholder(self.auth_video_frame, "Click 'Start Camera' to begin")
        
        # Control buttons
        btn_frame = tk.Frame(left_panel, bg=card_bg)
        btn_frame.pack(pady=15)
        
        self.auth_start_btn = ModernButton(btn_frame, "▶ Start Camera",
                                           command=self._toggle_auth_camera,
                                           bg_color=COLORS['primary'], width=180)
        self.auth_start_btn.pack(side='left', padx=5)
        
        self.lock_btn = ModernButton(btn_frame, "🔒 Lock",
                                     command=self._manual_lock,
                                     bg_color=COLORS['error'], width=100)
        self.lock_btn.pack(side='left', padx=5)
        
        # Right side - Status panel
        right_panel = ModernCard(container, title='🔐 Authentication Status', dark_mode=self.dark_mode.get())
        right_panel.pack(side='right', fill='y', padx=(10, 0), ipadx=20)
        
        # Lock status
        self.lock_status_frame = tk.Frame(right_panel, bg=card_bg)
        self.lock_status_frame.pack(fill='x', pady=10)
        
        self.lock_status_label = tk.Label(self.lock_status_frame,
                                          text="🔓 UNLOCKED",
                                          font=('Segoe UI', 16, 'bold'),
                                          bg=card_bg, fg=COLORS['success'])
        self.lock_status_label.pack(pady=10)
        
        # Result display
        self.auth_result_frame = tk.Frame(right_panel, bg=card_bg)
        self.auth_result_frame.pack(fill='x', pady=10)
        
        self.auth_result_label = tk.Label(self.auth_result_frame,
                                          text="",
                                          font=('Segoe UI', 14, 'bold'),
                                          bg=card_bg)
        self.auth_result_label.pack()
        
        self.auth_user_label = tk.Label(self.auth_result_frame,
                                        text="",
                                        font=('Segoe UI', 11),
                                        bg=card_bg,
                                        fg=COLORS['dark_text_secondary'] if self.dark_mode.get() else COLORS['text_secondary'])
        self.auth_user_label.pack()
        
        self.auth_confidence_label = tk.Label(self.auth_result_frame,
                                              text="",
                                              font=('Segoe UI', 10),
                                              bg=card_bg,
                                              fg=COLORS['dark_text_secondary'] if self.dark_mode.get() else COLORS['text_secondary'])
        self.auth_confidence_label.pack()
        
        # Multiple faces detected info
        self.multi_face_frame = tk.Frame(right_panel, bg=card_bg)
        self.multi_face_frame.pack(fill='x', pady=10)
        
        self.multi_face_label = tk.Label(self.multi_face_frame,
                                         text="",
                                         font=('Segoe UI', 10),
                                         bg=card_bg,
                                         fg=COLORS['dark_text_secondary'] if self.dark_mode.get() else COLORS['text_secondary'],
                                         wraplength=200)
        self.multi_face_label.pack()
        
        # Last authentication time
        self.last_auth_label = tk.Label(self.multi_face_frame,
                                        text="Last attempt: --",
                                        font=('Segoe UI', 9),
                                        bg=card_bg,
                                        fg=COLORS['dark_text_secondary'] if self.dark_mode.get() else COLORS['text_secondary'])
        self.last_auth_label.pack(pady=5)
        
        # Registered users list
        users_frame = tk.Frame(right_panel, bg=card_bg)
        users_frame.pack(fill='both', expand=True, pady=10)
        
        tk.Label(users_frame, text="👥 Registered Users:",
                font=('Segoe UI', 11, 'bold'),
                bg=card_bg, fg=text_color).pack(anchor='w')
        
        self.users_listbox = tk.Listbox(users_frame, height=6,
                                        font=('Segoe UI', 10),
                                        bg=COLORS['dark_surface'] if self.dark_mode.get() else COLORS['surface'],
                                        fg=text_color,
                                        selectbackground=COLORS['primary_light'],
                                        selectforeground=text_color,
                                        borderwidth=1, relief='solid')
        self.users_listbox.pack(fill='both', expand=True, pady=5)
        
        self._refresh_users_list()
    
    def _build_registration_tab(self):
        """Build the registration tab."""
        bg = COLORS['dark_bg'] if self.dark_mode.get() else COLORS['background']
        card_bg = COLORS['dark_card'] if self.dark_mode.get() else COLORS['card_bg']
        text_color = COLORS['dark_text'] if self.dark_mode.get() else COLORS['text_primary']
        
        container = tk.Frame(self.reg_frame, bg=bg)
        container.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Left side - Video feed
        left_panel = ModernCard(container, title='📷 Face Capture', dark_mode=self.dark_mode.get())
        left_panel.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        self.reg_video_frame = tk.Frame(left_panel, bg='#1a1a2e', width=640, height=480)
        self.reg_video_frame.pack(pady=10)
        self.reg_video_frame.pack_propagate(False)
        
        self._show_placeholder(self.reg_video_frame, "Position your face in the camera")
        
        # Quality indicator
        self.quality_frame = tk.Frame(left_panel, bg=card_bg)
        self.quality_frame.pack(fill='x', pady=5)
        
        self.quality_label = tk.Label(self.quality_frame, text="Face Quality: --",
                                      font=('Segoe UI', 10),
                                      bg=card_bg,
                                      fg=COLORS['dark_text_secondary'] if self.dark_mode.get() else COLORS['text_secondary'])
        self.quality_label.pack()
        
        # Face position guide
        self.position_label = tk.Label(self.quality_frame, text="Position: --",
                                       font=('Segoe UI', 9),
                                       bg=card_bg,
                                       fg=COLORS['dark_text_secondary'] if self.dark_mode.get() else COLORS['text_secondary'])
        self.position_label.pack()
        
        # Control buttons
        btn_frame = tk.Frame(left_panel, bg=card_bg)
        btn_frame.pack(pady=15)
        
        self.reg_start_btn = ModernButton(btn_frame, "▶ Start Camera",
                                          command=self._toggle_reg_camera,
                                          bg_color=COLORS['primary'], width=150)
        self.reg_start_btn.pack(side='left', padx=5)
        
        self.capture_btn = ModernButton(btn_frame, "📷 Capture",
                                        command=self._capture_face,
                                        bg_color=COLORS['secondary'], width=130)
        self.capture_btn.pack(side='left', padx=5)
        
        # Right side - Registration form
        right_panel = ModernCard(container, title='👤 Register New User', dark_mode=self.dark_mode.get())
        right_panel.pack(side='right', fill='y', padx=(10, 0), ipadx=20)
        
        # Username input
        input_frame = tk.Frame(right_panel, bg=card_bg)
        input_frame.pack(fill='x', pady=20)
        
        tk.Label(input_frame, text="Username:",
                font=('Segoe UI', 11, 'bold'),
                bg=card_bg, fg=text_color).pack(anchor='w')
        
        self.username_entry = tk.Entry(input_frame,
                                       font=('Segoe UI', 12),
                                       bg=COLORS['dark_surface'] if self.dark_mode.get() else COLORS['surface'],
                                       fg=text_color,
                                       insertbackground=text_color,
                                       relief='solid', borderwidth=1)
        self.username_entry.pack(fill='x', pady=8, ipady=8)
        
        # Register button
        self.register_btn = ModernButton(right_panel, "✓ Register Face",
                                         command=self._register_user,
                                         bg_color=COLORS['success'], width=200)
        self.register_btn.pack(pady=15)
        
        # Status display
        self.reg_status_label = tk.Label(right_panel,
                                         text="Start camera and capture your face",
                                         font=('Segoe UI', 10),
                                         bg=card_bg,
                                         fg=COLORS['dark_text_secondary'] if self.dark_mode.get() else COLORS['text_secondary'],
                                         wraplength=200)
        self.reg_status_label.pack(pady=10)
        
        # Captured preview
        preview_frame = tk.Frame(right_panel, bg=card_bg)
        preview_frame.pack(fill='x', pady=10)
        
        tk.Label(preview_frame, text="Captured Preview:",
                font=('Segoe UI', 10, 'bold'),
                bg=card_bg, fg=text_color).pack(anchor='w')
        
        self.preview_canvas = tk.Canvas(preview_frame, width=150, height=150,
                                        bg=COLORS['dark_surface'] if self.dark_mode.get() else COLORS['surface'],
                                        highlightthickness=1,
                                        highlightbackground=COLORS['divider'])
        self.preview_canvas.pack(pady=5)
        
        # Delete user section
        delete_frame = tk.Frame(right_panel, bg=card_bg)
        delete_frame.pack(fill='x', pady=20)
        
        tk.Label(delete_frame, text="🗑 Delete User:",
                font=('Segoe UI', 11, 'bold'),
                bg=card_bg, fg=text_color).pack(anchor='w')
        
        self.delete_user_combo = ttk.Combobox(delete_frame, font=('Segoe UI', 10))
        self.delete_user_combo.pack(fill='x', pady=8)
        
        self.delete_btn = ModernButton(delete_frame, "🗑 Delete",
                                       command=self._delete_user,
                                       bg_color=COLORS['error'], width=120)
        self.delete_btn.pack(pady=5)
        
        self._refresh_users_combo()
    
    def _build_settings_tab(self):
        """Build the settings tab."""
        bg = COLORS['dark_bg'] if self.dark_mode.get() else COLORS['background']
        card_bg = COLORS['dark_card'] if self.dark_mode.get() else COLORS['card_bg']
        text_color = COLORS['dark_text'] if self.dark_mode.get() else COLORS['text_primary']
        
        container = tk.Frame(self.settings_frame, bg=bg)
        container.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Appearance settings
        appearance_card = ModernCard(container, title='🎨 Appearance', dark_mode=self.dark_mode.get())
        appearance_card.pack(fill='x', pady=10)
        
        dark_frame = tk.Frame(appearance_card, bg=card_bg)
        dark_frame.pack(fill='x', pady=10)
        
        tk.Label(dark_frame, text="Dark Mode:",
                font=('Segoe UI', 10),
                bg=card_bg, fg=text_color).pack(side='left')
        
        dark_check = tk.Checkbutton(dark_frame, variable=self.dark_mode,
                                    bg=card_bg, fg=text_color,
                                    selectcolor=card_bg,
                                    activebackground=card_bg,
                                    command=self._toggle_dark_mode)
        dark_check.pack(side='left', padx=10)
        
        # Sound settings
        sound_card = ModernCard(container, title='🔊 Sound & Notifications', dark_mode=self.dark_mode.get())
        sound_card.pack(fill='x', pady=10)
        
        sound_frame = tk.Frame(sound_card, bg=card_bg)
        sound_frame.pack(fill='x', pady=10)
        
        tk.Label(sound_frame, text="Sound Effects:",
                font=('Segoe UI', 10),
                bg=card_bg, fg=text_color).pack(side='left')
        
        sound_check = tk.Checkbutton(sound_frame, variable=self.sound_enabled,
                                     bg=card_bg, fg=text_color,
                                     selectcolor=card_bg,
                                     activebackground=card_bg)
        sound_check.pack(side='left', padx=10)
        
        # Confidence display setting
        conf_frame = tk.Frame(sound_card, bg=card_bg)
        conf_frame.pack(fill='x', pady=5)
        
        tk.Label(conf_frame, text="Show Confidence Score:",
                font=('Segoe UI', 10),
                bg=card_bg, fg=text_color).pack(side='left')
        
        conf_check = tk.Checkbutton(conf_frame, variable=self.show_confidence,
                                    bg=card_bg, fg=text_color,
                                    selectcolor=card_bg,
                                    activebackground=card_bg)
        conf_check.pack(side='left', padx=10)
        
        # Security settings
        security_card = ModernCard(container, title='🔒 Security', dark_mode=self.dark_mode.get())
        security_card.pack(fill='x', pady=10)
        
        # Auto-lock
        auto_lock_frame = tk.Frame(security_card, bg=card_bg)
        auto_lock_frame.pack(fill='x', pady=10)
        
        tk.Label(auto_lock_frame, text="Auto-lock after inactivity:",
                font=('Segoe UI', 10),
                bg=card_bg, fg=text_color).pack(side='left')
        
        auto_lock_check = tk.Checkbutton(auto_lock_frame, variable=self.auto_lock,
                                         bg=card_bg, fg=text_color,
                                         selectcolor=card_bg,
                                         activebackground=card_bg,
                                         command=self._toggle_auto_lock)
        auto_lock_check.pack(side='left', padx=10)
        
        timeout_frame = tk.Frame(security_card, bg=card_bg)
        timeout_frame.pack(fill='x', pady=5)
        
        tk.Label(timeout_frame, text="Timeout (seconds):",
                font=('Segoe UI', 10),
                bg=card_bg, fg=text_color).pack(side='left')
        
        timeout_spin = tk.Spinbox(timeout_frame, from_=10, to=300, width=6,
                                  textvariable=self.auto_lock_timeout,
                                  font=('Segoe UI', 10))
        timeout_spin.pack(side='left', padx=10)
        
        # Camera settings
        camera_card = ModernCard(container, title='📷 Camera', dark_mode=self.dark_mode.get())
        camera_card.pack(fill='x', pady=10)
        
        cam_frame = tk.Frame(camera_card, bg=card_bg)
        cam_frame.pack(fill='x', pady=10)
        
        tk.Label(cam_frame, text="Camera Index:",
                font=('Segoe UI', 10),
                bg=card_bg, fg=text_color).pack(side='left')
        
        self.camera_index_var = tk.StringVar(value='0')
        camera_spin = tk.Spinbox(cam_frame, from_=0, to=5, width=5,
                                 textvariable=self.camera_index_var,
                                 font=('Segoe UI', 10))
        camera_spin.pack(side='left', padx=10)
        
        tk.Label(cam_frame, text="(Try different numbers if camera doesn't work)",
                font=('Segoe UI', 9),
                bg=card_bg,
                fg=COLORS['dark_text_secondary'] if self.dark_mode.get() else COLORS['text_secondary']).pack(side='left')
        
        # Recognition settings
        recog_card = ModernCard(container, title='🎯 Recognition', dark_mode=self.dark_mode.get())
        recog_card.pack(fill='x', pady=10)
        
        threshold_frame = tk.Frame(recog_card, bg=card_bg)
        threshold_frame.pack(fill='x', pady=10)
        
        tk.Label(threshold_frame, text="Matching Threshold:",
                font=('Segoe UI', 10),
                bg=card_bg, fg=text_color).pack(side='left')
        
        self.threshold_var = tk.DoubleVar(value=0.5)
        threshold_scale = tk.Scale(threshold_frame, from_=0.1, to=0.9,
                                   resolution=0.05, orient='horizontal',
                                   variable=self.threshold_var,
                                   bg=card_bg, fg=text_color,
                                   highlightthickness=0, length=200)
        threshold_scale.pack(side='left', padx=10)
        
        tk.Label(threshold_frame, text="(Lower = stricter)",
                font=('Segoe UI', 9),
                bg=card_bg,
                fg=COLORS['dark_text_secondary'] if self.dark_mode.get() else COLORS['text_secondary']).pack(side='left')
        
        # Save button
        save_frame = tk.Frame(container, bg=bg)
        save_frame.pack(fill='x', pady=20)
        
        ModernButton(save_frame, "💾 Save Settings",
                    command=self._save_all_settings,
                    bg_color=COLORS['success'], width=150).pack(side='left', padx=5)
        
        ModernButton(save_frame, "🔄 Reset to Defaults",
                    command=self._reset_settings,
                    bg_color=COLORS['secondary'], width=150).pack(side='left', padx=5)
    
    def _show_placeholder(self, parent, text):
        """Show a placeholder image with text."""
        for widget in parent.winfo_children():
            widget.destroy()
        
        img = Image.new('RGB', (640, 480), '#1a1a2e')
        draw = ImageDraw.Draw(img)
        
        cx, cy = 320, 200
        draw.ellipse([cx-60, cy-60, cx+60, cy+60], outline='#3d3d5c', width=3)
        draw.ellipse([cx-30, cy-20, cx-10, cy], fill='#3d3d5c')
        draw.ellipse([cx+10, cy-20, cx+30, cy], fill='#3d3d5c')
        draw.arc([cx-25, cy+10, cx+25, cy+40], 0, 180, fill='#3d3d5c', width=3)
        
        try:
            from PIL import ImageFont
            font = ImageFont.truetype("arial.ttf", 16)
        except:
            font = None
        
        draw.text((320, 350), text, fill='#666699', anchor='mm', font=font)
        
        photo = ImageTk.PhotoImage(img)
        label = tk.Label(parent, image=photo, bg='#1a1a2e')
        label.image = photo
        label.pack(expand=True)
    
    def _center_window(self):
        """Center the window on screen."""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def _play_sound(self, sound_type: str):
        """Play a sound notification."""
        if not self.sound_enabled.get():
            return
        
        try:
            if sound_type == 'success':
                winsound.Beep(1000, 200)
                winsound.Beep(1500, 200)
            elif sound_type == 'error':
                winsound.Beep(400, 300)
            elif sound_type == 'capture':
                winsound.Beep(800, 100)
        except:
            pass
    
    def _toggle_dark_mode(self):
        """Toggle dark mode."""
        self._save_settings()
        # Recreate the UI with new theme
        self.main_container.destroy()
        self._apply_theme()
        self._build_ui()
    
    def _toggle_auto_lock(self):
        """Toggle auto-lock feature."""
        if self.auto_lock.get():
            self._reset_lock_timer()
        else:
            self._cancel_lock_timer()
    
    def _reset_lock_timer(self):
        """Reset the auto-lock timer."""
        self._cancel_lock_timer()
        if self.auto_lock.get():
            self.lock_timer = self.root.after(
                self.auto_lock_timeout.get() * 1000,
                self._auto_lock
            )
    
    def _cancel_lock_timer(self):
        """Cancel the auto-lock timer."""
        if self.lock_timer:
            self.root.after_cancel(self.lock_timer)
            self.lock_timer = None
    
    def _auto_lock(self):
        """Auto-lock the application."""
        self._manual_lock()
    
    def _manual_lock(self):
        """Manually lock the application."""
        self.is_locked = True
        card_bg = COLORS['dark_card'] if self.dark_mode.get() else COLORS['card_bg']
        self.lock_status_label.config(text="🔒 LOCKED", fg=COLORS['error'])
        self._play_sound('error')
        
        # Stop camera if running
        if self.is_camera_running:
            self._stop_camera()
    
    def _unlock(self, username: str):
        """Unlock the application."""
        self.is_locked = False
        self.lock_status_label.config(text="🔓 UNLOCKED", fg=COLORS['success'])
        self._play_sound('success')
        self._reset_lock_timer()
    
    def _toggle_auth_camera(self):
        """Toggle authentication camera on/off."""
        if self.is_camera_running:
            self._stop_camera()
            self.auth_start_btn.text = "▶ Start Camera"
            self.auth_start_btn._draw()
        else:
            self._start_auth_camera()
            self.auth_start_btn.text = "⏹ Stop Camera"
            self.auth_start_btn._draw()
    
    def _toggle_reg_camera(self):
        """Toggle registration camera on/off."""
        if self.is_camera_running:
            self._stop_camera()
            self.reg_start_btn.text = "▶ Start Camera"
            self.reg_start_btn._draw()
        else:
            self._start_reg_camera()
            self.reg_start_btn.text = "⏹ Stop Camera"
            self.reg_start_btn._draw()
    
    def _start_auth_camera(self):
        """Start camera for authentication."""
        cam_index = int(self.camera_index_var.get())
        self.authentication = FaceAuthentication(
            camera_index=cam_index,
            threshold=self.threshold_var.get()
        )
        
        if not self.authentication.start_camera():
            messagebox.showerror("Error", "Could not start camera.")
            return
        
        self.is_camera_running = True
        self.stop_camera_flag = False
        self.status_indicator.config(text="● Camera Active", fg=COLORS['success'])
        
        def auth_loop():
            while not self.stop_camera_flag:
                frame = self.authentication.capture_frame()
                if frame is None:
                    continue
                
                self.current_frame = frame.copy()
                results = self.authentication.authenticate_frame(frame)
                
                # Draw rectangles for all detected faces
                display_frame = frame.copy()
                for result in results:
                    if result.face_location:
                        x, y, w, h = result.face_location
                        if result.success:
                            color = (76, 175, 80)  # Green for recognized
                            label = result.username
                        else:
                            color = (244, 67, 54)  # Red for unknown
                            label = "Unknown"
                        
                        cv2.rectangle(display_frame, (x, y), (x+w, y+h), color, 2)
                        cv2.putText(display_frame, label, (x, y - 10),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                
                # Update UI with results
                if results:
                    self.root.after(0, self._update_auth_ui, results)
                
                try:
                    frame_rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame_rgb)
                    img = img.resize((640, 480), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    self.root.after(0, self._update_auth_video, photo)
                except:
                    pass
        
        self.camera_thread = threading.Thread(target=auth_loop, daemon=True)
        self.camera_thread.start()
    
    def _start_reg_camera(self):
        """Start camera for registration."""
        cam_index = int(self.camera_index_var.get())
        self.registration = FaceRegistration(camera_index=cam_index)
        
        if not self.registration.start_camera():
            messagebox.showerror("Error", "Could not start camera.")
            return
        
        self.is_camera_running = True
        self.stop_camera_flag = False
        self.status_indicator.config(text="● Camera Active", fg=COLORS['success'])
        
        def reg_loop():
            while not self.stop_camera_flag:
                frame = self.registration.capture_frame()
                if frame is None:
                    continue
                
                self.current_frame = frame.copy()
                face_locations = self.registration.detect_faces(frame)
                
                display_frame = frame.copy()
                for (x, y, w, h) in face_locations:
                    cv2.rectangle(display_frame, (x, y), (x+w, y+h), (33, 150, 243), 2)
                    
                    # Calculate face quality
                    quality = self._calculate_face_quality(frame, (x, y, w, h))
                    self.root.after(0, lambda q=quality: self.quality_label.config(
                        text=f"Face Quality: {q:.0%}",
                        fg=COLORS['success'] if q > 0.7 else COLORS['warning'] if q > 0.4 else COLORS['error']
                    ))
                    
                    # Check face position
                    frame_h, frame_w = frame.shape[:2]
                    center_x, center_y = x + w//2, y + h//2
                    frame_center_x, frame_center_y = frame_w // 2, frame_h // 2
                    
                    position_status = "Good"
                    if abs(center_x - frame_center_x) > frame_w * 0.2:
                        position_status = "Move left/right"
                    elif abs(center_y - frame_center_y) > frame_h * 0.15:
                        position_status = "Move up/down"
                    
                    self.root.after(0, lambda p=position_status: self.position_label.config(
                        text=f"Position: {p}",
                        fg=COLORS['success'] if p == "Good" else COLORS['warning']
                    ))
                
                status = f"Detected {len(face_locations)} face(s)" if face_locations else "No face detected"
                self.root.after(0, lambda s=status: self.reg_status_label.config(text=s))
                
                try:
                    frame_rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame_rgb)
                    img = img.resize((640, 480), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    self.root.after(0, self._update_reg_video, photo)
                except:
                    pass
        
        self.camera_thread = threading.Thread(target=reg_loop, daemon=True)
        self.camera_thread.start()
    
    def _calculate_face_quality(self, frame, face_location) -> float:
        """Calculate face quality score."""
        x, y, w, h = face_location
        face = frame[y:y+h, x:x+w]
        
        if face.size == 0:
            return 0.0
        
        gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
        
        # Check brightness
        brightness = np.mean(gray) / 255.0
        brightness_score = 1.0 - abs(brightness - 0.5) * 2
        
        # Check blur (Laplacian variance)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        sharpness_score = min(1.0, laplacian_var / 500)
        
        # Check size
        size_score = min(1.0, min(w, h) / 150)
        
        return (brightness_score * 0.3 + sharpness_score * 0.4 + size_score * 0.3)
    
    def _stop_camera(self):
        """Stop the camera."""
        self.stop_camera_flag = True
        self.is_camera_running = False
        
        if self.authentication.video_capture:
            self.authentication.stop_camera()
        if self.registration.video_capture:
            self.registration.stop_camera()
        
        self.status_indicator.config(text="● Ready", fg=COLORS['success'])
    
    def _update_auth_video(self, photo):
        """Update authentication video display."""
        for widget in self.auth_video_frame.winfo_children():
            widget.destroy()
        label = tk.Label(self.auth_video_frame, image=photo, bg='#1a1a2e')
        label.image = photo
        label.pack(expand=True)
    
    def _update_reg_video(self, photo):
        """Update registration video display."""
        for widget in self.reg_video_frame.winfo_children():
            widget.destroy()
        label = tk.Label(self.reg_video_frame, image=photo, bg='#1a1a2e')
        label.image = photo
        label.pack(expand=True)
    
    def _update_auth_ui(self, results: List[AuthenticationResult]):
        """Update authentication UI with results for all detected faces."""
        if not results:
            return
        
        card_bg = COLORS['dark_card'] if self.dark_mode.get() else COLORS['card_bg']
        
        # Update last attempt time
        self.last_auth_time = datetime.now()
        self.last_auth_label.config(text=f"Last attempt: {self.last_auth_time.strftime('%H:%M:%S')}")
        
        # Count recognized vs unknown faces
        recognized = [r for r in results if r.success]
        unknown = [r for r in results if not r.success]
        
        num_faces = len(results)
        num_recognized = len(recognized)
        num_unknown = len(unknown)
        
        # Update multi-face info
        if num_faces > 1:
            self.multi_face_label.config(
                text=f"Detected {num_faces} face(s): {num_recognized} recognized, {num_unknown} unknown",
                fg=COLORS['warning'] if num_unknown > 0 else COLORS['success']
            )
        else:
            self.multi_face_label.config(text="")
        
        # Find the best result (prioritize recognized faces)
        if recognized:
            # Sort by confidence and get the best match
            best_result = max(recognized, key=lambda r: r.confidence)
            
            self.auth_result_label.config(text="✓ ACCESS GRANTED", fg=COLORS['success'])
            
            if num_recognized > 1:
                names = ", ".join([r.username for r in recognized])
                self.auth_user_label.config(text=f"Users: {names}")
            else:
                self.auth_user_label.config(text=f"User: {best_result.username}")
            
            if self.show_confidence.get():
                if num_recognized > 1:
                    confidences = ", ".join([f"{r.username}: {r.confidence:.0%}" for r in recognized])
                    self.auth_confidence_label.config(text=confidences)
                else:
                    self.auth_confidence_label.config(text=f"Confidence: {best_result.confidence:.1%}")
            else:
                self.auth_confidence_label.config(text="")
            
            if self.is_locked:
                self._unlock(best_result.username)
            
            self._play_sound('success')
            
        else:
            # No recognized faces
            self.auth_result_label.config(text="✗ ACCESS DENIED", fg=COLORS['error'])
            
            if num_unknown > 1:
                self.auth_user_label.config(text=f"{num_unknown} unknown faces detected")
            else:
                self.auth_user_label.config(text="User not recognized")
            
            if self.show_confidence.get() and results:
                best_unknown = max(results, key=lambda r: r.confidence)
                self.auth_confidence_label.config(text=f"Best match: {best_unknown.confidence:.1%}")
            else:
                self.auth_confidence_label.config(text="")
            
            self._play_sound('error')
    
    def _capture_face(self):
        """Capture current frame for registration."""
        if self.current_frame is None:
            messagebox.showwarning("Warning", "Please start the camera first.")
            return
        
        face_locations = self.registration.detect_faces(self.current_frame)
        
        if len(face_locations) == 0:
            self.reg_status_label.config(text="No face detected!", fg=COLORS['error'])
            return
        
        if len(face_locations) > 1:
            self.reg_status_label.config(text="Multiple faces detected. Please ensure only one face is visible.", fg=COLORS['warning'])
            return
        
        self.captured_frame = self.current_frame.copy()
        
        # Show preview
        x, y, w, h = face_locations[0]
        face_img = self.captured_frame[y:y+h, x:x+w]
        face_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
        face_img = Image.fromarray(face_img)
        face_img = face_img.resize((150, 150), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(face_img)
        
        self.preview_canvas.delete('all')
        self.preview_canvas.create_image(75, 75, image=photo)
        self.preview_canvas.image = photo
        
        self.reg_status_label.config(text="Face captured! Enter username and click Register.", fg=COLORS['success'])
        self._play_sound('capture')
    
    def _register_user(self):
        """Register a new user."""
        username = self.username_entry.get().strip()
        
        if not username:
            messagebox.showwarning("Warning", "Please enter a username.")
            return
        
        if self.captured_frame is None:
            messagebox.showwarning("Warning", "Please capture your face first.")
            return
        
        success, message = self.registration.register_user_single_frame(username, self.captured_frame)
        
        if success:
            messagebox.showinfo("Success", message)
            self.username_entry.delete(0, tk.END)
            self.captured_frame = None
            self.preview_canvas.delete('all')
            self.authentication.reload_encodings()
            self._refresh_users_list()
            self._refresh_users_combo()
            self._play_sound('success')
        else:
            messagebox.showerror("Error", message)
    
    def _delete_user(self):
        """Delete a registered user."""
        username = self.delete_user_combo.get().strip()
        
        if not username:
            messagebox.showwarning("Warning", "Please select a user to delete.")
            return
        
        if messagebox.askyesno("Confirm Delete", f"Delete user '{username}'?"):
            success, message = self.registration.delete_user(username)
            
            if success:
                messagebox.showinfo("Success", message)
                self.authentication.reload_encodings()
                self._refresh_users_list()
                self._refresh_users_combo()
            else:
                messagebox.showerror("Error", message)
    
    def _refresh_users_list(self):
        """Refresh the users listbox."""
        self.users_listbox.delete(0, tk.END)
        users = self.authentication.get_registered_users()
        for user in users:
            self.users_listbox.insert(tk.END, f"  👤 {user}")
    
    def _refresh_users_combo(self):
        """Refresh the users combobox."""
        users = self.storage.list_users()
        self.delete_user_combo['values'] = users
    
    def _save_all_settings(self):
        """Save all settings."""
        self._save_settings()
        messagebox.showinfo("Settings Saved", "Your settings have been saved.")
    
    def _reset_settings(self):
        """Reset settings to defaults."""
        self.dark_mode.set(False)
        self.sound_enabled.set(True)
        self.auto_lock.set(False)
        self.auto_lock_timeout.set(30)
        self.threshold_var.set(0.5)
        self.camera_index_var.set('0')
        self.show_confidence.set(True)
        
        self._save_settings()
        messagebox.showinfo("Settings Reset", "Settings have been reset to defaults.")
    
    def _on_close(self):
        """Handle window close."""
        self._stop_camera()
        self._save_settings()
        self.root.destroy()


def main():
    """Main entry point."""
    root = tk.Tk()
    app = FaceUnlockApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
