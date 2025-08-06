# SeaBee FieldUploader App

## Windows Setup Guide

The software is made to work on Windows computers without admin rights.

1. **Download Rclone**  
   - Obtain the latest `rclone.exe` from https://rclone.org/downloads/  
   - Rename it to `rclone.exe` and place it in the directory.

2. **Configure `rclone.conf`**  
   - Edit `rclone.conf` to include your SeaBee MinIO credentials.

3. **Modify Default Values**
   - Modify `defaults.txt` to change the default loaded `theme`, `organisation`, `creator_name` and `project`.

3. **Install Python (if needed)**
   - Install on path, or use WinPython/Thonny/similar.
   - You need to 

4. **Run the App in Python**  
   ```bash
   python app.py
   ```
   Select the folder you want to upload (we recommend using the root of a hard drive like `E:/`, which contains all the subfolders from the drones SD card) and press upload. Make sure the form values are correct.

## Behavior Notes
- When staring an upload, root-level files are auto-organized into timestamped subfolders named `fielduploader_uploads_YYYYMMDDHHMMSS` before upload.  
- In case of failed uploads, the upload can be restarted with the same settings and will continue where it left of (default `rclone` behaviour).
- The values from the form will only be applied to new folders (those without the `fielduploader.seabee.yaml`) when uploading.

## Running on Mac and Linux
- Adjust the values for `rclone_exe` in the `run_rclone_with_progress()` function.  
