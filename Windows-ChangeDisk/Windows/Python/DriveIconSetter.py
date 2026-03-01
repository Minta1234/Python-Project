"""
Drive Icon Setter  v10.0  —  WINDOWS EDITION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WORKS ON:
  🪟 Windows 10/11 (all versions)

FEATURES:
  ✅ Set custom icons for any drive (C:\, D:\, USB, External HDD)
  ✅ Registry-based (HKLM + HKCU) for instant updates
  ✅ All icon files HIDDEN on Windows (+H+S attributes)
  ✅ Automatic drive detection
  ✅ Safe eject for USB drives
  ✅ One click applies to selected drive
  ✅ Diagnostics shows what's hidden
  ✅ Built-in image crop editor
  ✅ Cross-platform files for Linux/macOS compatibility
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

# ==============================================================================
#  DRIVE DETECTION
# ==============================================================================

def get_drives():
    """Get all accessible drives on Windows"""
    drives = []
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        if bitmask & 1:
            drive_path = f"{letter}:\\"
            drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive_path)
            
            # Check if drive is accessible
            try:
                ctypes.windll.kernel32.GetDiskFreeSpaceExW(drive_path, None, None, None)
                
                # Get drive label
                label = get_drive_label(drive_path)
                
                # Get free space
                free_bytes = ctypes.c_ulonglong(0)
                total_bytes = ctypes.c_ulonglong(0)
                ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                    drive_path, None, ctypes.byref(total_bytes), ctypes.byref(free_bytes))
                
                drives.append({
                    'path': drive_path,
                    'letter': letter,
                    'type': drive_type,
                    'type_name': DRIVE_TYPE_LABEL.get(drive_type, "Unknown"),
                    'label': label,
                    'total': total_bytes.value,
                    'free': free_bytes.value,
                    'is_system': (drive_path.rstrip("\\").upper() == 
                                 os.environ.get("SystemDrive", "C:").upper())
                })
            except:
                pass
        bitmask >>= 1
    
    return drives

def get_drive_label(drive):
    """Get volume label for a drive"""
    buf = ctypes.create_unicode_buffer(261)
    try:
        ctypes.windll.kernel32.GetVolumeInformationW(
            drive, buf, 261, None, None, None, None, 0)
        return buf.value
    except:
        return ""

def is_admin():
    """Check if running as administrator"""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except:
        return False

def relaunch_as_admin():
    """Relaunch the script with administrator privileges"""
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    sys.exit()

# ==============================================================================
#  FILE ATTRIBUTE HELPERS (Windows)
# ==============================================================================

def clear_attribs(path):
    """Clear all file attributes"""
    if os.path.exists(path):
        subprocess.run(["attrib", "-R", "-H", "-S", path],
                       shell=True, capture_output=True)

def set_hidden_windows(path):
    """Hide on Windows with +H+S attributes"""
    if os.path.exists(path):
        subprocess.run(["attrib", "+H", "+S", path],
                       shell=True, capture_output=True)

def is_hidden_windows(path):
    """Check if file is hidden on Windows"""
    if not os.path.exists(path):
        return False
    result = subprocess.run(f"attrib {path}", shell=True, 
                           capture_output=True, text=True)
    return 'H' in result.stdout

# ==============================================================================
#  REGISTRY HELPERS
# ==============================================================================

def reg_set_icon(drive, ico_path, label=""):
    """Write icon to Windows Registry (HKLM + HKCU)"""
    letter = drive.rstrip("\\").rstrip(":")[0].upper()
    
    for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
        try:
            # Set DefaultIcon
            with winreg.CreateKeyEx(hive,
                                    f"{REG_BASE}\\{letter}\\DefaultIcon",
                                    0, winreg.KEY_SET_VALUE) as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, ico_path)
            
            # Set DefaultLabel if provided
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
    """Get current registry icon path"""
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
    """Remove registry icon entry for a drive"""
    letter = drive.rstrip("\\").rstrip(":")[0].upper()
    
    for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
        for sub in ["DefaultIcon", "DefaultLabel", ""]:
            try:
                path = f"{REG_BASE}\\{letter}" + (f"\\{sub}" if sub else "")
                winreg.DeleteKey(hive, path)
            except:
                pass

# ==============================================================================
#  EXPLORER CONTROL (Shell notifications)
# ==============================================================================

# Shell notification constants
SHCNE_UPDATEITEM = 0x00002000
SHCNE_RENAMEFOLDER = 0x00020000
SHCNE_ASSOCCHANGED = 0x08000000
SHCNE_ALLEVENTS = 0x7FFFFFFF
SHCNF_PATHW = 0x0005
SHCNF_FLUSH = 0x1000
SHCNF_FLUSHNOWAIT = 0x3000

def kill_explorer():
    """Kill Explorer and wait until fully terminated"""
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
    """Delete Windows icon cache files"""
    deleted = 0
    
    patterns = [
        r"%LOCALAPPDATA%\Microsoft\Windows\Explorer\iconcache*.db",
        r"%LOCALAPPDATA%\Microsoft\Windows\Explorer\thumbcache*.db",
    ]
    
    if IS_WIN11:
        patterns.append(r"%LOCALAPPDATA%\Microsoft\Windows\Explorer\*.db")
    
    for pattern in patterns:
        for f in glob.glob(os.path.expandvars(pattern)):
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
    """Start Explorer and wait until running"""
    subprocess.Popen("explorer.exe", shell=True)
    
    for _ in range(40):
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq explorer.exe"],
                           capture_output=True, text=True, shell=True)
        if "explorer.exe" in r.stdout.lower():
            break
        time.sleep(0.3)
    
    time.sleep(2.5 if IS_WIN11 else 2.0)

def notify_shell(drive):
    """Notify Windows Shell to update icon"""
    s32 = ctypes.windll.shell32
    p = ctypes.create_unicode_buffer(drive)
    
    s32.SHChangeNotify(SHCNE_UPDATEITEM, SHCNF_PATHW | SHCNF_FLUSH, p, None)
    s32.SHChangeNotify(SHCNE_RENAMEFOLDER, SHCNF_PATHW | SHCNF_FLUSH, p, None)
    s32.SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_FLUSHNOWAIT, None, None)
    s32.SHChangeNotify(SHCNE_ALLEVENTS, SHCNF_FLUSHNOWAIT, None, None)

# ==============================================================================
#  SAFE EJECT FUNCTION (USB Drives)
# ==============================================================================

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
    """Safely eject a USB drive"""
    letter = drive.rstrip("\\").rstrip(":")[0].upper()
    k32 = ctypes.windll.kernel32
    h = k32.CreateFileW(f"\\\\.\\{letter}:",
                        GR | GW, FSR | FSW, None, OE, FNB, None)
    
    if h == IHV:
        # Fallback to PowerShell
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
        
        # Final fallback to PowerShell
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

# ==============================================================================
#  ICON CONVERSION FUNCTIONS
# ==============================================================================

def pil_to_ico(img, out_path):
    """Convert PIL image to Windows .ico format"""
    img = img.convert("RGBA")
    icons = [img.resize((s, s), Image.LANCZOS) for s in SIZES]
    icons[0].save(out_path, format="ICO",
                  sizes=[(s, s) for s in SIZES], append_images=icons[1:])

def pil_to_png(img, out_path, size=256):
    """Convert PIL image to PNG for cross-platform compatibility"""
    img = img.convert("RGBA")
    resized = img.resize((size, size), Image.LANCZOS)
    resized.save(out_path, "PNG")

# ==============================================================================
#  WINDOWS ICON CREATION FUNCTIONS
# ==============================================================================

def create_windows_icons(drive, ico_src, ico_dest, icons_dir, label, step_cb):
    """Create Windows-specific icon files"""
    def log(msg):
        if step_cb:
            step_cb(msg)
    
    log("\n🪟 Creating Windows icons...")
    
    # Copy to ProgramData (for Registry)
    try:
        shutil.copy2(ico_src, ico_dest)
        log(f"  ✅ Copied to ProgramData")
    except Exception as e:
        log(f"  ⚠️ Could not copy to ProgramData: {e}")
    
    # Copy to .icons folder (for cross-platform)
    ico_root = os.path.join(icons_dir, "drive_icon.ico")
    try:
        shutil.copy2(ico_src, ico_root)
        log(f"  ✅ Copied to .icons folder")
    except Exception as e:
        log(f"  ⚠️ Could not copy to .icons: {e}")
    
    # Write to Registry
    try:
        reg_set_icon(drive, ico_dest, label)
        log(f"  ✅ Registry updated")
    except Exception as e:
        log(f"  ⚠️ Registry update failed: {e}")
    
    # Create desktop.ini
    desktop_ini = os.path.join(drive, "desktop.ini")
    ico_rel = f"{ICO_FOLDER}\\drive_icon.ico"
    ini_content = (
        "[.ShellClassInfo]\r\n"
        f"IconResource={ico_rel},0\r\n"
        f"IconFile={ico_rel}\r\n"
        "IconIndex=0\r\n"
    )
    
    try:
        if os.path.exists(desktop_ini):
            clear_attribs(desktop_ini)
        with open(desktop_ini, "w", encoding="utf-8", newline="") as f:
            f.write(ini_content)
        log(f"  ✅ Created desktop.ini")
    except Exception as e:
        log(f"  ⚠️ Could not create desktop.ini: {e}")
    
    # Create autorun.inf
    auto_path = os.path.join(drive, "autorun.inf")
    ico_rel_auto = ICO_FOLDER + chr(92) + "drive_icon.ico"
    auto_lines = ["[autorun]", f"icon={ico_rel_auto}"]
    if label.strip():
        auto_lines.append(f"label={label.strip()}")
    auto_content = "\r\n".join(auto_lines) + "\r\n"
    
    try:
        if os.path.exists(auto_path):
            clear_attribs(auto_path)
        with open(auto_path, "w", encoding="utf-8", newline="") as f:
            f.write(auto_content)
        log(f"  ✅ Created autorun.inf")
    except Exception as e:
        log(f"  ⚠️ Could not create autorun.inf: {e}")
    
    # Set drive attributes
    try:
        subprocess.run(["attrib", "+S", "+R", drive], shell=True, capture_output=True)
    except:
        pass
    
    return ico_root

# ==============================================================================
#  LINUX/MACOS COMPATIBILITY FUNCTIONS
# ==============================================================================

def create_linux_icons(drive, pil_img, icons_dir, step_cb):
    """Create Linux compatibility files"""
    def log(msg):
        if step_cb:
            step_cb(msg)
    
    log("\n🐧 Creating Linux compatibility files...")
    
    # Create PNGs for Linux
    png_sizes = [256, 128, 64, 48, 32, 16]
    png_files = []
    
    for size in png_sizes:
        png_path = os.path.join(icons_dir, f"drive_icon_{size}.png")
        try:
            resized = pil_img.resize((size, size), Image.LANCZOS)
            resized.save(png_path, "PNG")
            png_files.append(png_path)
            log(f"  ✅ Created {size}px PNG")
        except Exception as e:
            log(f"  ⚠️ Could not create {size}px PNG: {e}")
    
    # Create main PNG
    main_png = os.path.join(icons_dir, "drive_icon.png")
    try:
        pil_img.resize((256, 256), Image.LANCZOS).save(main_png, "PNG")
        png_files.append(main_png)
        log(f"  ✅ Created main PNG")
    except Exception as e:
        log(f"  ⚠️ Could not create main PNG: {e}")
    
    # Create .directory file for Linux
    directory_file = os.path.join(drive, ".directory")
    dir_content = (
        "[Desktop Entry]\n"
        f"Icon={ICO_FOLDER}/.drive_icon.png\n"
        "Name=Removable Drive\n"
        "Type=Directory\n"
    )
    
    try:
        with open(directory_file, "w", encoding="utf-8", newline="\n") as f:
            f.write(dir_content)
        log(f"  ✅ Created .directory (Linux)")
    except Exception as e:
        log(f"  ⚠️ Could not create .directory: {e}")
    
    return png_files

def create_macos_icons(drive, pil_img, icons_dir, step_cb):
    """Create macOS compatibility files"""
    def log(msg):
        if step_cb:
            step_cb(msg)
    
    log("\n🍎 Creating macOS compatibility files...")
    mac_files = []
    
    # Create 512px PNG for macOS
    png_large = os.path.join(icons_dir, "drive_icon_512.png")
    try:
        pil_img.resize((512, 512), Image.LANCZOS).save(png_large, "PNG")
        log(f"  ✅ Created 512px PNG")
    except Exception as e:
        log(f"  ⚠️ Could not create 512px PNG: {e}")
        return []
    
    # Create .VolumeIcon.icns (macOS volume icon)
    mac_icon = os.path.join(drive, ".VolumeIcon.icns")
    try:
        shutil.copy2(png_large, mac_icon)
        mac_files.append(mac_icon)
        log(f"  ✅ Created .VolumeIcon.icns")
    except Exception as e:
        log(f"  ⚠️ Could not create .VolumeIcon.icns: {e}")
    
    # Create VolumeIcon.icns (visible fallback)
    mac_icon_vis = os.path.join(drive, "VolumeIcon.icns")
    try:
        shutil.copy2(png_large, mac_icon_vis)
        mac_files.append(mac_icon_vis)
        log(f"  ✅ Created VolumeIcon.icns")
    except Exception as e:
        log(f"  ⚠️ Could not create VolumeIcon.icns: {e}")
    
    # Create .DS_Store
    ds_store = os.path.join(drive, ".DS_Store")
    try:
        with open(ds_store, 'wb') as f:
            f.write(b'\x00' * 4096)
        mac_files.append(ds_store)
        log(f"  ✅ Created .DS_Store")
    except Exception as e:
        log(f"  ⚠️ Could not create .DS_Store: {e}")
    
    # Create .fseventsd folder
    fseventsd = os.path.join(drive, ".fseventsd")
    try:
        os.makedirs(fseventsd, exist_ok=True)
        no_log = os.path.join(fseventsd, "no_log")
        with open(no_log, 'w') as f:
            f.write("")
        mac_files.append(fseventsd)
        log(f"  ✅ Created .fseventsd folder")
    except Exception as e:
        log(f"  ⚠️ Could not create .fseventsd: {e}")
    
    # Create .metadata_never_index
    never_index = os.path.join(drive, ".metadata_never_index")
    try:
        with open(never_index, 'w') as f:
            f.write("")
        mac_files.append(never_index)
        log(f"  ✅ Created .metadata_never_index")
    except Exception as e:
        log(f"  ⚠️ Could not create .metadata_never_index: {e}")
    
    return mac_files

# ==============================================================================
#  CLEANUP FUNCTIONS (Remove macOS temp files)
# ==============================================================================

def cleanup_macos_temp_files(drive, step_cb=None):
    """Remove macOS temporary files that appear on Windows"""
    def log(msg):
        if step_cb:
            step_cb(msg)
        else:
            print(msg)
    
    log("\n🧹 Cleaning up macOS temporary files...")
    removed = 0
    hidden = 0
    
    # Patterns for temporary files to remove
    remove_patterns = [
        ".DS_Store.tmp",
        ".DS_Store_temp",
        ".DS_Store_temp*",
        "._*",  # macOS resource forks
        ".Spotlight-V100",
        ".Trashes",
        ".fseventsd_temp*"
    ]
    
    # Remove temporary files
    for pattern in remove_patterns:
        for file in glob.glob(os.path.join(drive, pattern)):
            try:
                os.remove(file)
                log(f"  🗑️ Removed {os.path.basename(file)}")
                removed += 1
            except:
                try:
                    set_hidden_windows(file)
                    log(f"  🔒 Hidden {os.path.basename(file)} (could not delete)")
                    hidden += 1
                except:
                    pass
    
    # Hide regular .DS_Store files
    for file in glob.glob(os.path.join(drive, ".DS_Store*")):
        if os.path.exists(file) and not file.endswith('.tmp'):
            set_hidden_windows(file)
            log(f"  🔒 Hidden {os.path.basename(file)}")
            hidden += 1
    
    log(f"✅ Cleanup complete: {removed} removed, {hidden} hidden")
    return removed + hidden

# ==============================================================================
#  FILE HIDING FUNCTIONS (Windows)
# ==============================================================================

def hide_all_windows_files(drive, icons_dir, png_files, mac_files, step_cb):
    """Hide all icon files on Windows using +H+S attributes"""
    def log(msg):
        if step_cb:
            step_cb(msg)
    
    log("\n🔒 Hiding files on Windows...")
    hidden_count = 0
    
    # Hide .icons folder
    if os.path.exists(icons_dir):
        set_hidden_windows(icons_dir)
        log(f"  ✅ .icons/ folder hidden")
        hidden_count += 1
    
    # Hide Windows-specific files
    windows_files = [
        "desktop.ini",
        "autorun.inf",
        ".directory",
        ".VolumeIcon.icns",
        "VolumeIcon.icns",
        ".DS_Store",
        ".fseventsd",
        ".metadata_never_index"
    ]
    
    for file in windows_files:
        path = os.path.join(drive, file)
        if os.path.exists(path):
            set_hidden_windows(path)
            log(f"  ✅ {file} hidden")
            hidden_count += 1
    
    # Hide all PNG files
    for png in png_files:
        if os.path.exists(png):
            set_hidden_windows(png)
            hidden_count += 1
    
    # Hide all macOS files
    for mac_file in mac_files:
        if os.path.exists(mac_file):
            set_hidden_windows(mac_file)
            hidden_count += 1
    
    log(f"✅ Total {hidden_count} files hidden on Windows")
    return hidden_count

# ==============================================================================
#  MAIN APPLY PIPELINE
# ==============================================================================

ICO_FOLDER = ".icons"

def apply_icon_pipeline(drive_info, ico_src, label, do_eject, status_cb, done_cb):
    """Main pipeline to apply icon to drive"""
    drive = drive_info['path']
    is_usb = (drive_info['type'] == DRIVE_REMOVABLE)
    is_sys = drive_info['is_system']
    letter = drive_info['letter']
    t0 = time.time()

    def step(n, total, msg):
        status_cb(f"[{time.time() - t0:.1f}s] [{n}/{total}] {msg}")

    try:
        # Create necessary directories
        os.makedirs(ICO_STORE, exist_ok=True)
        ico_dest = os.path.join(ICO_STORE, f"drive_{letter}.ico")
        icons_dir = os.path.join(drive, ICO_FOLDER)

        # 1. Kill Explorer
        step(1, 15, f"Stopping Explorer (Windows {WIN_VER})...")
        kill_explorer()

        # 2. Delete icon cache
        step(2, 15, "Deleting Windows icon cache...")
        n = delete_icon_cache()
        step(2, 15, f"Removed {n} cache file(s).")

        # 3. Remove old icon files
        step(3, 15, "Removing old icon files...")
        removed = 0
        
        # Remove from ProgramData
        if os.path.exists(ico_dest):
            try:
                clear_attribs(ico_dest)
                os.remove(ico_dest)
                removed += 1
            except:
                pass
        
        # Remove old icon files from drive root
        for pattern in ["drive_icon*.ico", ".VolumeIcon*", "desktop.ini", "autorun.inf", ".directory"]:
            for old in glob.glob(os.path.join(drive, pattern)):
                try:
                    clear_attribs(old)
                    os.remove(old)
                    removed += 1
                except:
                    pass
        
        step(3, 15, f"Removed {removed} old file(s).")

        # 4. ie4uinit pre-clear
        step(4, 15, "ie4uinit pre-clear...")
        try:
            subprocess.run(["ie4uinit.exe", "-show"], capture_output=True, timeout=8)
        except:
            pass

        # 5. Create .icons folder
        step(5, 15, "Creating .icons folder...")
        if os.path.exists(icons_dir):
            clear_attribs(icons_dir)
        os.makedirs(icons_dir, exist_ok=True)

        # 6. Load PIL image
        step(6, 15, "Loading image...")
        from PIL import Image as _Img
        pil_img = _Img.open(ico_src).convert("RGBA")

        # 7. Create Windows icons
        step(7, 15, "Creating Windows icons...")
        create_windows_icons(drive, ico_src, ico_dest, icons_dir, label,
                            lambda m: step(7, 15, m))

        # 8. Create Linux compatibility files
        step(8, 15, "Creating Linux compatibility files...")
        png_files = create_linux_icons(drive, pil_img, icons_dir,
                                       lambda m: step(8, 15, m))

        # 9. Create macOS compatibility files
        step(9, 15, "Creating macOS compatibility files...")
        mac_files = create_macos_icons(drive, pil_img, icons_dir,
                                      lambda m: step(9, 15, m))

        # 10. Hide all files on Windows
        step(10, 15, "Hiding files on Windows...")
        hide_all_windows_files(drive, icons_dir, png_files, mac_files,
                              lambda m: step(10, 15, m))

        # 11. Clean up macOS temporary files
        step(11, 15, "Cleaning up macOS temporary files...")
        cleanup_macos_temp_files(drive, lambda m: step(11, 15, m))

        # 12. ie4uinit post
        step(12, 15, "Rebuilding Windows cache...")
        try:
            subprocess.run(["ie4uinit.exe", "-ClearIconCache"],
                           capture_output=True, timeout=8)
        except:
            pass
        subprocess.run(["ie4uinit.exe", "-show"], capture_output=True)

        # 13. Start Explorer
        step(13, 15, "Starting Explorer...")
        start_explorer()

        # 14. Notify shell
        step(14, 15, "Notifying Windows shell...")
        notify_shell(drive)
        time.sleep(1.0)
        notify_shell(drive)

        # 15. Final verification
        step(15, 15, "Verifying...")
        time.sleep(0.5)

        total = time.time() - t0
        step(15, 15, f"Done! Finished in {total:.1f}s")

        # Eject if requested
        eject_ok = False
        if do_eject and is_usb:
            status_cb("Ejecting drive...")
            time.sleep(0.5)
            eject_ok, eject_msg = safe_eject(drive)
            status_cb(eject_msg)

        msg_time = time.strftime("%H:%M:%S")

        success_msg = (
            f"✅ ICON APPLIED SUCCESSFULLY!\n\n"
            f"Drive: {drive}\n"
            f"Time: {msg_time}  ({total:.1f}s)\n\n"
            f"🪟 WINDOWS:\n"
            f"  • Registry updated (HKLM+HKCU)\n"
            f"  • desktop.ini + autorun.inf\n"
            f"  • All files hidden (+H+S)\n"
            f"  • Icon visible in File Explorer\n\n"
            f"🐧 LINUX COMPATIBILITY:\n"
            f"  • .directory file created\n"
            f"  • PNG icons in .icons/ folder\n\n"
            f"🍎 MACOS COMPATIBILITY:\n"
            f"  • .VolumeIcon.icns created\n"
            f"  • .DS_Store + metadata files\n\n"
            f"Plug this drive into ANY computer:\n"
            f"  ✅ Windows → sees icon (clean drive)\n"
            f"  ✅ Linux → sees icon (hidden files)\n"
            f"  ✅ macOS → sees icon (hidden files)\n"
        )

        if eject_ok:
            success_msg += f"\n✅ Drive ejected successfully!"

        if is_sys:
            success_msg += f"\n\n⚠️ System drive may need a restart for full effect."

        done_cb(True, success_msg)

    except PermissionError as e:
        done_cb(False, f"❌ Permission denied:\n{e}\n\nRight-click → Run as Administrator")
    except Exception as e:
        import traceback
        done_cb(False, f"❌ Error: {e}\n\n{traceback.format_exc()}")

# ==============================================================================
#  REMOVE ICON FUNCTION
# ==============================================================================

def remove_icon(drive_info, status_cb, done_cb):
    """Remove all icon files and registry entries"""
    drive = drive_info['path']
    t0 = time.time()

    def step(msg):
        status_cb(f"[{time.time() - t0:.1f}s] {msg}")

    try:
        removed = 0

        # Remove registry entries
        step("Removing registry entries...")
        reg_remove_icon(drive)
        removed += 1

        # Remove Windows files
        for fname in ["desktop.ini", "autorun.inf"]:
            path = os.path.join(drive, fname)
            if os.path.exists(path):
                clear_attribs(path)
                os.remove(path)
                removed += 1
                step(f"Removed {fname}")

        # Remove Linux files
        linux_file = os.path.join(drive, ".directory")
        if os.path.exists(linux_file):
            os.remove(linux_file)
            removed += 1
            step("Removed .directory")

        # Remove macOS files
        mac_files = [".VolumeIcon.icns", "VolumeIcon.icns", ".DS_Store",
                     ".fseventsd", ".metadata_never_index"]
        for fname in mac_files:
            path = os.path.join(drive, fname)
            if os.path.exists(path):
                clear_attribs(path)
                os.remove(path)
                removed += 1
                step(f"Removed {fname}")

        # Remove .icons folder
        icons_dir = os.path.join(drive, ICO_FOLDER)
        if os.path.exists(icons_dir):
            shutil.rmtree(icons_dir, ignore_errors=True)
            removed += 1
            step("Removed .icons folder")

        # Refresh Explorer
        step("Refreshing Explorer...")
        notify_shell(drive)
        subprocess.run(["ie4uinit.exe", "-ClearIconCache"], capture_output=True)

        done_cb(True, f"✅ Icon removed from {drive}\n{removed} files/folders deleted")

    except Exception as e:
        done_cb(False, f"❌ Error: {e}")

# ==============================================================================
#  DIAGNOSTICS
# ==============================================================================

def drive_diagnostics(drive_info):
    """Show diagnostic information for a drive"""
    drive = drive_info['path']
    letter = drive_info['letter']
    
    lines = [f"=== Diagnostics: {drive} ===",
             f"Windows        : {WIN_VER}",
             f"Admin rights   : {'YES' if is_admin() else 'NO'}",
             f"Drive type     : {drive_info['type_name']}",
             f"Drive label    : {drive_info['label'] or 'None'}"]

    # Check registry
    reg = reg_get_icon(drive)
    lines.append(f"Registry icon  : {reg or 'NONE'}")

    # Check Windows files
    for fname in ["desktop.ini", "autorun.inf"]:
        path = os.path.join(drive, fname)
        status = "EXISTS" if os.path.exists(path) else "missing"
        hidden = " (HIDDEN)" if os.path.exists(path) and is_hidden_windows(path) else ""
        lines.append(f"Windows {fname:12}: {status}{hidden}")

    # Check Linux files
    linux_file = os.path.join(drive, ".directory")
    status = "EXISTS" if os.path.exists(linux_file) else "missing"
    lines.append(f"Linux .directory: {status}")

    # Check macOS files
    mac_files = [".VolumeIcon.icns", "VolumeIcon.icns", ".DS_Store",
                 ".fseventsd", ".metadata_never_index"]
    for fname in mac_files:
        path = os.path.join(drive, fname)
        status = "EXISTS" if os.path.exists(path) else "missing"
        hidden = " (HIDDEN)" if os.path.exists(path) and is_hidden_windows(path) else ""
        lines.append(f"macOS {fname:20}: {status}{hidden}")

    # Check .icons folder
    icons_dir = os.path.join(drive, ICO_FOLDER)
    if os.path.exists(icons_dir):
        icons = glob.glob(os.path.join(icons_dir, "*"))
        lines.append(f"\nIcons in .icons/: {len(icons)} files")
        for i in sorted(icons)[:8]:
            size = os.path.getsize(i)
            name = os.path.basename(i)
            hidden = " (HIDDEN)" if is_hidden_windows(i) else ""
            lines.append(f"  {name:30} ({size:,} bytes){hidden}")
        if len(icons) > 8:
            lines.append(f"  ... and {len(icons) - 8} more")
    else:
        lines.append(f"Icons in .icons/: missing")

    # Check ProgramData
    pd = os.path.join(ICO_STORE, f"drive_{letter}.ico")
    status = "EXISTS" if os.path.exists(pd) else "missing"
    lines.append(f"\nProgramData ico: {status}")

    return "\n".join(lines)

# ==============================================================================
#  RESTART COMPUTER COUNTDOWN
# ==============================================================================

def restart_computer_countdown(parent=None):
    """Show countdown window before restart"""
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
             text="System drive requires a restart to show the new icon.",
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

# ==============================================================================
#  GUI COMPONENTS
# ==============================================================================

# Colors (Catppuccin theme)
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
        flat_btn(br, "Use this icon", self._confirm, accent=True).pack(side="right")

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

# ==============================================================================
#  MAIN APPLICATION
# ==============================================================================

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Drive Icon Setter  v10.0  —  Windows Edition")
        self.configure(bg=BG, padx=28, pady=22)
        self.resizable(False, False)
        
        self._src = None
        self._final = None
        self._ico = None
        self._tmp = tempfile.mkdtemp()
        self._drives = []
        
        self.drive_var = tk.StringVar()
        self.label_var = tk.StringVar()
        self.eject_var = tk.BooleanVar(value=False)
        
        self._build_ui()
        self._refresh_drives()
        
        if not is_admin():
            self._admin_banner()

    def _build_ui(self):
        # Title
        tk.Label(self,
                 text=f"  Drive Icon Setter  v10.0  —  Windows Edition",
                 bg=BG, fg=ACCENT,
                 font=("Segoe UI", 15, "bold")).pack(anchor="w", pady=(0, 4))

        # Info frame
        info = tk.Frame(self, bg=SURFACE, padx=12, pady=8)
        info.pack(fill="x", pady=(0, 6))
        
        tk.Label(info,
                 text=f"Windows {WIN_VER} • Registry + desktop.ini • Cross-platform compatibility",
                 bg=SURFACE, fg=GREEN,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Label(info,
                 text="Set icons for any drive • All files hidden • Works on Linux/macOS too",
                 bg=SURFACE, fg=SUBTEXT,
                 font=("Segoe UI", 9)).pack(anchor="w")

        # Step 1 - Choose image
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

        # Step 2 - Select drive
        self._sec("Step 2  —  Select drive")
        
        f2 = tk.Frame(self, bg=BG)
        f2.pack(fill="x", pady=(0, 4))
        
        tk.Label(f2, text="Drive:", bg=BG, fg=TEXT,
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
        
        tk.Label(f2, text="Label:", bg=BG, fg=TEXT,
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

        # Step 3 - Options
        self._sec("Step 3  —  Options & Apply")
        
        self.eject_chk = tk.Checkbutton(
            self, text="  Auto Eject after Apply  (USB / External HDD)",
            variable=self.eject_var, bg=BG, fg=GREEN, selectcolor=SURFACE,
            activebackground=BG, activeforeground=GREEN,
            font=("Segoe UI", 10, "bold"), state="disabled")
        self.eject_chk.pack(anchor="w", pady=(3, 10))

        # Progress bar
        self.progress = ttk.Progressbar(self, mode="indeterminate", length=420)
        tk.Frame(self, bg=BG, height=5).pack()

        # Apply button
        self.apply_btn = flat_btn(
            self, "  ✅ APPLY ICON TO DRIVE  ",
            self._apply, accent=True)
        self.apply_btn.pack(fill="x", pady=(5, 0))

        # Status
        self.status_v = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self.status_v, bg="#181825", fg=SUBTEXT,
                anchor="w", font=("Consolas", 9), padx=10, pady=5
                ).pack(fill="x", pady=(8, 0))

        # Bottom buttons
        bf = tk.Frame(self, bg=BG)
        bf.pack(fill="x", pady=(6, 0))
        
        flat_btn(bf, "  Remove Icon  ",
                self._remove_icon, color="#585b70"
                ).pack(side="left", fill="x", expand=True, padx=(0, 3))
        
        flat_btn(bf, "  Diagnostics  ",
                self._diagnostics, color=ORANGE
                ).pack(side="left", fill="x", expand=True, padx=(3, 0))

    def _admin_banner(self):
        b = tk.Frame(self, bg=YELLOW, padx=10, pady=8)
        b.pack(fill="x", before=self.winfo_children()[0])
        tk.Label(b,
                 text="  Not running as Administrator — Registry writes will fail!",
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
        """Refresh list of drives"""
        self._drives = get_drives()
        
        choices = []
        for d in self._drives:
            display = (f"{d['path']}  {d['label']}  ({d['type_name']})"
                      + (" [SYSTEM]" if d['is_system'] else ""))
            choices.append(display)
        
        self.combo["values"] = choices
        if choices:
            # Don't select system drive by default
            for i, d in enumerate(self._drives):
                if not d['is_system']:
                    self.combo.current(i)
                    break
            else:
                self.combo.current(0)
        self._on_drive()

    def _get_drive(self):
        """Get selected drive info"""
        idx = self.combo.current()
        if idx < 0 or idx >= len(self._drives):
            return None
        return self._drives[idx]

    def _on_drive(self, event=None):
        """Handle drive selection"""
        if not hasattr(self, "warn_l"):
            return
        
        drive = self._get_drive()
        if not drive:
            return
        
        is_usb = (drive['type'] == DRIVE_REMOVABLE)
        is_sys = drive['is_system']
        
        # Show current icon
        cur = reg_get_icon(drive['path'])
        self.cur_ico_l.config(
            text=f"Current icon: {cur}" if cur
            else "No custom icon set for this drive.")
        
        # Show warning for system drive
        if is_sys:
            self.warn_l.config(
                text="  System Drive — Restart PC to fully apply icon.",
                fg=ORANGE)
            if not hasattr(self, "so_btn"):
                self.so_btn = tk.Button(
                    self, text="Restart PC Now",
                    command=restart_computer_countdown,
                    bg=ORANGE, fg="#1e1e2e",
                    font=("Segoe UI", 8, "bold"),
                    relief="flat", padx=6)
                self.so_btn.pack(pady=(0, 4), after=self.warn_l)
        else:
            self.warn_l.config(text="")
            if hasattr(self, "so_btn"):
                self.so_btn.destroy()
                del self.so_btn
        
        # Enable eject for USB
        self.eject_chk.config(state="normal" if is_usb else "disabled")
        if not is_usb:
            self.eject_var.set(False)

    def _browse(self):
        """Browse for image file"""
        path = filedialog.askopenfilename(
            title="Select image",
            filetypes=[("Image files",
                       "*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tiff *.tif *.ico"),
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
                f"Size: {img.width} x {img.height} px  |  {ext}")
            
            self._ico = None
            self._final = None
            self.conv_l.config(text="Click 'Edit / Crop icon' to adjust.",
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
            out = os.path.join(self._tmp, "drive_icon.ico")
            pil_to_ico(result, out)
            self._ico = out
            self.conv_l.config(text="Icon ready! Click Apply.", fg=GREEN)
            self.status_v.set("Icon ready")
        except Exception as e:
            self.conv_l.config(text=f"Convert failed: {e}", fg=RED)

    def _check_ready(self):
        """Check if ready to apply"""
        if not self._ico or not os.path.isfile(self._ico):
            messagebox.showwarning("Not Ready",
                "Please select and edit an image first.")
            return False
        
        drive = self._get_drive()
        if not drive:
            messagebox.showwarning("No Drive", "Please select a drive.")
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
        """Apply icon to drive"""
        if not self._check_ready():
            return
        
        drive = self._get_drive()
        
        if drive['is_system']:
            if not messagebox.askyesno("System Drive",
                f"Apply icon to SYSTEM drive {drive['path']}?\n\n"
                f"Explorer will restart briefly.\n"
                f"Restart PC for full effect.\n\nContinue?",
                icon="warning"):
                return
        elif self.eject_var.get():
            if not messagebox.askyesno("Confirm Eject",
                f"Apply icon to {drive['path']} then eject?\n"
                f"Close all files on this drive first."):
                return

        self._run_pipeline(apply_icon_pipeline,
                          (drive, self._ico, self.label_var.get(),
                           self.eject_var.get()))

    def _finish(self, success, msg, log):
        """Handle completion"""
        self.progress.stop()
        self.progress.pack_forget()
        log.done()
        
        if success:
            messagebox.showinfo("Success!", msg)
            self._refresh_drives()
        else:
            messagebox.showerror("Error", msg)

    def _remove_icon(self):
        """Remove icon from drive"""
        drive = self._get_drive()
        if not drive:
            return
        
        if not messagebox.askyesno("Remove Icon",
            f"Remove custom icon from {drive['path']}?\n"
            f"Will restore default Windows icon."):
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
            target=remove_icon,
            args=(drive, _status, _done),
            daemon=True).start()

    def _finish_remove(self, success, msg, log):
        """Handle remove completion"""
        self.progress.stop()
        self.progress.pack_forget()
        log.done()
        
        if success:
            messagebox.showinfo("Success!", msg)
            self._refresh_drives()
        else:
            messagebox.showerror("Error", msg)

    def _diagnostics(self):
        """Show diagnostics"""
        drive = self._get_drive()
        if not drive:
            return
        messagebox.showinfo("Diagnostics", drive_diagnostics(drive))

    def destroy(self):
        """Cleanup"""
        try:
            shutil.rmtree(self._tmp, ignore_errors=True)
        except:
            pass
        super().destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()