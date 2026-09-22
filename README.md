# LANDrop 🚀

> High-speed, private local Wi-Fi file transfer & Safe List folder explorer for Windows, Android, iOS, Mac, and Linux.

---

## ✨ Highlights

- **⚡ No QR Code & No IP Hassle**:
  - **Permanent Address**: Bookmark **`http://landrop.local:5000`** on your phone. Even when your Wi-Fi router changes or reassigns your computer's IP address (DHCP renewal), mDNS automatically resolves to the new IP!
  - **Automatic Subnet Finder**: If needed, visit **`http://<any-ip>:5000/finder`** or use the auto-finder. In 1–2 seconds, it sweeps your Wi-Fi network and reconnects to your PC automatically.
- **🔒 Safe List Folder Explorer**: Choose specific folders on your computer to share. Remote devices can browse subfolders, view files with breadcrumbs, preview media, and download single files or whole directories as a ZIP.
- **📥 Instant Auto-Save**: Incoming files from phones/tablets are **automatically saved** straight to your designated folder (`Downloads/LANDrop_Received`) with automatic duplicate protection (`photo (1).jpg`).
- **📋 Cross-Device Shared Clipboard**: Seamlessly copy/paste links, notes, and text between PC and mobile with 1-tap copy.
- **🚀 Maximum LAN Speed**: Uses direct Wi-Fi local network bandwidth (30–100+ MB/s). No cloud servers, no file size caps, zero data usage.
- **🖥️ Dual Mode**: Sleek native Windows Desktop GUI (with system tray minimize) or Headless CLI (`--headless`).

---

## 🛠️ Quick Start

### Option 1: Double-Click (Windows)
Double-click `start.bat` in this folder.

### Option 2: Python Command
```bash
python main.py
```

### Option 3: Terminal Headless Mode
```bash
python main.py --headless
```

---

## 📱 How to Connect from Your Phone (No QR Needed)

1. Connect your phone to the **same Wi-Fi** as your PC.
2. Open Safari, Chrome, or any browser on your phone.
3. Type the local address shown on your desktop app:
   - **Permanent URL**: `http://landrop.local:5000` (Works natively on iOS, Android, and macOS via mDNS)
   - **Hostname URL**: `http://<your-pc-name>.local:5000`
   - **Direct IP**: `http://192.168.1.101:5000`
4. The web app will open immediately. You can now:
   - Browse folders you added to your Safe List.
   - Send photos, videos, and files directly to your PC (they will be auto-saved).
   - Sync clipboard text back and forth.

---

## 📂 Features Guide

### 1. Safe List (Shared Folders)
1. On the LANDrop desktop app, click **"+ Add Folder to Safe List"**.
2. Select any folder or drive on your PC (e.g. `C:\Users\...\Documents` or `D:\Movies`).
3. Connected devices can now navigate the folder tree, preview files, and download individual files or download folders as a ZIP.
4. **Security**: Devices are strictly sandboxed inside the Safe List folders. Directory traversal attempts (`../`) are automatically blocked.

### 2. Auto-Save Incoming Transfers
1. When you send a file from your phone, it is saved immediately to `Downloads/LANDrop_Received`.
2. If a file with the same name already exists, LANDrop automatically creates a numbered version (e.g. `document (1).pdf`) so nothing is ever overwritten or lost.
3. You can change your auto-save directory at any time using the "Change Folder" button in the desktop app.

### 3. Shared Clipboard
- Copy text on your phone and tap **"Sync to All Devices"** — it instantly appears in the LANDrop app on your PC.
- Paste text on your PC and tap **"Copy to My Clipboard"** on your phone to copy it immediately to your phone's clipboard.

---

## 🧪 Running Tests
To run the automated test suite:
```bash
python -m unittest tests/test_backend.py
```
