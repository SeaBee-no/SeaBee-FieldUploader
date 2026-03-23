# SeaBee FieldUploader App

## Windows Setup Guide

### Option A (recommended): Run directly from GitHub using `uvx`

This is the easiest way to distribute updates to fieldworkers without shipping a custom Python environment.

1. **Install uv (user install, no admin needed)**
    - Open PowerShell and run:
       ```powershell
       irm https://astral.sh/uv/install.ps1 | iex
       ```

2. **Download `rclone.exe`**
    - Download from https://rclone.org/downloads/
    - Extract `rclone.exe` somewhere you have write access.
    - Recommended (per-user) location:
       - `%APPDATA%\SeaBee-FieldUploader\rclone.exe`
    - If you put it elsewhere, set:
       - `SEABEE_RCLONE_EXE=C:\path\to\rclone.exe`

3. **Generate `%APPDATA%\SeaBee-FieldUploader\rclone.conf` (credentials)**
    - Do NOT commit credentials to git.
   - On first run, the app will create the file from `rclone.conf.template` if it is missing.
   - Then edit the generated file and fill in the credentials.
   - If you want to create it manually (only needed if you cloned this repo), you can run:
     ```powershell
     New-Item -ItemType Directory -Force "$env:APPDATA\SeaBee-FieldUploader" | Out-Null
     Copy-Item -Force ".\resources\rclone.conf.template" "$env:APPDATA\SeaBee-FieldUploader\rclone.conf"
     notepad "$env:APPDATA\SeaBee-FieldUploader\rclone.conf"
     ```
    - The remote name must match `minio` (see `REMOTE_NAME` in the code).

4. **Run the app from GitHub**
    - Public repo example:
       ```powershell
       uvx --from "git+https://github.com/SeaBee-no/SeaBee-FieldUploader#subdirectory=app" seabee-fielduploader
       ```
    - Tip: pin to a tag for stable field deployments:
       ```powershell
       uvx --from "git+https://github.com/SeaBee-no/SeaBee-FieldUploader@v0.1.0#subdirectory=app" seabee-fielduploader
       ```

The software is made to work on Windows computers without admin rights.

### Option B: Download zip release

1. **Download the software**
   - Download the `.zip` file from https://github.com/SeaBee-no/SeaBee-FieldUploader/releases

2. **Download Rclone**  
   - Obtain the latest `rclone.exe` from https://rclone.org/downloads/  
   - Place it next to the app as `rclone.exe` or at `%APPDATA%\SeaBee-FieldUploader\rclone.exe`.

3. **Configure `rclone.conf`**  
   - On first run, the app will create `%APPDATA%\SeaBee-FieldUploader\rclone.conf` from `rclone.conf.template` if it is missing.
   - Edit the generated file and fill in the credentials.

4. **Modify Default Values**
   - Modify `defaults.txt` to change the default loaded `theme`, `organisation`, `creator_name` and `project`.

5. **Run the App**
   - Run `SeaBee-FieldUploader.exe`.

## Behavior Notes
- When staring an upload, root-level files are auto-organized into timestamped subfolders named `fielduploader_uploads_YYYYMMDDHHMMSS` before upload.  
- In case of failed uploads, the upload can be restarted with the same settings and will continue where it left of (default `rclone` behaviour).
- The values from the form will only be applied to new folders (those without the `fielduploader.seabee.yaml`) when uploading.

## Running on Mac and Linux
- Adjust the values for `rclone_exe` in the `run_rclone_with_progress()` function.
- Run the `app.py` script from python or in the terminal.
