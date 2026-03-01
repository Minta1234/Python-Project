# Run
    # Save as linux-drive-icon-setter.py
    chmod +x DriveIconSetterLinux.py
    
    # Run normally (user space)
    python3 DriveIconSetterLinux.py
    
    # For persistent udev rules (optional)
    sudo python3 DriveIconSetterLinux.py

    Ubuntu/Debian
    sudo apt install python3-pil.imagetk python3-tk
    
    # Fedora
    sudo dnf install python3-pillow-tk python3-tkinter
    
    # Arch
    sudo pacman -S python-pillow python-tkinter
