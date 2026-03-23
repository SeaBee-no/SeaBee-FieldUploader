# SeaBee FieldUploader Project

## Overview
This repository contains the SeaBee FieldUploader (Windows-friendly Tkinter GUI) for field computers.

The backend/server components that ingest and process uploads have been moved to a separate repository to keep this one clean.

## Run the FieldUploader (recommended)

If you want to run the GUI directly from this GitHub repo (without bundling Python), you can use `uvx`:

```powershell
uvx --from "git+https://github.com/SeaBee-no/SeaBee-FieldUploader#subdirectory=app" seabee-fielduploader
```

You must provide `rclone.exe` and a local `rclone.conf` (credentials). The app will create `%APPDATA%\\SeaBee-FieldUploader\\rclone.conf` from a template on first run. See `app/readme.md` for details.

## App
- The GUI app lives in `app/resources/app.py`.
- Setup and fieldworker instructions are in `app/readme.md`.
