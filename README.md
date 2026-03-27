# SeaBee FieldUploader Project

## Overview
This repository contains the SeaBee FieldUploader (Tkinter GUI) for field computers.

The backend/server components that ingest and process uploads have been moved to a separate repository to keep this one clean.

## Running through UV

This method will not work on a NINA laptop, but if you have a non-restricted computer, this method is preferred. Install UV through:

```powershell
# On Windows.
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

```bash
# On Linux / macOS.
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then install Rclone:
```powershell
# Windows
winget install Rclone.Rclone
```
```bash
# Debian/Ubuntu
sudo apt install rclone
```

Then you can run directly from GitHub:

```
uvx --from "git+https://github.com/SeaBee-no/SeaBee-FieldUploader" seabee-fielduploader
```

## Linux setup

1. Install system dependencies:
	```bash
	# Debian / Ubuntu
	sudo apt install python3 python3-tk python3-pip rclone

	# Fedora
	sudo dnf install python3 python3-tkinter python3-pip rclone

	# Arch
	sudo pacman -S python tk python-pip rclone
	```

2. Install Python dependencies:
	```bash
	pip install PyYAML
	```

3. Run the app:
	```bash
	python3 -m app
	```

Config files are stored in `~/.config/seabee-fielduploader/`.

## Windows setup (zip + Python)

An alternative method is downloading the source code and running locally. This is the method for NINA restricted computers.

1. Download the `.zip` from the GitHub Releases page.

2. Install Python (3.10+).
	- If you don't have admin rights, use a portable Python distribution (e.g. WinPython) and point to its `python.exe`.

3. Download/Install Rclone
	Either:
	- `winget install Rclone.Rclone`

	Or:
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

The GUI has buttons for editing `rclone.conf`, `defaults.txt`, and opening the config folder.

## Desktop shortcut (Windows)

1. Right-click the Desktop → **New** → **Shortcut**
2. **Location** (example):
	- `cd "C:/Users/sindre.molvarsmyr/OneDrive - NINA/GitHub/SeaBee-FieldUploader"; "C:/Program Files/Python312/python.exe" -m app`
3. Click **Next**, name it e.g. `SeaBee FieldUploader`, then **Finish**
4. Right-click the new shortcut → **Properties**
	- **Start in**: set this to the folder where you downloaded/cloned SeaBee-FieldUploader
	- **Change Icon…**: point it to `app\seabee.ico`

If `pythonw.exe` is not on PATH, replace it with your full path to Python, e.g.
`"C:\Program Files\Python312\pythonw.exe" -m app`

