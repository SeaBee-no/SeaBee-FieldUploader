import os
import sys
import time
import threading
import datetime
import shutil
import yaml
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import subprocess
import re

# ─── CONFIGURATION ─────────────────────────────────────────────────────────────
REMOTE_NAME    = 'minio'
BUCKET_NAME    = 'fielduploads'
OBJECT_PREFIX  = 'seabirds/'  # ← Remote path inside bucket
# ───────────────────────────────────────────────────────────────────────────────

def safe_load_yaml(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def count_files_in_folder(folder_path: str, yaml_filename: str) -> int:
    # Count only files directly in this folder (not recursive), excluding the metadata YAML itself
    n = 0
    try:
        for name in os.listdir(folder_path):
            full = os.path.join(folder_path, name)
            if os.path.isfile(full) and name != yaml_filename:
                # Optional: skip Windows recycle bin artifacts if they show up
                if name.lower() == "thumbs.db":
                    continue
                n += 1
    except Exception:
        pass
    return n

def get_own_file_path(filename=None, from_parent=False):
    if getattr(sys, 'frozen', False):
        # If running from a bundled executable
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.realpath(__file__))

    if from_parent:
        base_path = os.path.abspath(os.path.join(base_path, os.pardir))

    return os.path.join(base_path, filename) if filename else base_path

def load_defaults():
    path = get_own_file_path('defaults.txt', from_parent=False)
    defs = {}
    if os.path.isfile(path):
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    k, v = line.split('=', 1)
                    defs[k.strip()] = v.strip()
    return defs

__defaults      = load_defaults()
THEME_DEFAULT   = __defaults.get('theme', 'Seabirds')
ORG_DEFAULT     = __defaults.get('organisation', 'NINA')
CREATOR_DEFAULT = __defaults.get('creator_name', '')
PROJECT_DEFAULT = __defaults.get('project', '')

class S3UploaderApp(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=15)
        self.grid(sticky="NSEW")
        master.title("SeaBee FieldUploader")
        master.resizable(False, False)
        master.maxsize(600, master.winfo_screenheight())

        style = ttk.Style(master)
        style.theme_use('clam')
        style.configure('TLabel', font=('Segoe UI', 10))
        style.configure('TEntry', padding=4)
        style.configure('TButton', padding=6)

        self.theme_var   = tk.StringVar(master=self, value=THEME_DEFAULT)
        self.org_var     = tk.StringVar(master=self, value=ORG_DEFAULT)
        self.creator_var = tk.StringVar(master=self, value=CREATOR_DEFAULT)
        self.project_var = tk.StringVar(master=self, value=PROJECT_DEFAULT)

        fields = [
            ("Theme:",        self.theme_var),
            ("Organisation:", self.org_var),
            ("Creator name:", self.creator_var),
            ("Project:",      self.project_var),
        ]
        for i, (lbl, var) in enumerate(fields):
            ttk.Label(self, text=lbl).grid(row=i, column=0, sticky='E', pady=4)
            ttk.Entry(self, textvariable=var, width=40)\
               .grid(row=i, column=1, columnspan=2, sticky='EW', pady=4)

        ttk.Label(self, text="Folder to upload:")\
           .grid(row=4, column=0, sticky='E', pady=(10,4))
        self.folder_var = tk.StringVar(master=self)
        ttk.Entry(self, textvariable=self.folder_var, width=40)\
           .grid(row=4, column=1, sticky='EW', pady=(10,4))
        ttk.Button(self, text="Browse…", command=self.select_folder)\
           .grid(row=4, column=2, padx=5, pady=(10,4))

        ttk.Button(self, text="Upload to S3", command=self.start_upload)\
           .grid(row=5, column=1, pady=(10,0))

        self.status_var = tk.StringVar(master=self, value="Idle")
        self.speed_var  = tk.StringVar(master=self, value="")
        self.eta_var    = tk.StringVar(master=self, value="")

        ttk.Label(self, textvariable=self.status_var, wraplength=580)\
           .grid(row=6, column=0, columnspan=3, sticky='W', pady=(15,2))
        ttk.Label(self, textvariable=self.speed_var, wraplength=580)\
           .grid(row=7, column=0, columnspan=3, sticky='W')
        ttk.Label(self, textvariable=self.eta_var, wraplength=580)\
           .grid(row=8, column=0, columnspan=3, sticky='W')

        self.columnconfigure(1, weight=1)

    def select_folder(self):
        fld = filedialog.askdirectory()
        if fld:
            self.folder_var.set(fld)

    def start_upload(self):
        fld = self.folder_var.get().strip()
        if not fld or not os.path.isdir(fld):
            messagebox.showwarning("Select Folder", "Please choose a valid folder first.")
            return
        threading.Thread(target=self.upload_folder, args=(fld,), daemon=True).start()

    def run_rclone_with_progress(self, source, dest, include_yaml_only=False):
        rclone_exe = os.path.join(get_own_file_path(), 'rclone.exe')
        rclone_conf = os.path.join(get_own_file_path(), 'rclone.conf')

        command = [
            rclone_exe,
            'copy',
            source,
            dest,
            '--config', rclone_conf,
            '--progress',
            '--exclude', '$RECYCLE.BIN/**'
        ]
        if include_yaml_only:
            command += ['--include', '*.yaml']
        
        print(f"Running command: {' '.join(command)}")

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        for line in process.stdout:
            line = line.strip()
            match = re.search(
                r'Transferred:\s+([\d.]+\s\w+)\s*/\s*([\d.]+\s\w+),.*?([\d.]+\s\w+/s),\s*ETA\s*([\dhms]+)',
                line
            )
            if match:
                transferred = match.group(1)
                total = match.group(2)
                speed = match.group(3)
                eta = match.group(4)
                self.speed_var.set(f"Speed: {speed}")
                self.eta_var.set(f"ETA: {eta}")
                self.status_var.set(f"Transferred: {transferred} / {total}")

        process.wait()

    def upload_folder(self, folder):
        # Package root files into subfolder if needed
        files_at_root = [
            f for f in os.listdir(folder)
            if os.path.isfile(os.path.join(folder, f))
        ]
        if files_at_root:
            ts = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
            pkg_name = f'fielduploader_upload_{ts}'
            pkg_path = os.path.join(folder, pkg_name)
            os.makedirs(pkg_path, exist_ok=True)
            for fname in files_at_root:
                shutil.move(
                    os.path.join(folder, fname),
                    os.path.join(pkg_path, fname)
                )

        # Write per-folder YAML metadata
        yaml_filename = 'fielduploads.seabee.yaml'
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        base_meta = {
            'theme':         self.theme_var.get(),
            'organisation':  self.org_var.get(),
            'creator_name':  self.creator_var.get(),
            'project':       self.project_var.get()
        }

        for root, dirs, files in os.walk(folder):
            # skip the selected top folder itself (your current behavior)
            if os.path.abspath(root) == os.path.abspath(folder):
                continue

            # skip recycle bin paths
            if '$RECYCLE.BIN' in root.upper():
                continue

            # Count files directly in this folder (excluding the YAML itself)
            nfiles = count_files_in_folder(root, yaml_filename)

            # Only create/update YAML for folders that actually have content
            if nfiles == 0:
                continue

            yaml_path = os.path.join(root, yaml_filename)

            existing = safe_load_yaml(yaml_path) if os.path.exists(yaml_path) else {}
            old_nfiles = existing.get('nfiles')

            # If YAML exists and nfiles hasn't changed, do not rewrite (preserve lastupdated)
            if os.path.exists(yaml_path) and old_nfiles == nfiles:
                continue

            # If we're writing now:
            meta = dict(base_meta)
            meta['nfiles'] = nfiles

            # Preserve old lastupdated if present AND nfiles unchanged (handled above).
            # Otherwise update lastupdated to now.
            meta['lastupdated'] = now_iso

            yaml_text = yaml.dump(meta, sort_keys=False, allow_unicode=True)
            with open(yaml_path, 'w', encoding='utf-8') as yf:
                yf.write(yaml_text)


        # Upload using rclone
        self.status_var.set("Uploading YAML config files via rclone…")
        self.run_rclone_with_progress(folder, f"{REMOTE_NAME}:{BUCKET_NAME}/{OBJECT_PREFIX}", include_yaml_only=True)

        self.status_var.set("Uploading all files via rclone…")
        self.run_rclone_with_progress(folder, f"{REMOTE_NAME}:{BUCKET_NAME}/{OBJECT_PREFIX}", include_yaml_only=False)

        self.status_var.set("✅ Upload complete.")
        messagebox.showinfo("Upload Complete", "All files uploaded successfully via rclone.")


if __name__ == "__main__":
    root = tk.Tk()
    try:
        root.iconbitmap(get_own_file_path('seabee.ico'))
    except Exception as e:
        print(f"Error loading icon: {e}")

    S3UploaderApp(root)
    root.mainloop()
