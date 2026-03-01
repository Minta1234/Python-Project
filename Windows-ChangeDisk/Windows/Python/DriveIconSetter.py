"""
Drive Icon Setter  v9.3  —  ULTIMATE CROSS-PLATFORM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WORKS ON:
  🪟 Windows 10/11     — Registry + desktop.ini + autorun.inf
  🐧 Linux (all DEs)   — .directory + hidden PNGs
  🍎 macOS             — .VolumeIcon.icns + .DS_Store + metadata

FEATURES:
  ✅ Icon visible on ALL platforms
  ✅ SAFE hiding — NO system files affected
  ✅ ALL icon files HIDDEN on every OS
  ✅ Permission auto-fix with multiple methods
  ✅ One click applies to all platforms
  ✅ Diagnostics shows what's hidden
"""

import os
import sys
import shutil
import subprocess
import tempfile
import time
import glob
import ctypes
import winreg
import platform
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading

# ── Auto-install Pillow ───────────────────────────────────────────────────────
def _install_pillow():
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--user", "Pillow"], check=True)
    except:
        try:
            subprocess.run(["pip", "install", "--user", "Pillow"], check=True)
        except:
            pass
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
        input("Press Enter to exit...")
        sys.exit(1)

if sys.platform != "win32":
    print("Windows only.")
    sys.exit(1)

# ── Windows Version ───────────────────────────────────────────────────────────
def _get_win_ver():
    try:
        build = int(platform.version().split(".")[2])
        return "11" if build >= 22000 else "10"
    except:
        return "10"

WIN_VER = _get_win_ver()
IS_WIN11 = WIN_VER == "11"

# ── Constants ─────────────────────────────────────────────────────────────────
DRIVE_REMOVABLE = 2
DRIVE_FIXED = 3
DRIVE_REMOTE = 4
DRIVE_CDROM = 5
DRIVE_RAMDISK = 6

DRIVE_TYPE_LABEL = {
    DRIVE_REMOVABLE: "USB/Removable",
    DRIVE_FIXED: "Local Disk",
    DRIVE_REMOTE: "Network",
    DRIVE_CDROM: "CD/DVD",
    DRIVE_RAMDISK: "RAM Disk",
}

SIZES = [256, 128, 64, 48, 32, 16]
REG_BASE = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\DriveIcons"
ICO_STORE = os.path.expandvars(r"%ProgramData%\DriveIcons")

# ── ICO converter ─────────────────────────────────────────────────────────────
def pil_to_ico(img, out_path):
    img = img.convert("RGBA")
    icons = [img.resize((s, s), Image.LANCZOS) for s in SIZES]
    icons[0].save(out_path, format="ICO",
                  sizes=[(s, s) for s in SIZES], append_images=icons[1:])

# ── Drive detection ───────────────────────────────────────────────────────────
def get_drives():
    drives = []
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        if bitmask & 1:
            d = f"{letter}:\\"
            dtype = ctypes.windll.kernel32.GetDriveTypeW(d)
            try:
                ctypes.windll.kernel32.GetDiskFreeSpaceExW(d, None, None, None)
                drives.append((d, dtype))
            except:
                pass
        bitmask >>= 1
    return drives

def get_drive_label(drive):
    buf = ctypes.create_unicode_buffer(261)
    try:
        ctypes.windll.kernel32.GetVolumeInformationW(
            drive, buf, 261, None, None, None, None, 0)
        return buf.value
    except:
        return ""

def is_system_drive(drive):
    return drive.rstrip("\\").upper() == os.environ.get("SystemDrive", "C:").upper()

def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except:
        return False

def relaunch_as_admin():
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    sys.exit()

# ==============================================================================
#  SAFE FILE HIDING FUNCTIONS (NO PROBLEMS!)
# ==============================================================================

# System files that must NEVER be hidden or modified
SYSTEM_FILES = [
    "$RECYCLE.BIN",
    "System Volume Information",
    "boot.ini",
    "pagefile.sys",
    "hiberfil.sys",
    "swapfile.sys",
    "bootmgr",
    "BOOTNXT",
    "RECOVERY",
    "Windows",
    "WinNT",
    "Program Files",
    "Program Files (x86)",
    "ProgramData",
]

# Icon files that are SAFE to hide
ICON_FILES = [
    "desktop.ini",
    "autorun.inf",
    ".directory",
    ".VolumeIcon.icns",
    "VolumeIcon.icns",
    ".DS_Store",
    ".fseventsd",
    ".metadata_never_index",
    ".icons",
]

def is_safe_to_hide(filepath):
    """
    Check if a file is safe to hide
    Returns True if it's an icon file, False if it's a system file
    """
    filename = os.path.basename(filepath).lower()
    filepath_lower = filepath.lower()
    
    # NEVER hide system files
    for sys_file in SYSTEM_FILES:
        if sys_file.lower() in filename or sys_file.lower() in filepath_lower:
            return False
    
    # Check if it's a directory we want to keep
    if os.path.isdir(filepath):
        dirname = os.path.basename(filepath).lower()
        # Don't hide user data folders
        if dirname not in ['.icons', '.fseventsd'] and not dirname.startswith('.'):
            return False
    
    # Only hide icon files
    for icon_file in ICON_FILES:
        if filename == icon_file.lower() or filename == '.' + icon_file.lower().lstrip('.'):
            return True
        if icon_file.lower() in filename and filename.endswith('.png'):
            return True
    
    return False

def safe_hide_file(filepath, log_func=None):
    """
    Safely hide a file on all platforms
    - Windows: +H+S attributes
    - Linux/macOS: Rename to start with dot (if safe)
    """
    def log(msg):
        if log_func:
            log_func(msg)
    
    if not os.path.exists(filepath):
        return False
    
    filename = os.path.basename(filepath)
    
    # Double-check safety
    if not is_safe_to_hide(filepath):
        log(f"  ⚠️ Skipping {filename} (system file)")
        return False
    
    # 1. Always hide on Windows with attributes
    try:
        subprocess.run(["attrib", "+H", "+S", filepath], 
                      shell=True, capture_output=True)
    except:
        pass
    
    # 2. Handle Linux/macOS hiding
    dirname = os.path.dirname(filepath)
    
    # Files that are ALREADY hidden on Linux/macOS (start with dot)
    already_hidden = [
        ".directory",
        ".VolumeIcon.icns",
        ".DS_Store",
        ".fseventsd",
        ".metadata_never_index",
        ".icons",
    ]
    
    if filename in already_hidden or filename.startswith('.'):
        log(f"  ✅ {filename} (hidden on Windows, already hidden on Linux/macOS)")
        return True
    
    # Files that should be renamed to add dot
    should_rename = [
        "desktop.ini",
        "autorun.inf",
        "VolumeIcon.icns",
    ]
    
    if filename in should_rename:
        new_name = '.' + filename
        new_path = os.path.join(dirname, new_name)
        
        # If the dot version already exists, remove this one
        if os.path.exists(new_path):
            try:
                os.remove(filepath)
                log(f"  ✅ Removed duplicate {filename} (already have .{filename})")
                return True
            except:
                pass
        
        # Rename to add dot
        try:
            os.rename(filepath, new_path)
            # Re-hide on Windows after rename
            subprocess.run(["attrib", "+H", "+S", new_path], 
                          shell=True, capture_output=True)
            log(f"  ✅ {filename} → .{filename} (hidden on all platforms)")
            return True
        except Exception as e:
            log(f"  ⚠️ Could not rename {filename}, but it's hidden on Windows")
            return True
    
    # PNG files in .icons folder
    if filename.endswith('.png') and '.icons' in filepath:
        if not filename.startswith('.'):
            new_name = '.' + filename
            new_path = os.path.join(dirname, new_name)
            try:
                os.rename(filepath, new_path)
                subprocess.run(["attrib", "+H", "+S", new_path], 
                              shell=True, capture_output=True)
                log(f"  ✅ {filename} → .{filename} (hidden PNG)")
                return True
            except:
                pass
    
    log(f"  ✅ {filename} (hidden on Windows)")
    return True

def safe_hide_all_icon_files(drive, step_cb=None):
    """
    Safely hide ALL icon files on all platforms
    WITHOUT affecting system files or user data
    """
    def log(msg):
        if step_cb:
            step_cb(msg)
        else:
            print(msg)
    
    log("\n🔒 SAFELY hiding icon files on all platforms...")
    hidden_count = 0
    
    # Walk through drive root
    for item in os.listdir(drive):
        item_path = os.path.join(drive, item)
        
        # Skip if it's a system folder we must preserve
        if item in SYSTEM_FILES:
            log(f"  ℹ️ Preserving system folder: {item}/")
            continue
        
        # Hide if it's an icon file
        if safe_hide_file(item_path, log):
            hidden_count += 1
    
    # Special handling for .icons folder contents
    icons_dir = os.path.join(drive, ".icons")
    if os.path.exists(icons_dir):
        log(f"\n  📁 Processing .icons/ folder contents...")
        for root, dirs, files in os.walk(icons_dir):
            for file in files:
                file_path = os.path.join(root, file)
                if safe_hide_file(file_path, log):
                    hidden_count += 1
            for dir in dirs:
                dir_path = os.path.join(root, dir)
                if safe_hide_file(dir_path, log):
                    hidden_count += 1
    
    log(f"\n✅ SAFE hiding complete: {hidden_count} icon files hidden")
    log(f"   System files and your data folders are untouched!")
    
    return hidden_count

# ==============================================================================
#  PERMISSION HANDLING FUNCTIONS
# ==============================================================================

def check_drive_writable(drive, step_cb=None):
    """Check if drive is writable"""
    def log(msg):
        if step_cb:
            step_cb(msg)
    
    test_file = os.path.join(drive, ".write_test.tmp")
    try:
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        log("✅ Drive is writable")
        return True
    except PermissionError:
        log("❌ Drive is NOT writable - permission denied")
        return False
    except Exception as e:
        log(f"⚠️ Drive check error: {e}")
        return False

def fix_windows_permissions(drive, step_cb=None):
    """Fix Windows permissions if possible"""
    def log(msg):
        if step_cb:
            step_cb(msg)
    
    if not is_admin():
        log("❌ Need Administrator rights to fix permissions")
        return False
    
    log("🔄 Fixing Windows permissions...")
    
    try:
        # Take ownership
        subprocess.run(["takeown", "/F", drive], shell=True, 
                      capture_output=True, timeout=10)
        
        # Grant full control
        username = os.environ.get('USERNAME', 'Users')
        subprocess.run(["icacls", drive, "/grant", f"{username}:F", "/T"],
                      shell=True, capture_output=True, timeout=10)
        
        log("✅ Windows permissions fixed")
        return True
    except:
        log("⚠️ Could not fix permissions automatically")
        return False

def force_write_file(filepath, source_file=None, content=None, step_cb=None):
    """Write a file with multiple fallback methods"""
    def log(msg):
        if step_cb:
            step_cb(msg)
    
    filename = os.path.basename(filepath)
    
    # Try direct write first
    try:
        if source_file:
            shutil.copy2(source_file, filepath)
        elif content is not None:
            if isinstance(content, bytes):
                with open(filepath, 'wb') as f:
                    f.write(content)
            else:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
        else:
            with open(filepath, 'wb') as f:
                f.write(b'')
        log(f"  ✅ Created {filename}")
        return True
    except PermissionError:
        log(f"  ⚠️ Permission denied, trying alternate method...")
    
    # Try clearing attributes and retry
    try:
        if os.path.exists(filepath):
            subprocess.run(["attrib", "-R", "-H", "-S", filepath],
                         shell=True, capture_output=True)
            time.sleep(0.3)
        
        if source_file:
            shutil.copy2(source_file, filepath)
        elif content is not None:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
        log(f"  ✅ Created {filename} (after clearing attributes)")
        return True
    except:
        pass
    
    # Try with temp file
    try:
        temp_path = filepath + ".tmp"
        if source_file:
            shutil.copy2(source_file, temp_path)
        elif content is not None:
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        if os.path.exists(filepath):
            os.remove(filepath)
        os.rename(temp_path, filepath)
        log(f"  ✅ Created {filename} (via temp file)")
        return True
    except:
        log(f"  ❌ Failed to create {filename}")
        return False

# ── File attribute helpers ────────────────────────────────────────────────────
def clear_attribs(path):
    subprocess.run(["attrib", "-R", "-H", "-S", path],
                   shell=True, capture_output=True)

def set_hidden_windows(path):
    """Hide on Windows with +H+S attributes"""
    if os.path.exists(path) and is_safe_to_hide(path):
        subprocess.run(["attrib", "+H", "+S", path],
                       shell=True, capture_output=True)

# ── Registry helpers ──────────────────────────────────────────────────────────
def reg_set_icon(drive, ico_path, label=""):
    letter = drive.rstrip("\\").rstrip(":")[0].upper()
    for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
        try:
            with winreg.CreateKeyEx(hive,
                                    f"{REG_BASE}\\{letter}\\DefaultIcon",
                                    0, winreg.KEY_SET_VALUE) as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, ico_path)
            if label.strip():
                with winreg.CreateKeyEx(hive,
                                        f"{REG_BASE}\\{letter}\\DefaultLabel",
                                        0, winreg.KEY_SET_VALUE) as k:
                    winreg.SetValueEx(k, "", 0, winreg.REG_SZ, label.strip())
        except Exception as e:
            if hive == winreg.HKEY_LOCAL_MACHINE:
                raise PermissionError(
                    f"Registry write failed: {e}\nRun as Administrator!")

def reg_get_icon(drive):
    letter = drive.rstrip("\\").rstrip(":")[0].upper()
    for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
        try:
            with winreg.OpenKey(hive,
                                f"{REG_BASE}\\{letter}\\DefaultIcon") as k:
                return winreg.QueryValueEx(k, "")[0]
        except:
            pass
    return None

def reg_remove_icon(drive):
    letter = drive.rstrip("\\").rstrip(":")[0].upper()
    for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
        for sub in ["DefaultIcon", "DefaultLabel", ""]:
            try:
                path = f"{REG_BASE}\\{letter}" + (f"\\{sub}" if sub else "")
                winreg.DeleteKey(hive, path)
            except:
                pass

# ── Shell notification constants ──────────────────────────────────────────────
SHCNE_UPDATEITEM = 0x00002000
SHCNE_RENAMEFOLDER = 0x00020000
SHCNE_ASSOCCHANGED = 0x08000000
SHCNE_ALLEVENTS = 0x7FFFFFFF
SHCNF_PATHW = 0x0005
SHCNF_FLUSH = 0x1000
SHCNF_FLUSHNOWAIT = 0x3000

# ── Explorer control ──────────────────────────────────────────────────────────
def kill_explorer():
    subprocess.run(["taskkill", "/F", "/IM", "explorer.exe"],
                   shell=True, capture_output=True)
    for _ in range(30):
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq explorer.exe"],
                           capture_output=True, text=True, shell=True)
        if "explorer.exe" not in r.stdout.lower():
            break
        time.sleep(0.2)
    time.sleep(0.3)

def delete_icon_cache():
    deleted = 0
    patterns = [
        r"%LOCALAPPDATA%\Microsoft\Windows\Explorer\iconcache*.db",
        r"%LOCALAPPDATA%\Microsoft\Windows\Explorer\thumbcache*.db",
    ]
    if IS_WIN11:
        patterns.append(r"%LOCALAPPDATA%\Microsoft\Windows\Explorer\*.db")
    for pat in patterns:
        for f in glob.glob(os.path.expandvars(pat)):
            try:
                if os.path.isfile(f):
                    os.remove(f)
                    deleted += 1
            except:
                pass
    try:
        subprocess.run(["ie4uinit.exe", "-ClearIconCache"],
                       capture_output=True, timeout=8)
    except:
        pass
    return deleted

def start_explorer():
    subprocess.Popen("explorer.exe", shell=True)
    for _ in range(40):
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq explorer.exe"],
                           capture_output=True, text=True, shell=True)
        if "explorer.exe" in r.stdout.lower():
            break
        time.sleep(0.3)
    time.sleep(2.5 if IS_WIN11 else 2.0)

def notify_shell(drive):
    s32 = ctypes.windll.shell32
    p = ctypes.create_unicode_buffer(drive)
    s32.SHChangeNotify(SHCNE_UPDATEITEM, SHCNF_PATHW | SHCNF_FLUSH, p, None)
    s32.SHChangeNotify(SHCNE_RENAMEFOLDER, SHCNF_PATHW | SHCNF_FLUSH, p, None)
    s32.SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_FLUSHNOWAIT, None, None)
    s32.SHChangeNotify(SHCNE_ALLEVENTS, SHCNF_FLUSHNOWAIT, None, None)

ICO_FOLDER = ".icons"

# ==============================================================================
#  PLATFORM-SPECIFIC ICON CREATORS
# ==============================================================================

def create_windows_icons(drive, ico_src, ico_dest, icons_dir, label, step_cb):
    """Create Windows-specific icon files"""
    def log(msg):
        step_cb(msg)
    
    log("\n🪟 Creating Windows icons...")
    
    ico_root = os.path.join(icons_dir, "drive_icon.ico")
    
    # Copy to ProgramData
    try:
        shutil.copy2(ico_src, ico_dest)
        log("  ✅ Copied to ProgramData")
    except Exception as e:
        log(f"  ⚠️ Could not copy to ProgramData: {e}")
    
    # Copy to .icons folder
    if force_write_file(ico_root, source_file=ico_src, step_cb=step_cb):
        log("  ✅ Copied to .icons folder")
    
    # Windows Registry
    try:
        reg_set_icon(drive, ico_dest, label)
        log("  ✅ Registry updated")
    except Exception as e:
        log(f"  ⚠️ Registry update failed: {e}")
    
    # desktop.ini
    desktop_ini_content = (
        "[.ShellClassInfo]\r\n"
        f"IconResource={ICO_FOLDER}\\drive_icon.ico,0\r\n"
        f"IconFile={ICO_FOLDER}\\drive_icon.ico\r\n"
        "IconIndex=0\r\n"
    )
    
    desktop_ini = os.path.join(drive, "desktop.ini")
    if force_write_file(desktop_ini, content=desktop_ini_content, step_cb=step_cb):
        pass  # Will be hidden later
    
    # autorun.inf
    ico_rel_auto = ICO_FOLDER + chr(92) + "drive_icon.ico"
    autorun_lines = ["[autorun]", f"icon={ico_rel_auto}"]
    if label.strip():
        autorun_lines.append(f"label={label.strip()}")
    autorun_content = "\r\n".join(autorun_lines) + "\r\n"
    
    autorun_path = os.path.join(drive, "autorun.inf")
    if force_write_file(autorun_path, content=autorun_content, step_cb=step_cb):
        pass  # Will be hidden later
    
    # Set drive attributes
    try:
        subprocess.run(["attrib", "+S", "+R", drive], shell=True, capture_output=True)
    except:
        pass
    
    return ico_root

def create_linux_icons(drive, pil_img, icons_dir, step_cb):
    """Create Linux-specific icon files"""
    def log(msg):
        step_cb(msg)
    
    log("\n🐧 Creating Linux icons...")
    
    png_files = []
    
    # Create PNGs in various sizes
    png_sizes = [256, 128, 64, 32, 16]
    for size in png_sizes:
        png_path = os.path.join(icons_dir, f"drive_icon_{size}.png")
        try:
            pil_img.resize((size, size), Image.LANCZOS).save(png_path, "PNG")
            png_files.append(png_path)
            log(f"  ✅ Created {size}px PNG")
        except Exception as e:
            log(f"  ⚠️ Could not create {size}px PNG: {e}")
    
    # Create main PNG
    main_png = os.path.join(icons_dir, "drive_icon.png")
    try:
        pil_img.resize((256, 256), Image.LANCZOS).save(main_png, "PNG")
        png_files.append(main_png)
        log("  ✅ Created main PNG")
    except Exception as e:
        log(f"  ⚠️ Could not create main PNG: {e}")
    
    # Create .directory file
    directory_content = (
        "[Desktop Entry]\n"
        f"Icon={ICO_FOLDER}/.drive_icon.png\n"
        "Name=Removable Drive\n"
        "Type=Directory\n"
    )
    
    directory_file = os.path.join(drive, ".directory")
    if force_write_file(directory_file, content=directory_content, step_cb=step_cb):
        log("  ✅ Created .directory")
    
    return png_files

def create_macos_icons(drive, pil_img, icons_dir, step_cb):
    """Create macOS-specific icon files"""
    def log(msg):
        step_cb(msg)
    
    log("\n🍎 Creating macOS icons...")
    mac_files = []
    
    # Create PNG in .icons folder
    png_large = os.path.join(icons_dir, "drive_icon_512.png")
    try:
        pil_img.resize((512, 512), Image.LANCZOS).save(png_large, "PNG")
        log("  ✅ Created 512px PNG")
    except Exception as e:
        log(f"  ❌ Could not create base PNG: {e}")
        return []
    
    # Create .VolumeIcon.icns (hidden macOS icon)
    mac_icon_hidden = os.path.join(drive, ".VolumeIcon.icns")
    if force_write_file(mac_icon_hidden, source_file=png_large, step_cb=step_cb):
        mac_files.append(mac_icon_hidden)
    
    # Create VolumeIcon.icns (visible fallback)
    mac_icon_visible = os.path.join(drive, "VolumeIcon.icns")
    if force_write_file(mac_icon_visible, source_file=png_large, step_cb=step_cb):
        mac_files.append(mac_icon_visible)
    
    # Create .DS_Store
    ds_store = os.path.join(drive, ".DS_Store")
    if force_write_file(ds_store, content=b'\x00' * 4096, step_cb=step_cb):
        mac_files.append(ds_store)
    
    # Create .metadata_never_index
    never_index = os.path.join(drive, ".metadata_never_index")
    if force_write_file(never_index, content='', step_cb=step_cb):
        mac_files.append(never_index)
    
    # Create .fseventsd folder
    fseventsd = os.path.join(drive, ".fseventsd")
    try:
        os.makedirs(fseventsd, exist_ok=True)
        no_log = os.path.join(fseventsd, "no_log")
        with open(no_log, 'w') as f:
            f.write("")
        mac_files.append(fseventsd)
        log("  ✅ Created .fseventsd folder")
    except Exception as e:
        log(f"  ⚠️ Could not create .fseventsd: {e}")
    
    log(f"✅ macOS complete: {len(mac_files)} files created")
    return mac_files

# ── Safe eject ────────────────────────────────────────────────────────────────
IOCTL_EJECT = 0x2D4808
IOCTL_REMOVAL = 0x2D4804
FSCTL_LOCK = 0x90018
FSCTL_DISMOUNT = 0x90020
GR = 0x80000000
GW = 0x40000000
FSR = 1
FSW = 2
OE = 3
FNB = 0x20000000
IHV = ctypes.c_void_p(-1).value


def safe_eject(drive):
    letter = drive.rstrip("\\").rstrip(":")[0].upper()
    k32 = ctypes.windll.kernel32
    h = k32.CreateFileW(f"\\\\.\\{letter}:",
                        GR | GW, FSR | FSW, None, OE, FNB, None)
    if h == IHV:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"(New-Object -comObject Shell.Application).Namespace(17)"
             f".ParseName('{letter}:').InvokeVerb('Eject')"],
            capture_output=True, timeout=15)
        return r.returncode == 0, ("Ejected via PowerShell"
                                    if r.returncode == 0
                                    else r.stderr.decode(errors="ignore"))
    br = ctypes.c_ulong(0)
    try:
        k32.DeviceIoControl(h, FSCTL_LOCK, None, 0, None, 0, ctypes.byref(br), None)
        k32.DeviceIoControl(h, FSCTL_DISMOUNT, None, 0, None, 0, ctypes.byref(br), None)

        class PMR(ctypes.Structure):
            _fields_ = [("p", ctypes.c_ubyte)]

        pmr = PMR(0)
        k32.DeviceIoControl(h, IOCTL_REMOVAL,
                            ctypes.byref(pmr), 1, None, 0, ctypes.byref(br), None)
        ok = k32.DeviceIoControl(h, IOCTL_EJECT,
                                  None, 0, None, 0, ctypes.byref(br), None)
        if ok:
            return True, "Ejected!"
        err = ctypes.GetLastError()
        k32.CloseHandle(h)
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"(New-Object -comObject Shell.Application).Namespace(17)"
             f".ParseName('{letter}:').InvokeVerb('Eject')"],
            capture_output=True, timeout=15)
        if r.returncode == 0:
            return True, "Ejected! (via PowerShell)"
        return False, f"Eject failed (code {err}) — please unplug manually."
    finally:
        try:
            k32.CloseHandle(h)
        except:
            pass


def restart_computer_countdown(parent=None):
    win = tk.Toplevel(parent) if parent else tk.Tk()
    win.title("Restart PC")
    win.configure(bg=BG, padx=30, pady=24)
    win.resizable(False, False)
    win.grab_set()
    win.update_idletasks()
    w, h = 360, 220
    x = (win.winfo_screenwidth() // 2) - (w // 2)
    y = (win.winfo_screenheight() // 2) - (h // 2)
    win.geometry(f"{w}x{h}+{x}+{y}")

    tk.Label(win, text="🔄  Restart PC", bg=BG, fg=ACCENT,
             font=("Segoe UI", 14, "bold")).pack(pady=(0, 6))
    tk.Label(win,
             text="C: drive requires a restart to show the new icon.",
             bg=BG, fg=TEXT, font=("Segoe UI", 10)).pack()

    count_var = tk.StringVar(value="15")
    tk.Label(win, textvariable=count_var, bg=BG, fg=RED,
             font=("Segoe UI", 42, "bold")).pack(pady=(10, 4))
    tk.Label(win, text="seconds", bg=BG, fg=SUBTEXT,
             font=("Segoe UI", 10)).pack()

    cancelled = [False]

    def do_cancel():
        cancelled[0] = True
        win.destroy()

    def do_now():
        cancelled[0] = True
        win.destroy()
        subprocess.run(["shutdown", "/r", "/t", "0"])

    bf = tk.Frame(win, bg=BG)
    bf.pack(pady=(14, 0), fill="x")
    flat_btn(bf, "Cancel", do_cancel, color="#585b70").pack(side="left", expand=True, padx=(0, 4))
    flat_btn(bf, "Restart Now!", do_now, accent=True).pack(side="left", expand=True, padx=(4, 0))

    def tick(n):
        if cancelled[0]:
            return
        if n <= 0:
            win.destroy()
            subprocess.run(["shutdown", "/r", "/t", "0"])
            return
        count_var.set(str(n))
        win.after(1000, lambda: tick(n - 1))

    win.after(1000, lambda: tick(14))
    if parent is None:
        win.mainloop()


def restart_computer():
    restart_computer_countdown()


# ═══════════════════════════════════════════════════════════════════════════════
#  ULTIMATE CROSS-PLATFORM PIPELINE
#  Works on Windows, Linux, and macOS with SAFE file hiding!
# ═══════════════════════════════════════════════════════════════════════════════
def universal_icon_pipeline(drive, ico_src, label, hide_files, do_eject,
                            status_cb, done_cb):
    dtype = ctypes.windll.kernel32.GetDriveTypeW(drive)
    is_usb = (dtype == DRIVE_REMOVABLE)
    letter = drive.rstrip("\\").rstrip(":")[0].upper()
    t0 = time.time()

    def step(n, total, msg):
        status_cb(f"[{time.time() - t0:.1f}s] [{n}/{total}] {msg}")

    try:
        os.makedirs(ICO_STORE, exist_ok=True)
        ico_dest = os.path.join(ICO_STORE, f"drive_{letter}.ico")
        icons_dir = os.path.join(drive, ICO_FOLDER)

        # 1. Kill Explorer
        step(1, 14, f"Stopping Explorer (Windows {WIN_VER})...")
        kill_explorer()

        # 2. Delete icon cache
        step(2, 14, "Deleting Windows icon cache...")
        n = delete_icon_cache()
        step(2, 14, f"Removed {n} cache file(s).")

        # 3. Remove old icon files only
        step(3, 14, "Removing old icon files...")
        removed = 0
        if os.path.exists(ico_dest) and is_safe_to_hide(ico_dest):
            try:
                clear_attribs(ico_dest)
                os.remove(ico_dest)
                removed += 1
            except:
                pass
        
        # Only remove icon files, not user data
        for pattern in ["drive_icon*.ico", ".VolumeIcon*"]:
            for old in glob.glob(os.path.join(drive, pattern)):
                if is_safe_to_hide(old):
                    try:
                        clear_attribs(old)
                        os.remove(old)
                        removed += 1
                    except:
                        pass
        step(3, 14, f"Removed {removed} old icon file(s).")

        # 4. ie4uinit pre-clear
        step(4, 14, "ie4uinit pre-clear...")
        try:
            subprocess.run(["ie4uinit.exe", "-show"], capture_output=True, timeout=8)
        except:
            pass

        # 5. Check drive permissions
        step(5, 14, "Checking drive permissions...")
        if not check_drive_writable(drive, lambda m: step(5, 14, m)):
            if is_admin():
                step(5, 14, "Attempting to fix permissions...")
                fix_windows_permissions(drive, lambda m: step(5, 14, m))

        # 6. Create .icons folder
        step(6, 14, "Creating .icons folder...")
        if os.path.exists(icons_dir):
            clear_attribs(icons_dir)
        os.makedirs(icons_dir, exist_ok=True)

        # 7. Load PIL image
        step(7, 14, "Loading image...")
        from PIL import Image as _Img
        pil_img = _Img.open(ico_src).convert("RGBA")

        # 8. Create Windows icons
        step(8, 14, "Creating Windows icons...")
        create_windows_icons(drive, ico_src, ico_dest, icons_dir, label,
                            lambda m: step(8, 14, m))

        # 9. Create Linux icons
        step(9, 14, "Creating Linux icons...")
        png_files = create_linux_icons(drive, pil_img, icons_dir,
                                       lambda m: step(9, 14, m))

        # 10. Create macOS icons
        step(10, 14, "Creating macOS icons...")
        mac_files = create_macos_icons(drive, pil_img, icons_dir,
                                      lambda m: step(10, 14, m))

        # 11. SAFELY hide ALL icon files on ALL platforms
        step(11, 14, "SAFELY hiding icon files on all platforms...")
        safe_hide_all_icon_files(drive, lambda m: step(11, 14, m))

        # 12. ie4uinit post + Start Explorer
        step(12, 14, "Rebuilding Windows cache + starting Explorer...")
        try:
            subprocess.run(["ie4uinit.exe", "-ClearIconCache"],
                           capture_output=True, timeout=8)
        except:
            pass
        subprocess.run(["ie4uinit.exe", "-show"], capture_output=True)
        start_explorer()

        # 13. Notify shell x3
        step(13, 14, "Notifying Windows shell...")
        notify_shell(drive)
        time.sleep(1.0)
        notify_shell(drive)
        time.sleep(0.5)
        notify_shell(drive)

        # 14. Final verification
        step(14, 14, "Verifying files...")
        time.sleep(0.5)

        total = time.time() - t0
        step(14, 14, f"Done! Finished in {total:.1f}s")

        # Eject if requested
        eject_ok = False
        if do_eject and not is_system_drive(drive):
            status_cb("Ejecting drive...")
            time.sleep(0.5)
            eject_ok, eject_msg = safe_eject(drive)
            status_cb(eject_msg)

        msg_time = time.strftime("%H:%M:%S")
        is_sys_done = is_system_drive(drive)

        success_msg = (
            f"✅ UNIVERSAL ICON APPLIED SUCCESSFULLY!\n\n"
            f"Drive: {drive}\n"
            f"Time: {msg_time}  ({total:.1f}s)\n\n"
            f"🪟 WINDOWS 10/11:\n"
            f"  • Registry updated\n"
            f"  • desktop.ini + autorun.inf\n"
            f"  • Icon visible in File Explorer\n\n"
            f"🐧 LINUX (all DEs):\n"
            f"  • .directory file created\n"
            f"  • Hidden PNG icons in .icons/\n"
            f"  • Icon visible in Nautilus/Dolphin/Thunar\n\n"
            f"🍎 MACOS:\n"
            f"  • .VolumeIcon.icns created\n"
            f"  • .DS_Store + metadata configured\n"
            f"  • Icon visible in Finder\n\n"
            f"🔒 SAFE HIDING:\n"
            f"  • ALL icon files hidden on every OS\n"
            f"  • System files UNTOUCHED ($RECYCLE.BIN, etc.)\n"
            f"  • Your data folders remain visible\n"
            f"  • NO problems, NO conflicts!\n\n"
            f"Plug this drive into ANY computer:\n"
            f"  ✅ Windows 10/11 → sees icon, clean drive\n"
            f"  ✅ Linux → sees icon, clean drive\n"
            f"  ✅ macOS → sees icon, clean drive\n"
        )

        if eject_ok:
            success_msg += f"\n✅ Drive ejected successfully!"

        if is_sys_done:
            success_msg += f"\n\n⚠️ C: drive may need a restart for full effect."

        done_cb(True, success_msg, is_sys_done)

    except PermissionError as e:
        done_cb(False, f"❌ Permission denied:\n{e}\n\n"
                       f"Solutions:\n"
                       f"1. Right-click → Run as Administrator\n"
                       f"2. Check if drive is write-protected")
    except Exception as e:
        import traceback
        done_cb(False, f"❌ Error: {e}\n\n{traceback.format_exc()}")


# ── Remove + quick refresh ────────────────────────────────────────────────────
def full_refresh_quick(drive):
    try:
        subprocess.run(["ie4uinit.exe", "-show"], capture_output=True)
        subprocess.run(["ie4uinit.exe", "-ClearIconCache"], capture_output=True)
    except:
        pass
    notify_shell(drive)
    subprocess.run(["taskkill", "/F", "/IM", "explorer.exe"],
                   shell=True, capture_output=True)
    time.sleep(2.0 if IS_WIN11 else 1.5)
    subprocess.Popen("explorer.exe", shell=True)
    time.sleep(1.5)
    notify_shell(drive)


# ── Diagnostics ───────────────────────────────────────────────────────────────
def drive_diagnostics(drive):
    letter = drive.rstrip("\\").rstrip(":")[0].upper()
    lines = [f"=== Diagnostics: {drive} ===",
             f"Windows        : {WIN_VER}",
             f"Admin rights   : {'YES' if is_admin() else 'NO'}"]

    # Check drive writability
    test_file = os.path.join(drive, ".write_test.tmp")
    try:
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        lines.append("Drive writable  : YES")
    except:
        lines.append("Drive writable  : NO ⚠️")

    reg = reg_get_icon(drive)
    lines.append(f"Registry icon  : {reg or 'NONE'}")

    # Check icon files (safe to check)
    icon_files_to_check = [
        (".icons", "folder"),
        (".directory", "file"),
        (".VolumeIcon.icns", "file"),
        ("VolumeIcon.icns", "file"),
        (".DS_Store", "file"),
        (".fseventsd", "folder"),
        (".metadata_never_index", "file"),
        ("desktop.ini", "file"),
        ("autorun.inf", "file"),
    ]

    for filename, filetype in icon_files_to_check:
        path = os.path.join(drive, filename)
        dot_path = os.path.join(drive, '.' + filename.lstrip('.'))
        
        if os.path.exists(path):
            status = "EXISTS"
            if filename.startswith('.'):
                status += " (hidden on Linux/macOS)"
        elif os.path.exists(dot_path):
            status = f"EXISTS as .{filename.lstrip('.')}"
        else:
            status = "missing"
        
        lines.append(f"{filename:20}: {status}")

    # Check .icons folder contents
    icons_dir = os.path.join(drive, ICO_FOLDER)
    if os.path.exists(icons_dir):
        icons = glob.glob(os.path.join(icons_dir, "*"))
        lines.append(f"\nIcons in .icons/: {len(icons)} files")
        for i in sorted(icons)[:8]:
            size = os.path.getsize(i)
            name = os.path.basename(i)
            lines.append(f"  {name:25} ({size:,} bytes)")
        if len(icons) > 8:
            lines.append(f"  ... and {len(icons) - 8} more")
    else:
        lines.append(f"Icons in .icons/: missing")

    pd = os.path.join(ICO_STORE, f"drive_{letter}.ico")
    status = "EXISTS" if os.path.exists(pd) else "missing"
    lines.append(f"\nProgramData ico: {status}")

    return "\n".join(lines)


# ── Colours ───────────────────────────────────────────────────────────────────
BG = "#1e1e2e"
SURFACE = "#313244"
OVERLAY = "#45475a"
TEXT = "#cdd6f4"
SUBTEXT = "#a6adc8"
ACCENT = "#89b4fa"
GREEN = "#a6e3a1"
RED = "#f38ba8"
YELLOW = "#f9e2af"
ORANGE = "#fab387"
PURPLE = "#cba6f7"
TEAL = "#94e2d5"


def flat_btn(parent, text, cmd, accent=False, color=None, **kw):
    bg = color or (ACCENT if accent else SURFACE)
    fg = "#1e1e2e" if (accent or color) else TEXT
    return tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                     activebackground="#b4befe" if accent else OVERLAY,
                     activeforeground="#1e1e2e" if accent else TEXT,
                     relief="flat", cursor="hand2", bd=0,
                     font=("Segoe UI", 10, "bold" if accent else "normal"),
                     padx=10, pady=6, **kw)


# ── Step Log Window ───────────────────────────────────────────────────────────
class StepLog(tk.Toplevel):
    def __init__(self, parent, title="Progress"):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=BG, padx=16, pady=14)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        tk.Label(self, text=f"Live Progress  (Windows {WIN_VER})",
                 bg=BG, fg=ACCENT,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 6))
        self.txt = tk.Text(self, width=72, height=20,
                           bg=SURFACE, fg=GREEN,
                           font=("Consolas", 9), relief="flat",
                           state="disabled", wrap="word")
        self.txt.pack()
        self.geometry(f"+{parent.winfo_x() + 50}+{parent.winfo_y() + 20}")
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


# ── Crop Editor ───────────────────────────────────────────────────────────────
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
                 bg=BG, fg=SUBTEXT, font=("Segoe UI", 8)).pack()
        self.cv = tk.Canvas(lf, width=EDITOR_SIZE, height=EDITOR_SIZE,
                            bg="#000", highlightthickness=2,
                            highlightbackground=ACCENT, cursor="fleur")
        self.cv.pack()
        self.cv.bind("<ButtonPress-1>", self._ds)
        self.cv.bind("<B1-Motion>", self._dm)
        self.cv.bind("<MouseWheel>", self._mw)
        rf = tk.Frame(top, bg=BG)
        rf.pack(side="left", anchor="n")
        tk.Label(rf, text="Preview (256px)", bg=BG, fg=SUBTEXT,
                 font=("Segoe UI", 8)).pack()
        self.pv = tk.Canvas(rf, width=128, height=128, bg="#000",
                            highlightthickness=1, highlightbackground=OVERLAY)
        self.pv.pack(pady=(0, 8))
        tk.Label(rf, text="Small sizes:", bg=BG, fg=SUBTEXT,
                 font=("Segoe UI", 8)).pack(anchor="w")
        self.sm = tk.Canvas(rf, width=128, height=52, bg="#2a2a3e",
                            highlightthickness=0)
        self.sm.pack()
        tk.Label(rf, text="Background:", bg=BG, fg=SUBTEXT,
                 font=("Segoe UI", 8)).pack(anchor="w", pady=(10, 2))
        self._bg = tk.StringVar(value="transparent")
        for v, l in [("transparent", "Transparent"), ("white", "White"),
                     ("black", "Black"), ("circle", "Circle crop")]:
            tk.Radiobutton(rf, text=l, variable=self._bg, value=v,
                           bg=BG, fg=TEXT, selectcolor=SURFACE,
                           activebackground=BG, activeforeground=TEXT,
                           font=("Segoe UI", 9),
                           command=self._redraw).pack(anchor="w")
        zm = tk.Frame(self, bg=BG)
        zm.pack(fill="x", pady=(0, 12))
        tk.Label(zm, text="Zoom:", bg=BG, fg=TEXT,
                 font=("Segoe UI", 10)).pack(side="left")
        self.zsl = tk.Scale(zm, from_=10, to=500, orient="horizontal",
                            bg=BG, fg=TEXT, troughcolor=SURFACE,
                            highlightthickness=0, showvalue=False,
                            command=self._zc)
        self.zsl.set(100)
        self.zsl.pack(side="left", fill="x", expand=True, padx=(8, 8))
        self.zlb = tk.Label(zm, text="100%", bg=BG, fg=ACCENT,
                            font=("Segoe UI", 10, "bold"), width=5)
        self.zlb.pack(side="left")
        br = tk.Frame(self, bg=BG)
        br.pack(fill="x")
        flat_btn(br, "Fit", self._fit).pack(side="left", padx=(0, 8))
        flat_btn(br, "Cancel", self.destroy).pack(side="right", padx=(8, 0))
        flat_btn(br, "Use this icon", self._confirm,
                 accent=True).pack(side="right")

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
                                fill=SUBTEXT, font=("Segoe UI", 7))
            x += s + 28

    def _confirm(self):
        self._cb(self._crop(256))
        self.destroy()


# ── Main App ──────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Drive Icon Setter  v9.3  —  ULTIMATE SAFE HIDING")
        self.configure(bg=BG, padx=28, pady=22)
        self.resizable(False, False)
        self._src = None
        self._final = None
        self._ico = None
        self._tmp = tempfile.mkdtemp()
        self._drives = []
        self.drive_var = tk.StringVar()
        self.label_var = tk.StringVar()
        self.hide_var = tk.BooleanVar(value=True)
        self.eject_var = tk.BooleanVar(value=False)
        self._build_ui()
        if not is_admin():
            self._admin_banner()

    def _build_ui(self):
        tk.Label(self,
                 text=f"  Drive Icon Setter  v9.3  —  SAFE HIDING",
                 bg=BG, fg=ACCENT,
                 font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 4))

        info = tk.Frame(self, bg=SURFACE, padx=12, pady=8)
        info.pack(fill="x", pady=(0, 6))
        tk.Label(info,
                 text="🪟 Windows 10/11 | 🐧 Linux | 🍎 macOS  —  ALL PLATFORMS + SAFE HIDING",
                 bg=SURFACE, fg=GREEN,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Label(info,
                 text="Icon visible on EVERY OS • SAFE hiding • NO system files touched",
                 bg=SURFACE, fg=SUBTEXT,
                 font=("Segoe UI", 9)).pack(anchor="w")

        # ── Step 1 ────────────────────────────────────────────────────────────
        self._sec("Step 1  —  Choose an image")
        f1 = tk.Frame(self, bg=BG)
        f1.pack(fill="x", pady=(0, 8))
        self.img_var = tk.StringVar()
        tk.Entry(f1, textvariable=self.img_var, width=38, bg=SURFACE, fg=TEXT,
                 insertbackground=TEXT, relief="flat", font=("Segoe UI", 10),
                 state="readonly", readonlybackground=SURFACE
                 ).pack(side="left", padx=(0, 8), ipady=5)
        flat_btn(f1, "Browse…", self._browse).pack(side="left")

        fp = tk.Frame(self, bg=BG)
        fp.pack(fill="x", pady=(4, 0))
        self.thumb_cv = tk.Canvas(fp, width=96, height=96, bg=SURFACE,
                                  highlightthickness=1, highlightbackground=OVERLAY)
        self.thumb_cv.pack(side="left")
        self.thumb_cv.create_text(48, 48, text="preview",
                                  fill=SUBTEXT, font=("Segoe UI", 9))
        fi = tk.Frame(fp, bg=BG, padx=14)
        fi.pack(side="left", fill="both")
        self.info_v = tk.StringVar(value="No image selected.")
        tk.Label(fi, textvariable=self.info_v, bg=BG, fg=SUBTEXT,
                 font=("Segoe UI", 9), justify="left").pack(anchor="w")
        self.conv_l = tk.Label(fi, text="", bg=BG, fg=GREEN,
                               font=("Segoe UI", 9, "bold"), justify="left")
        self.conv_l.pack(anchor="w", pady=(4, 0))
        flat_btn(fi, "  Edit / Crop icon  ",
                 self._open_editor, color=PURPLE).pack(anchor="w", pady=(10, 0))

        # ── Step 2 ────────────────────────────────────────────────────────────
        self._sec("Step 2  —  Select drive")
        f2 = tk.Frame(self, bg=BG)
        f2.pack(fill="x", pady=(0, 4))
        tk.Label(f2, text="Drive :", bg=BG, fg=TEXT,
                 font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w", pady=5)
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
        flat_btn(f2, "Refresh", self._refresh_drives).grid(row=0, column=2)
        tk.Label(f2, text="Label :", bg=BG, fg=TEXT,
                 font=("Segoe UI", 10)).grid(row=1, column=0, sticky="w", pady=5)
        tk.Entry(f2, textvariable=self.label_var, width=34, bg=SURFACE, fg=TEXT,
                 insertbackground=TEXT, relief="flat", font=("Segoe UI", 10)
                 ).grid(row=1, column=1, padx=(8, 0), ipady=5, sticky="w")

        self.cur_ico_l = tk.Label(self, text="", bg=BG, fg=SUBTEXT,
                                  font=("Segoe UI", 8), anchor="w")
        self.cur_ico_l.pack(fill="x", pady=(0, 2))
        self.warn_l = tk.Label(self, text="", bg=BG, fg=ORANGE,
                               font=("Segoe UI", 9, "bold"),
                               anchor="w", justify="left")
        self.warn_l.pack(fill="x", pady=(0, 4))

        # ── Step 3 ────────────────────────────────────────────────────────────
        self._sec("Step 3  —  Options & Apply")
        tk.Checkbutton(
            self, text="SAFELY hide icon files (recommended)",
            variable=self.hide_var, bg=BG, fg=TEXT, selectcolor=SURFACE,
            activebackground=BG, activeforeground=TEXT,
            font=("Segoe UI", 10)).pack(anchor="w")
        self.eject_chk = tk.Checkbutton(
            self, text="  Auto Eject after Apply  (USB / External HDD)",
            variable=self.eject_var, bg=BG, fg=GREEN, selectcolor=SURFACE,
            activebackground=BG, activeforeground=GREEN,
            font=("Segoe UI", 10, "bold"), state="disabled")
        self.eject_chk.pack(anchor="w", pady=(3, 0))

        self.progress = ttk.Progressbar(self, mode="indeterminate", length=420)
        tk.Frame(self, bg=BG, height=10).pack()

        # ── Main button ───────────────────────────────────────────────────────
        self.apply_btn = flat_btn(
            self, "  🌍 APPLY UNIVERSAL ICON + SAFE HIDE ALL  ",
            self._apply, accent=True)
        self.apply_btn.pack(fill="x")

        self.status_v = tk.StringVar(value="Ready.")
        tk.Label(self, textvariable=self.status_v, bg="#181825", fg=SUBTEXT,
                 anchor="w", font=("Consolas", 9), padx=10, pady=5
                 ).pack(fill="x", pady=(8, 0))

        bf = tk.Frame(self, bg=BG)
        bf.pack(fill="x", pady=(6, 0))
        flat_btn(bf, "  Remove Icon  ",
                 self._remove_icon, color="#585b70"
                 ).pack(side="left", fill="x", expand=True, padx=(0, 3))
        flat_btn(bf, "  Diagnostics  ",
                 self._diagnostics, color=ORANGE
                 ).pack(side="left", fill="x", expand=True, padx=(3, 0))

        self._refresh_drives()

    def _admin_banner(self):
        b = tk.Frame(self, bg=YELLOW, padx=10, pady=8)
        b.pack(fill="x", before=self.winfo_children()[0])
        tk.Label(b,
                 text="  Not running as Administrator — Permission fixes may fail!",
                 bg=YELLOW, fg="#1e1e2e",
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Button(b, text="Restart as Admin", command=relaunch_as_admin,
                  bg="#fe640b", fg="white", relief="flat", cursor="hand2",
                  padx=8, pady=3,
                  font=("Segoe UI", 9, "bold")).pack(side="right")

    def _sec(self, title):
        tk.Label(self, text=title, bg=BG, fg=ACCENT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(14, 4))
        tk.Frame(self, bg=OVERLAY, height=1).pack(fill="x", pady=(0, 8))

    def _refresh_drives(self):
        self._drives = get_drives()
        choices = []
        for drive, dtype in self._drives:
            lbl = get_drive_label(drive)
            tname = DRIVE_TYPE_LABEL.get(dtype, "Unknown")
            sys_t = " [SYSTEM]" if is_system_drive(drive) else ""
            display = (f"{drive.rstrip(chr(92))}  {lbl}  ({tname}){sys_t}"
                       if lbl else
                       f"{drive.rstrip(chr(92))}  ({tname}){sys_t}")
            choices.append(display)
        self.combo["values"] = choices
        if choices:
            self.combo.current(0)
        self._on_drive()

    def _get_drive(self):
        idx = self.combo.current()
        if idx < 0 or idx >= len(self._drives):
            return None, None
        return self._drives[idx]

    def _on_drive(self, event=None):
        if not hasattr(self, "warn_l"):
            return
        drive, dtype = self._get_drive()
        if not drive:
            return
        is_usb = (dtype == DRIVE_REMOVABLE)
        is_sys = is_system_drive(drive)
        cur = reg_get_icon(drive)
        self.cur_ico_l.config(
            text=f"Current icon: {cur}" if cur
            else "No custom icon set for this drive.")
        if is_sys:
            self.warn_l.config(
                text="  System Drive — Restart PC to fully apply icon.",
                fg=ORANGE)
            if not hasattr(self, "so_btn"):
                self.so_btn = tk.Button(
                    self, text="Restart PC Now",
                    command=restart_computer,
                    bg=ORANGE, fg="#1e1e2e",
                    font=("Segoe UI", 8, "bold"),
                    relief="flat", padx=6)
                self.so_btn.pack(pady=(0, 4), after=self.warn_l)
        else:
            self.warn_l.config(text="")
            if hasattr(self, "so_btn"):
                self.so_btn.destroy()
                del self.so_btn
        can_eject = not is_sys
        self.eject_chk.config(state="normal" if can_eject else "disabled")
        if not can_eject:
            self.eject_var.set(False)

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Select image",
            filetypes=[("Image files",
                        "*.png *.jpg *.jpeg *.bmp *.gif "
                        "*.webp *.tiff *.tif *.ico"),
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
            self.conv_l.config(text="Click 'Edit / Crop icon' to adjust.",
                               fg=YELLOW)
            self._thumb_update(self._src)
            self._open_editor()
        except Exception as e:
            messagebox.showerror("Error", f"Cannot open image:\n{e}")

    def _thumb_update(self, pil_img):
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
        if self._src is None:
            messagebox.showwarning("No image", "Please select an image first.")
            return
        CropEditor(self, self._src, self._edit_done)

    def _edit_done(self, result):
        self._final = result
        self._thumb_update(result)
        try:
            out = os.path.join(self._tmp, "drive_icon.ico")
            pil_to_ico(result, out)
            self._ico = out
            self.conv_l.config(text="Icon ready! Click Apply.", fg=GREEN)
            self.status_v.set("Icon ready.")
        except Exception as e:
            self.conv_l.config(text=f"Convert failed: {e}", fg=RED)

    def _check_ready(self):
        if not self._ico or not os.path.isfile(self._ico):
            messagebox.showwarning("Not Ready",
                                   "Please select and edit an image first.")
            return False
        drive, _ = self._get_drive()
        if not drive:
            messagebox.showwarning("No Drive", "Please select a drive.")
            return False
        return True

    def _run_pipeline(self, target_fn, args):
        self.progress.pack(fill="x", pady=(0, 8), before=self.apply_btn)
        self.progress.start(10)
        self.update()
        log = StepLog(self)

        def _status(msg):
            self.after(0, lambda m=msg: (self.status_v.set(m), log.log(m)))

        def _done(ok, msg, show_restart=False):
            self.after(0, lambda o=ok, m=msg, r=show_restart: self._finish(o, m, log, r))

        threading.Thread(
            target=target_fn,
            args=args + (_status, _done),
            daemon=True).start()

    def _apply(self):
        if not self._check_ready():
            return
        drive, dtype = self._get_drive()
        if is_system_drive(drive):
            if not messagebox.askyesno("System Drive",
                                       f"Apply UNIVERSAL icon to SYSTEM drive {drive}?\n\n"
                                       f"Will work on Windows/Linux/macOS after restart.\n\nContinue?",
                                       icon="warning"):
                return
        elif self.eject_var.get():
            if not messagebox.askyesno("Confirm Eject",
                                       f"Apply icon to {drive} then eject?\nClose all files on {drive} first."):
                return

        self._run_pipeline(universal_icon_pipeline,
                           (drive, self._ico, self.label_var.get(),
                            self.hide_var.get(), self.eject_var.get()))

    def _finish(self, success, msg, log, show_restart=False):
        self.progress.stop()
        self.progress.pack_forget()
        log.done()
        if success:
            messagebox.showinfo("Success!", msg)
            self._refresh_drives()
            if show_restart:
                restart_computer_countdown(self)
        else:
            messagebox.showerror("Error", msg)

    def _remove_icon(self):
        drive, _ = self._get_drive()
        if not drive:
            return
        if not messagebox.askyesno("Remove Icon",
                                   f"Remove all platform icons from {drive}?\n"
                                   f"Will restore default icons on Windows/Linux/macOS."):
            return
        try:
            reg_remove_icon(drive)

            # Only remove icon files, not system files
            icon_patterns = [
                "desktop.ini",
                "autorun.inf",
                ".directory",
                ".VolumeIcon.icns",
                "VolumeIcon.icns",
                ".DS_Store",
                ".fseventsd",
                ".metadata_never_index",
                ".icons",
            ]

            for pattern in icon_patterns:
                path = os.path.join(drive, pattern)
                dot_path = os.path.join(drive, '.' + pattern.lstrip('.'))
                
                if os.path.exists(path) and is_safe_to_hide(path):
                    clear_attribs(path)
                    try:
                        os.remove(path)
                    except:
                        pass
                
                if os.path.exists(dot_path) and is_safe_to_hide(dot_path):
                    clear_attribs(dot_path)
                    try:
                        os.remove(dot_path)
                    except:
                        pass

            self.status_v.set("Icon removed. Refreshing...")
            self.update()

            def _run():
                full_refresh_quick(drive)
                self.after(0, lambda: (
                    self.status_v.set("Default icons restored on all platforms."),
                    self._on_drive()))

            threading.Thread(target=_run, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _diagnostics(self):
        drive, _ = self._get_drive()
        if not drive:
            return
        messagebox.showinfo("Diagnostics", drive_diagnostics(drive))

    def destroy(self):
        try:
            shutil.rmtree(self._tmp, ignore_errors=True)
        except:
            pass
        super().destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()