"""
Drive Icon Setter
Uses Windows Registry for ALL drives — instant refresh, no eject needed.
HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\DriveIcons
Auto-installs Pillow if missing.
"""

import os, sys, shutil, subprocess, tempfile, time, glob, ctypes, winreg
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading

# ── Auto-install Pillow ───────────────────────────────────────────────────────
def _install_pillow():
    print("Installing Pillow...")
    try:
        # Try both direct pip and python -m pip
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
        from importlib import reload
        reload(site)
        from PIL import Image, ImageTk, ImageDraw
    except ModuleNotFoundError:
        print(f"Run: {sys.executable} -m pip install Pillow")
        input("Press Enter to exit..."); sys.exit(1)

if sys.platform != "win32":
    print("Windows only."); sys.exit(1)

# ── Constants ─────────────────────────────────────────────────────────────────
DRIVE_REMOVABLE = 2; DRIVE_FIXED = 3; DRIVE_REMOTE = 4
DRIVE_CDROM = 5; DRIVE_RAMDISK = 6
DRIVE_TYPE_LABEL = {
    DRIVE_REMOVABLE:"USB/Removable", DRIVE_FIXED:"Local Disk",
    DRIVE_REMOTE:"Network", DRIVE_CDROM:"CD/DVD", DRIVE_RAMDISK:"RAM Disk"
}
SIZES = [256, 128, 64, 48, 32, 16]

# Registry path for drive icons
REG_BASE = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\DriveIcons"
# Permanent folder to store .ico files (survives reconnect)
ICO_STORE = os.path.expandvars(r"%ProgramData%\DriveIcons")

# ── ico converter ─────────────────────────────────────────────────────────────
def pil_to_ico(img, out_path):
    img = img.convert("RGBA")
    icons = [img.resize((s,s), Image.LANCZOS) for s in SIZES]
    icons[0].save(out_path, format="ICO",
                  sizes=[(s,s) for s in SIZES], append_images=icons[1:])

# ── Drive helpers ─────────────────────────────────────────────────────────────
def get_drives():
    drives = []
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        if bitmask & 1:
            d = f"{letter}:\\"
            dtype = ctypes.windll.kernel32.GetDriveTypeW(d)
            # Filter out inaccessible drives (like empty card slots/D:)
            try:
                # This call will fail if the drive is not accessible
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
    except: return ""

def is_system_drive(drive):
    return drive.rstrip("\\").upper() == os.environ.get("SystemDrive","C:").upper()

def is_admin():
    try: return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except: return False

def relaunch_as_admin():
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    sys.exit()

# ── Registry icon (works for ALL drives including USB) ────────────────────────
def reg_set_icon(drive, ico_path, label=""):
    """Write icon to HKLM DriveIcons. Works instantly on all drive types."""
    letter = drive.rstrip("\\").rstrip(":")[0].upper()
    # DefaultIcon
    with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE,
                            f"{REG_BASE}\\{letter}\\DefaultIcon",
                            0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, ico_path)
    # DefaultLabel (optional)
    if label.strip():
        with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE,
                                f"{REG_BASE}\\{letter}\\DefaultLabel",
                                0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, label.strip())

def reg_get_icon(drive):
    """Return current registry icon path or None."""
    letter = drive.rstrip("\\").rstrip(":")[0].upper()
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            f"{REG_BASE}\\{letter}\\DefaultIcon") as k:
            return winreg.QueryValueEx(k, "")[0]
    except: return None

def reg_remove_icon(drive):
    """Remove registry icon entry for a drive."""
    letter = drive.rstrip("\\").rstrip(":")[0].upper()
    for sub in ["DefaultIcon", "DefaultLabel", ""]:
        try:
            path = f"{REG_BASE}\\{letter}" + (f"\\{sub}" if sub else "")
            winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, path)
        except: pass

# ── Explorer refresh ──────────────────────────────────────────────────────────
SHCNE_UPDATEITEM=0x2000; SHCNE_RENAMEFOLDER=0x20000
SHCNE_ASSOCCHANGED=0x8000000; SHCNE_ALLEVENTS=0x7FFFFFFF
SHCNF_PATHW=0x0005; SHCNF_FLUSH=0x1000; SHCNF_FLUSHNOWAIT=0x3000

def clear_icon_cache():
    # Attempt to use Windows built-in icon utility for better refresh
    try:
        subprocess.run(["ie4uinit.exe", "-show"], shell=True)
        subprocess.run(["ie4uinit.exe", "-ClearIconCache"], shell=True)
    except: pass
    
    # Manual deletion as fallback
    for pat in [r"%LOCALAPPDATA%\Microsoft\Windows\Explorer\iconcache*.db",
                r"%LOCALAPPDATA%\Microsoft\Windows\Explorer\thumbcache*.db"]:
        for f in glob.glob(os.path.expandvars(pat)):
            try: os.remove(f)
            except: pass

def restart_explorer():
    try:
        subprocess.run(["taskkill","/F","/IM","explorer.exe"],
                       shell=True, capture_output=True)
        time.sleep(1.5)
        subprocess.Popen("explorer.exe", shell=True)
        time.sleep(1.0)
    except: pass

def notify_shell(drive):
    """Send SHChangeNotify so Explorer updates icon immediately."""
    s32 = ctypes.windll.shell32
    p   = ctypes.create_unicode_buffer(drive)
    # Broad notifications for better success
    s32.SHChangeNotify(SHCNE_UPDATEITEM,   SHCNF_PATHW|SHCNF_FLUSH, p, None)
    s32.SHChangeNotify(SHCNE_RENAMEFOLDER, SHCNF_PATHW|SHCNF_FLUSH, p, None)
    s32.SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_FLUSHNOWAIT, None, None)
    s32.SHChangeNotify(SHCNE_ALLEVENTS,    SHCNF_FLUSHNOWAIT, None, None)

def full_refresh(drive):
    """
    Full icon refresh sequence:
    1. ie4uinit -show (Standard Windows refresh)
    2. SHChangeNotify — instant signal to Explorer
    3. Clear icon cache — force rebuild of all cached icons
    4. Restart Explorer — guarantees icon reloads
    """
    try: subprocess.run(["ie4uinit.exe", "-show"], shell=True) # First attempt
    except: pass
    notify_shell(drive)
    clear_icon_cache()
    restart_explorer()
    notify_shell(drive)
    try: subprocess.run(["ie4uinit.exe", "-ClearIconCache"], shell=True) # Final kick
    except: pass

# ── Safe eject ────────────────────────────────────────────────────────────────
IOCTL_EJECT=0x2D4808; IOCTL_REMOVAL=0x2D4804
FSCTL_LOCK=0x90018; FSCTL_DISMOUNT=0x90020
GR=0x80000000; GW=0x40000000; FSR=1; FSW=2; OE=3
FNB=0x20000000; IHV=ctypes.c_void_p(-1).value

def safe_eject(drive):
    letter = drive.rstrip("\\").rstrip(":")[0].upper()
    k32 = ctypes.windll.kernel32
    h   = k32.CreateFileW(f"\\\\.\\{letter}:", GR|GW, FSR|FSW, None, OE, FNB, None)
    if h == IHV:
        # Fallback: PowerShell
        r = subprocess.run(
            ["powershell","-NoProfile","-Command",
             f"(New-Object -comObject Shell.Application).Namespace(17)"
             f".ParseName('{letter}:').InvokeVerb('Eject')"],
            capture_output=True, timeout=15)
        return r.returncode == 0, "Ejected via PowerShell" if r.returncode==0 \
               else r.stderr.decode(errors="ignore")
    br = ctypes.c_ulong(0)
    try:
        k32.DeviceIoControl(h, FSCTL_LOCK,    None,0,None,0,ctypes.byref(br),None)
        k32.DeviceIoControl(h, FSCTL_DISMOUNT, None,0,None,0,ctypes.byref(br),None)
        class PMR(ctypes.Structure): _fields_=[("p",ctypes.c_ubyte)]
        pmr = PMR(0)
        k32.DeviceIoControl(h, IOCTL_REMOVAL, ctypes.byref(pmr),1,None,0,ctypes.byref(br),None)
        ok = k32.DeviceIoControl(h, IOCTL_EJECT, None,0,None,0,ctypes.byref(br),None)
        return (bool(ok), "Ejected!" if ok else f"Eject failed ({ctypes.GetLastError()})")
    finally:
        k32.CloseHandle(h)

# ── Main apply pipeline ───────────────────────────────────────────────────────
def apply_icon_pipeline(drive, ico_src, label, hide_files, do_eject, status_cb, done_cb):
    dtype    = ctypes.windll.kernel32.GetDriveTypeW(drive)
    is_usb   = dtype == DRIVE_REMOVABLE
    is_sys   = is_system_drive(drive)
    letter   = drive.rstrip("\\").rstrip(":")[0].upper()

    try:
        # ── Step 1: Copy .ico to permanent location ───────────────────────────
        # We ALWAYS store the .ico in ProgramData\DriveIcons so the registry
        # path stays valid even after the drive is reconnected / re-lettered.
        status_cb("Preparing icon storage folder…")
        os.makedirs(ICO_STORE, exist_ok=True)
        ico_dest = os.path.join(ICO_STORE, f"drive_{letter}.ico")
        if os.path.exists(ico_dest):
            try:
                subprocess.run(["attrib","-R","-H","-S",ico_dest], shell=True)
            except: pass
        shutil.copy2(ico_src, ico_dest)

        # ── Step 2: Write to Registry ─────────────────────────────────────────
        # Registry works for ALL drives — USB, fixed, system.
        # autorun.inf is DISABLED by Windows 7+ for USB drives.
        status_cb("Writing icon to Windows Registry…")
        reg_set_icon(drive, ico_dest, label)

        # ── Step 3: Also write autorun.inf (extra compatibility) ──────────────
        if not is_sys:
            status_cb(f"Writing autorun.inf to {drive}…")
            auto_path = os.path.join(drive, "autorun.inf")
            # Use unique name to bypass file locks
            ts = int(time.time())
            ico_local_name = f"drive_icon_{ts}.ico"
            ico_local = os.path.join(drive, ico_local_name)
            
            # Clean up old icons first
            for old_ico in glob.glob(os.path.join(drive, "drive_icon_*.ico")) + [os.path.join(drive, "drive_icon.ico")]:
                try:
                    subprocess.run(["attrib","-R","-H","-S",old_ico], shell=True, capture_output=True)
                    os.remove(old_ico)
                except: pass
            
            # Clear attributes of autorun.inf
            if os.path.exists(auto_path):
                try:
                    subprocess.run(["attrib","-R","-H","-S",auto_path], shell=True, capture_output=True)
                except: pass
            
            try:
                # Copy icon to drive root
                shutil.copy2(ico_src, ico_local)
                
                lines = ["[autorun]", f"icon={ico_local_name}"]
                if label.strip(): lines.append(f"label={label.strip()}")
                
                with open(auto_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")
                
                if hide_files:
                    subprocess.run(["attrib","+H","+S",auto_path], shell=True)
                    subprocess.run(["attrib","+H","+S",ico_local], shell=True)
            except Exception as ae:
                raise Exception(f"Failed to write icon to drive {letter}:.\nIs the drive write-protected?\nError: {ae}")

        # ── Step 4: Refresh Explorer ──────────────────────────────────────────
        status_cb("Force clearing icon cache & restarting Explorer…")
        full_refresh(drive)
        
        # ── Optional: Extra Registry kick for Explorer ───────────────────────
        try:
             subprocess.run(["cmd", "/c", "taskkill /f /im explorer.exe & start explorer.exe"], shell=True, capture_output=True)
        except: pass

        # ── Step 5: Eject (Optional) ─────────────────────────────────────────
        eject_ok = False
        if do_eject:
            status_cb("Safely ejecting drive…")
            time.sleep(0.5)
            eject_ok, eject_msg = safe_eject(drive)

        # ── Done ──────────────────────────────────────────────────────────────
        msg_time = time.strftime("%H:%M:%S")
        method = "Registry" + (" + autorun.inf" if is_usb else "")
        if eject_ok:
            msg = (f"✅  Icon applied to {drive}  [{method}]\n"
                   f"✅  Drive ejected at {msg_time}!\n\n"
                   f"New icon will show when you reconnect.")
        else:
            msg = (f"✅  Icon applied to {drive}  [{method}]\n\n"
                   f"Last Update: {msg_time}\n"
                   f"Icon cache cleared & Explorer restarted.\n"
                   f"Icon should now be visible in File Explorer!\n\n"
                   f"If still not showing: sign out and back in once.")
        status_cb(f"Done at {msg_time}! {drive} updated.")
        done_cb(True, msg)

    except PermissionError:
        status_cb("Permission denied.")
        done_cb(False,
                "Permission denied.\n\n"
                "Please right-click the script and choose\n"
                "'Run as administrator'.")
    except Exception as e:
        status_cb(f"Error: {e}")
        done_cb(False, str(e))

# ── Colours ───────────────────────────────────────────────────────────────────
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
                     font=("Segoe UI",10,"bold" if accent else "normal"),
                     padx=10, pady=6, **kw)

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
        tk.Label(rf,text="Preview (256px)",bg=BG,fg=SUBTEXT,font=("Segoe UI",8)).pack()
        self.pv=tk.Canvas(rf,width=128,height=128,bg="#000",
                          highlightthickness=1,highlightbackground=OVERLAY)
        self.pv.pack(pady=(0,8))
        tk.Label(rf,text="Small sizes:",bg=BG,fg=SUBTEXT,font=("Segoe UI",8)).pack(anchor="w")
        self.sm=tk.Canvas(rf,width=128,height=52,bg="#2a2a3e",highlightthickness=0)
        self.sm.pack()
        tk.Label(rf,text="Background:",bg=BG,fg=SUBTEXT,
                 font=("Segoe UI",8)).pack(anchor="w",pady=(10,2))
        self._bg=tk.StringVar(value="transparent")
        for v,l in [("transparent","Transparent"),("white","White"),
                    ("black","Black"),("circle","Circle crop")]:
            tk.Radiobutton(rf,text=l,variable=self._bg,value=v,
                           bg=BG,fg=TEXT,selectcolor=SURFACE,activebackground=BG,
                           activeforeground=TEXT,font=("Segoe UI",9),
                           command=self._redraw).pack(anchor="w")
        zm=tk.Frame(self,bg=BG); zm.pack(fill="x",pady=(0,12))
        tk.Label(zm,text="Zoom:",bg=BG,fg=TEXT,font=("Segoe UI",10)).pack(side="left")
        self.zsl=tk.Scale(zm,from_=10,to=500,orient="horizontal",
                          bg=BG,fg=TEXT,troughcolor=SURFACE,
                          highlightthickness=0,showvalue=False,command=self._zc)
        self.zsl.set(100); self.zsl.pack(side="left",fill="x",expand=True,padx=(8,8))
        self.zlb=tk.Label(zm,text="100%",bg=BG,fg=ACCENT,
                          font=("Segoe UI",10,"bold"),width=5)
        self.zlb.pack(side="left")
        br=tk.Frame(self,bg=BG); br.pack(fill="x")
        flat_btn(br,"Fit",self._fit).pack(side="left",padx=(0,8))
        flat_btn(br,"Cancel",self.destroy).pack(side="right",padx=(8,0))
        flat_btn(br,"Use this icon",self._confirm,accent=True).pack(side="right")

    def _center(self):
        sw,sh=self._src.size
        self._zoom=min(EDITOR_SIZE/sw,EDITOR_SIZE/sh)
        self._off=[(sw-EDITOR_SIZE/self._zoom)/2,(sh-EDITOR_SIZE/self._zoom)/2]
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
        self._off=[ox+(sx-e.x)/self._zoom,oy+(sy-e.y)/self._zoom]
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
        sx0,sy0=max(0,x0),max(0,y0); sx1,sy1=min(sw,x1),min(sh,y1)
        if sx1>sx0 and sy1>sy0:
            rg=self._src.crop((sx0,sy0,sx1,sy1))
            px=int((sx0-x0)*self._zoom); py=int((sy0-y0)*self._zoom)
            pw=max(1,int((sx1-sx0)*self._zoom)); ph=max(1,int((sy1-sy0)*self._zoom))
            rs=rg.resize((pw,ph),Image.LANCZOS)
            ci.paste(rs,(px,py),rs)
        if bv=="circle":
            mk=Image.new("L",(EDITOR_SIZE,EDITOR_SIZE),0)
            ImageDraw.Draw(mk).ellipse((0,0,EDITOR_SIZE-1,EDITOR_SIZE-1),fill=255)
            ot=Image.new("RGBA",(EDITOR_SIZE,EDITOR_SIZE),(0,0,0,0))
            ot.paste(ci,mask=mk); ci=ot
        return ci.resize((size,size),Image.LANCZOS)

    @staticmethod
    def _chk(size,b=8):
        img=Image.new("RGBA",(size,size)); d=ImageDraw.Draw(img)
        for y in range(0,size,b):
            for x in range(0,size,b):
                c=(200,200,200,255) if (x//b+y//b)%2==0 else (160,160,160,255)
                d.rectangle([x,y,x+b-1,y+b-1],fill=c)
        return img

    def _redraw(self):
        img=self._crop(EDITOR_SIZE)
        self._te=ImageTk.PhotoImage(Image.alpha_composite(self._chk(EDITOR_SIZE),img))
        self.cv.delete("all"); self.cv.create_image(0,0,anchor="nw",image=self._te)
        pv=img.resize((128,128),Image.LANCZOS)
        self._tp=ImageTk.PhotoImage(Image.alpha_composite(self._chk(128),pv))
        self.pv.delete("all"); self.pv.create_image(0,0,anchor="nw",image=self._tp)
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

# ── Diagnostic Tool ───────────────────────────────────────────────────────────
def drive_diagnostics(drive):
    letter = drive.rstrip("\\").rstrip(":")[0].upper()
    report = [f"--- Diagnostics for {drive} ---"]
    
    # Registry check
    reg = reg_get_icon(drive)
    report.append(f"Registry Icon: {reg if reg else 'NONE'}")
    
    # Files check
    auto_path = os.path.join(drive, "autorun.inf")
    report.append(f"autorun.inf exists: {os.path.exists(auto_path)}")
    if os.path.exists(auto_path):
        try:
            with open(auto_path, "r", errors="ignore") as f:
                report.append(f"autorun.inf content:\n{f.read().strip()}")
        except Exception as e:
            report.append(f"Could not read autorun.inf: {e}")
            
    # List icons on drive root
    icons = glob.glob(os.path.join(drive, "drive_icon*.ico"))
    report.append(f"Icon files on drive: {len(icons)}")
    for i in icons:
        report.append(f" - {os.path.basename(i)} ({os.path.getsize(i)} bytes)")
        
    return "\n".join(report)

def restart_computer():
    if messagebox.askyesno("Restart", "Restart your computer now to apply the system drive icon?"):
        subprocess.run(["shutdown", "-r", "-t", "0"])

# ── Main App ──────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Drive Icon Setter")
        self.configure(bg=BG,padx=28,pady=22)
        self.resizable(False,False)
        self._src=None; self._final=None; self._ico=None
        self._tmp=tempfile.mkdtemp(); self._thumb=None; self._drives=[]
        self.drive_var=tk.StringVar(); self.label_var=tk.StringVar()
        self.hide_var=tk.BooleanVar(value=True)
        self.eject_var=tk.BooleanVar(value=False)
        self._build_ui()
        if not is_admin(): self._admin_banner()

    def _build_ui(self):
        tk.Label(self,text="  Drive Icon Setter",bg=BG,fg=ACCENT,
                 font=("Segoe UI",15,"bold")).pack(anchor="w",pady=(0,4))

        # ── Method info banner ────────────────────────────────────────────────
        info = tk.Frame(self,bg="#313244",padx=12,pady=8)
        info.pack(fill="x",pady=(0,6))
        tk.Label(info,
                 text="Uses Windows Registry for instant icon update on ALL drives.",
                 bg="#313244",fg=GREEN,font=("Segoe UI",9,"bold")).pack(anchor="w")
        tk.Label(info,
                 text="No eject/reconnect needed. Works on C:\\, D:\\, USB, and more.",
                 bg="#313244",fg=SUBTEXT,font=("Segoe UI",9)).pack(anchor="w")

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
        self.cv=tk.Canvas(fp,width=96,height=96,bg=SURFACE,
                          highlightthickness=1,highlightbackground=OVERLAY)
        self.cv.pack(side="left")
        self.cv.create_text(48,48,text="preview",fill=SUBTEXT,font=("Segoe UI",9))
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
        self._sec("Step 2  —  Select drive & label")
        f2=tk.Frame(self,bg=BG); f2.pack(fill="x",pady=(0,4))
        tk.Label(f2,text="Drive :",bg=BG,fg=TEXT,
                 font=("Segoe UI",10)).grid(row=0,column=0,sticky="w",pady=5)
        style=ttk.Style(self); style.theme_use("clam")
        style.configure("TCombobox",fieldbackground=SURFACE,background=SURFACE,
                        foreground=TEXT,selectbackground=SURFACE,selectforeground=TEXT)
        self.combo=ttk.Combobox(f2,textvariable=self.drive_var,width=32,state="readonly")
        self.combo.grid(row=0,column=1,padx=(8,8),sticky="w")
        self.combo.bind("<<ComboboxSelected>>",self._on_drive)
        flat_btn(f2,"Refresh",self._refresh_drives).grid(row=0,column=2)
        tk.Label(f2,text="Label :",bg=BG,fg=TEXT,
                 font=("Segoe UI",10)).grid(row=1,column=0,sticky="w",pady=5)
        tk.Entry(f2,textvariable=self.label_var,width=34,bg=SURFACE,fg=TEXT,
                 insertbackground=TEXT,relief="flat",font=("Segoe UI",10)
                 ).grid(row=1,column=1,padx=(8,0),ipady=5,sticky="w")

        # Current icon info
        self.cur_ico_l=tk.Label(self,text="",bg=BG,fg=SUBTEXT,
                                font=("Segoe UI",8),anchor="w")
        self.cur_ico_l.pack(fill="x",pady=(0,2))

        # Drive warning
        self.warn_l=tk.Label(self,text="",bg=BG,fg=ORANGE,
                             font=("Segoe UI",9,"bold"),anchor="w",justify="left")
        self.warn_l.pack(fill="x",pady=(0,4))

        # ── Step 3 ────────────────────────────────────────────────────────────
        self._sec("Step 3  —  Options & Apply")

        tk.Checkbutton(self,
                       text="Hide autorun.inf & icon file on the drive (USB only)",
                       variable=self.hide_var,bg=BG,fg=TEXT,selectcolor=SURFACE,
                       activebackground=BG,activeforeground=TEXT,
                       font=("Segoe UI",10)).pack(anchor="w")

        self.eject_chk=tk.Checkbutton(
            self,text="⏏  Auto safe-eject after applying  (Eject Drive)",
            variable=self.eject_var,bg=BG,fg=GREEN,selectcolor=SURFACE,
            activebackground=BG,activeforeground=GREEN,
            font=("Segoe UI",10,"bold"))
        self.eject_chk.pack(anchor="w",pady=(3,14))

        self.progress=ttk.Progressbar(self,mode="indeterminate",length=400)
        self.apply_btn=flat_btn(self,"  Apply Icon to Drive  ",
                                self._apply,accent=True)
        self.apply_btn.pack(fill="x")

        self.status_v=tk.StringVar(value="Ready.")
        tk.Label(self,textvariable=self.status_v,bg="#181825",fg=SUBTEXT,
                 anchor="w",font=("Segoe UI",9),padx=10,pady=5
                 ).pack(fill="x",pady=(14,0))

        # Also add "Remove icon" button
        bf = tk.Frame(self, bg=BG)
        bf.pack(fill="x", pady=(6,0))
        flat_btn(bf,"  Remove Icon  ",
                 self._remove_icon,color="#585b70").pack(side="left", fill="x", expand=True, padx=(0,4))
        flat_btn(bf,"  Diagnostics  ",
                 self._diagnostics,color=ORANGE).pack(side="left", fill="x", expand=True, padx=(4,0))

        # Now safe to populate drives
        self._refresh_drives()

    def _admin_banner(self):
        b=tk.Frame(self,bg=YELLOW,padx=10,pady=8)
        b.pack(fill="x",before=self.winfo_children()[0])
        tk.Label(b,text="  Not running as Administrator — Registry writes will fail!",
                 bg=YELLOW,fg="#1e1e2e",font=("Segoe UI",9,"bold")).pack(side="left")
        tk.Button(b,text="Restart as Admin",command=relaunch_as_admin,
                  bg="#fe640b",fg="white",relief="flat",cursor="hand2",
                  padx=8,pady=3,font=("Segoe UI",9,"bold")).pack(side="right")

    def _sec(self,title):
        tk.Label(self,text=title,bg=BG,fg=ACCENT,
                 font=("Segoe UI",10,"bold")).pack(anchor="w",pady=(14,4))
        tk.Frame(self,bg=OVERLAY,height=1).pack(fill="x",pady=(0,8))

    def _refresh_drives(self):
        self._drives=get_drives()
        choices=[]
        for drive,dtype in self._drives:
            lbl=get_drive_label(drive)
            tname=DRIVE_TYPE_LABEL.get(dtype,"Unknown")
            sys_tag=" [SYSTEM]" if is_system_drive(drive) else ""
            display=(f"{drive.rstrip(chr(92))}  {lbl}  ({tname}){sys_tag}"
                     if lbl else f"{drive.rstrip(chr(92))}  ({tname}){sys_tag}")
            choices.append(display)
        self.combo["values"]=choices
        if choices: self.combo.current(0)
        self._on_drive()

    def _get_drive(self):
        idx=self.combo.current()
        if idx<0 or idx>=len(self._drives): return None,None
        return self._drives[idx]

    def _on_drive(self, event=None):
        if not hasattr(self,"warn_l"): return
        drive,dtype=self._get_drive()
        if not drive: return
        is_usb=(dtype==DRIVE_REMOVABLE)
        is_sys=is_system_drive(drive)

        # Show current registry icon
        cur=reg_get_icon(drive)
        self.cur_ico_l.config(
            text=f"Current registry icon: {cur}" if cur else
                 "No registry icon set for this drive.")

        is_usb = (dtype == DRIVE_REMOVABLE)
        is_sys = is_system_drive(drive)
        
        if is_sys:
            self.eject_chk.config(state="disabled")
            self.eject_var.set(False)
            self.warn_l.config(
                text=f"⚠️  System Drive ({drive}) — Eject disabled.\n    If icon doesn't update, please Restart.",
                fg=ORANGE)
            # Add Restart button to warning area if it doesn't exist
            if not hasattr(self, "so_btn"):
                self.so_btn = tk.Button(self, text="Restart Now", command=restart_computer,
                                        bg=ORANGE, fg="#1e1e2e", font=("Segoe UI", 8, "bold"),
                                        relief="flat", padx=6)
                self.so_btn.pack(pady=(0,4), after=self.warn_l)
        else:
            self.eject_chk.config(state="normal")
            self.warn_l.config(text="")
            if hasattr(self, "so_btn"):
                self.so_btn.destroy()
                del self.so_btn

        self.apply_btn.config(
            text="  Apply Icon & Eject  " if is_usb and self.eject_var.get()
            else "  Apply Icon to Drive  ")

    # ── Image ─────────────────────────────────────────────────────────────────
    def _browse(self):
        path=filedialog.askopenfilename(
            title="Select image",
            filetypes=[("Image files",
                        "*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tiff *.tif *.ico"),
                       ("All files","*.*")])
        if not path: return
        try:
            img=Image.open(path)
            self._src=img.convert("RGBA")
            self.img_var.set(path)
            ext=os.path.splitext(path)[1].upper()
            self.info_v.set(
                f"File : {os.path.basename(path)}\n"
                f"Size : {img.width} x {img.height} px  |  {ext}")
            self._ico=None; self._final=None
            self.conv_l.config(text="Click 'Edit / Crop icon' to adjust.",fg=YELLOW)
            self._thumb_update(self._src)
            self._open_editor()
        except Exception as e:
            messagebox.showerror("Error",f"Cannot open image:\n{e}")

    def _thumb_update(self,pil_img):
        t=pil_img.copy().convert("RGBA"); t.thumbnail((96,96),Image.LANCZOS)
        chk=Image.new("RGBA",(96,96)); d=ImageDraw.Draw(chk)
        for y in range(0,96,8):
            for x in range(0,96,8):
                c=(200,200,200,255) if (x//8+y//8)%2==0 else (160,160,160,255)
                d.rectangle([x,y,x+7,y+7],fill=c)
        ox=(96-t.width)//2; oy=(96-t.height)//2
        chk.paste(t,(ox,oy),t)
        self._tk_thumb=ImageTk.PhotoImage(chk)
        self.cv.delete("all")
        self.cv.create_image(0,0,anchor="nw",image=self._tk_thumb)

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
            self.conv_l.config(text="Icon ready!  Click Apply.",fg=GREEN)
            self.status_v.set(f"Icon ready: {out}")
        except Exception as e:
            self.conv_l.config(text=f"Convert failed: {e}",fg=RED)

    # ── Apply ─────────────────────────────────────────────────────────────────
    def _apply(self):
        if not self._ico or not os.path.isfile(self._ico):
            messagebox.showwarning("Not ready","Please select and edit an image first.")
            return
        drive,dtype=self._get_drive()
        if not drive:
            messagebox.showwarning("No Drive","Please select a drive.")
            return
        if is_system_drive(drive):
            if not messagebox.askyesno("⚠️ System Drive",
                f"Apply icon to system drive {drive}?\n\n"
                f"Explorer will restart automatically.\n\nContinue?",
                icon="warning"): return
        elif self.eject_var.get():
            if not messagebox.askyesno("Confirm",
                f"Apply icon to {drive} then safely eject?\n"
                f"Make sure no files are open on {drive}."): return

        self.progress.pack(fill="x",pady=(0,8),before=self.winfo_children()[-1])
        self.progress.start(10); self.update()

        def _run():
            apply_icon_pipeline(
                drive, self._ico, self.label_var.get(),
                self.hide_var.get(), self.eject_var.get(),
                lambda m: self.after(0,lambda msg=m: self.status_v.set(msg)),
                lambda ok,msg: self.after(0,lambda o=ok,m=msg: self._done(o,m)))
        threading.Thread(target=_run,daemon=True).start()

    def _remove_icon(self):
        drive,_=self._get_drive()
        if not drive: return
        if not messagebox.askyesno("Remove Icon",
            f"Remove the custom icon from {drive}?\n"
            f"Drive will go back to default icon."): return
        try:
            reg_remove_icon(drive)
            self.status_v.set(f"Icon removed from {drive}. Refreshing Explorer…")
            self.update()
            def _run():
                full_refresh(drive)
                self.after(0, lambda: (
                    self.status_v.set(f"Default icon restored for {drive}."),
                    self._on_drive()
                ))
            threading.Thread(target=_run,daemon=True).start()
        except Exception as e:
            messagebox.showerror("Error",str(e))

    def _done(self,success,msg):
        self.progress.stop(); self.progress.pack_forget()
        if success:
            messagebox.showinfo("Done!",msg)
            self._refresh_drives()
        else:
            messagebox.showerror("Error",msg)

    def destroy(self):
        try: shutil.rmtree(self._tmp,ignore_errors=True)
        except: pass
        super().destroy()
        

    def _diagnostics(self):
        drive, _ = self._get_drive()
        if not drive: return
        res = drive_diagnostics(drive)
        messagebox.showinfo("Diagnostics", res)

if __name__=="__main__":
    app=App(); app.mainloop()
    