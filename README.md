# SeaBee-Drone2Cloud
This software is under development. Purpose made for seabird mapping uploads.

In a merged group differences in the creator name is not respected as long as the folders are merged. It will use the last creator name for each merged group.

If you have a non-mission folder you want merged, you need to add a name/forth element to the folder name, like DJI_YYYYMMDDHHII_NNN to DJI_YYYYMMDDHHII_NNN_newname, before running the program. Be aware that this will run the images in the pipeline and try using OpenDroneMap, so be sure to have enough overlap between images.

pyinstaller --onefile --windowed --icon=myicon.ico app.py