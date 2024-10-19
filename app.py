import tkinter as tk
from tkinter import ttk, filedialog, messagebox, PhotoImage
import customtkinter as ctk
import os
import sys
import glob
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from tkintermapview import TkinterMapView
from geopy.distance import geodesic
from datetime import datetime
import requests
import subprocess
import shutil
import time
import threading
import yaml

def get_own_file_path():
    if getattr(sys, 'frozen', False):  # Check if running as compiled .exe
        # If running as a PyInstaller bundled app, use the location of the executable
        application_path = os.path.dirname(sys.executable)
    else:
        # If running as a normal Python script, use the location of the script
        application_path = os.path.dirname(os.path.realpath(__file__))

    # Join the path to defaults.txt with the application path
    return application_path

# Path to defaults.txt file
defaults_file_path = os.path.join(get_own_file_path(), "defaults.txt")

# Function to read defaults from the defaults.txt file
def load_defaults():
    defaults = {
        "drone_backup": "",
        "seabee_structure": "",
        "organisation": "",
        "theme": "Seabirds",
        "creator_name": "",
        "project": "",
        "defaultrclonecommand": "",
        "uploadbydefault": "False"
    }
    
    if os.path.exists(defaults_file_path):
        with open(defaults_file_path, "r", encoding="utf-8") as file:
            for line in file:
                key, value = line.strip().split("=")
                if key in defaults:
                    if(key == "uploadbydefault"):
                        if value == "True":
                            defaults[key] = True
                        else:
                            defaults[key] = False
                    else:
                        defaults[key] = value
    
    return defaults

# Function to save updated defaults to the defaults.txt file
def save_defaults():
    # First, load the existing values from the defaults.txt file
    current_defaults = {}
    
    if os.path.exists(defaults_file_path):
        with open(defaults_file_path, "r", encoding="utf-8") as file:
            for line in file:
                key, value = line.strip().split("=")
                current_defaults[key] = value

    # Update the relevant values from the form
    current_defaults["drone_backup"] = folder2_var.get()
    current_defaults["seabee_structure"] = folder3_var.get()
    current_defaults["organisation"] = organisation_var.get()
    current_defaults["theme"] = theme_var.get()
    current_defaults["creator_name"] = creator_name_var.get()
    current_defaults["project"] = project_var.get()

    # Write everything back to the file
    with open(defaults_file_path, "w", encoding="utf-8") as file:
        for key, value in current_defaults.items():
            file.write(f"{key}={value}\n")

# Function to select a folder
def select_folder(folder_var):
    folder_selected = filedialog.askdirectory()
    folder_var.set(folder_selected)  # Update the corresponding text variable

# Function to extract GPS data and timestamp from images
def extract_gps_and_timestamp_from_image(image_path):
    try:
        image = Image.open(image_path)
        exif_data = image._getexif()

        if not exif_data:
            return None, None
        
        gps_info = {}
        timestamp = None
        for tag, value in exif_data.items():
            decoded = TAGS.get(tag, tag)
            if decoded == "GPSInfo":
                for t in value:
                    gps_tag = GPSTAGS.get(t, t)
                    gps_info[gps_tag] = value[t]
            elif decoded == "DateTimeOriginal":
                timestamp = value

        if 'GPSLatitude' in gps_info and 'GPSLongitude' in gps_info:
            lat = gps_info['GPSLatitude']
            lon = gps_info['GPSLongitude']

            def convert_to_degrees(value):
                d, m, s = value
                return d + (m / 60.0) + (s / 3600.0)

            latitude = convert_to_degrees(lat)
            if gps_info['GPSLatitudeRef'] != 'N':
                latitude = -latitude

            longitude = convert_to_degrees(lon)
            if gps_info['GPSLongitudeRef'] != 'E':
                longitude = -longitude

            return (latitude, longitude), timestamp
    except Exception as e:
        print(f"Error extracting GPS data from {image_path}: {e}")
    return None, None

already_copied = set()  # Set to store already copied folders

# Function to process folders and extract GPS every 10th image
def process_folders_and_extract_gps_and_times():
    folder2 = folder2_var.get()

    if not folder2:
        messagebox.showerror("Error", "Please select the 'Drone Backup' folder.")
        return

    save_defaults()

    drone_backup = folder2
    folders = sorted([f for f in glob.glob(os.path.join(drone_backup, "*")) if os.path.isdir(f)])  # Sort folders alphabetically
    
    folder_data = {}
    already_copied.clear()  # Clear the set of already copied folders
    
    for folder in folders:
        # Check if 'copied.txt' exists, mark as already copied
        copied_file_path = os.path.join(folder, "copied.txt")
        if os.path.exists(copied_file_path):
            already_copied.add(folder)
            continue  # Skip the rest of the processing for this folder

        image_files = glob.glob(os.path.join(folder, "*.jpg"))[::10]  # Get every 10th image
        gps_positions = []
        timestamps = []

        for image_file in image_files:
            gps_coords, timestamp = extract_gps_and_timestamp_from_image(image_file)
            if gps_coords:
                gps_positions.append(gps_coords)
            if timestamp:
                timestamps.append(datetime.strptime(timestamp, '%Y:%m:%d %H:%M:%S'))

        if gps_positions and timestamps:
            avg_latitude = sum(lat for lat, lon in gps_positions) / len(gps_positions)
            avg_longitude = sum(lon for lat, lon in gps_positions) / len(gps_positions)
            start_time = min(timestamps)
            end_time = max(timestamps)
            folder_data[folder] = {
                "average_gps": (avg_latitude, avg_longitude),
                "start_time": start_time,
                "end_time": end_time,
                "gps_positions": gps_positions,
                "timestamps": timestamps
            }

    return folder_data

# Function to merge folders based on time and distance criteria
def merge_folders(folder_data):
    merged_folders = []
    visited = set()

    folder_names = list(folder_data.keys())
    for i in range(len(folder_names)):
        if folder_names[i] in visited:
            continue

        current_merge = [folder_names[i]]
        visited.add(folder_names[i])

        for j in range(i + 1, len(folder_names)):
            if folder_names[j] in visited:
                continue

            folder1 = folder_data[folder_names[i]]
            folder2 = folder_data[folder_names[j]]

            # Check if time ranges overlap within 30 minutes
            time_diff_start = abs((folder1["start_time"] - folder2["end_time"]).total_seconds()) / 60
            time_diff_end = abs((folder1["end_time"] - folder2["start_time"]).total_seconds()) / 60

            if time_diff_start <= 30 or time_diff_end <= 30:
                # Check if any GPS point is within 100 meters
                close_points = any(
                    geodesic(pos1, pos2).meters < 300
                    for pos1 in folder1["gps_positions"]
                    for pos2 in folder2["gps_positions"]
                )

                if close_points:
                    current_merge.append(folder_names[j])
                    visited.add(folder_names[j])

        merged_folders.append(current_merge)

    return merged_folders

# Function to get place name from API
def get_place_name(lat, lon):
    url = f"https://ws.geonorge.no/stedsnavn/v1/punkt?nord={lat}&ost={lon}&koordsys=4326&radius=500&treffPerSide=500"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data and 'navn' in data and data['navn']:
            closest = min(data['navn'], key=lambda x: x['meterFraPunkt'])
            place_name = closest['stedsnavn'][0]['skrivemåte']
            return place_name
    return None

# Function to get municipality and county from API
def get_municipality_and_county(lat, lon):
    url = f"https://ws.geonorge.no/kommuneinfo/v1/punkt?nord={lat}&ost={lon}&koordsys=4326"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        municipality = data.get('kommunenavn', 'Unknown')
        county = data.get('fylkesnavn', 'Unknown')
        return municipality, county
    return None, None

# Function to ask API about each folder
def ask_api_for_folders(folder_data):
    folder_info = {}
    for folder, data in folder_data.items():
        lat, lon = data["average_gps"]
        place_name = get_place_name(lat, lon)
        municipality, county = get_municipality_and_county(lat, lon)
        folder_info[folder] = {
            "place_name": place_name,
            "municipality": municipality,
            "county": county
        }
        print(f"Folder: {folder}, Place Name: {place_name}, Municipality: {municipality}, County: {county}")
    return folder_info

# Function to get place name from average GPS for merged folders
def get_place_name_from_avg_gps(gps_positions):
    avg_latitude = sum(lat for lat, lon in gps_positions) / len(gps_positions)
    avg_longitude = sum(lon for lat, lon in gps_positions) / len(gps_positions)
    return get_place_name(avg_latitude, avg_longitude), (avg_latitude, avg_longitude)

# Function to get municipality and county from average GPS for merged folders
def get_municipality_and_county_from_avg_gps(gps_positions):
    avg_latitude = sum(lat for lat, lon in gps_positions) / len(gps_positions)
    avg_longitude = sum(lon for lat, lon in gps_positions) / len(gps_positions)
    return get_municipality_and_county(avg_latitude, avg_longitude)

# Function triggered when 'Start Processing' button is clicked
def start_processing():
    folder_data = process_folders_and_extract_gps_and_times()

    # Merge folders based on time and distance criteria
    merged_folders = merge_folders(folder_data)

    # Ask API for additional information about each folder
    folder_info = ask_api_for_folders(folder_data)

    # Show the results in a new window
    show_results_window(folder_data, folder_info, merged_folders)

# Global variable to signal cancellation of the copy process
cancel_copy = False

# Function to copy and merge folders to the seabee structure folder with progress bar and feedback
def copy_and_merge_folders(merged_folders, folder_data, folder_info, progress_bar, progress_label, folder_entries, cancel_button):
    global cancel_copy
    seabee_structure = folder3_var.get()

    if not seabee_structure:
        messagebox.showerror("Error", "Please select the 'SeaBee structure' folder.")
        return

    total_files = 0
    copied_files = 0

    # Calculate total number of files to copy for the progress bar
    for merged_group in merged_folders:
        for folder in merged_group:
            total_files += len(glob.glob(os.path.join(folder, "*")))  # Count all files

    progress_bar["value"] = 0  # Reset progress bar
    #app.config(cursor="wait")  # Disable input, set cursor to "wait"
    progress_label.config(text="Copying files...")

    entry_index = 0  # To track which folder_entries index we are working with

    # Loop over merged folders and handle each folder individually
    for merged_group in merged_folders:
        for folder in merged_group:
            if cancel_copy:
                app.config(cursor="")  # Re-enable input # this dont work
                progress_label.config(text="Copying cancelled!")
                messagebox.showinfo("Cancelled", "Copying process was cancelled.")
                return

            # Check if the folder has only three parts in its name (like DJI_202405221908_010)
            folder_name_parts = os.path.basename(folder).split("_")
            if len(folder_name_parts) == 3:
                # Copy this folder to the "nonmission" folder without any changes
                destination_folder = os.path.join(seabee_structure, "nonmission", os.path.basename(folder))
                os.makedirs(destination_folder, exist_ok=True)
            else:
                # Get the user-modified folder names from the input fields (grouping, area, datetime)
                folder_grouping = folder_entries[entry_index]["grouping"].get()
                folder_area = folder_entries[entry_index]["area"].get()
                folder_datetime = folder_entries[entry_index]["datetime"].get()
                folder_creator_name = folder_entries[entry_index]["creator_name"].get()

                new_folder_name = f"{folder_grouping}_{folder_area}_{folder_datetime}/images"
                new_folder_name = new_folder_name.lower().replace("æ", "ae").replace("ø", "oe").replace("å", "aa")
                destination_folder = os.path.join(seabee_structure, new_folder_name)
                os.makedirs(destination_folder, exist_ok=True)

            # Copy all the files from the respective folder to the new folder
            for file_path in glob.glob(os.path.join(folder, "*")):  # Copy all files
                if cancel_copy:
                    app.config(cursor="")  # Re-enable input
                    progress_label.config(text="Copying cancelled!")
                    messagebox.showinfo("Cancelled", "Copying process was cancelled.")
                    time.sleep(1)  # Wait for 1 second before updating the text
                    cancel_button.configure(text="Copy, merge (and upload) folders", command=lambda: run_copy_in_thread(merged_folders, folder_data, folder_info, progress_bar, progress_label, folder_entries, cancel_button))
                    cancel_button.configure(state=tk.NORMAL)
                    return

                shutil.copy(file_path, destination_folder)
                copied_files += 1

                # Update the progress bar
                progress_percentage = (copied_files / total_files) * 100
                progress_bar["value"] = progress_percentage
                app.update_idletasks()  # Force update GUI

            # After copying, add the `copied.txt` file to the original folder
            with open(os.path.join(folder, "copied.txt"), "w") as f:
                f.write("Folder contents were copied to the seabee structure.")
            
            if len(folder_name_parts) != 3:
                # Count number of files in the new "images" folder
                nfiles = len(glob.glob(os.path.join(destination_folder, "*")))

                # Create the YAML structure
                yaml_data = {
                    'area': folder_area,
                    'classify': True,
                    'creator_name': folder_creator_name,
                    'datetime': folder_datetime,
                    'grouping': folder_grouping,
                    'mosaic': True,
                    'nfiles': nfiles,
                    'organisation': organisation_var.get(),
                    'publish': True,
                    'theme': theme_var.get()
                }

                # Write the YAML file in the root of the destination folder
                yaml_file_path = os.path.join(os.path.dirname(destination_folder), "config.seabee.yaml")
                with open(yaml_file_path, 'w', encoding='utf-8') as yaml_file:
                    yaml.dump(yaml_data, yaml_file, default_flow_style=False, allow_unicode=True)

            entry_index += 1  # Increment to the next folder entry after processing each folder

    app.config(cursor="")  # Re-enable input
    progress_label.config(text="Copying complete!")
    cancel_button.configure(text="Copy and merge folders", command=lambda: run_copy_in_thread(merged_folders, folder_data, folder_info, progress_bar, progress_label, folder_entries, cancel_button))
    #messagebox.showinfo("Success", "Folders copied and merged successfully.")
    print("Folders copied and merged successfully.")
    
    # Check if the 'Also upload' checkbox was checked
    if upload_var.get():
        rclone_command = defaults.get("defaultrclonecommand")
        if rclone_command:
            # Get seabee_structure path
            seabee_structure = folder3_var.get()

            # Add quotes around seabee_structure path if it contains spaces
            if " " in seabee_structure:
                seabee_structure = f'"{seabee_structure}"'

            # Replace LOCAL in the command with the seabee_structure path
            rclone_command = rclone_command.replace("LOCAL", seabee_structure)

            # Ensure rclone.exe path is quoted (manually handle quotes)
            if not rclone_command.startswith('"'):
                rclone_command = f'"{rclone_command}"'

            # Open the command in a new cmd window
            subprocess.Popen(f'start cmd /K {rclone_command}', shell=True)

# Function to cancel the copy process
def cancel_copy_process(cancel_button):
    global cancel_copy
    cancel_copy = True
    cancel_button.configure(state=tk.DISABLED)  # Disable the cancel button during the process

# Wrapper function to run the copying process in a separate thread
def run_copy_in_thread(merged_folders, folder_data, folder_info, progress_bar, progress_label, folder_entries, cancel_button):
    global cancel_copy
    cancel_copy = False  # Reset cancellation flag

    # Change to cancel button and update the text correctly using configure
    cancel_button.configure(text="Cancel", command=lambda: cancel_copy_process(cancel_button))  
    cancel_button.configure(state=tk.NORMAL)  # Enable cancel button

    threading.Thread(target=copy_and_merge_folders, args=(merged_folders, folder_data, folder_info, progress_bar, progress_label, folder_entries, cancel_button)).start()

# Function to zoom and pan to a folder's GPS location
def zoom_to_folder(folder, folder_data, map_widget):
    lat, lon = folder_data[folder]["average_gps"]
    map_widget.set_position(lat, lon)
    map_widget.set_zoom(15)  # Adjust the zoom level as needed

# Function to show the results in a new window with a scrollable left pane and minimum width
def show_results_window(folder_data, folder_info, merged_folders):
    results_window = tk.Toplevel(app)
    results_window.geometry("1024x800")  # Adjust size of the results window
    results_window.title("Merging Suggestions")

    # Minimum width for the scrollable frame
    min_width = 600

    # Create a frame for the left pane with a scrollbar
    left_frame_container = tk.Frame(results_window)
    left_frame_container.pack(side="left", fill="both", expand=True)

    # Create a canvas and a vertical scrollbar for the left pane
    canvas = ctk.CTkCanvas(left_frame_container)
    scrollbar = tk.Scrollbar(left_frame_container, orient="vertical", command=canvas.yview)
    scrollable_frame = tk.Frame(canvas)

    # Configure the canvas and scrollbar
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    # Create a window inside the canvas with a minimum width
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    # Set the minimum width for the scrollable frame
    canvas.itemconfig(canvas.create_window((0, 0), window=scrollable_frame, anchor="nw"), width=min_width)

    # Pack the canvas and the scrollbar
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # List to store entries for each merged group (grouping, area, datetime)
    folder_entries = []

    # Load the location icon image
    location_icon = tk.PhotoImage(file=os.path.join(get_own_file_path(), "location_icon.png"))
    # Scale the image to be smaller (subsample)
    scalefactor = round(location_icon.height() / 20)
    location_icon = location_icon.subsample(scalefactor, scalefactor)

    # Display already copied folders at the top of the scrollable frame
    if already_copied:
        already_copied_frame = tk.Frame(scrollable_frame)
        already_copied_frame.pack(anchor="w", padx=5, pady=5, fill="x")
        # Separate the string joining logic from the f-string
        already_copied_text = "Already copied:\n" + '\n'.join(already_copied)
        tk.Label(already_copied_frame, text=already_copied_text, font='Helvetica 10', fg='grey', wraplength=500, justify="left").pack(side="left")
        # Add a separator line between each mission
        separator = tk.Frame(scrollable_frame, height=2, bd=1, relief=tk.SUNKEN)
        separator.pack(fill="x", pady=10)

    # Display folder information with individual entries for each field in the scrollable frame
    for merged_group in merged_folders:
        # If folders are merged, show "MERGED" in red
        if len(merged_group) > 1:
            merged_frame = tk.Frame(scrollable_frame)
            merged_frame.pack(anchor="w", padx=5, pady=5, fill="x")
            tk.Label(merged_frame, text=f"MERGED", font='Helvetica 10 bold', fg='red').pack(side="left")
            tk.Label(merged_frame, text=f"If you change names so they are different, they are not merged", font='Helvetica 10', fg='grey').pack(side="left", padx=(10, 0))

        # Generate the auto-filled names for the merged group
        all_gps_positions = []
        for folder in merged_group:
            all_gps_positions.extend(folder_data[folder]["gps_positions"])

        avg_place_name, avg_gps = get_place_name_from_avg_gps(all_gps_positions)
        avg_municipality, avg_county = get_municipality_and_county_from_avg_gps(all_gps_positions)

        # Get the smallest datetime for the merged group
        min_timestamp = min(folder_data[folder]['timestamps'][0] for folder in merged_group).strftime('%Y%m%d%H%M')

        # Store the entries for each folder in the merged group
        for folder in merged_group:
            folder_name = os.path.basename(folder)
            folder_frame = tk.Frame(scrollable_frame)
            folder_frame.pack(fill="x", padx=5, pady=5)

            folder_label_frame = tk.Frame(folder_frame)
            folder_label_frame.pack(fill="x")

            # Folder name label
            tk.Label(folder_label_frame, text=f"{folder_name}", font='Helvetica 10 bold', fg='black').pack(side="left")

            # Create a button with the location icon and zoom functionality
            zoom_button = tk.Button(folder_label_frame, image=location_icon, command=lambda folder=folder: zoom_to_folder(folder, folder_data, map_widget))
            zoom_button.image = location_icon  # Keep a reference to the image to prevent garbage collection
            zoom_button.pack(side="left", padx=5, pady=0)

            # Check if the folder has only three parts in its name (like DJI_202405221908_010)
            folder_name_parts = folder_name.split("_")
            if len(folder_name_parts) == 3:
                # No input fields for "nonmission" folders
                tk.Label(folder_frame, text=f"Non-mission folder, copied without changes.", font='Helvetica 10', fg='grey').pack(anchor="w", padx=5)
            else:
                entry_group = {}

                # Display place name, municipality, and county for each folder (based on average GPS if merged)
                new_name_frame = tk.Frame(folder_frame)
                new_name_frame.pack(fill="x")

                tk.Label(new_name_frame, text="New name:", font='Helvetica 10').pack(side="left", anchor="w", padx=(10, 2))

                # Set auto-filled values based on the merged group
                grouping = (avg_county or "Unknown") + "-" + (avg_municipality or "Unknown")
                grouping = grouping.replace(" ", "-")
                county_entry = tk.Entry(new_name_frame, width=30)
                county_entry.insert(0, grouping)
                county_entry.pack(side="left", padx=5)
                entry_group["grouping"] = county_entry

                area = avg_place_name.replace(" ", "-") if avg_place_name else "Unknown"
                place_name_entry = tk.Entry(new_name_frame, width=25)
                place_name_entry.insert(0, area)
                place_name_entry.pack(side="left", padx=5)
                entry_group["area"] = place_name_entry

                # Display the datetime (smallest from merged folders)
                datetime_entry = tk.Entry(new_name_frame, width=15)
                datetime_entry.insert(0, min_timestamp or "")
                datetime_entry.pack(side="left", padx=5)
                entry_group["datetime"] = datetime_entry

                # Add a creator name field with default from creator_name_var
                new_creator_frame = tk.Frame(folder_frame)
                new_creator_frame.pack(fill="x")
                tk.Label(new_creator_frame, text="Creator name:", font='Helvetica 10').pack(side="left", anchor="w", padx=(10, 2))
                creator_name_entry = tk.Entry(new_creator_frame, width=25)
                creator_name_entry.insert(0, creator_name_var.get())  # Default from the first page
                creator_name_entry.pack(side="left", padx=5, pady=5)
                entry_group["creator_name"] = creator_name_entry

                folder_entries.append(entry_group)

        # Add a separator line between each mission
        separator = tk.Frame(scrollable_frame, height=2, bd=1, relief=tk.SUNKEN)
        separator.pack(fill="x", pady=10)

    # Progress bar and label at the bottom of the scrollable frame
    progress_label = tk.Label(scrollable_frame, text="Ready to copy.")
    progress_label.pack(pady=5)
    progress_bar = ttk.Progressbar(scrollable_frame, orient="horizontal", length=300, mode="determinate")
    progress_bar.pack(pady=5)

    # Checkbox to also upload
    upload_checkbox = tk.Checkbutton(scrollable_frame, text="Also upload using rclone", variable=upload_var)
    upload_checkbox.pack(pady=5)
    
    # Add the button at the bottom of the scrollable frame
    cancel_button = ctk.CTkButton(scrollable_frame, 
                                text="Copy, merge (and upload) folders",
                                width=300,
                                command=lambda: run_copy_in_thread(merged_folders, folder_data, folder_info, progress_bar, progress_label, folder_entries, cancel_button))
    cancel_button.pack(pady=5)

    # Right side: Map showing the average GPS points
    right_frame = tk.Frame(results_window, width=280, height=600)
    right_frame.pack(side="right", fill="both", expand=True)

    map_widget = TkinterMapView(right_frame, width=280, height=600, corner_radius=0)
    map_widget.pack(fill="both", expand=True)

    latitudes = []
    longitudes = []

    # Collect all latitudes and longitudes
    for folder, data in folder_data.items():
        lat, lon = data["average_gps"]
        latitudes.append(lat)
        longitudes.append(lon)
        map_widget.set_marker(lat, lon, text=os.path.basename(folder))  # Set marker for each folder

    # Calculate the centroid of the latitudes and longitudes
    if latitudes and longitudes:
        avg_lat = sum(latitudes) / len(latitudes)
        avg_lon = sum(longitudes) / len(longitudes)

        # Center the map on the centroid and set an appropriate zoom level
        map_widget.set_position(avg_lat, avg_lon)
        map_widget.set_zoom(6)  # Adjust zoom level as needed

# Initialize the CustomTkinter application
app = ctk.CTk()
app.geometry("700x500")  # Adjust the main window size to 500px height
app.title("SeaBee Processing App")

# Information label at the top
info_label1 = ctk.CTkLabel(app, 
                           width=600, 
                           text="Please select the 'Drone Backup' and 'SeaBee structure' folders, and fill out the config file information.", 
                           font=("Arial", 12), 
                           wraplength=650, justify="left")
info_label1.pack(pady=10)

# Variables to store folder paths and config fields
defaults = load_defaults()
folder2_var = tk.StringVar(value=defaults.get("drone_backup", "")) 
folder3_var = tk.StringVar(value=defaults.get("seabee_structure", "")) 
organisation_var = tk.StringVar(value=defaults.get("organisation", "")) 
theme_var = tk.StringVar(value=defaults.get("theme", "")) 
creator_name_var = tk.StringVar(value=defaults.get("creator_name", "")) 
project_var = tk.StringVar(value=defaults.get("project", ""))
upload_var = tk.BooleanVar(value=defaults.get("uploadbydefault", "False"))

# Folder 2 selection (Drone Backup)
folder2_frame = ctk.CTkFrame(app)
folder2_frame.pack(pady=10, fill="x", padx=20)
folder2_label = ctk.CTkLabel(folder2_frame, text="Drone Backup:", width=120)
folder2_label.pack(side="left", padx=10)
folder2_entry = ctk.CTkEntry(folder2_frame, textvariable=folder2_var, width=400)
folder2_entry.pack(side="left", padx=10)
folder2_button = ctk.CTkButton(folder2_frame, text="Browse", command=lambda: select_folder(folder2_var), width=100)
folder2_button.pack(side="left")

# Folder 3 selection (SeaBee structure)
folder3_frame = ctk.CTkFrame(app)
folder3_frame.pack(pady=10, fill="x", padx=20)
folder3_label = ctk.CTkLabel(folder3_frame, text="SeaBee structure:", width=120)
folder3_label.pack(side="left", padx=10)
folder3_entry = ctk.CTkEntry(folder3_frame, textvariable=folder3_var, width=400)
folder3_entry.pack(side="left", padx=10)
folder3_button = ctk.CTkButton(folder3_frame, text="Browse", command=lambda: select_folder(folder3_var), width=100)
folder3_button.pack(side="left")

# Information label for config file
config_label = ctk.CTkLabel(app, text="Config File Information", font=("Arial", 14))
config_label.pack(pady=5)

# Organisation input
organisation_frame = ctk.CTkFrame(app)
organisation_frame.pack(pady=5, fill="x", padx=20)
organisation_label = ctk.CTkLabel(organisation_frame, text="Organisation:", width=120)
organisation_label.pack(side="left", padx=10)
organisation_entry = ctk.CTkEntry(organisation_frame, textvariable=organisation_var, width=400)
organisation_entry.pack(side="left", padx=10)

# Theme input
theme_frame = ctk.CTkFrame(app)
theme_frame.pack(pady=5, fill="x", padx=20)
theme_label = ctk.CTkLabel(theme_frame, text="Theme:", width=120)
theme_label.pack(side="left", padx=10)
theme_entry = ctk.CTkEntry(theme_frame, textvariable=theme_var, width=400)
theme_entry.pack(side="left", padx=10)

# Creator Name input
creator_name_frame = ctk.CTkFrame(app)
creator_name_frame.pack(pady=5, fill="x", padx=20)
creator_name_label = ctk.CTkLabel(creator_name_frame, text="Creator Name:", width=120)
creator_name_label.pack(side="left", padx=10)
creator_name_entry = ctk.CTkEntry(creator_name_frame, textvariable=creator_name_var, width=400)
creator_name_entry.pack(side="left", padx=10)

# Project input
project_frame = ctk.CTkFrame(app)
project_frame.pack(pady=5, fill="x", padx=20)
project_label = ctk.CTkLabel(project_frame, text="Project:", width=120)
project_label.pack(side="left", padx=10)
project_entry = ctk.CTkEntry(project_frame, textvariable=project_var, width=400)
project_entry.pack(side="left", padx=10)

# Start Processing button at the bottom
start_button = ctk.CTkButton(app, text="Start Processing", command=start_processing, width=200)
start_button.pack(pady=40)

# Run the application
app.mainloop()