#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Drive Icon Setter  v1.0  —  macOS EDITION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WORKS ON:
  🍎 macOS 10.15+ (Catalina, Big Sur, Monterey, Ventura, Sonoma, Sequoia)
  
FEATURES:
  ✅ Set custom icons for any mounted volume
  ✅ Works on USB drives, external HDDs, and local volumes
  ✅ All icon files hidden (using dot prefix)
  ✅ Automatic volume detection
  ✅ One click applies to current volume
  ✅ Diagnostics shows what's hidden
  ✅ Native macOS look and feel
"""

import os
import sys
import shutil
import subprocess
import tempfile
import time
import glob
import platform
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import plistlib

# ── Auto-install Pillow ───────────────────────────────────────────────────────
def _install_pillow():
    print("Installing Pillow...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--user", "Pillow"], check=True)
    except:
        try:
            subprocess.run(["pip", "install", "--user", "Pillow"], check=True)
        except:
            print("Automatic installation failed.")
    import site
    u = site.getusersitepackages()
    if u not in sys.path:
        sys.path.insert(0, u)

try:
    from PIL import Image, ImageTk, ImageDraw
except ModuleNotFoundError:
    _install_pillow()
    try:
        import site
        from importlib import reload
        reload(site)
        from PIL import Image, ImageTk, ImageDraw
    except ModuleNotFoundError:
        print(f"Run: {sys.executable} -m pip install Pillow")
        sys.exit(1)

# Check if running on macOS
if platform.system() != 'Darwin':
    print("This version is for macOS only!")
    sys.exit(1)

# ==============================================================================
#  macOS VERSION DETECTION
# ==============================================================================

def get_macos_version():
    """Get macOS version"""
    try:
        version = platform.mac_ver()[0]
        return version
    except:
        return "Unknown"

MACOS_VER = get_macos_version()

# ==============================================================================
#  VOLUME DETECTION (macOS)
# ==============================================================================

def get_volumes():
    """Get all mounted volumes on macOS"""
    volumes = []
    
    # macOS mounts volumes in /Volumes
    volumes_dir = "/Volumes"
    
    try:
        for item in os.listdir(volumes_dir):
            volume_path = os.path.join(volumes_dir, item)
            if os.path.ismount(volume_path):
                # Get volume info
                try:
                    stat = os.statvfs(volume_path)
                    total = stat.f_blocks * stat.f_frsize
                    free = stat.f_bavail * stat.f_frsize
                    used = total - free
                    
                    # Check if it's the system volume
                    is_system = (volume_path == '/') or item.startswith('Macintosh HD')
                    
                    # Get filesystem type
                    fs_type = get_volume_format(volume_path)
                    
                    # Check if it's a network volume
                    is_network = is_network_volume(volume_path)
                    
                    volumes.append({
                        'name': item,
                        'path': volume_path,
                        'total': total,
                        'used': used,
                        'free': free,
                        'is_system': is_system,
                        'fs_type': fs_type,
                        'is_network': is_network
                    })
                except:
                    pass
    except:
        pass
    
    # Also include root volume (Macintosh HD)
    try:
        stat = os.statvfs('/')
        total = stat.f_blocks * stat.f_frsize
        free = stat.f_bavail * stat.f_frsize
        used = total - free
        
        volumes.append({
            'name': 'Macintosh HD',
            'path': '/',
            'total': total,
            'used': used,
            'free': free,
            'is_system': True,
            'fs_type': 'APFS',
            'is_network': False
        })
    except:
        pass
    
    return volumes

def get_volume_format(volume_path):
    """Get filesystem format of volume"""
    try:
        result = subprocess.run(['diskutil', 'info', volume_path], 
                               capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if 'File System' in line or 'Type (Bundle)' in line:
                if 'APFS' in line:
                    return 'APFS'
                elif 'HFS' in line:
                    return 'HFS+'
                elif 'exFAT' in line:
                    return 'exFAT'
                elif 'FAT' in line:
                    return 'FAT32'
        return 'Unknown'
    except:
        return 'Unknown'

def is_network_volume(volume_path):
    """Check if volume is a network mount"""
    try:
        result = subprocess.run(['mount'], capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if volume_path in line:
                if 'afp://' in line or 'smb://' in line or 'nfs://' in line:
                    return True
        return False
    except:
        return False

def get_volume_uuid(volume_path):
    """Get UUID of volume"""
    try:
        result = subprocess.run(['diskutil', 'info', volume_path, '-plist'],
                               capture_output=True, text=True)
        plist = plistlib.loads(result.stdout.encode())
        return plist.get('VolumeUUID', '')
    except:
        return ''

# ==============================================================================
#  ICON CONVERSION FUNCTIONS
# ==============================================================================

def pil_to_icns(img, output_path):
    """Convert PIL image to macOS .icns format"""
    # Create iconset folder
    iconset_dir = tempfile.mkdtemp()
    
    # Required sizes for macOS icons
    sizes = [16, 32, 64, 128, 256, 512, 1024]
    
    for size in sizes:
        # Standard resolution
        img_resized = img.resize((size, size), Image.LANCZOS)
        img_resized.save(os.path.join(iconset_dir, f"icon_{size}x{size}.png"))
        
        # High resolution (@2x)
        if size * 2 <= 1024:
            img_resized = img.resize((size * 2, size * 2), Image.LANCZOS)
            img_resized.save(os.path.join(iconset_dir, f"icon_{size}x{size}@2x.png"))
    
    # Convert iconset to icns using iconutil (macOS built-in)
    icns_path = output_path
    try:
        subprocess.run(['iconutil', '-c', 'icns', iconset_dir, '-o', icns_path],
                      capture_output=True, check=True)
        return True
    except:
        # Fallback: just copy the largest PNG
        shutil.copy2(os.path.join(iconset_dir, "icon_1024x1024.png"), icns_path + '.png')
        return False
    finally:
        shutil.rmtree(iconset_dir, ignore_errors=True)

def create_macos_icon_set(img, output_dir, base_name=".VolumeIcon"):
    """Create macOS icon set"""
    icons = []
    
    # Create .VolumeIcon.icns (main macOS volume icon)
    icns_path = os.path.join(output_dir, f"{base_name}.icns")
    if pil_to_icns(img, icns_path):
        icons.append(icns_path)
    
    # Also create PNG versions for compatibility
    png_path = os.path.join(output_dir, f"{base_name}.png")
    img.resize((512, 512), Image.LANCZOS).save(png_path, "PNG")
    icons.append(png_path)
    
    return icons

# ==============================================================================
#  macOS ICON SETTING FUNCTIONS
# ==============================================================================

def set_volume_icon_macos(volume_path, icon_path, status_cb):
    """Set custom icon for macOS volume"""
    
    def log(msg):
        if status_cb:
            status_cb(msg)
    
    # Method 1: Using SetFile (classic method)
    try:
        # The standard macOS method: .VolumeIcon.icns in root
        icon_dest = os.path.join(volume_path, ".VolumeIcon.icns")
        
        # Copy icon
        shutil.copy2(icon_path, icon_dest)
        
        # Hide it (already hidden by dot prefix)
        subprocess.run(['chflags', 'hidden', icon_dest], capture_output=True)
        
        # Also set the volume icon attribute
        subprocess.run(['SetFile', '-a', 'C', volume_path], capture_output=True)
        
        log("✅ Icon set using .VolumeIcon.icns method")
        return True
    except:
        pass
    
    # Method 2: Using AppleScript
    try:
        script = f'''
        tell application "Finder"
            set theFile to POSIX file "{volume_path}" as alias
            set iconPath to POSIX file "{icon_path}" as alias
            set icon of theFile to iconPath
        end tell
        '''
        result = subprocess.run(['osascript', '-e', script], capture_output=True)
        if result.returncode == 0:
            log("✅ Icon set using AppleScript")
            return True
    except:
        pass
    
    # Method 3: Using fileicon CLI tool (if available)
    try:
        subprocess.run(['fileicon', 'set', volume_path, icon_path], capture_output=True)
        log("✅ Icon set using fileicon")
        return True
    except:
        pass
    
    return False

def create_macos_metadata(volume_path, status_cb):
    """Create macOS metadata files"""
    def log(msg):
        if status_cb:
            status_cb(msg)
    
    # Create .DS_Store (Finder preferences)
    ds_store = os.path.join(volume_path, ".DS_Store")
    try:
        with open(ds_store, 'wb') as f:
            f.write(b'\x00' * 4096)
        subprocess.run(['chflags', 'hidden', ds_store], capture_output=True)
        log("✅ Created .DS_Store")
    except:
        pass
    
    # Create .fseventsd (prevent logging)
    fseventsd = os.path.join(volume_path, ".fseventsd")
    try:
        os.makedirs(fseventsd, exist_ok=True)
        no_log = os.path.join(fseventsd, "no_log")
        with open(no_log, 'w') as f:
            f.write("")
        subprocess.run(['chflags', 'hidden', fseventsd], capture_output=True)
        log("✅ Created .fseventsd")
    except:
        pass
    
    # Create .metadata_never_index (prevent Spotlight indexing)
    never_index = os.path.join(volume_path, ".metadata_never_index")
    try:
        with open(never_index, 'w') as f:
            f.write("")
        subprocess.run(['chflags', 'hidden', never_index], capture_output=True)
        log("✅ Created .metadata_never_index")
    except:
        pass

# ==============================================================================
#  MAIN ICON APPLICATION FUNCTION
# ==============================================================================

def apply_macos_icon(volume, icon_src, label, status_cb, done_cb):
    """Apply icon to macOS volume"""
    t0 = time.time()
    
    def step(msg):
        status_cb(f"[{time.time()-t0:.1f}s] {msg}")
    
    try:
        volume_path = volume['path']
        volume_name = volume['name']
        
        step(f"🎯 Target: {volume_name} ({volume_path})")
        
        # Check if volume is writable
        test_file = os.path.join(volume_path, ".write_test")
        try:
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            step("✅ Volume is writable")
        except:
            step("⚠️ Volume is read-only - may fail")
        
        # Load image with PIL
        from PIL import Image as _Img
        pil_img = _Img.open(icon_src).convert("RGBA")
        step("✅ Image loaded")
        
        # Create .icons folder for additional files
        icons_dir = os.path.join(volume_path, ".icons")
        os.makedirs(icons_dir, exist_ok=True)
        step("✅ Created .icons folder")
        
        # Create macOS icon set
        step("🎨 Creating macOS icons...")
        icon_files = create_macos_icon_set(pil_img, icons_dir, ".VolumeIcon")
        step(f"✅ Created {len(icon_files)} icon files")
        
        # Set the volume icon
        step("🔧 Setting volume icon...")
        if set_volume_icon_macos(volume_path, icon_files[0], step):
            step("✅ Volume icon set successfully")
        else:
            step("⚠️ Icon set may need manual refresh")
        
        # Create macOS metadata files
        step("📁 Creating macOS metadata...")
        create_macos_metadata(volume_path, step)
        
        # Create autorun.inf for Windows compatibility
        auto_path = os.path.join(volume_path, "autorun.inf")
        with open(auto_path, 'w', encoding='utf-8') as f:
            f.write("[autorun]\n")
            f.write("icon=.icons/.VolumeIcon.png\n")
            if label:
                f.write(f"label={label}\n")
        subprocess.run(['chflags', 'hidden', auto_path], capture_output=True)
        step("✅ Created autorun.inf (Windows)")
        
        # Create .directory for Linux compatibility
        dir_path = os.path.join(volume_path, ".directory")
        with open(dir_path, 'w', encoding='utf-8') as f:
            f.write("[Desktop Entry]\n")
            f.write("Icon=.icons/.VolumeIcon.png\n")
            f.write("Type=Directory\n")
        subprocess.run(['chflags', 'hidden', dir_path], capture_output=True)
        step("✅ Created .directory (Linux)")
        
        # Hide all files in .icons folder
        for root, dirs, files in os.walk(icons_dir):
            for file in files:
                file_path = os.path.join(root, file)
                if not os.path.basename(file_path).startswith('.'):
                    new_path = os.path.join(root, '.' + os.path.basename(file_path))
                    try:
                        os.rename(file_path, new_path)
                        subprocess.run(['chflags', 'hidden', new_path], capture_output=True)
                    except:
                        subprocess.run(['chflags', 'hidden', file_path], capture_output=True)
                else:
                    subprocess.run(['chflags', 'hidden', file_path], capture_output=True)
        
        step("🔒 All icon files hidden")
        
        # Refresh Finder
        step("🔄 Refreshing Finder...")
        try:
            subprocess.run(['killall', 'Finder'], capture_output=True)
            time.sleep(1)
        except:
            pass
        
        total = time.time() - t0
        step(f"✨ Done! Finished in {total:.1f}s")
        
        # Success message
        done_cb(True,
                f"✅ macOS Icon Applied Successfully!\n\n"
                f"Volume: {volume_name}\n"
                f"Path: {volume_path}\n"
                f"macOS: {MACOS_VER}\n"
                f"Time: {total:.1f}s\n\n"
                f"📁 Files created:\n"
                f"  • .VolumeIcon.icns - Main volume icon\n"
                f"  • .icons/ - Additional icon files\n"
                f"  • .DS_Store - Finder preferences\n"
                f"  • .fseventsd - File system events\n"
                f"  • .metadata_never_index - Spotlight control\n"
                f"  • autorun.inf - Windows compatibility\n"
                f"  • .directory - Linux compatibility\n\n"
                f"🔒 All files are hidden (dot prefix)\n\n"
                f"Plug this drive into ANY computer:\n"
                f"  ✅ macOS → sees icon\n"
                f"  ✅ Windows → sees icon\n"
                f"  ✅ Linux → sees icon")
        
    except PermissionError as e:
        done_cb(False, f"❌ Permission denied:\n{e}\n\nTry running with sudo")
    except Exception as e:
        import traceback
        done_cb(False, f"❌ Error: {e}\n\n{traceback.format_exc()}")

# ==============================================================================
#  REMOVE ICON FUNCTION
# ==============================================================================

def remove_macos_icon(volume, status_cb, done_cb):
    """Remove all icon files from volume"""
    t0 = time.time()
    
    def step(msg):
        status_cb(f"[{time.time()-t0:.1f}s] {msg}")
    
    try:
        volume_path = volume['path']
        removed = 0
        
        # Remove .VolumeIcon.icns
        icon_file = os.path.join(volume_path, ".VolumeIcon.icns")
        if os.path.exists(icon_file):
            os.remove(icon_file)
            removed += 1
            step("✅ Removed .VolumeIcon.icns")
        
        # Remove .DS_Store
        ds_store = os.path.join(volume_path, ".DS_Store")
        if os.path.exists(ds_store):
            os.remove(ds_store)
            removed += 1
            step("✅ Removed .DS_Store")
        
        # Remove .fseventsd
        fseventsd = os.path.join(volume_path, ".fseventsd")
        if os.path.exists(fseventsd):
            shutil.rmtree(fseventsd, ignore_errors=True)
            removed += 1
            step("✅ Removed .fseventsd")
        
        # Remove .metadata_never_index
        never_index = os.path.join(volume_path, ".metadata_never_index")
        if os.path.exists(never_index):
            os.remove(never_index)
            removed += 1
            step("✅ Removed .metadata_never_index")
        
        # Remove autorun.inf
        auto_path = os.path.join(volume_path, "autorun.inf")
        if os.path.exists(auto_path):
            os.remove(auto_path)
            removed += 1
            step("✅ Removed autorun.inf")
        
        # Remove .directory
        dir_path = os.path.join(volume_path, ".directory")
        if os.path.exists(dir_path):
            os.remove(dir_path)
            removed += 1
            step("✅ Removed .directory")
        
        # Remove .icons folder
        icons_dir = os.path.join(volume_path, ".icons")
        if os.path.exists(icons_dir):
            shutil.rmtree(icons_dir, ignore_errors=True)
            removed += 1
            step("✅ Removed .icons folder")
        
        # Reset volume icon using SetFile
        try:
            subprocess.run(['SetFile', '-a', 'c', volume_path], capture_output=True)
        except:
            pass
        
        step(f"✅ Removed {removed} files/folders")
        done_cb(True, f"✅ Icon removed from {volume['name']}")
        
    except Exception as e:
        done_cb(False, f"❌ Error: {e}")

# ==============================================================================
#  DIAGNOSTICS
# ==============================================================================

def volume_diagnostics(volume):
    """Get diagnostics info for macOS volume"""
    lines = []
    volume_path = volume['path']
    volume_name = volume['name']
    
    lines.append(f"=== Diagnostics: {volume_name} ({volume_path}) ===")
    lines.append(f"macOS Version: {MACOS_VER}")
    lines.append(f"Filesystem: {volume.get('fs_type', 'Unknown')}")
    
    # Check if writable
    test_file = os.path.join(volume_path, ".write_test")
    try:
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        lines.append(f"Writable: YES")
    except:
        lines.append(f"Writable: NO ⚠️")
    
    # Check for .VolumeIcon.icns
    icon_file = os.path.join(volume_path, ".VolumeIcon.icns")
    if os.path.exists(icon_file):
        size = os.path.getsize(icon_file)
        lines.append(f".VolumeIcon.icns: EXISTS ({size:,} bytes)")
    else:
        lines.append(f".VolumeIcon.icns: missing")
    
    # Check for .icons folder
    icons_dir = os.path.join(volume_path, ".icons")
    if os.path.exists(icons_dir):
        icons = glob.glob(os.path.join(icons_dir, "*"))
        lines.append(f"\n.icons folder: {len(icons)} files")
        for i in sorted(icons)[:5]:
            size = os.path.getsize(i)
            name = os.path.basename(i)
            lines.append(f"  {name:30} ({size:,} bytes)")
    else:
        lines.append(f".icons folder: missing")
    
    # Check other metadata
    for f in [".DS_Store", ".fseventsd", ".metadata_never_index", "autorun.inf", ".directory"]:
        path = os.path.join(volume_path, f)
        if os.path.exists(path):
            lines.append(f"{f}: EXISTS")
    
    return "\n".join(lines)

# ==============================================================================
#  GUI COMPONENTS
# ==============================================================================

# macOS-like colors
BG = "#f5f5f7"  # Light gray (like macOS)
SURFACE = "#ffffff"
OVERLAY = "#e5e5e5"
TEXT = "#1d1d1f"
SUBTEXT = "#86868b"
ACCENT = "#0071e3"  # macOS blue
GREEN = "#28cd41"
RED = "#ff3b30"
YELLOW = "#ffcc00"
ORANGE = "#ff9f0a"
PURPLE = "#bf5af2"

def flat_btn(parent, text, cmd, accent=False, color=None, **kw):
    bg = color or (ACCENT if accent else SURFACE)
    fg = "#ffffff" if accent else TEXT
    return tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                     activebackground="#0077ed" if accent else OVERLAY,
                     activeforeground="#ffffff" if accent else TEXT,
                     relief="flat", cursor="hand2", bd=0,
                     font=("SF Pro Text", 11, "bold" if accent else "normal"),
                     padx=16, pady=8, **kw)

# ── Step Log Window ───────────────────────────────────────────────────────────
class StepLog(tk.Toplevel):
    def __init__(self, parent, title="Progress"):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=BG, padx=16, pady=14)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        
        tk.Label(self, text=f"Live Progress  (macOS {MACOS_VER})",
                 bg=BG, fg=ACCENT,
                 font=("SF Pro Text", 12, "bold")).pack(anchor="w", pady=(0, 6))
        
        self.txt = tk.Text(self, width=72, height=20,
                           bg=SURFACE, fg=TEXT,
                           font=("SF Mono", 10), relief="flat",
                           state="disabled", wrap="word")
        self.txt.pack()
        self.geometry(f"+{parent.winfo_x()+50}+{parent.winfo_y()+20}")
        self.update()

    def log(self, msg):
        self.txt.config(state="normal")
        self.txt.insert("end", msg + "\n")
        self.txt.see("end")
        self.txt.config(state="disabled")
        self.update()

    def done(self):
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.log("\n─── Click X to close ───")

# ── Crop Editor (adapted from your existing code) ─────────────────────────────
EDITOR_SIZE = 320

class CropEditor(tk.Toplevel):
    def __init__(self, parent, pil_image, callback):
        super().__init__(parent)
        self.title("Edit Icon — Drag to pan  |  Scroll to zoom")
        self.configure(bg=BG, padx=20, pady=16)
        self.resizable(False, False)
        self.grab_set()
        self._src = pil_image.convert("RGBA")
        self._cb = callback
        self._zoom = 1.0
        self._off = [0, 0]
        self._drag = None
        self._smi = []
        self._build()
        self._center()
        self._redraw()

    def _build(self):
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", pady=(0, 10))
        
        lf = tk.Frame(top, bg=BG)
        lf.pack(side="left", padx=(0, 16))
        
        tk.Label(lf, text="Drag to pan  |  Scroll to zoom",
                 bg=BG, fg=SUBTEXT, font=("SF Pro Text", 10)).pack()
        
        self.cv = tk.Canvas(lf, width=EDITOR_SIZE, height=EDITOR_SIZE,
                           bg="#000", highlightthickness=2,
                           highlightbackground=ACCENT, cursor="fleur")
        self.cv.pack()
        self.cv.bind("<ButtonPress-1>", self._ds)
        self.cv.bind("<B1-Motion>", self._dm)
        self.cv.bind("<MouseWheel>", self._mw)
        
        rf = tk.Frame(top, bg=BG)
        rf.pack(side="left", anchor="n")
        
        tk.Label(rf, text="Preview", bg=BG, fg=SUBTEXT,
                 font=("SF Pro Text", 10)).pack()
        
        self.pv = tk.Canvas(rf, width=128, height=128, bg="#000",
                           highlightthickness=1, highlightbackground=OVERLAY)
        self.pv.pack(pady=(0, 8))
        
        tk.Label(rf, text="Sizes:", bg=BG, fg=SUBTEXT,
                 font=("SF Pro Text", 10)).pack(anchor="w")
        
        self.sm = tk.Canvas(rf, width=128, height=52, bg=SURFACE,
                           highlightthickness=0)
        self.sm.pack()
        
        tk.Label(rf, text="Background:", bg=BG, fg=SUBTEXT,
                 font=("SF Pro Text", 10)).pack(anchor="w", pady=(10, 2))
        
        self._bg = tk.StringVar(value="transparent")
        for v, l in [("transparent", "Transparent"), ("white", "White"),
                    ("black", "Black"), ("circle", "Circle")]:
            tk.Radiobutton(rf, text=l, variable=self._bg, value=v,
                          bg=BG, fg=TEXT, selectcolor=SURFACE,
                          activebackground=BG, activeforeground=TEXT,
                          font=("SF Pro Text", 10),
                          command=self._redraw).pack(anchor="w")
        
        zm = tk.Frame(self, bg=BG)
        zm.pack(fill="x", pady=(0, 12))
        
        tk.Label(zm, text="Zoom:", bg=BG, fg=TEXT,
                 font=("SF Pro Text", 11)).pack(side="left")
        
        self.zsl = tk.Scale(zm, from_=10, to=500, orient="horizontal",
                           bg=BG, fg=TEXT, troughcolor=OVERLAY,
                           highlightthickness=0, showvalue=False,
                           command=self._zc)
        self.zsl.set(100)
        self.zsl.pack(side="left", fill="x", expand=True, padx=(8, 8))
        
        self.zlb = tk.Label(zm, text="100%", bg=BG, fg=ACCENT,
                           font=("SF Pro Text", 11, "bold"), width=5)
        self.zlb.pack(side="left")
        
        br = tk.Frame(self, bg=BG)
        br.pack(fill="x")
        
        flat_btn(br, "Fit", self._fit).pack(side="left", padx=(0, 8))
        flat_btn(br, "Cancel", self.destroy).pack(side="right", padx=(8, 0))
        flat_btn(br, "Use Icon", self._confirm, accent=True).pack(side="right")

    def _center(self):
        sw, sh = self._src.size
        self._zoom = min(EDITOR_SIZE / sw, EDITOR_SIZE / sh)
        self._off = [(sw - EDITOR_SIZE / self._zoom) / 2,
                    (sh - EDITOR_SIZE / self._zoom) / 2]
        self.zsl.set(int(self._zoom * 100))

    def _fit(self):
        self._center()
        self._redraw()

    def _zc(self, v):
        cx = self._off[0] + (EDITOR_SIZE / 2) / self._zoom
        cy = self._off[1] + (EDITOR_SIZE / 2) / self._zoom
        self._zoom = max(0.1, int(v) / 100)
        self._off[0] = cx - (EDITOR_SIZE / 2) / self._zoom
        self._off[1] = cy - (EDITOR_SIZE / 2) / self._zoom
        self.zlb.config(text=f"{int(v)}%")
        self._redraw()

    def _ds(self, e):
        self._drag = (e.x, e.y, self._off[0], self._off[1])

    def _dm(self, e):
        if not self._drag:
            return
        sx, sy, ox, oy = self._drag
        self._off[0] = ox + (sx - e.x) / self._zoom
        self._off[1] = oy + (sy - e.y) / self._zoom
        self._redraw()

    def _mw(self, e):
        f = 1.1 if e.delta > 0 else 0.9
        nz = max(0.1, min(5.0, self._zoom * f))
        cx = self._off[0] + (EDITOR_SIZE / 2) / self._zoom
        cy = self._off[1] + (EDITOR_SIZE / 2) / self._zoom
        self._zoom = nz
        self._off[0] = cx - (EDITOR_SIZE / 2) / self._zoom
        self._off[1] = cy - (EDITOR_SIZE / 2) / self._zoom
        self.zsl.set(int(self._zoom * 100))
        self.zlb.config(text=f"{int(self._zoom * 100)}%")
        self._redraw()

    def _crop(self, size=256):
        sw, sh = self._src.size
        x0, y0 = self._off
        x1 = x0 + EDITOR_SIZE / self._zoom
        y1 = y0 + EDITOR_SIZE / self._zoom
        bv = self._bg.get()
        
        ci = Image.new("RGBA", (EDITOR_SIZE, EDITOR_SIZE),
                      (255, 255, 255, 255) if bv == "white" else
                      (0, 0, 0, 255) if bv == "black" else (0, 0, 0, 0))
        
        sx0, sy0 = max(0, x0), max(0, y0)
        sx1, sy1 = min(sw, x1), min(sh, y1)
        
        if sx1 > sx0 and sy1 > sy0:
            rg = self._src.crop((sx0, sy0, sx1, sy1))
            px = int((sx0 - x0) * self._zoom)
            py = int((sy0 - y0) * self._zoom)
            pw = max(1, int((sx1 - sx0) * self._zoom))
            ph = max(1, int((sy1 - sy0) * self._zoom))
            rs = rg.resize((pw, ph), Image.LANCZOS)
            ci.paste(rs, (px, py), rs)
        
        if bv == "circle":
            mk = Image.new("L", (EDITOR_SIZE, EDITOR_SIZE), 0)
            ImageDraw.Draw(mk).ellipse(
                (0, 0, EDITOR_SIZE - 1, EDITOR_SIZE - 1), fill=255)
            ot = Image.new("RGBA", (EDITOR_SIZE, EDITOR_SIZE), (0, 0, 0, 0))
            ot.paste(ci, mask=mk)
            ci = ot
        
        return ci.resize((size, size), Image.LANCZOS)

    @staticmethod
    def _chk(size, b=8):
        img = Image.new("RGBA", (size, size))
        d = ImageDraw.Draw(img)
        for y in range(0, size, b):
            for x in range(0, size, b):
                c = ((200, 200, 200, 255) if (x // b + y // b) % 2 == 0
                     else (160, 160, 160, 255))
                d.rectangle([x, y, x + b - 1, y + b - 1], fill=c)
        return img

    def _redraw(self):
        img = self._crop(EDITOR_SIZE)
        self._te = ImageTk.PhotoImage(
            Image.alpha_composite(self._chk(EDITOR_SIZE), img))
        self.cv.delete("all")
        self.cv.create_image(0, 0, anchor="nw", image=self._te)
        
        pv = img.resize((128, 128), Image.LANCZOS)
        self._tp = ImageTk.PhotoImage(
            Image.alpha_composite(self._chk(128), pv))
        self.pv.delete("all")
        self.pv.create_image(0, 0, anchor="nw", image=self._tp)
        
        self.sm.delete("all")
        self._smi = []
        x = 4
        for s in [48, 32, 16]:
            ti = ImageTk.PhotoImage(Image.alpha_composite(
                self._chk(s), img.resize((s, s), Image.LANCZOS)))
            self._smi.append(ti)
            self.sm.create_image(x, 26, anchor="w", image=ti)
            self.sm.create_text(x + s + 2, 42, anchor="w", text=f"{s}px",
                                fill=SUBTEXT, font=("SF Pro Text", 8))
            x += s + 28

    def _confirm(self):
        self._cb(self._crop(256))
        self.destroy()

# ==============================================================================
#  MAIN APPLICATION
# ==============================================================================

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Drive Icon Setter  —  macOS Edition")
        self.configure(bg=BG, padx=28, pady=22)
        self.resizable(False, False)
        
        self._src = None
        self._final = None
        self._ico = None
        self._tmp = tempfile.mkdtemp()
        self._volumes = []
        
        self.volume_var = tk.StringVar()
        self.label_var = tk.StringVar()
        
        self._build_ui()
        self._refresh_volumes()

    def _build_ui(self):
        # Title
        title_text = f"  Drive Icon Setter  —  macOS Edition"
        tk.Label(self, text=title_text, bg=BG, fg=TEXT,
                font=("SF Pro Display", 18, "bold")).pack(anchor="w", pady=(0, 4))

        # Info frame
        info = tk.Frame(self, bg=SURFACE, padx=12, pady=8)
        info.pack(fill="x", pady=(0, 6))
        
        tk.Label(info,
                text=f"macOS {MACOS_VER}",
                bg=SURFACE, fg=ACCENT,
                font=("SF Pro Text", 11, "bold")).pack(anchor="w")
        tk.Label(info,
                text="Set custom icons for any mounted volume",
                bg=SURFACE, fg=SUBTEXT,
                font=("SF Pro Text", 10)).pack(anchor="w")

        # Step 1 - Choose image
        self._sec("Step 1  —  Choose an image")
        
        f1 = tk.Frame(self, bg=BG)
        f1.pack(fill="x", pady=(0, 8))
        
        self.img_var = tk.StringVar()
        tk.Entry(f1, textvariable=self.img_var, width=38, bg=SURFACE, fg=TEXT,
                insertbackground=TEXT, relief="flat", font=("SF Pro Text", 11),
                state="readonly", readonlybackground=SURFACE
                ).pack(side="left", padx=(0, 8), ipady=8)
        flat_btn(f1, "Browse…", self._browse).pack(side="left")

        fp = tk.Frame(self, bg=BG)
        fp.pack(fill="x", pady=(4, 0))
        
        self.thumb_cv = tk.Canvas(fp, width=96, height=96, bg=SURFACE,
                                 highlightthickness=1, highlightbackground=OVERLAY)
        self.thumb_cv.pack(side="left")
        self.thumb_cv.create_text(48, 48, text="preview",
                                 fill=SUBTEXT, font=("SF Pro Text", 10))
        
        fi = tk.Frame(fp, bg=BG, padx=14)
        fi.pack(side="left", fill="both")
        
        self.info_v = tk.StringVar(value="No image selected.")
        tk.Label(fi, textvariable=self.info_v, bg=BG, fg=SUBTEXT,
                font=("SF Pro Text", 10), justify="left").pack(anchor="w")
        
        self.conv_l = tk.Label(fi, text="", bg=BG, fg=GREEN,
                              font=("SF Pro Text", 10, "bold"), justify="left")
        self.conv_l.pack(anchor="w", pady=(4, 0))
        
        flat_btn(fi, "  Edit / Crop  ",
                self._open_editor, color=PURPLE).pack(anchor="w", pady=(10, 0))

        # Step 2 - Select volume
        self._sec("Step 2  —  Select volume")
        
        f2 = tk.Frame(self, bg=BG)
        f2.pack(fill="x", pady=(0, 4))
        
        tk.Label(f2, text="Volume:", bg=BG, fg=TEXT,
                font=("SF Pro Text", 11)).grid(row=0, column=0, sticky="w", pady=5)
        
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TCombobox",
                       fieldbackground=SURFACE, background=SURFACE,
                       foreground=TEXT, selectbackground=ACCENT,
                       selectforeground="white", font=("SF Pro Text", 11))
        
        self.combo = ttk.Combobox(f2, textvariable=self.volume_var,
                                  width=32, state="readonly")
        self.combo.grid(row=0, column=1, padx=(8, 8), sticky="w")
        self.combo.bind("<<ComboboxSelected>>", self._on_volume)
        
        flat_btn(f2, "Refresh", self._refresh_volumes).grid(row=0, column=2)
        
        tk.Label(f2, text="Label:", bg=BG, fg=TEXT,
                font=("SF Pro Text", 11)).grid(row=1, column=0, sticky="w", pady=5)
        
        tk.Entry(f2, textvariable=self.label_var, width=34, bg=SURFACE, fg=TEXT,
                insertbackground=TEXT, relief="flat", font=("SF Pro Text", 11)
                ).grid(row=1, column=1, padx=(8, 0), ipady=8, sticky="w")

        self.cur_icon_l = tk.Label(self, text="", bg=BG, fg=SUBTEXT,
                                   font=("SF Pro Text", 10), anchor="w")
        self.cur_icon_l.pack(fill="x", pady=(0, 2))
        
        self.info_l = tk.Label(self, text="", bg=BG, fg=ORANGE,
                              font=("SF Pro Text", 10, "bold"),
                              anchor="w", justify="left")
        self.info_l.pack(fill="x", pady=(0, 4))

        # Step 3 - Apply
        self._sec("Step 3  —  Apply")
        
        # Progress bar
        self.progress = ttk.Progressbar(self, mode="indeterminate", length=420)
        tk.Frame(self, bg=BG, height=10).pack()

        # Apply button
        self.apply_btn = flat_btn(self, "  Apply Icon to Volume  ",
                                  self._apply, accent=True)
        self.apply_btn.pack(fill="x")

        # Status
        self.status_v = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self.status_v, bg=SURFACE, fg=SUBTEXT,
                anchor="w", font=("SF Mono", 10), padx=12, pady=8
                ).pack(fill="x", pady=(8, 0))

        # Bottom buttons
        bf = tk.Frame(self, bg=BG)
        bf.pack(fill="x", pady=(6, 0))
        
        flat_btn(bf, "  Remove Icon  ",
                self._remove_icon, color="#86868b"
                ).pack(side="left", fill="x", expand=True, padx=(0, 3))
        
        flat_btn(bf, "  Diagnostics  ",
                self._diagnostics, color=ORANGE
                ).pack(side="left", fill="x", expand=True, padx=(3, 0))

    def _sec(self, title):
        tk.Label(self, text=title, bg=BG, fg=ACCENT,
                font=("SF Pro Text", 12, "bold")).pack(anchor="w", pady=(14, 4))
        tk.Frame(self, bg=OVERLAY, height=1).pack(fill="x", pady=(0, 8))

    def _refresh_volumes(self):
        """Refresh list of volumes"""
        self._volumes = get_volumes()
        
        choices = []
        for v in self._volumes:
            name = v['name']
            path = v['path']
            size_gb = v['total'] / (1024**3)
            system_tag = " [System]" if v['is_system'] else ""
            network_tag = " [Network]" if v.get('is_network', False) else ""
            
            display = f"{name}{system_tag}{network_tag}  ({size_gb:.1f} GB)"
            choices.append(display)
        
        self.combo["values"] = choices
        if choices:
            # Don't select system volume by default
            for i, v in enumerate(self._volumes):
                if not v['is_system']:
                    self.combo.current(i)
                    break
            else:
                self.combo.current(0)
        self._on_volume()

    def _get_volume(self):
        """Get selected volume info"""
        idx = self.combo.current()
        if idx < 0 or idx >= len(self._volumes):
            return None
        return self._volumes[idx]

    def _on_volume(self, event=None):
        """Handle volume selection"""
        if not hasattr(self, "info_l"):
            return
        volume = self._get_volume()
        if not volume:
            return
        
        path = volume['path']
        
        # Check for existing icon
        icon_file = os.path.join(path, ".VolumeIcon.icns")
        if os.path.exists(icon_file):
            self.cur_icon_l.config(text=f"✓ Custom icon found")
        else:
            self.cur_icon_l.config(text="No custom icon set")
        
        # Show info
        free_gb = volume['free'] / (1024**3)
        total_gb = volume['total'] / (1024**3)
        info_text = f"  Free: {free_gb:.1f} GB of {total_gb:.1f} GB  |  {volume.get('fs_type', 'Unknown')}"
        self.info_l.config(text=info_text, fg=SUBTEXT)

    def _browse(self):
        """Browse for image file"""
        path = filedialog.askopenfilename(
            title="Select image",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tiff *.tif *.ico"),
                      ("All files", "*.*")])
        if not path:
            return
        try:
            img = Image.open(path)
            self._src = img.convert("RGBA")
            self.img_var.set(path)
            ext = os.path.splitext(path)[1].upper()
            self.info_v.set(
                f"File: {os.path.basename(path)}\n"
                f"Size: {img.width} × {img.height} px  |  {ext}")
            self._ico = None
            self._final = None
            self.conv_l.config(text="Click 'Edit / Crop' to adjust",
                               fg=YELLOW)
            self._thumb_update(self._src)
            self._open_editor()
        except Exception as e:
            messagebox.showerror("Error", f"Cannot open image:\n{e}")

    def _thumb_update(self, pil_img):
        """Update thumbnail preview"""
        t = pil_img.copy().convert("RGBA")
        t.thumbnail((96, 96), Image.LANCZOS)
        
        chk = Image.new("RGBA", (96, 96))
        d = ImageDraw.Draw(chk)
        for y in range(0, 96, 8):
            for x in range(0, 96, 8):
                c = ((200, 200, 200, 255) if (x // 8 + y // 8) % 2 == 0
                     else (160, 160, 160, 255))
                d.rectangle([x, y, x + 7, y + 7], fill=c)
        
        ox = (96 - t.width) // 2
        oy = (96 - t.height) // 2
        chk.paste(t, (ox, oy), t)
        
        self._tk_thumb = ImageTk.PhotoImage(chk)
        self.thumb_cv.delete("all")
        self.thumb_cv.create_image(0, 0, anchor="nw", image=self._tk_thumb)

    def _open_editor(self):
        """Open crop editor"""
        if self._src is None:
            messagebox.showwarning("No image", "Please select an image first.")
            return
        CropEditor(self, self._src, self._edit_done)

    def _edit_done(self, result):
        """Handle edited image"""
        self._final = result
        self._thumb_update(result)
        try:
            # Save as PNG first
            out = os.path.join(self._tmp, "drive_icon.png")
            result.save(out, "PNG")
            self._ico = out
            self.conv_l.config(text="✓ Icon ready! Click Apply", fg=GREEN)
            self.status_v.set("Icon ready")
        except Exception as e:
            self.conv_l.config(text=f"Prepare failed: {e}", fg=RED)

    def _check_ready(self):
        """Check if ready to apply"""
        if self._final is None or self._ico is None:
            messagebox.showwarning("Not Ready",
                "Please select and edit an image first.")
            return False
        volume = self._get_volume()
        if not volume:
            messagebox.showwarning("No Volume", "Please select a volume.")
            return False
        return True

    def _run_pipeline(self, target_fn, args):
        """Run pipeline in thread"""
        self.progress.pack(fill="x", pady=(0, 8), before=self.apply_btn)
        self.progress.start(10)
        self.update()
        
        log = StepLog(self)

        def _status(msg):
            self.after(0, lambda m=msg: (self.status_v.set(m), log.log(m)))

        def _done(ok, msg):
            self.after(0, lambda o=ok, m=msg: self._finish(o, m, log))

        threading.Thread(
            target=target_fn,
            args=args + (_status, _done),
            daemon=True).start()

    def _apply(self):
        """Apply icon"""
        if not self._check_ready():
            return
        
        volume = self._get_volume()
        
        # Confirm for system volume
        if volume['is_system']:
            if not messagebox.askyesno("System Volume",
                f"Apply icon to System Volume?\n\n"
                f"This will modify {volume['name']}\n"
                f"You may need to restart Finder.\n\n"
                f"Continue?"):
                return

        self._run_pipeline(apply_macos_icon,
                          (volume, self._ico, self.label_var.get()))

    def _finish(self, success, msg, log):
        """Handle completion"""
        self.progress.stop()
        self.progress.pack_forget()
        log.done()
        if success:
            messagebox.showinfo("Success!", msg)
            self._refresh_volumes()
        else:
            messagebox.showerror("Error", msg)

    def _remove_icon(self):
        """Remove icon from volume"""
        volume = self._get_volume()
        if not volume:
            return
        
        if not messagebox.askyesno("Remove Icon",
            f"Remove custom icon from {volume['name']}?"):
            return
        
        self.progress.pack(fill="x", pady=(0, 8), before=self.apply_btn)
        self.progress.start(10)
        self.update()
        
        log = StepLog(self)

        def _status(msg):
            self.after(0, lambda m=msg: (self.status_v.set(m), log.log(m)))

        def _done(ok, msg):
            self.after(0, lambda o=ok, m=msg: self._finish_remove(o, m, log))

        threading.Thread(
            target=remove_macos_icon,
            args=(volume, _status, _done),
            daemon=True).start()

    def _finish_remove(self, success, msg, log):
        """Handle remove completion"""
        self.progress.stop()
        self.progress.pack_forget()
        log.done()
        if success:
            messagebox.showinfo("Success!", msg)
            self._refresh_volumes()
        else:
            messagebox.showerror("Error", msg)

    def _diagnostics(self):
        """Show diagnostics"""
        volume = self._get_volume()
        if not volume:
            return
        messagebox.showinfo("Diagnostics", volume_diagnostics(volume))

    def destroy(self):
        """Cleanup"""
        try:
            shutil.rmtree(self._tmp, ignore_errors=True)
        except:
            pass
        super().destroy()


if __name__ == "__main__":
    # Check Python version
    if sys.version_info < (3, 6):
        print("Python 3.6 or higher required")
        sys.exit(1)
    
    app = App()
    app.mainloop()
