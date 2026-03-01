"""
Drive Icon Setter  v7.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Features:
  ✅ Apply Icon        — local icon (Registry + real-time refresh)
  ✅ Remove Icon       — remove icon, restore Windows default
  ✅ Diagnostics       — check drive icon status
  ✅ Win10/11 support  — auto-detect Windows version
  ✅ Live StepLog      — real-time progress window
  ✅ Crop Editor       — crop/zoom image before applying

Apply pipeline:
  1.  Kill Explorer        → release all file locks
  2.  Delete icon cache    → while Explorer is dead
  3.  Delete old .ico      → no stale icons
  4.  ie4uinit pre-clear   → clear cache before copy
  5.  Copy new .ico        → ProgramData + drive root
  6.  Write Registry       → HKLM + HKCU (ProgramData path)
  7.  Write desktop.ini    → UTF-8, +H+S
  8.  autorun.inf (USB)    → compatibility
  9.  ie4uinit post-clear  → rebuild cache
  10. Start Explorer       → load new icon
  11. Notify shell x3      → force redraw
"""

import os, sys, shutil, subprocess, tempfile, time, glob, ctypes, winreg, platform
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
        input("Press Enter to exit..."); sys.exit(1)

if sys.platform != "win32":
    print("Windows only."); sys.exit(1)

# ── Windows Version ───────────────────────────────────────────────────────────
def _get_win_ver():
    try:
        build = int(platform.version().split(".")[2])
        return "11" if build >= 22000 else "10"
    except:
        return "10"

WIN_VER  = _get_win_ver()
IS_WIN11 = WIN_VER == "11"

# ── Constants ─────────────────────────────────────────────────────────────────
DRIVE_REMOVABLE = 2; DRIVE_FIXED = 3; DRIVE_REMOTE = 4
DRIVE_CDROM = 5;     DRIVE_RAMDISK = 6
DRIVE_TYPE_LABEL = {
    DRIVE_REMOVABLE: "USB/Removable", DRIVE_FIXED: "Local Disk",
    DRIVE_REMOTE:    "Network",        DRIVE_CDROM: "CD/DVD",
    DRIVE_RAMDISK:   "RAM Disk",
}
SIZES     = [256, 128, 64, 48, 32, 16]
REG_BASE  = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\DriveIcons"
ICO_STORE = os.path.expandvars(r"%ProgramData%\DriveIcons")

# ── ICO converter ─────────────────────────────────────────────────────────────
def pil_to_ico(img, out_path):
    img   = img.convert("RGBA")
    icons = [img.resize((s, s), Image.LANCZOS) for s in SIZES]
    icons[0].save(out_path, format="ICO",
                  sizes=[(s, s) for s in SIZES], append_images=icons[1:])

# ── Drive detection ───────────────────────────────────────────────────────────
def get_drives():
    drives  = []
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        if bitmask & 1:
            d     = f"{letter}:\\"
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
    try:    return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except: return False

def relaunch_as_admin():
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    sys.exit()

# ── File attribute helpers ────────────────────────────────────────────────────
def clear_attribs(path):
    subprocess.run(["attrib", "-R", "-H", "-S", path],
                   shell=True, capture_output=True)

def set_hidden(path):
    """Hide with +H+S"""
    subprocess.run(["attrib", "+H", "+S", path],
                   shell=True, capture_output=True)

def set_system_only(path):
    """Hide with +S only — other machines can still read it"""
    subprocess.run(["attrib", "+S", "-H", "-R", path],
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
SHCNE_UPDATEITEM   = 0x00002000
SHCNE_RENAMEFOLDER = 0x00020000
SHCNE_ASSOCCHANGED = 0x08000000
SHCNE_ALLEVENTS    = 0x7FFFFFFF
SHCNF_PATHW        = 0x0005
SHCNF_FLUSH        = 0x1000
SHCNF_FLUSHNOWAIT  = 0x3000

# ── Explorer control ──────────────────────────────────────────────────────────
def kill_explorer():
    """Kill Explorer and wait until fully terminated."""
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
    """Delete cache DB files — only works while Explorer is NOT running."""
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
                    os.remove(f); deleted += 1
            except:
                pass
    try:
        subprocess.run(["ie4uinit.exe", "-ClearIconCache"],
                       capture_output=True, timeout=8)
    except:
        pass
    return deleted

def start_explorer():
    """Start Explorer and wait until running and settled."""
    subprocess.Popen("explorer.exe", shell=True)
    for _ in range(40):
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq explorer.exe"],
                           capture_output=True, text=True, shell=True)
        if "explorer.exe" in r.stdout.lower():
            break
        time.sleep(0.3)
    time.sleep(2.5 if IS_WIN11 else 2.0)

def notify_shell(drive):
    """Notify Shell to update icon — pure ctypes (real-time)."""
    s32 = ctypes.windll.shell32
    p   = ctypes.create_unicode_buffer(drive)
    s32.SHChangeNotify(SHCNE_UPDATEITEM,   SHCNF_PATHW | SHCNF_FLUSH, p, None)
    s32.SHChangeNotify(SHCNE_RENAMEFOLDER, SHCNF_PATHW | SHCNF_FLUSH, p, None)
    s32.SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_FLUSHNOWAIT, None, None)
    s32.SHChangeNotify(SHCNE_ALLEVENTS,    SHCNF_FLUSHNOWAIT, None, None)

ICO_FOLDER = ".icons"  # hidden folder for drive_icon.ico

def write_desktop_ini(drive, step_cb):
    """Write desktop.ini pointing to .icons/drive_icon.ico — UTF-8 no BOM."""
    desktop_ini = os.path.join(drive, "desktop.ini")
    if os.path.exists(desktop_ini):
        clear_attribs(desktop_ini)
    ico_rel = f"{ICO_FOLDER}\\drive_icon.ico"
    ini = (
        "[.ShellClassInfo]\r\n"
        "IconResource=" + ico_rel + ",0\r\n"
        "IconFile=" + ico_rel + "\r\n"
        "IconIndex=0\r\n"
    )
    with open(desktop_ini, "w", encoding="utf-8", newline="") as fh:
        fh.write(ini)
    subprocess.run(["attrib", "+H", "+S", "-R", desktop_ini],
                   shell=True, capture_output=True)
    # +S +R บน drive root — บอก Windows ให้อ่าน desktop.ini
    subprocess.run(["attrib", "+S", "+R", drive],
                   shell=True, capture_output=True)
    step_cb(f"desktop.ini → {ico_rel}  (UTF-8, +H+S) | drive +S+R")

# ── Safe eject ────────────────────────────────────────────────────────────────
IOCTL_EJECT=0x2D4808; IOCTL_REMOVAL=0x2D4804
FSCTL_LOCK=0x90018;   FSCTL_DISMOUNT=0x90020
GR=0x80000000; GW=0x40000000; FSR=1; FSW=2; OE=3
FNB=0x20000000; IHV=ctypes.c_void_p(-1).value

def safe_eject(drive):
    letter = drive.rstrip("\\").rstrip(":")[0].upper()
    k32    = ctypes.windll.kernel32
    h      = k32.CreateFileW(f"\\\\.\\{letter}:",
                             GR|GW, FSR|FSW, None, OE, FNB, None)
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
        k32.DeviceIoControl(h, FSCTL_LOCK,    None,0,None,0,ctypes.byref(br),None)
        k32.DeviceIoControl(h, FSCTL_DISMOUNT, None,0,None,0,ctypes.byref(br),None)
        class PMR(ctypes.Structure): _fields_=[("p", ctypes.c_ubyte)]
        pmr = PMR(0)
        k32.DeviceIoControl(h, IOCTL_REMOVAL,
                            ctypes.byref(pmr),1,None,0,ctypes.byref(br),None)
        ok = k32.DeviceIoControl(h, IOCTL_EJECT,
                                 None,0,None,0,ctypes.byref(br),None)
        if ok:
            return True, "Ejected!"
        # IOCTL failed — fallback to PowerShell (works for External HDD)
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
        try: k32.CloseHandle(h)
        except: pass

def restart_computer_countdown(parent=None):
    """15-second countdown window before PC restart."""
    win = tk.Toplevel(parent) if parent else tk.Tk()
    win.title("Restart PC")
    win.configure(bg=BG, padx=30, pady=24)
    win.resizable(False, False)
    win.grab_set()
    # Center window
    win.update_idletasks()
    w, h = 360, 220
    x = (win.winfo_screenwidth()  // 2) - (w // 2)
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

    bf = tk.Frame(win, bg=BG); bf.pack(pady=(14, 0), fill="x")
    flat_btn(bf, "Cancel", do_cancel, color="#585b70").pack(side="left", expand=True, padx=(0,4))
    flat_btn(bf, "Restart Now!", do_now, accent=True).pack(side="left", expand=True, padx=(4,0))

    def tick(n):
        if cancelled[0]: return
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
#  PIPELINE 1: APPLY ICON (เครื่องตัวเอง + real-time update)
#  Registry ชี้ไป ProgramData (ไม่ซ่อน) → Windows โหลดได้เสมอ
#  drive_icon.ico บน drive root ใช้ +S (ซ่อนจาก Explorer แต่อ่านได้)
# ═══════════════════════════════════════════════════════════════════════════════
def apply_icon_pipeline(drive, ico_src, label, hide_files, do_eject,
                        status_cb, done_cb):
    dtype  = ctypes.windll.kernel32.GetDriveTypeW(drive)
    is_usb = (dtype == DRIVE_REMOVABLE)
    letter = drive.rstrip("\\").rstrip(":")[0].upper()
    t0     = time.time()

    def step(n, total, msg):
        status_cb(f"[{time.time()-t0:.1f}s] [{n}/{total}] {msg}")

    try:
        os.makedirs(ICO_STORE, exist_ok=True)
        ico_dest    = os.path.join(ICO_STORE, f"drive_{letter}.ico")  # ProgramData
        icons_dir   = os.path.join(drive, ICO_FOLDER)                # D:\.icons\
        ico_root    = os.path.join(icons_dir, "drive_icon.ico")      # D:\.icons\drive_icon.ico

        # 1. Kill Explorer ────────────────────────────────────────────────────
        step(1,11,f"Stopping Explorer (Windows {WIN_VER})...")
        kill_explorer()

        # 2. ลบ icon cache ────────────────────────────────────────────────────
        step(2,11,"Deleting icon cache...")
        n = delete_icon_cache()
        step(2,11,f"Removed {n} cache file(s).")

        # 3. ลบ .ico เก่า ─────────────────────────────────────────────────────
        step(3,11,"Removing old icon files...")
        removed = 0
        if os.path.exists(ico_dest):
            try: clear_attribs(ico_dest); os.remove(ico_dest); removed += 1
            except Exception as e: step(3,11,f"Warn: {e}")
        for old in glob.glob(os.path.join(drive, "drive_icon*.ico")):
            try: clear_attribs(old); os.remove(old); removed += 1
            except: pass
        step(3,11,f"Removed {removed} old file(s).")

        # 4. ie4uinit pre-clear ───────────────────────────────────────────────
        step(4,11,"ie4uinit pre-clear...")
        try: subprocess.run(["ie4uinit.exe","-show"], capture_output=True, timeout=8)
        except: pass

        # 5. copy .ico ใหม่ ───────────────────────────────────────────────────
        step(5,11,"Copying new icon files...")
        # สร้างโฟลเดอร์ .icons (ซ่อน +H+S)
        if os.path.exists(icons_dir):
            clear_attribs(icons_dir)
        os.makedirs(icons_dir, exist_ok=True)
        shutil.copy2(ico_src, ico_dest)  # ProgramData — for Registry
        shutil.copy2(ico_src, ico_root)  # .icons\ — for desktop.ini
        # ไฟล์ข้างในไม่ซ่อน — โฟลเดอร์ซ่อนแทน
        clear_attribs(ico_root)
        # ซ่อนโฟลเดอร์ .icons หลัง copy เสร็จ
        set_hidden(icons_dir)
        step(5,11,f"ProgramData : {ico_dest}")
        step(5,11,f".icons dir  : {ico_root}")
        if os.path.exists(icons_dir):
            step(5,11,".icons\\ created ✓")
        else:
            step(5,11,"⚠️ .icons\\ creation failed!")

        # 6. Registry (ชี้ไป ProgramData — ไม่ซ่อน อ่านได้เสมอ) ─────────────
        step(6,11,"Writing Registry (HKLM + HKCU)...")
        reg_set_icon(drive, ico_dest, label)   # ← ico_dest not ico_root!
        step(6,11,f"Registry → {ico_dest}")

        # 7. desktop.ini ──────────────────────────────────────────────────────
        step(7,11,"Writing desktop.ini...")
        write_desktop_ini(drive, lambda m: step(7,11,m))

        # 8. ไม่ต้องซ่อน ico_root แยก — โฟลเดอร์ .icons ซ่อนทั้งหมดแล้ว
        step(8,11,".icons\\ folder +H+S — hidden from Explorer")

        # 9. autorun.inf (USB) ────────────────────────────────────────────────
        auto_path = os.path.join(drive, "autorun.inf")
        step(9,11,"Writing autorun.inf...")
        if os.path.exists(auto_path): clear_attribs(auto_path)
        # ชี้ไปที่ .icons\drive_icon.ico — ให้ตรงกับ desktop.ini
        ico_rel_auto = ICO_FOLDER + chr(92) + "drive_icon.ico"
        inf_lines = ["[autorun]", "icon=" + ico_rel_auto]
        if label.strip(): inf_lines.append("label=" + label.strip())
        with open(auto_path, "w", encoding="utf-8", newline="") as f:
            f.write("\r\n".join(inf_lines) + "\r\n")
        set_hidden(auto_path)

        # 10. ie4uinit post + Start Explorer ──────────────────────────────────
        step(10,11,"Rebuilding cache + starting Explorer...")
        try: subprocess.run(["ie4uinit.exe","-ClearIconCache"],
                            capture_output=True, timeout=8)
        except: pass
        subprocess.run(["ie4uinit.exe","-show"], capture_output=True)
        start_explorer()

        # 11. Notify shell x3 ─────────────────────────────────────────────────
        step(11,11,"Notifying shell (x3)...")
        notify_shell(drive)
        time.sleep(1.0)
        notify_shell(drive)
        time.sleep(0.5)
        notify_shell(drive)

        total = time.time() - t0
        step(11,11,f"Done! Finished in {total:.1f}s")

        # Eject ────────────────────────────────────────────────────────────────
        eject_ok = False
        if do_eject and not is_system_drive(drive):
            status_cb("Ejecting drive...")
            time.sleep(0.5)
            eject_ok, eject_msg = safe_eject(drive)
            status_cb(eject_msg)

        msg_time = time.strftime("%H:%M:%S")
        is_sys_done = is_system_drive(drive)
        if eject_ok:
            done_cb(True,
                    f"✅ Icon applied to {drive}\n"
                    f"✅ Ejected at {msg_time}\n\n"
                    f"Reconnect to see the icon.", False)
        else:
            sys_note = " — Auto restart countdown will open." if is_sys_done else ""
            done_cb(True,
                    f"✅ Icon applied to {drive}  (Win {WIN_VER}){sys_note}\n\n"
                    f"  Old icon deleted\n"
                    f"  New icon copied\n"
                    f"  Registry updated (HKLM+HKCU)\n"
                    f"  desktop.ini written\n"
                    f"  Icon cache cleared\n"
                    f"  Explorer restarted\n"
                    f"  Shell notified x3\n\n"
                    f"Done at {msg_time}  ({total:.1f}s)",
                    is_sys_done)

    except PermissionError as e:
        done_cb(False, f"Permission denied:\n{e}\n\nRight-click → Run as Administrator")
    except Exception as e:
        import traceback
        done_cb(False, f"Error: {e}\n\n{traceback.format_exc()}")

# ═══════════════════════════════════════════════════════════════════════════════
#  PIPELINE 2: PORTABLE ICON (เสียบเครื่องอื่นเห็นได้ทันที)
#  ไม่แตะ Registry — ใช้ desktop.ini + autorun.inf + drive_icon.ico (+S)
#  เครื่องอื่นเสียบแล้วเห็นไอคอนทันที ไม่ต้องติดตั้งอะไร
# ═══════════════════════════════════════════════════════════════════════════════
def portable_icon_pipeline(drive, ico_src, status_cb, done_cb):
    t0 = time.time()

    def step(n, total, msg):
        status_cb(f"[{time.time()-t0:.1f}s] [{n}/{total}] {msg}")

    try:
        icons_dir = os.path.join(drive, ICO_FOLDER)
        ico_root  = os.path.join(icons_dir, "drive_icon.ico")

        # 1. ลบไฟล์เก่า ───────────────────────────────────────────────────────
        step(1,4,"Removing old icon files...")
        for old in glob.glob(os.path.join(drive, "drive_icon*.ico")):
            try: clear_attribs(old); os.remove(old)
            except: pass
        desktop_ini = os.path.join(drive, "desktop.ini")
        if os.path.exists(desktop_ini): clear_attribs(desktop_ini)

        # 2. copy drive_icon.ico (+S — ซ่อนจาก Explorer แต่เครื่องอื่นอ่านได้)
        step(2,4,"Copying drive_icon.ico to .icons\\ ...")
        os.makedirs(icons_dir, exist_ok=True)
        set_hidden(icons_dir)   # folder +H+S
        shutil.copy2(ico_src, ico_root)
        clear_attribs(ico_root) # files inside not hidden — folder hides them
        step(2,4,".icons\\ folder +H+S | files inside readable")

        # 3. desktop.ini + autorun.inf ────────────────────────────────────────
        step(3,4,"Writing desktop.ini + autorun.inf...")
        write_desktop_ini(drive, lambda m: step(3,4,m))
        auto_path = os.path.join(drive, "autorun.inf")
        if os.path.exists(auto_path): clear_attribs(auto_path)
        with open(auto_path, "w", encoding="utf-8", newline="") as f:
            f.write("[autorun]\r\nicon=drive_icon.ico\r\n")
        set_hidden(auto_path)  # autorun.inf can be hidden +H+S

        # 4. Notify shell ─────────────────────────────────────────────────────
        step(4,4,"Notifying shell...")
        notify_shell(drive)
        time.sleep(0.5)
        notify_shell(drive)

        total = time.time() - t0
        step(4,4,f"Done! {total:.1f}s")

        done_cb(True,
                f"✅ Portable Icon set!\n\n"
                f"  drive_icon.ico  → +S (hidden but readable by others)\n"
                f"  desktop.ini     → +H+S (UTF-8)\n"
                f"  autorun.inf     → +H+S\n"
                f"  drive root      → +S+R\n\n"
                f"Plug into another PC → icon shows immediately!\n"
                f"(Press F5 if icon not showing)")

    except PermissionError as e:
        done_cb(False, f"Permission denied:\n{e}\n\nRight-click → Run as Administrator")
    except Exception as e:
        import traceback
        done_cb(False, f"Error: {e}\n\n{traceback.format_exc()}")

# ── Remove + quick refresh ────────────────────────────────────────────────────
def full_refresh_quick(drive):
    try:
        subprocess.run(["ie4uinit.exe", "-show"],          capture_output=True)
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
    lines  = [f"=== Diagnostics: {drive} ===",
              f"Windows        : {WIN_VER}"]
    reg = reg_get_icon(drive)
    lines.append(f"Registry icon  : {reg or 'NONE'}")
    for fname in ["desktop.ini", "autorun.inf"]:
        p = os.path.join(drive, fname)
        lines.append(f"{fname:15}: {'EXISTS' if os.path.exists(p) else 'missing'}")
    icons = glob.glob(os.path.join(drive, "drive_icon*.ico"))
    lines.append(f"Icons on drive : {len(icons)}")
    for i in icons:
        lines.append(f"  {os.path.basename(i)}  ({os.path.getsize(i):,} bytes)")
    pd = os.path.join(ICO_STORE, f"drive_{letter}.ico")
    lines.append(f"ProgramData ico: {'EXISTS' if os.path.exists(pd) else 'missing'}")
    auto = os.path.join(drive, "autorun.inf")
    if os.path.exists(auto):
        try:
            with open(auto, "r", errors="ignore") as f:
                lines.append(f"autorun.inf:\n{f.read().strip()}")
        except:
            pass
    return "\n".join(lines)

# ── Colours ───────────────────────────────────────────────────────────────────
BG="#1e1e2e"; SURFACE="#313244"; OVERLAY="#45475a"; TEXT="#cdd6f4"
SUBTEXT="#a6adc8"; ACCENT="#89b4fa"; GREEN="#a6e3a1"; RED="#f38ba8"
YELLOW="#f9e2af"; ORANGE="#fab387"; PURPLE="#cba6f7"; TEAL="#94e2d5"

def flat_btn(parent, text, cmd, accent=False, color=None, **kw):
    bg = color or (ACCENT if accent else SURFACE)
    fg = "#1e1e2e" if (accent or color) else TEXT
    return tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                     activebackground="#b4befe" if accent else OVERLAY,
                     activeforeground="#1e1e2e" if accent else TEXT,
                     relief="flat", cursor="hand2", bd=0,
                     font=("Segoe UI",10,"bold" if accent else "normal"),
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
                 font=("Segoe UI",11,"bold")).pack(anchor="w", pady=(0,6))
        self.txt = tk.Text(self, width=64, height=18,
                           bg=SURFACE, fg=GREEN,
                           font=("Consolas",9), relief="flat",
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

# ── Crop Editor ───────────────────────────────────────────────────────────────
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
                 bg=BG,fg=SUBTEXT,font=("Segoe UI",8)).pack()
        self.cv=tk.Canvas(lf,width=EDITOR_SIZE,height=EDITOR_SIZE,
                          bg="#000",highlightthickness=2,
                          highlightbackground=ACCENT,cursor="fleur")
        self.cv.pack()
        self.cv.bind("<ButtonPress-1>",self._ds)
        self.cv.bind("<B1-Motion>",    self._dm)
        self.cv.bind("<MouseWheel>",   self._mw)
        rf=tk.Frame(top,bg=BG); rf.pack(side="left",anchor="n")
        tk.Label(rf,text="Preview (256px)",bg=BG,fg=SUBTEXT,
                 font=("Segoe UI",8)).pack()
        self.pv=tk.Canvas(rf,width=128,height=128,bg="#000",
                          highlightthickness=1,highlightbackground=OVERLAY)
        self.pv.pack(pady=(0,8))
        tk.Label(rf,text="Small sizes:",bg=BG,fg=SUBTEXT,
                 font=("Segoe UI",8)).pack(anchor="w")
        self.sm=tk.Canvas(rf,width=128,height=52,bg="#2a2a3e",
                          highlightthickness=0)
        self.sm.pack()
        tk.Label(rf,text="Background:",bg=BG,fg=SUBTEXT,
                 font=("Segoe UI",8)).pack(anchor="w",pady=(10,2))
        self._bg=tk.StringVar(value="transparent")
        for v,l in [("transparent","Transparent"),("white","White"),
                    ("black","Black"),("circle","Circle crop")]:
            tk.Radiobutton(rf,text=l,variable=self._bg,value=v,
                           bg=BG,fg=TEXT,selectcolor=SURFACE,
                           activebackground=BG,activeforeground=TEXT,
                           font=("Segoe UI",9),
                           command=self._redraw).pack(anchor="w")
        zm=tk.Frame(self,bg=BG); zm.pack(fill="x",pady=(0,12))
        tk.Label(zm,text="Zoom:",bg=BG,fg=TEXT,
                 font=("Segoe UI",10)).pack(side="left")
        self.zsl=tk.Scale(zm,from_=10,to=500,orient="horizontal",
                          bg=BG,fg=TEXT,troughcolor=SURFACE,
                          highlightthickness=0,showvalue=False,
                          command=self._zc)
        self.zsl.set(100)
        self.zsl.pack(side="left",fill="x",expand=True,padx=(8,8))
        self.zlb=tk.Label(zm,text="100%",bg=BG,fg=ACCENT,
                          font=("Segoe UI",10,"bold"),width=5)
        self.zlb.pack(side="left")
        br=tk.Frame(self,bg=BG); br.pack(fill="x")
        flat_btn(br,"Fit",self._fit).pack(side="left",padx=(0,8))
        flat_btn(br,"Cancel",    self.destroy).pack(side="right",padx=(8,0))
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
                     (0,0,0,255)       if bv=="black" else (0,0,0,0))
        sx0,sy0=max(0,x0),max(0,y0); sx1,sy1=min(sw,x1),min(sh,y1)
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
                                fill=SUBTEXT,font=("Segoe UI",7))
            x+=s+28

    def _confirm(self): self._cb(self._crop(256)); self.destroy()

# ── Main App ──────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Drive Icon Setter  v7.0  (Windows {WIN_VER})")
        self.configure(bg=BG,padx=28,pady=22)
        self.resizable(False,False)
        self._src=None; self._final=None; self._ico=None
        self._tmp=tempfile.mkdtemp(); self._drives=[]
        self.drive_var=tk.StringVar(); self.label_var=tk.StringVar()
        self.hide_var =tk.BooleanVar(value=True)
        self.eject_var=tk.BooleanVar(value=False)
        self._build_ui()
        if not is_admin(): self._admin_banner()

    def _build_ui(self):
        tk.Label(self,
                 text=f"  Drive Icon Setter  v7.0  (Windows {WIN_VER})",
                 bg=BG,fg=ACCENT,
                 font=("Segoe UI",14,"bold")).pack(anchor="w",pady=(0,4))

        info=tk.Frame(self,bg=SURFACE,padx=12,pady=8)
        info.pack(fill="x",pady=(0,6))
        tk.Label(info,
                 text="Kill-first pipeline | real-time update | Win10/11",
                 bg=SURFACE,fg=GREEN,
                 font=("Segoe UI",9,"bold")).pack(anchor="w")
        tk.Label(info,
                 text="C:\\ D:\\ E:\\ All drives | Registry + desktop.ini | Portable USB/HDD",
                 bg=SURFACE,fg=SUBTEXT,
                 font=("Segoe UI",9)).pack(anchor="w")

        # ── Step 1 ────────────────────────────────────────────────────────────
        self._sec("Step 1  —  Choose an image")
        f1=tk.Frame(self,bg=BG); f1.pack(fill="x",pady=(0,8))
        self.img_var=tk.StringVar()
        tk.Entry(f1,textvariable=self.img_var,width=38,bg=SURFACE,fg=TEXT,
                 insertbackground=TEXT,relief="flat",font=("Segoe UI",10),
                 state="readonly",readonlybackground=SURFACE
                 ).pack(side="left",padx=(0,8),ipady=5)
        flat_btn(f1,"Browse…",self._browse).pack(side="left")

        fp=tk.Frame(self,bg=BG); fp.pack(fill="x",pady=(4,0))
        self.thumb_cv=tk.Canvas(fp,width=96,height=96,bg=SURFACE,
                                highlightthickness=1,highlightbackground=OVERLAY)
        self.thumb_cv.pack(side="left")
        self.thumb_cv.create_text(48,48,text="preview",
                                  fill=SUBTEXT,font=("Segoe UI",9))
        fi=tk.Frame(fp,bg=BG,padx=14); fi.pack(side="left",fill="both")
        self.info_v=tk.StringVar(value="No image selected.")
        tk.Label(fi,textvariable=self.info_v,bg=BG,fg=SUBTEXT,
                 font=("Segoe UI",9),justify="left").pack(anchor="w")
        self.conv_l=tk.Label(fi,text="",bg=BG,fg=GREEN,
                             font=("Segoe UI",9,"bold"),justify="left")
        self.conv_l.pack(anchor="w",pady=(4,0))
        flat_btn(fi,"  Edit / Crop icon  ",
                 self._open_editor,color=PURPLE).pack(anchor="w",pady=(10,0))

        # ── Step 2 ────────────────────────────────────────────────────────────
        self._sec("Step 2  —  Select drive")
        f2=tk.Frame(self,bg=BG); f2.pack(fill="x",pady=(0,4))
        tk.Label(f2,text="Drive :",bg=BG,fg=TEXT,
                 font=("Segoe UI",10)).grid(row=0,column=0,sticky="w",pady=5)
        style=ttk.Style(self); style.theme_use("clam")
        style.configure("TCombobox",
                        fieldbackground=SURFACE,background=SURFACE,
                        foreground=TEXT,selectbackground=SURFACE,
                        selectforeground=TEXT)
        self.combo=ttk.Combobox(f2,textvariable=self.drive_var,
                                width=32,state="readonly")
        self.combo.grid(row=0,column=1,padx=(8,8),sticky="w")
        self.combo.bind("<<ComboboxSelected>>",self._on_drive)
        flat_btn(f2,"Refresh",self._refresh_drives).grid(row=0,column=2)
        tk.Label(f2,text="Label :",bg=BG,fg=TEXT,
                 font=("Segoe UI",10)).grid(row=1,column=0,sticky="w",pady=5)
        tk.Entry(f2,textvariable=self.label_var,width=34,bg=SURFACE,fg=TEXT,
                 insertbackground=TEXT,relief="flat",font=("Segoe UI",10)
                 ).grid(row=1,column=1,padx=(8,0),ipady=5,sticky="w")

        self.cur_ico_l=tk.Label(self,text="",bg=BG,fg=SUBTEXT,
                                font=("Segoe UI",8),anchor="w")
        self.cur_ico_l.pack(fill="x",pady=(0,2))
        self.warn_l=tk.Label(self,text="",bg=BG,fg=ORANGE,
                             font=("Segoe UI",9,"bold"),
                             anchor="w",justify="left")
        self.warn_l.pack(fill="x",pady=(0,4))

        # ── Step 3 ────────────────────────────────────────────────────────────
        self._sec("Step 3  —  Options & Apply")
        tk.Checkbutton(
            self,text="Hide drive_icon.ico & autorun.inf on drive",
            variable=self.hide_var,bg=BG,fg=TEXT,selectcolor=SURFACE,
            activebackground=BG,activeforeground=TEXT,
            font=("Segoe UI",10)).pack(anchor="w")
        self.eject_chk=tk.Checkbutton(
            self,text="  Auto Eject after Apply  (USB / External HDD)",
            variable=self.eject_var,bg=BG,fg=GREEN,selectcolor=SURFACE,
            activebackground=BG,activeforeground=GREEN,
            font=("Segoe UI",10,"bold"),state="disabled")
        self.eject_chk.pack(anchor="w",pady=(3,0))

        self.progress=ttk.Progressbar(self,mode="indeterminate",length=420)
        tk.Frame(self,bg=BG,height=10).pack()

        # ── ปุ่มหลัก ──────────────────────────────────────────────────────────
        self.apply_btn=flat_btn(
            self,"  ✅ Apply Icon (local + real-time update)  ",
            self._apply, accent=True)
        self.apply_btn.pack(fill="x")



        self.status_v=tk.StringVar(value="Ready.")
        tk.Label(self,textvariable=self.status_v,bg="#181825",fg=SUBTEXT,
                 anchor="w",font=("Consolas",9),padx=10,pady=5
                 ).pack(fill="x",pady=(8,0))

        bf=tk.Frame(self,bg=BG); bf.pack(fill="x",pady=(6,0))
        flat_btn(bf,"  Remove Icon  ",
                 self._remove_icon,color="#585b70"
                 ).pack(side="left",fill="x",expand=True,padx=(0,3))
        flat_btn(bf,"  Diagnostics  ",
                 self._diagnostics,color=ORANGE
                 ).pack(side="left",fill="x",expand=True,padx=(3,0))

        self._refresh_drives()

    def _admin_banner(self):
        b=tk.Frame(self,bg=YELLOW,padx=10,pady=8)
        b.pack(fill="x",before=self.winfo_children()[0])
        tk.Label(b,
                 text="  Not running as Administrator — Registry writes will fail!",
                 bg=YELLOW,fg="#1e1e2e",
                 font=("Segoe UI",9,"bold")).pack(side="left")
        tk.Button(b,text="Restart as Admin",command=relaunch_as_admin,
                  bg="#fe640b",fg="white",relief="flat",cursor="hand2",
                  padx=8,pady=3,
                  font=("Segoe UI",9,"bold")).pack(side="right")

    def _sec(self,title):
        tk.Label(self,text=title,bg=BG,fg=ACCENT,
                 font=("Segoe UI",10,"bold")).pack(anchor="w",pady=(14,4))
        tk.Frame(self,bg=OVERLAY,height=1).pack(fill="x",pady=(0,8))

    def _refresh_drives(self):
        self._drives=get_drives()
        choices=[]
        for drive,dtype in self._drives:
            lbl  =get_drive_label(drive)
            tname=DRIVE_TYPE_LABEL.get(dtype,"Unknown")
            sys_t=" [SYSTEM]" if is_system_drive(drive) else ""
            display=(f"{drive.rstrip(chr(92))}  {lbl}  ({tname}){sys_t}"
                     if lbl else
                     f"{drive.rstrip(chr(92))}  ({tname}){sys_t}")
            choices.append(display)
        self.combo["values"]=choices
        if choices: self.combo.current(0)
        self._on_drive()

    def _get_drive(self):
        idx=self.combo.current()
        if idx<0 or idx>=len(self._drives): return None,None
        return self._drives[idx]

    def _on_drive(self,event=None):
        if not hasattr(self,"warn_l"): return
        drive,dtype=self._get_drive()
        if not drive: return
        is_usb=(dtype==DRIVE_REMOVABLE)
        is_sys=is_system_drive(drive)
        cur=reg_get_icon(drive)
        self.cur_ico_l.config(
            text=f"Current icon: {cur}" if cur
            else "No custom icon set for this drive.")
        if is_sys:
            self.warn_l.config(
                text="  System Drive — Restart PC to fully apply icon.",
                fg=ORANGE)
            if not hasattr(self,"so_btn"):
                self.so_btn=tk.Button(
                    self,text="Restart PC Now",
                    command=restart_computer,
                    bg=ORANGE,fg="#1e1e2e",
                    font=("Segoe UI",8,"bold"),
                    relief="flat",padx=6)
                self.so_btn.pack(pady=(0,4),after=self.warn_l)
        else:
            self.warn_l.config(text="")
            if hasattr(self,"so_btn"):
                self.so_btn.destroy(); del self.so_btn
        # Enable eject for USB and external HDD (non-system drives)
        can_eject = not is_sys
        self.eject_chk.config(state="normal" if can_eject else "disabled")
        if not can_eject: self.eject_var.set(False)

    def _browse(self):
        path=filedialog.askopenfilename(
            title="Select image",
            filetypes=[("Image files",
                        "*.png *.jpg *.jpeg *.bmp *.gif "
                        "*.webp *.tiff *.tif *.ico"),
                       ("All files","*.*")])
        if not path: return
        try:
            img=Image.open(path); self._src=img.convert("RGBA")
            self.img_var.set(path)
            ext=os.path.splitext(path)[1].upper()
            self.info_v.set(
                f"File : {os.path.basename(path)}\n"
                f"Size : {img.width} x {img.height} px  |  {ext}")
            self._ico=None; self._final=None
            self.conv_l.config(text="Click 'Edit / Crop icon' to adjust.",
                               fg=YELLOW)
            self._thumb_update(self._src)
            self._open_editor()
        except Exception as e:
            messagebox.showerror("Error",f"Cannot open image:\n{e}")

    def _thumb_update(self,pil_img):
        t=pil_img.copy().convert("RGBA")
        t.thumbnail((96,96),Image.LANCZOS)
        chk=Image.new("RGBA",(96,96)); d=ImageDraw.Draw(chk)
        for y in range(0,96,8):
            for x in range(0,96,8):
                c=((200,200,200,255) if (x//8+y//8)%2==0
                   else (160,160,160,255))
                d.rectangle([x,y,x+7,y+7],fill=c)
        ox=(96-t.width)//2; oy=(96-t.height)//2
        chk.paste(t,(ox,oy),t)
        self._tk_thumb=ImageTk.PhotoImage(chk)
        self.thumb_cv.delete("all")
        self.thumb_cv.create_image(0,0,anchor="nw",image=self._tk_thumb)

    def _open_editor(self):
        if self._src is None:
            messagebox.showwarning("No image","Please select an image first.")
            return
        CropEditor(self,self._src,self._edit_done)

    def _edit_done(self,result):
        self._final=result; self._thumb_update(result)
        try:
            out=os.path.join(self._tmp,"drive_icon.ico")
            pil_to_ico(result,out); self._ico=out
            self.conv_l.config(text="Icon ready! Click Apply.",fg=GREEN)
            self.status_v.set("Icon ready.")
        except Exception as e:
            self.conv_l.config(text=f"Convert failed: {e}",fg=RED)

    def _check_ready(self):
        if not self._ico or not os.path.isfile(self._ico):
            messagebox.showwarning("Not Ready",
                "Please select and edit an image first.")
            return False
        drive,_=self._get_drive()
        if not drive:
            messagebox.showwarning("No Drive","Please select a drive.")
            return False
        return True

    def _run_pipeline(self, target_fn, args):
        """Show progress bar + StepLog then run pipeline in thread."""
        self.progress.pack(fill="x",pady=(0,8),before=self.apply_btn)
        self.progress.start(10); self.update()
        log=StepLog(self)

        def _status(msg):
            self.after(0,lambda m=msg:(self.status_v.set(m),log.log(m)))
        def _done(ok, msg, show_restart=False):
            self.after(0,lambda o=ok,m=msg,r=show_restart:self._finish(o,m,log,r))

        threading.Thread(
            target=target_fn,
            args=args + (_status, _done),
            daemon=True).start()

    def _apply(self):
        if not self._check_ready(): return
        drive,dtype=self._get_drive()
        if is_system_drive(drive):
            if not messagebox.askyesno("System Drive",
                f"Apply icon to SYSTEM drive {drive}?\n\nExplorer will restart briefly.\nRestart PC for full effect.\n\nContinue?",
                icon="warning"): return
        elif self.eject_var.get():
            if not messagebox.askyesno("Confirm Eject",
                f"Apply icon to {drive} then eject?\nClose all files on {drive} first."): return

        self._run_pipeline(apply_icon_pipeline,
                           (drive, self._ico, self.label_var.get(),
                            self.hide_var.get(), self.eject_var.get()))

    def _finish(self, success, msg, log, show_restart=False):
        self.progress.stop(); self.progress.pack_forget()
        log.done()
        if success:
            messagebox.showinfo("Done!", msg)
            self._refresh_drives()
            if show_restart:
                restart_computer_countdown(self)
        else:
            messagebox.showerror("Error", msg)

    def _remove_icon(self):
        drive,_=self._get_drive()
        if not drive: return
        if not messagebox.askyesno("Remove Icon",
            f"Remove custom icon from {drive}?\nWill restore default Windows icon."): return
        try:
            reg_remove_icon(drive)
            for fname in ["drive_icon.ico","desktop.ini","autorun.inf"]:
                p=os.path.join(drive,fname)
                if os.path.exists(p):
                    clear_attribs(p)
                    try: os.remove(p)
                    except: pass
            # ลบโฟลเดอร์ .icons ด้วย
            icons_dir_r = os.path.join(drive, ICO_FOLDER)
            if os.path.exists(icons_dir_r):
                try:
                    clear_attribs(icons_dir_r)
                    for f in glob.glob(os.path.join(icons_dir_r, "*")):
                        clear_attribs(f)
                        try: os.remove(f)
                        except: pass
                    os.rmdir(icons_dir_r)
                except: pass
            self.status_v.set("Icon removed. Refreshing...")
            self.update()
            def _run():
                full_refresh_quick(drive)
                self.after(0,lambda:(
                    self.status_v.set("Default icon restored."),
                    self._on_drive()))
            threading.Thread(target=_run,daemon=True).start()
        except Exception as e:
            messagebox.showerror("Error",str(e))

    def _diagnostics(self):
        drive,_=self._get_drive()
        if not drive: return
        messagebox.showinfo("Diagnostics",drive_diagnostics(drive))

    def destroy(self):
        try: shutil.rmtree(self._tmp,ignore_errors=True)
        except: pass
        super().destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()
