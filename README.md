
# SeaBee-Drone2Cloud

This software is specifically designed for seabird mapping uploads, currently supporting only the `Seabirds theme`. It processes image folders, such as those created by DJI Enterprise drones during repeated missions, and restructures them into a format compatible with SeaBee's MinIO storage. The program also generates the necessary configuration files for processing the images through the SeaBee pipeline.

The software is intended for fieldwork scenarios where images are captured across multiple drone missions. After each field day, the drone's SD card can be copied to a backup drive, preserving their original folder structure. The software then restructures these folders and copies them to another hard drive before uploading them to the cloud. This ensures there are always two local backups during the field campains, in addition to an off-site backup stored on MinIO.

### Key Features:
- In a merged group, differences in the creator name are not respected as long as the folders are merged. It will use the last creator name for each merged group.
- If you have a non-mission folder you want merged, you need to add a name/fourth element to the folder name. For example, change `DJI_YYYYMMDDHHII_NNN` to `DJI_YYYYMMDDHHII_NNN_newname` before running the program. **Note:** This will run the images in the pipeline and attempt to use OpenDroneMap, so ensure you have enough overlap between images.

#### Installing & Configuring rclone:

To enable the software to upload data to SeaBee, you need to install [rclone](https://rclone.org/install/). The easiest setup for Windows, where you don't have admin privileges, is as follows:

1. **Download rclone:**
   - Download the zip file for your system from [rclone.org/downloads](https://rclone.org/downloads/).
   
2. **Configure rclone:**
   - Open the command prompt and run:
   ```bash
   "C:/absolute/path/to/rclone.exe" config
   ```
   
   - Add a new configuration:
     - **Name:** `minio`
     - **Type:** `s3`
     - **Provider:** `Minio`
     - **Endpoint:** `storage.seabee.sigma2.no`
     - **ACL:** `private`
     - **Secret Access Key:** Your access key (password)
     - **Access Key ID:** Your access ID (username)

3. **Test the rclone configuration:**
   ```bash
   "C:/absolute/path/to/rclone.exe" lsd minio:
   ```

#### defaults.txt File:
The program uses `defaults.txt` to store default values. After setting up rclone, you will need to update the `defaultrclonecommand` in the `defaults.txt` file on your computer.

### Example `defaults.txt` File:

```ini
drone_backup=D:/test_SD
seabee_structure=D:/test_seabee
organisation=NINA
theme=Seabirds
creator_name=Sindre Molværsmyr
project=SEAPOP Kartlegging 2025
defaultrclonecommand="C:/Users/sindre.molvarsmyr/OneDrive - NINA/Portable tech/rclone-v1.60.1-windows-amd64/rclone.exe" copy LOCAL minio:seabirds/2024 --progress
uploadbydefault=True
```

- In the `defaultrclonecommand`, `LOCAL` is replaced with the SeaBee path set in the program, while the beginning of the path refers to the `rclone.exe` file on your local system.
- If `rclone` is on your system’s `PATH`, the path to `rclone.exe` can be replaced with just `rclone`.

### Setup & Installation:

A pre-compiled `.exe` file is availible under releases.

#### PyInstaller Command (for generating the executable):
```bash
pyinstaller --onefile --windowed --icon=seabee.ico --add-data "C:/absolute/path/to/location_icon.png;." --add-data "C:/absolute/path/to/seabee.ico;." app.py
```

**Note:** The `exe` file might give an error that you don't have permission to open it. This can usually be solved by just trying to open it again.

### Troubleshooting:
- If the `exe` gives a permission error, try running it again.
- If rclone is not functioning, ensure that the path to `rclone.exe` is correct and that the configuration has been tested successfully.
