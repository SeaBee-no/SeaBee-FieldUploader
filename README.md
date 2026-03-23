# SeaBee FieldUploader Project

## Overview
This repository contains the SeaBee FieldUploader (Windows-friendly Tkinter GUI) for field computers.

The backend/server components that ingest and process uploads have been moved to a separate repository to keep this one clean.

## Windows setup (zip + Python)

This is the recommended deployment method for field computers.

1. Download the `.zip` from the GitHub Releases page.

2. Install Python (3.10+).
	- If you don't have admin rights, use a portable Python distribution (e.g. WinPython) and point to its `python.exe`.

3. Download `rclone.exe`
	- Download from https://rclone.org/downloads/
	- Place it either:
	  - Next to the program files, OR
	  - In `%APPDATA%\SeaBee-FieldUploader\rclone.exe`

4. Install Python dependencies
	- From inside the extracted folder (the one containing both `app/` and `resources/`):
	  ```powershell
	  python -m pip install -r app/requirements.txt
	  ```

5. Run the app
	- From inside the extracted folder (the one containing both `app/` and `resources/`):
	  ```powershell
	  python -m app
	  ```

On first startup, the app will auto-create these per-user config files:
- `%APPDATA%\SeaBee-FieldUploader\rclone.conf` (from `resources/rclone.conf.template`)
- `%APPDATA%\SeaBee-FieldUploader\defaults.txt` (from `resources/defaults.txt`)
- `%APPDATA%\SeaBee-FieldUploader\bucket.conf` (from `resources/bucket.conf.template`)

`bucket.conf` controls the upload target (`REMOTE_NAME`, `BUCKET_NAME`, `OBJECT_PREFIX`).

The GUI also has buttons for editing `rclone.conf` and saving defaults.

## Desktop shortcut (Windows)

### Option A: Manual shortcut

1. Right-click the Desktop → **New** → **Shortcut**
2. **Location** (example):
	- `pythonw.exe -m app`
3. Click **Next**, name it e.g. `SeaBee FieldUploader`, then **Finish**
4. Right-click the new shortcut → **Properties**
	- **Start in**: set this to the folder where you downloaded/cloned SeaBee-FieldUploader
	- **Change Icon…**: point it to `resources\seabee.ico`

If `pythonw.exe` is not on PATH, replace it with your full path to Python, e.g.
`"C:\Program Files\Python312\pythonw.exe" -m app`

### Option B: Create shortcut via PowerShell

Run this from the SeaBee-FieldUploader folder:

`$wsh = New-Object -ComObject WScript.Shell`

`$lnk = $wsh.CreateShortcut("$env:USERPROFILE\Desktop\SeaBee FieldUploader.lnk")`

`$lnk.TargetPath = (Get-Command pythonw.exe).Source`

`$lnk.Arguments = "-m app"`

`$lnk.WorkingDirectory = (Get-Location).Path`

`$lnk.Save()`

## Optional: install uv

If you prefer using uv on a non-restricted computer, install it with:

```powershell
# On Windows.
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then you can run directly from GitHub:

```powershell
uvx --from "git+https://github.com/SeaBee-no/SeaBee-FieldUploader" seabee-fielduploader
```
