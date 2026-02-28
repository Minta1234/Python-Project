#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Linux Drive/Folder Icon Setter
Works on: GNOME, KDE, XFCE, Cinnamon, MATE, LXDE, LXQt, etc.
"""

import os
import sys
import shutil
import subprocess
import tempfile
import time
import glob
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import platform
import pwd
import grp

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
    if u not in sys.path: sys.path.insert(0, u)

try:
    from PIL import Image, ImageTk, ImageDraw
except ModuleNotFoundError:
    _install_pillow()
    try:
        import site
        from importlib import reload; reload(site)
        from PIL import Image, ImageTk, ImageDraw
    except ModuleNotFoundError:
        print(f"Run: {sys.executable} -m pip install Pillow")
        sys.exit(1)

# ── Linux Desktop Environment Detection ───────────────────────────────────────
def detect_desktop_environment():
    """Detect which Linux DE is running"""
    desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
    session = os.environ.get('DESKTOP_SESSION', '').lower()
    
    if 'gnome' in desktop or 'gnome' in session:
        return 'gnome'
    elif 'kde' in desktop or 'kde' in session or 'plasmashell' in session:
        return 'kde'
    elif 'xfce' in desktop or 'xfce' in session:
        return 'xfce'
    elif 'cinnamon' in desktop or 'cinnamon' in session:
        return 'cinnamon'
    elif 'mate' in desktop or 'mate' in session:
        return 'mate'
    elif 'lxde' in desktop or 'lxde' in session:
        return 'lxde'
    elif 'lxqt' in desktop or 'lxqt' in session:
        return 'lxqt'
    elif 'unity' in desktop or 'unity' in session:
        return 'unity'
    elif 'pantheon' in desktop or 'pantheon' in session:
        return 'pantheon'
    elif 'deepin' in desktop or 'deepin' in session:
        return 'deepin'
    else:
        return 'generic'

DE = detect_desktop_environment()

# ── Linux Distribution Detection ──────────────────────────────────────────────
def get_distro():
    """Get Linux distribution name"""
    try:
        with open('/etc/os-release') as f:
            lines = f.readlines()
            for line in lines:
                if line.startswith('NAME='):
                    return line.split('=')[1].strip().strip('"')
    except:
        pass
    return platform.linux_distribution()[0] if hasattr(platform, 'linux_distribution') else 'Linux'

DISTRO = get_distro()

# ── Constants ─────────────────────────────────────────────────────────────────
HOME = os.path.expanduser("~")
CONFIG_DIR = os.path.join(HOME, ".config", "drive-icon-setter")
ICON_STORE = os.path.join(CONFIG_DIR, "icons")
os.makedirs(ICON_STORE, exist_ok=True)

# Mount point detection
def get_mount_points():
    """Get all mounted drives/partitions"""
    mounts = []
    with open('/proc/mounts', 'r') as f:
        for line in f:
            parts = line.split()
            if len(parts) > 1:
                device = parts[0]
                mount_point = parts[1]
                fstype = parts[2]
                
                # Skip pseudo filesystems
                if fstype in ['proc', 'sysfs', 'devtmpfs', 'tmpfs', 'devpts', 'fusectl', 
                             'securityfs', 'cgroup', 'pstore', 'debugfs', 'hugetlbfs',
                             'mqueue', 'configfs', 'binfmt_misc', 'rpc_pipefs']:
                    continue
                    
                # Skip system directories
                if mount_point in ['/boot', '/boot/efi', '/dev', '/sys', '/proc', '/run']:
                    continue
                    
                # Get device info
                try:
                    stat = os.statvfs(mount_point)
                    total = stat.f_blocks * stat.f_frsize
                    free = stat.f_bavail * stat.f_frsize
                    used = (stat.f_blocks - stat.f_bfree) * stat.f_frsize
                    
                    # Get label if available
                    label = get_filesystem_label(device)
                    
                    mounts.append({
                        'device': device,
                        'mount_point': mount_point,
                        'fstype': fstype,
                        'total': total,
                        'used': used,
                        'free': free,
                        'label': label or os.path.basename(mount_point)
                    })
                except:
                    pass
    return mounts

def get_filesystem_label(device):
    """Get filesystem label for a device"""
    try:
        if device.startswith('/dev/'):
            # Try blkid command
            result = subprocess.run(['blkid', '-s', 'LABEL', '-o', 'value', device],
                                   capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
    except:
        pass
    return None

def get_removable_mounts():
    """Get removable drives (USB, external HDD)"""
    removable = []
    mounts = get_mount_points()
    
    for mount in mounts:
        device = mount['device']
        if device.startswith('/dev/'):
            # Check if it's a removable device
            try:
                # Get base device name (e.g., sdb from /dev/sdb1)
                base_device = ''.join(c for c in device if c.isalpha())[5:]  # remove /dev/
                base_device = base_device.rstrip('0123456789')
                
                # Check sysfs for removable flag
                removable_path = f'/sys/block/{base_device}/removable'
                if os.path.exists(removable_path):
                    with open(removable_path, 'r') as f:
                        if f.read().strip() == '1':
                            mount['type'] = 'removable'
                            removable.append(mount)
                            continue
                
                # Check if it's a USB device
                usb_path = f'/sys/block/{base_device}'
                if os.path.exists(usb_path):
                    if 'usb' in os.path.realpath(usb_path):
                        mount['type'] = 'usb'
                        removable.append(mount)
                        continue
                
                mount['type'] = 'fixed'
            except:
                mount['type'] = 'unknown'
    
    return removable

# ── ICO converter ─────────────────────────────────────────────────────────────
SIZES = [256, 128, 64, 48, 32, 16]

def pil_to_png_set(img, out_dir, base_name):
    """Convert PIL image to PNGs of different sizes (Linux uses PNG for icons)"""
    img = img.convert("RGBA")
    icons = []
    for size in SIZES:
        resized = img.resize((size, size), Image.LANCZOS)
        out_path = os.path.join(out_dir, f"{base_name}_{size}.png")
        resized.save(out_path, "PNG")
        icons.append(out_path)
    return icons

def create_desktop_icon_set(img, out_dir, base_name="icon"):
    """Create a set of icons for Linux desktop"""
    return pil_to_png_set(img, out_dir, base_name)

# ═══════════════════════════════════════════════════════════════════════════════
#  LINUX DESKTOP INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════

def set_icon_gnome(path, icon_path):
    """Set icon for GNOME (Nautilus)"""
    try:
        # Create .directory file
        dir_file = os.path.join(path, ".directory")
        with open(dir_file, 'w') as f:
            f.write(f"""[Desktop Entry]
Icon={icon_path}
Type=Directory
""")
        
        # Set appropriate permissions
        os.chmod(dir_file, 0o644)
        
        # Set hidden attribute (optional)
        subprocess.run(['gio', 'set', path, 'metadata::hidden', 'false'], 
                      capture_output=True)
        
        # Restart nautilus
        subprocess.run(['nautilus', '-q'], capture_output=True)
        time.sleep(1)
        
        return True, f"Icon set for GNOME (Nautilus) using {icon_path}"
    except Exception as e:
        return False, str(e)

def set_icon_kde(path, icon_path):
    """Set icon for KDE Plasma (Dolphin)"""
    try:
        # KDE uses .directory files with different structure
        dir_file = os.path.join(path, ".directory")
        with open(dir_file, 'w') as f:
            f.write(f"""[Desktop Entry]
Icon={icon_path}
""")
        
        # Also create/update user-dirs.dirs if needed
        user_dirs = os.path.expanduser("~/.config/user-dirs.dirs")
        if os.path.exists(user_dirs):
            # KDE might need this updated
            pass
        
        # Restart dolphin
        subprocess.run(['kbuildsycoca5'], capture_output=True)
        time.sleep(1)
        
        return True, f"Icon set for KDE Plasma using {icon_path}"
    except Exception as e:
        return False, str(e)

def set_icon_xfce(path, icon_path):
    """Set icon for XFCE (Thunar)"""
    try {
        # XFCE uses gio/gsettings
        subprocess.run(['gio', 'set', path, 'metadata::custom-icon', icon_path],
                      capture_output=True)
        
        # Alternative: create .directory
        dir_file = os.path.join(path, ".directory")
        with open(dir_file, 'w') as f:
            f.write(f"""[Desktop Entry]
Icon={icon_path}
""")
        
        return True, f"Icon set for XFCE using {icon_path}"
    except Exception as e:
        return False, str(e)

def set_icon_cinnamon(path, icon_path):
    """Set icon for Cinnamon (Nemo)"""
    try:
        # Cinnamon uses gsettings
        subprocess.run(['gsettings', 'set', 'org.nemo', 'show-icon-file', 'true'],
                      capture_output=True)
        
        # Use gio to set metadata
        subprocess.run(['gio', 'set', path, 'metadata::custom-icon', icon_path],
                      capture_output=True)
        
        # Restart nemo
        subprocess.run(['nemo', '-q'], capture_output=True)
        time.sleep(1)
        
        return True, f"Icon set for Cinnamon using {icon_path}"
    except Exception as e:
        return False, str(e)

def set_icon_mate(path, icon_path):
    """Set icon for MATE (Caja)"""
    try:
        # MATE uses gio/gsettings
        subprocess.run(['gsettings', 'set', 'org.mate.caja', 'show-icon-file', 'true'],
                      capture_output=True)
        
        # Set custom icon via gio
        subprocess.run(['gio', 'set', path, 'metadata::custom-icon', icon_path],
                      capture_output=True)
        
        # Restart caja
        subprocess.run(['caja', '-q'], capture_output=True)
        time.sleep(1)
        
        return True, f"Icon set for MATE using {icon_path}"
    except Exception as e:
        return False, str(e)

def set_icon_lxde(path, icon_path):
    """Set icon for LXDE (PCManFM)"""
    try:
        # LXDE uses simple configuration
        dir_file = os.path.join(path, ".directory")
        with open(dir_file, 'w') as f:
            f.write(f"""[Desktop Entry]
Icon={icon_path}
""")
        
        return True, f"Icon set for LXDE using {icon_path}"
    except Exception as e:
        return False, str(e)

def set_icon_lxqt(path, icon_path):
    """Set icon for LXQt (PCManFM-Qt)"""
    try:
        # LXQt uses same .directory method
        dir_file = os.path.join(path, ".directory")
        with open(dir_file, 'w') as f:
            f.write(f"""[Desktop Entry]
Icon={icon_path}
""")
        
        return True, f"Icon set for LXQt using {icon_path}"
    except Exception as e:
        return False, str(e)

def set_icon_generic(path, icon_path):
    """Generic method for unknown DEs"""
    try:
        # Create .directory file (works on most DEs)
        dir_file = os.path.join(path, ".directory")
        with open(dir_file, 'w') as f:
            f.write(f"""[Desktop Entry]
Icon={icon_path}
Type=Directory
""")
        
        # Also try gio if available
        try:
            subprocess.run(['gio', 'set', path, 'metadata::custom-icon', icon_path],
                          capture_output=True)
        except:
            pass
        
        return True, f"Icon set using generic method with {icon_path}"
    except Exception as e:
        return False, str(e)

def set_icon_udev_rule(drive, icon_path):
    """Set icon for mounted drive using udev (system-wide)"""
    try:
        if os.geteuid() == 0:  # Root
            # Create udev rule for persistent icon
            device = drive['device'].replace('/', '_')
            rule = f"""# Custom icon for {drive['mount_point']}
SUBSYSTEM=="block", KERNEL=="{device}", ACTION=="add|change", RUN+="/usr/local/bin/set-drive-icon.sh {drive['mount_point']} {icon_path}"
"""
            rule_path = f"/etc/udev/rules.d/99-drive-icon-{device}.rules"
            with open(rule_path, 'w') as f:
                f.write(rule)
            
            # Create helper script
            script_path = "/usr/local/bin/set-drive-icon.sh"
            with open(script_path, 'w') as f:
                f.write(f"""#!/bin/bash
# Wait for mount
sleep 2
# Set icon
if [ -d "$1" ]; then
    echo "[Desktop Entry]\nIcon=$2\nType=Directory" > "$1/.directory"
fi
""")
            os.chmod(script_path, 0o755)
            
            subprocess.run(['udevadm', 'control', '--reload-rules'], capture_output=True)
            subprocess.run(['udevadm', 'trigger'], capture_output=True)
            
            return True, "Created udev rule for persistent icon"
        else:
            return False, "Need root for udev rules"
    except Exception as e:
        return False, str(e)

# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN APPLY FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def apply_icon_linux(drive, icon_src, label, persistent, status_cb, done_cb):
    """Apply icon to drive/folder on Linux"""
    mount_point = drive['mount_point']
    t0 = time.time()
    
    def step(msg):
        status_cb(f"[{time.time()-t0:.1f}s] {msg}")
    
    try:
        # Create icon set in store
        icon_name = f"drive_{os.path.basename(mount_point)}_{int(time.time())}"
        icon_dir = os.path.join(ICON_STORE, icon_name)
        os.makedirs(icon_dir, exist_ok=True)
        
        step("[1/5] Converting icon for Linux...")
        icon_files = create_desktop_icon_set(icon_src, icon_dir, "icon")
        
        # Use largest icon for display
        icon_path = icon_files[0]  # 256px
        
        step(f"[2/5] Detected DE: {DE.upper()}")
        
        # Apply icon based on DE
        step("[3/5] Setting icon...")
        
        if DE == 'gnome':
            success, msg = set_icon_gnome(mount_point, icon_path)
        elif DE == 'kde':
            success, msg = set_icon_kde(mount_point, icon_path)
        elif DE == 'xfce':
            success, msg = set_icon_xfce(mount_point, icon_path)
        elif DE == 'cinnamon':
            success, msg = set_icon_cinnamon(mount_point, icon_path)
        elif DE == 'mate':
            success, msg = set_icon_mate(mount_point, icon_path)
        elif DE == 'lxde':
            success, msg = set_icon_lxde(mount_point, icon_path)
        elif DE == 'lxqt':
            success, msg = set_icon_lxqt(mount_point, icon_path)
        else:
            success, msg = set_icon_generic(mount_point, icon_path)
        
        if not success:
            raise Exception(msg)
        
        step(f"[3/5] {msg}")
        
        # Set label if provided
        if label.strip():
            step("[4/5] Setting volume label...")
            try:
                # Try to set filesystem label (needs root)
                if os.geteuid() == 0 and drive['device'].startswith('/dev/'):
                    if 'ext' in drive['fstype']:
                        subprocess.run(['e2label', drive['device'], label.strip()],
                                     capture_output=True)
                    elif 'ntfs' in drive['fstype']:
                        subprocess.run(['ntfslabel', drive['device'], label.strip()],
                                     capture_output=True)
                    elif 'vfat' in drive['fstype'] or 'fat' in drive['fstype']:
                        subprocess.run(['fatlabel', drive['device'], label.strip()],
                                     capture_output=True)
            except:
                pass
        
        # Create persistent rule if requested and possible
        if persistent:
            step("[5/5] Creating persistent rule...")
            pers_success, pers_msg = set_icon_udev_rule(drive, icon_path)
            if pers_success:
                step(f"[5/5] {pers_msg}")
        
        total = time.time() - t0
        step(f"[DONE] Finished in {total:.1f}s")
        
        # Success message
        done_cb(True,
                f"Icon applied to {mount_point}\n"
                f"Desktop Environment: {DE.upper()}\n"
                f"Distribution: {DISTRO}\n\n"
                f"Icon path: {icon_path}\n"
                f"Method: {msg}\n\n"
                f"You may need to refresh your file manager:\n"
                f"  GNOME: Alt+F2 → 'r' (or restart)\n"
                f"  KDE:   F5\n"
                f"  Other: Log out/in or restart")
        
    except Exception as e:
        import traceback
        done_cb(False, f"Error: {e}\n\n{traceback.format_exc()}")

# ── Diagnostics ───────────────────────────────────────────────────────────────
def drive_diagnostics_linux(drive):
    """Get diagnostics info for Linux"""
    mount_point = drive['mount_point']
    lines = []
    lines.append(f"=== Diagnostics: {mount_point} ===")
    lines.append(f"Device: {drive['device']}")
    lines.append(f"Filesystem: {drive['fstype']}")
    lines.append(f"Label: {drive.get('label', 'None')}")
    lines.append(f"Type: {drive.get('type', 'unknown')}")
    lines.append(f"Desktop Environment: {DE.upper()}")
    lines.append(f"Distribution: {DISTRO}")
    
    # Check for .directory file
    dir_file = os.path.join(mount_point, ".directory")
    if os.path.exists(dir_file):
        lines.append(f".directory: EXISTS")
        try:
            with open(dir_file, 'r') as f:
                content = f.read().strip()
                lines.append(f"Content:\n{content}")
        except:
            pass
    else:
        lines.append(f".directory: missing")
    
    # Check gio metadata (GNOME/others)
    try:
        result = subprocess.run(['gio', 'info', mount_point], 
                              capture_output=True, text=True)
        if 'metadata::custom-icon' in result.stdout:
            lines.append("gio metadata: custom icon set")
    except:
        pass
    
    return "\n".join(lines)

def refresh_file_manager():
    """Refresh current file manager"""
    if DE == 'gnome':
        subprocess.Popen(['nautilus', '-q'])
    elif DE == 'kde':
        subprocess.Popen(['kbuildsycoca5'])
    elif DE == 'cinnamon':
        subprocess.Popen(['nemo', '-q'])
    elif DE == 'mate':
        subprocess.Popen(['caja', '-q'])
    # For others, just suggest manual refresh

# ── Colours (Catppuccin theme) ────────────────────────────────────────────────
BG="#1e1e2e"; SURFACE="#313244"; OVERLAY="#45475a"; TEXT="#cdd6f4"
SUBTEXT="#a6adc8"; ACCENT="#89b4fa"; GREEN="#a6e3a1"; RED="#f38ba8"
YELLOW="#f9e2af"; ORANGE="#fab387"; PURPLE="#cba6f7"

def flat_btn(parent, text, cmd, accent=False, color=None, **kw):
    bg = color or (ACCENT if accent else SURFACE)
    fg = "#1e1e2e" if (accent or color) else TEXT
    return tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                     activebackground="#b4befe" if accent else OVERLAY,
                     activeforeground="#1e1e2e" if accent else TEXT,
                     relief="flat", cursor="hand2", bd=0,
                     font=("Sans", 10, "bold" if accent else "normal"),
                     padx=10, pady=6, **kw)

# ── Step Log Window ───────────────────────────────────────────────────────────
class StepLog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Progress")
        self.configure(bg=BG, padx=16, pady=14)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        
        de_text = f"Live Progress - {DE.upper()} on {DISTRO}"
        tk.Label(self, text=de_text, bg=BG, fg=ACCENT,
                 font=("Sans", 11, "bold")).pack(anchor="w", pady=(0,6))
        
        self.txt = tk.Text(self, width=62, height=16,
                           bg=SURFACE, fg=GREEN,
                           font=("Monospace", 9), relief="flat",
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

# ── Crop Editor (same as Windows version) ─────────────────────────────────────
EDITOR_SIZE = 320

class CropEditor(tk.Toplevel):
    def __init__(self, parent, pil_image, callback):
        super().__init__(parent)
        self.title("Edit Icon — Drag to pan  |  Scroll to zoom")
        self.configure(bg=BG, padx=20, pady=16)
        self.resizable(False, False); self.grab_set()
        self._src=pil_image.convert("RGBA"); self._cb=callback
        self._zoom=1.0; self._off=[0,0]; self._drag=None; self._smi=[]
        self._build(); self._center(); self._redraw()

    def _build(self):
        top=tk.Frame(self,bg=BG); top.pack(fill="x",pady=(0,10))
        lf=tk.Frame(top,bg=BG); lf.pack(side="left",padx=(0,16))
        tk.Label(lf,text="Drag to pan  |  Scroll to zoom",
                 bg=BG,fg=SUBTEXT,font=("Sans",8)).pack()
        self.cv=tk.Canvas(lf,width=EDITOR_SIZE,height=EDITOR_SIZE,
                          bg="#000",highlightthickness=2,
                          highlightbackground=ACCENT,cursor="fleur")
        self.cv.pack()
        self.cv.bind("<ButtonPress-1>",self._ds)
        self.cv.bind("<B1-Motion>",    self._dm)
        self.cv.bind("<MouseWheel>",   self._mw)
        rf=tk.Frame(top,bg=BG); rf.pack(side="left",anchor="n")
        tk.Label(rf,text="Preview (256px)",bg=BG,fg=SUBTEXT,
                 font=("Sans",8)).pack()
        self.pv=tk.Canvas(rf,width=128,height=128,bg="#000",
                          highlightthickness=1,highlightbackground=OVERLAY)
        self.pv.pack(pady=(0,8))
        tk.Label(rf,text="Small sizes:",bg=BG,fg=SUBTEXT,
                 font=("Sans",8)).pack(anchor="w")
        self.sm=tk.Canvas(rf,width=128,height=52,
                          bg="#2a2a3e",highlightthickness=0)
        self.sm.pack()
        tk.Label(rf,text="Background:",bg=BG,fg=SUBTEXT,
                 font=("Sans",8)).pack(anchor="w",pady=(10,2))
        self._bg=tk.StringVar(value="transparent")
        for v,l in [("transparent","Transparent"),("white","White"),
                    ("black","Black"),("circle","Circle crop")]:
            tk.Radiobutton(rf,text=l,variable=self._bg,value=v,
                           bg=BG,fg=TEXT,selectcolor=SURFACE,
                           activebackground=BG,activeforeground=TEXT,
                           font=("Sans",9),
                           command=self._redraw).pack(anchor="w")
        zm=tk.Frame(self,bg=BG); zm.pack(fill="x",pady=(0,12))
        tk.Label(zm,text="Zoom:",bg=BG,fg=TEXT,
                 font=("Sans",10)).pack(side="left")
        self.zsl=tk.Scale(zm,from_=10,to=500,orient="horizontal",
                          bg=BG,fg=TEXT,troughcolor=SURFACE,
                          highlightthickness=0,showvalue=False,
                          command=self._zc)
        self.zsl.set(100)
        self.zsl.pack(side="left",fill="x",expand=True,padx=(8,8))
        self.zlb=tk.Label(zm,text="100%",bg=BG,fg=ACCENT,
                          font=("Sans",10,"bold"),width=5)
        self.zlb.pack(side="left")
        br=tk.Frame(self,bg=BG); br.pack(fill="x")
        flat_btn(br,"Fit",      self._fit).pack(side="left",padx=(0,8))
        flat_btn(br,"Cancel",   self.destroy).pack(side="right",padx=(8,0))
        flat_btn(br,"Use this icon",self._confirm,
                 accent=True).pack(side="right")

    def _center(self):
        sw,sh=self._src.size
        self._zoom=min(EDITOR_SIZE/sw, EDITOR_SIZE/sh)
        self._off=[(sw-EDITOR_SIZE/self._zoom)/2,
                   (sh-EDITOR_SIZE/self._zoom)/2]
        self.zsl.set(int(self._zoom*100))

    def _fit(self): self._center(); self._redraw()

    def _zc(self,v):
        cx=self._off[0]+(EDITOR_SIZE/2)/self._zoom
        cy=self._off[1]+(EDITOR_SIZE/2)/self._zoom
        self._zoom=max(0.1,int(v)/100)
        self._off[0]=cx-(EDITOR_SIZE/2)/self._zoom
        self._off[1]=cy-(EDITOR_SIZE/2)/self._zoom
        self.zlb.config(text=f"{int(v)}%"); self._redraw()

    def _ds(self,e): self._drag=(e.x,e.y,self._off[0],self._off[1])
    def _dm(self,e):
        if not self._drag: return
        sx,sy,ox,oy=self._drag
        self._off=[ox+(sx-e.x)/self._zoom, oy+(sy-e.y)/self._zoom]
        self._redraw()
    def _mw(self,e):
        f=1.1 if e.delta>0 else 0.9
        nz=max(0.1,min(5.0,self._zoom*f))
        cx=self._off[0]+(EDITOR_SIZE/2)/self._zoom
        cy=self._off[1]+(EDITOR_SIZE/2)/self._zoom
        self._zoom=nz
        self._off[0]=cx-(EDITOR_SIZE/2)/self._zoom
        self._off[1]=cy-(EDITOR_SIZE/2)/self._zoom
        self.zsl.set(int(self._zoom*100))
        self.zlb.config(text=f"{int(self._zoom*100)}%"); self._redraw()

    def _crop(self,size=256):
        sw,sh=self._src.size; x0,y0=self._off
        x1=x0+EDITOR_SIZE/self._zoom; y1=y0+EDITOR_SIZE/self._zoom
        bv=self._bg.get()
        ci=Image.new("RGBA",(EDITOR_SIZE,EDITOR_SIZE),
                     (255,255,255,255) if bv=="white" else
                     (0,0,0,255) if bv=="black" else (0,0,0,0))
        sx0,sy0=max(0,x0),max(0,y0)
        sx1,sy1=min(sw,x1),min(sh,y1)
        if sx1>sx0 and sy1>sy0:
            rg=self._src.crop((sx0,sy0,sx1,sy1))
            px=int((sx0-x0)*self._zoom); py=int((sy0-y0)*self._zoom)
            pw=max(1,int((sx1-sx0)*self._zoom))
            ph=max(1,int((sy1-sy0)*self._zoom))
            rs=rg.resize((pw,ph),Image.LANCZOS)
            ci.paste(rs,(px,py),rs)
        if bv=="circle":
            mk=Image.new("L",(EDITOR_SIZE,EDITOR_SIZE),0)
            ImageDraw.Draw(mk).ellipse(
                (0,0,EDITOR_SIZE-1,EDITOR_SIZE-1),fill=255)
            ot=Image.new("RGBA",(EDITOR_SIZE,EDITOR_SIZE),(0,0,0,0))
            ot.paste(ci,mask=mk); ci=ot
        return ci.resize((size,size),Image.LANCZOS)

    @staticmethod
    def _chk(size,b=8):
        img=Image.new("RGBA",(size,size)); d=ImageDraw.Draw(img)
        for y in range(0,size,b):
            for x in range(0,size,b):
                c=((200,200,200,255) if (x//b+y//b)%2==0
                   else (160,160,160,255))
                d.rectangle([x,y,x+b-1,y+b-1],fill=c)
        return img

    def _redraw(self):
        img=self._crop(EDITOR_SIZE)
        self._te=ImageTk.PhotoImage(
            Image.alpha_composite(self._chk(EDITOR_SIZE),img))
        self.cv.delete("all")
        self.cv.create_image(0,0,anchor="nw",image=self._te)
        pv=img.resize((128,128),Image.LANCZOS)
        self._tp=ImageTk.PhotoImage(
            Image.alpha_composite(self._chk(128),pv))
        self.pv.delete("all")
        self.pv.create_image(0,0,anchor="nw",image=self._tp)
        self.sm.delete("all"); self._smi=[]; x=4
        for s in [48,32,16]:
            ti=ImageTk.PhotoImage(Image.alpha_composite(
                self._chk(s),img.resize((s,s),Image.LANCZOS)))
            self._smi.append(ti)
            self.sm.create_image(x,26,anchor="w",image=ti)
            self.sm.create_text(x+s+2,42,anchor="w",text=f"{s}px",
                                fill=SUBTEXT,font=("Sans",7))
            x+=s+28

    def _confirm(self): self._cb(self._crop(256)); self.destroy()

# ── Main App ──────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Linux Drive Icon Setter  v1.0  ({DE.upper()} on {DISTRO})")
        self.configure(bg=BG, padx=28, pady=22)
        self.resizable(False, False)
        self._src = None
        self._final = None
        self._ico = None
        self._tmp = tempfile.mkdtemp()
        self._thumb = None
        self._mounts = []
        self.drive_var = tk.StringVar()
        self.label_var = tk.StringVar()
        self.persistent_var = tk.BooleanVar(value=False)
        self._build_ui()
        
        # Check if running as root for persistent rules
        if os.geteuid() != 0:
            self._non_root_banner()

    def _build_ui(self):
        # Title
        title_text = f"  Linux Drive Icon Setter  v1.0  ({DE.upper()})"
        tk.Label(self, text=title_text, bg=BG, fg=ACCENT,
                 font=("Sans", 15, "bold")).pack(anchor="w", pady=(0, 4))

        # Info frame
        info = tk.Frame(self, bg=SURFACE, padx=12, pady=8)
        info.pack(fill="x", pady=(0, 6))
        
        tk.Label(info,
                 text=f"Desktop: {DE.upper()}  |  Distro: {DISTRO}",
                 bg=SURFACE, fg=GREEN,
                 font=("Sans", 9, "bold")).pack(anchor="w")
        tk.Label(info,
                 text="Mount points | .directory files | gio metadata",
                 bg=SURFACE, fg=SUBTEXT,
                 font=("Sans", 9)).pack(anchor="w")

        # Step 1 - Choose image
        self._sec("Step 1  —  Choose an image")
        f1 = tk.Frame(self, bg=BG)
        f1.pack(fill="x", pady=(0, 8))
        self.img_var = tk.StringVar()
        tk.Entry(f1, textvariable=self.img_var, width=38, bg=SURFACE, fg=TEXT,
                 insertbackground=TEXT, relief="flat", font=("Sans", 10),
                 state="readonly", readonlybackground=SURFACE
                 ).pack(side="left", padx=(0, 8), ipady=5)
        flat_btn(f1, "Browse…", self._browse).pack(side="left")

        fp = tk.Frame(self, bg=BG)
        fp.pack(fill="x", pady=(4, 0))
        self.thumb_cv = tk.Canvas(fp, width=96, height=96, bg=SURFACE,
                                   highlightthickness=1,
                                   highlightbackground=OVERLAY)
        self.thumb_cv.pack(side="left")
        self.thumb_cv.create_text(48, 48, text="preview",
                                   fill=SUBTEXT, font=("Sans", 9))
        fi = tk.Frame(fp, bg=BG, padx=14)
        fi.pack(side="left", fill="both")
        self.info_v = tk.StringVar(value="No image selected.")
        tk.Label(fi, textvariable=self.info_v, bg=BG, fg=SUBTEXT,
                 font=("Sans", 9), justify="left").pack(anchor="w")
        self.conv_l = tk.Label(fi, text="", bg=BG, fg=GREEN,
                                font=("Sans", 9, "bold"), justify="left")
        self.conv_l.pack(anchor="w", pady=(4, 0))
        flat_btn(fi, "  Edit / Crop icon  ",
                 self._open_editor, color=PURPLE).pack(anchor="w", pady=(10, 0))

        # Step 2 - Select mount point
        self._sec("Step 2  —  Select mount point & label")
        f2 = tk.Frame(self, bg=BG)
        f2.pack(fill="x", pady=(0, 4))
        tk.Label(f2, text="Mount :", bg=BG, fg=TEXT,
                 font=("Sans", 10)).grid(row=0, column=0, sticky="w", pady=5)
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TCombobox",
                        fieldbackground=SURFACE, background=SURFACE,
                        foreground=TEXT, selectbackground=SURFACE,
                        selectforeground=TEXT)
        self.combo = ttk.Combobox(f2, textvariable=self.drive_var,
                                   width=32, state="readonly")
        self.combo.grid(row=0, column=1, padx=(8, 8), sticky="w")
        self.combo.bind("<<ComboboxSelected>>", self._on_drive)
        flat_btn(f2, "Refresh", self._refresh_mounts).grid(row=0, column=2)
        
        tk.Label(f2, text="Label :", bg=BG, fg=TEXT,
                 font=("Sans", 10)).grid(row=1, column=0, sticky="w", pady=5)
        tk.Entry(f2, textvariable=self.label_var, width=34, bg=SURFACE, fg=TEXT,
                 insertbackground=TEXT, relief="flat", font=("Sans", 10)
                 ).grid(row=1, column=1, padx=(8, 0), ipady=5, sticky="w")

        self.cur_icon_l = tk.Label(self, text="", bg=BG, fg=SUBTEXT,
                                    font=("Sans", 8), anchor="w")
        self.cur_icon_l.pack(fill="x", pady=(0, 2))
        
        self.info_l = tk.Label(self, text="", bg=BG, fg=ORANGE,
                                font=("Sans", 9, "bold"),
                                anchor="w", justify="left")
        self.info_l.pack(fill="x", pady=(0, 4))

        # Step 3 - Options
        self._sec("Step 3  —  Options & Apply")
        tk.Checkbutton(
            self, text="Create persistent rule (requires root for udev)",
            variable=self.persistent_var, bg=BG, fg=TEXT, selectcolor=SURFACE,
            activebackground=BG, activeforeground=TEXT,
            font=("Sans", 10)).pack(anchor="w")

        # Progress bar
        self.progress = ttk.Progressbar(self, mode="indeterminate", length=420)
        tk.Frame(self, bg=BG, height=12).pack()

        self.apply_btn = flat_btn(self, "  Apply Icon to Mount Point  ",
                                   self._apply, accent=True)
        self.apply_btn.pack(fill="x")

        self.status_v = tk.StringVar(value="Ready.")
        tk.Label(self, textvariable=self.status_v, bg="#181825", fg=SUBTEXT,
                 anchor="w", font=("Monospace", 9), padx=10, pady=5
                 ).pack(fill="x", pady=(8, 0))

        bf = tk.Frame(self, bg=BG)
        bf.pack(fill="x", pady=(6, 0))
        flat_btn(bf, "  Remove Icon  ",
                 self._remove_icon,
                 color="#585b70").pack(side="left", fill="x",
                                        expand=True, padx=(0, 3))
        flat_btn(bf, "  Diagnostics  ",
                 self._diagnostics,
                 color=ORANGE).pack(side="left", fill="x",
                                     expand=True, padx=(3, 0))
        flat_btn(bf, "  Refresh FM  ",
                 self._refresh_fm,
                 color=GREEN).pack(side="left", fill="x",
                                    expand=True, padx=(3, 0))

        self._refresh_mounts()

    def _non_root_banner(self):
        """Show banner if not running as root"""
        b = tk.Frame(self, bg=YELLOW, padx=10, pady=8)
        b.pack(fill="x", before=self.winfo_children()[0])
        tk.Label(b,
                 text="  Not running as root — Persistent udev rules won't work!",
                 bg=YELLOW, fg="#1e1e2e",
                 font=("Sans", 9, "bold")).pack(side="left")

    def _sec(self, title):
        tk.Label(self, text=title, bg=BG, fg=ACCENT,
                 font=("Sans", 10, "bold")).pack(anchor="w", pady=(14, 4))
        tk.Frame(self, bg=OVERLAY, height=1).pack(fill="x", pady=(0, 8))

    def _refresh_mounts(self):
        """Refresh list of mount points"""
        self._mounts = get_mount_points()
        removable = get_removable_mounts()
        
        # Mark removable drives
        removable_set = {m['mount_point'] for m in removable}
        for m in self._mounts:
            if m['mount_point'] in removable_set:
                m['type'] = 'removable'
            else:
                m.setdefault('type', 'fixed')
        
        choices = []
        for m in self._mounts:
            mount = m['mount_point']
            label = m.get('label', '')
            fstype = m['fstype']
            dtype = m.get('type', 'fixed')
            
            # Format size
            total_gb = m['total'] / (1024**3)
            size_str = f"{total_gb:.1f}GB" if total_gb >= 1 else f"{m['total']/(1024**2):.0f}MB"
            
            type_icon = "💾" if dtype == 'removable' else "💽"
            display = f"{type_icon} {mount}  {label}  ({fstype}, {size_str})"
            choices.append(display)
        
        self.combo["values"] = choices
        if choices:
            self.combo.current(0)
        self._on_drive()

    def _get_drive(self):
        """Get selected drive info"""
        idx = self.combo.current()
        if idx < 0 or idx >= len(self._mounts):
            return None
        return self._mounts[idx]

    def _on_drive(self, event=None):
        """Handle drive selection"""
        if not hasattr(self, "info_l"):
            return
        drive = self._get_drive()
        if not drive:
            return
        
        mount = drive['mount_point']
        dtype = drive.get('type', 'fixed')
        
        # Check for existing icon
        dir_file = os.path.join(mount, ".directory")
        if os.path.exists(dir_file):
            self.cur_icon_l.config(text=f"Custom icon found: {dir_file}")
        else:
            self.cur_icon_l.config(text="No custom icon set for this mount point.")
        
        # Show info
        info_text = f"  Device: {drive['device']}  |  Type: {dtype}  |  FS: {drive['fstype']}"
        self.info_l.config(text=info_text, fg=SUBTEXT)

    def _browse(self):
        """Browse for image file"""
        path = filedialog.askopenfilename(
            title="Select image",
            filetypes=[("Image files",
                       "*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tiff *.tif *.svg"),
                      ("All files", "*.*")])
        if not path:
            return
        try:
            img = Image.open(path)
            self._src = img.convert("RGBA")
            self.img_var.set(path)
            ext = os.path.splitext(path)[1].upper()
            self.info_v.set(
                f"File : {os.path.basename(path)}\n"
                f"Size : {img.width} x {img.height} px  |  {ext}")
            self._ico = None
            self._final = None
            self.conv_l.config(
                text="Click Edit / Crop icon to adjust.", fg=YELLOW)
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
            # For Linux, we'll create PNG set later
            self._ico = result  # Store PIL image for later conversion
            self.conv_l.config(text="Icon ready!  Click Apply.", fg=GREEN)
            self.status_v.set("Icon ready.")
        except Exception as e:
            self.conv_l.config(text=f"Prepare failed: {e}", fg=RED)

    def _apply(self):
        """Apply icon to mount point"""
        if self._final is None:
            messagebox.showwarning("Not ready",
                "Please select and edit an image first.")
            return
        
        drive = self._get_drive()
        if not drive:
            messagebox.showwarning("No Mount Point", "Please select a mount point.")
            return
        
        # Check if mount point is writable
        if not os.access(drive['mount_point'], os.W_OK):
            if not messagebox.askyesno("Permission",
                f"Mount point {drive['mount_point']} is not writable.\n"
                f"Run as root with sudo?\n\n"
                f"Current user: {os.getlogin()}"):
                return
        
        # Show progress
        self.progress.pack(fill="x", pady=(0, 8), before=self.apply_btn)
        self.progress.start(10)
        self.update()

        log = StepLog(self)

        def _status(msg):
            self.after(0, lambda m=msg: (
                self.status_v.set(m), log.log(m)))

        def _done(ok, msg):
            self.after(0, lambda o=ok, m=msg: self._finish(o, m, log))

        threading.Thread(
            target=apply_icon_linux,
            args=(drive, self._final, self.label_var.get(),
                  self.persistent_var.get(),
                  _status, _done),
            daemon=True).start()

    def _finish(self, success, msg, log):
        """Handle apply completion"""
        self.progress.stop()
        self.progress.pack_forget()
        log.done()
        if success:
            messagebox.showinfo("Done!", msg)
            self._refresh_mounts()
        else:
            messagebox.showerror("Error", msg)

    def _remove_icon(self):
        """Remove custom icon from mount point"""
        drive = self._get_drive()
        if not drive:
            return
        
        mount = drive['mount_point']
        
        if not messagebox.askyesno("Remove Icon",
            f"Remove custom icon from {mount}?\n"
            f"Will restore default icon."):
            return
        
        try:
            # Remove .directory file
            dir_file = os.path.join(mount, ".directory")
            if os.path.exists(dir_file):
                os.remove(dir_file)
            
            # Remove gio metadata if exists
            try:
                subprocess.run(['gio', 'set', mount, 'metadata::custom-icon', ''],
                             capture_output=True)
            except:
                pass
            
            self.status_v.set("Icon removed. Refreshing...")
            self.update()
            
            def _run():
                time.sleep(1)
                self.after(0, lambda: (
                    self.status_v.set("Default icon restored."),
                    self._on_drive()))
            
            threading.Thread(target=_run, daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _diagnostics(self):
        """Show diagnostics"""
        drive = self._get_drive()
        if not drive:
            return
        messagebox.showinfo("Diagnostics", drive_diagnostics_linux(drive))

    def _refresh_fm(self):
        """Refresh file manager"""
        refresh_file_manager()
        self.status_v.set(f"Refreshed {DE.upper()} file manager")

    def destroy(self):
        """Cleanup on exit"""
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
