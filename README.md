# SeaBee FieldUploader Project

## Overview
The SeaBee FieldUploader project consists of a Python-based application for field computers and a suite of backend scripts that automate data ingestion and processing for the SeaBee MinIO server.

## Components
1. **FieldUploader Application in `/app`**  
   - Standalone Python GUI for selecting local folders and uploading content to MinIO.  
   - Bundled with Rclone for secure, resumable transfers.

2. **WebUploader Application in `/server/frontend/webuploader`**
   - Online version of the FieldUploader intended for smaller amounts of data.
   - Will not resume failed uploads, each upload goes into its own folder `webuploader_uploads_YYYYMMDDHHIISS`.

3. **FieldUploader Admin Application in `/server/frontend/fielduploader`**
   - Web application to manage clusters of images.
   - You can split or merge clusters, change names and project.
   - Clusters get marked as `Ready for Sigma`, tagging them for the automated scripts.

4. **Backend Processing Scripts in `/server/backend`**  
   - `scanfielduploads.py`: Detects and stores new uploaded files to the database.  
   - `makeclusters.py`: Groups files into clusters based on time and distance.  
   - `delivertosigma.py`: Exports accepted data to the SeaBee analytics platform.

   Schedule the backend scripts using cron:
   ```
   10 1 * * * python3 scanfielduploads.py
   0 3 * * * python3 makeclusters.py
   0 * * * * python3 delivertosigma.py
   ```


## Setup
- Replace placeholder credentials in `credentials.py` with environment-secured variables.
- The repository is missing `authentication.php`. Either create your own, or remove the authentication section from the frontend webpages.
