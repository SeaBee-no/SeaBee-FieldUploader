# SeaBee FieldUploader Project

## Overview
The SeaBee FieldUploader project consists of a Python-based application for field computers and a suite of backend scripts that automate data ingestion and processing for the SeaBee MinIO server.

## Components
1. **FieldUploader Application in `/app`**  
   - Standalone Python GUI for selecting local folders and uploading content to MinIO.  
   - Bundled with Rclone for secure, resumable transfers.

2. **WebUploader Application in `/server/frontend/webuploader`**
   - Online version of the FieldUploader intended for smaller amounts of data.
   - Will not resume failed uploads, each upload goes into its own folder `webuploader_uploads_YYYYMMDDHHIISS`


3. **Backend Processing Scripts in `/server/backend`**  
   - `scanfielduploads.py`: Detects and records new uploads in the database.  
   - `makeclusters.py`: Groups uploaded files into clusters.  
   - `delivertosigma.py`: Exports accepted data to the SeaBee analytics platform.

   Schedule the backend scripts using cron:
   ```
   10 1 * * * python3 scanfielduploads.py
   0 3 * * * python3 makeclusters.py
   0 * * * * python3 delivertosigma.py
   ```


## Setup
- Replace placeholder credentials in `credentials.py` with environment-secured variables.   
