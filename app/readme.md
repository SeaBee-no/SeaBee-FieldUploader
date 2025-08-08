# SeaBee FieldUploader App

## Windows Setup Guide

The software is made to work on Windows computers without admin rights.

1. **Download Rclone**  
   - Obtain the latest `rclone.exe` from https://rclone.org/downloads/  
   - Rename it to `rclone.exe` and place it in the `resources` directory.

2. **Configure `rclone.conf`**  
   - Edit `rclone.conf` to include your SeaBee MinIO credentials.

3. **Modify Default Values**
   - Modify `defaults.txt` to change the default loaded `theme`, `organisation`, `creator_name` and `project`.

3. **Install or Configure Python**
   - **If you dont have Python installed:**
      - Download WinPython from https://github.com/winpython/winpython/releases. Choose the latest stable `...dot.zip` file, ie. `Winpython64-3.12.10.1dot.zip`.
      - Exctract the `WPy...` folder somewhere on your computer, ie. in the `resources` folder.
   - **Then, with Python installed:**
      - Open `SeaBee-FieldUpdater.bat` in a text editor and change the path for `PYTHON` to your computers `python.exe` or `python` if you have it installed on PATH.
      - Exaples:
         ```
         set "PYTHON=%BASEDIR%\resources\WPy64-312101\python\python.exe"
         ```
         or
         ```
         set "PYTHON=C:\WPy64-312101\python\python.exe"
         ```
   - Open the `Properties` of the shortcut file, and change the paths for both `Target` and `Start in` to match the `.bat` files location.

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
- Run the `app.py` script from python or in the terminal.
