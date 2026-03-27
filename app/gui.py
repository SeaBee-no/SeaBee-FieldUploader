import datetime
import os
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk

import time

import shlex
import importlib.resources
import ctypes
import ctypes.wintypes

import yaml

APP_NAME = "SeaBee-FieldUploader"


def _is_windows_store_python() -> bool:
    if not sys.platform.startswith("win"):
        return False
    exe = (sys.executable or "").replace("/", "\\").lower()
    return (
        "\\windowsapps\\" in exe
        or "pythonsoftwarefoundation.python" in exe
        or "\\appdata\\local\\packages\\pythonsoftwarefoundation.python" in exe
    )


def _get_windows_log_base() -> str:
    return os.path.join("C:\\", "log", APP_NAME)


def _get_windows_log_config_dir() -> str:
    return os.path.join(_get_windows_log_base(), "config")


def _get_windows_store_cache_roaming_base() -> str | None:
    localappdata = os.environ.get("LOCALAPPDATA")
    if not localappdata:
        return None

    packages_dir = os.path.join(localappdata, "Packages")
    if not os.path.isdir(packages_dir):
        return None

    exe = (sys.executable or "").replace("/", "\\")
    exe_lower = exe.lower()

    preferred_pkg: str | None = None
    marker = "\\packages\\"
    idx = exe_lower.find(marker)
    if idx != -1:
        rest = exe[idx + len(marker) :]
        preferred_pkg = rest.split("\\", 1)[0]

    # Prefer the package referenced by sys.executable if possible.
    candidates: list[str] = []
    if preferred_pkg and preferred_pkg.lower().startswith("pythonsoftwarefoundation.python"):
        candidates.append(preferred_pkg)

    try:
        for entry in os.listdir(packages_dir):
            if not entry.lower().startswith("pythonsoftwarefoundation.python"):
                continue
            if entry not in candidates:
                candidates.append(entry)
    except Exception:
        return None

    for pkg in candidates:
        base = os.path.join(packages_dir, pkg, "LocalCache", "Roaming")
        # The folder may not exist until something writes to it.
        if os.path.isdir(os.path.join(packages_dir, pkg)):
            return base

    return None


def _is_windows_store_python_roaming(path: str | None) -> bool:
    if not path:
        return False
    p = path.replace("/", "\\").lower()
    return "\\appdata\\local\\packages\\" in p and "\\localcache\\roaming" in p


def _get_windows_real_roaming_base() -> str:
    userprofile = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    return os.path.join(userprofile, "AppData", "Roaming")


def _get_windows_env_roaming_base() -> str:
    base = os.environ.get("APPDATA")
    if base:
        return base
    return _get_windows_real_roaming_base()


def _get_user_config_dir_windows() -> str:
    # Allow explicit override (useful for debugging / locked-down environments).
    override = os.environ.get("SEABEE_CONFIG_DIR")
    if override:
        return override

    # Microsoft Store Python can silently redirect writes to Roaming into LocalCache.
    # Embrace that and use the cache path directly so users can actually find the files.
    if _is_windows_store_python():
        cache_base = _get_windows_store_cache_roaming_base()
        if cache_base:
            return os.path.join(cache_base, APP_NAME)

    env_base = _get_windows_env_roaming_base()

    # Microsoft Store Python often redirects APPDATA to a per-package LocalCache\Roaming.
    # Prefer the real profile roaming folder in that case, so config is visible and stable.
    if _is_windows_store_python_roaming(env_base):
        return os.path.join(_get_windows_real_roaming_base(), APP_NAME)

    return os.path.join(env_base, APP_NAME)


def _migrate_config_dir_if_needed() -> None:
    if not sys.platform.startswith("win"):
        return

    if not _is_windows_store_python():
        return

    new_dir = get_user_config_dir()
    if not _safe_makedirs(new_dir):
        log_debug(f"Config migration skipped: cannot create {new_dir}")
        return

    candidates: list[str] = []

    # Candidate 1: normal Roaming target (what we'd expect on non-Store Python)
    candidates.append(os.path.join(_get_windows_real_roaming_base(), APP_NAME))

    # Candidate 2: whatever APPDATA points to
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(os.path.join(appdata, APP_NAME))

    # Candidate 3: Store package LocalCache\Roaming
    try:
        localappdata = os.environ.get("LOCALAPPDATA")
        if localappdata:
            packages_dir = os.path.join(localappdata, "Packages")
            if os.path.isdir(packages_dir):
                for entry in os.listdir(packages_dir):
                    if not entry.lower().startswith("pythonsoftwarefoundation.python"):
                        continue
                    candidates.append(os.path.join(packages_dir, entry, "LocalCache", "Roaming", APP_NAME))
    except Exception as e:
        log_debug(f"Migration scan failed: {e}")

    # Deduplicate
    seen: set[str] = set()
    unique_candidates: list[str] = []
    for c in candidates:
        key = os.path.normcase(os.path.abspath(c))
        if key in seen:
            continue
        seen.add(key)
        unique_candidates.append(c)

    for old_dir in unique_candidates:
        if not os.path.isdir(old_dir):
            continue
        if os.path.normcase(os.path.abspath(old_dir)) == os.path.normcase(os.path.abspath(new_dir)):
            continue
        log_debug(f"Config migration: old={old_dir} new={new_dir}")
        for name in ["defaults.txt", "rclone.conf", "bucket.conf", "rclone.exe"]:
            src = os.path.join(old_dir, name)
            dst = os.path.join(new_dir, name)
            try:
                if not os.path.isfile(src):
                    continue
                if os.path.isfile(dst):
                    continue
                shutil.copyfile(src, dst)
                log_debug(f"Migrated {name}: {src} -> {dst}")
            except Exception as e:
                log_debug(f"Migration failed for {name}: {e}")


def _safe_makedirs(path: str) -> bool:
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except Exception:
        return False


def _debug_log_path() -> str | None:
    # Easy-to-find location for field debugging.
    if sys.platform.startswith("win"):
        try:
            c_log_dir = _get_windows_log_base()
            if _safe_makedirs(c_log_dir):
                return os.path.join(c_log_dir, "debug.log")
        except Exception:
            pass

    # Best-effort: write to the per-user config dir. If that fails, fall back to temp.
    try:
        cfg_dir = get_user_config_dir()
        if _safe_makedirs(cfg_dir):
            return os.path.join(cfg_dir, "debug.log")
    except Exception:
        pass

    try:
        tmp = os.environ.get("TEMP") or os.environ.get("TMP")
        if tmp and _safe_makedirs(tmp):
            return os.path.join(tmp, "seabee-fielduploader-debug.log")
    except Exception:
        pass

    return None


def log_debug(message: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {message}"
    try:
        print(line, flush=True)
    except Exception:
        pass

    path = _debug_log_path()
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

DEFAULT_REMOTE_NAME = "minio"
DEFAULT_BUCKET_NAME = "fielduploads"
DEFAULT_OBJECT_PREFIX = "seabirds/"  # Remote path inside bucket


def safe_load_yaml(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def count_files_in_folder(folder_path: str, yaml_filename: str) -> int:
    n = 0
    try:
        for name in os.listdir(folder_path):
            full = os.path.join(folder_path, name)
            if os.path.isfile(full) and name != yaml_filename:
                if name.lower() == "thumbs.db":
                    continue
                n += 1
    except Exception:
        pass
    return n


def get_own_file_path(filename: str | None = None) -> str:
    if getattr(sys, "frozen", False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(base_path, filename) if filename else base_path


def get_app_root_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir))


def get_resources_dir() -> str:
    return os.path.join(get_app_root_dir(), "resources")


def get_icon_path() -> str:
    return os.path.join(get_resources_dir(), "seabee.ico")


def get_legacy_or_app_icon_path() -> str:
    # Current repo layout: app/seabee.ico
    return os.path.join(get_app_root_dir(), "app", "seabee.ico")


def _try_set_windows_appusermodel_id(app_id: str) -> None:
    if not sys.platform.startswith("win"):
        return
    try:
        shell32 = ctypes.windll.shell32
        set_id = getattr(shell32, "SetCurrentProcessExplicitAppUserModelID", None)
        if set_id is None:
            return
        set_id.argtypes = [ctypes.wintypes.LPCWSTR]
        set_id.restype = ctypes.c_long
        set_id(app_id)
    except Exception as e:
        print(f"[SeaBee FieldUploader] AppUserModelID failed: {e}", flush=True)


def _try_set_windows_taskbar_icon(root: tk.Tk, icon_path: str) -> bool:
    if not sys.platform.startswith("win"):
        return False
    try:
        root.update_idletasks()
        hwnd = root.winfo_id()
        if not hwnd:
            return False

        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1

        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x0010

        user32 = ctypes.windll.user32

        LoadImageW = user32.LoadImageW
        LoadImageW.argtypes = [
            ctypes.wintypes.HINSTANCE,
            ctypes.wintypes.LPCWSTR,
            ctypes.wintypes.UINT,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.wintypes.UINT,
        ]
        LoadImageW.restype = ctypes.wintypes.HANDLE

        SendMessageW = user32.SendMessageW
        SendMessageW.argtypes = [
            ctypes.wintypes.HWND,
            ctypes.wintypes.UINT,
            ctypes.wintypes.WPARAM,
            ctypes.wintypes.LPARAM,
        ]
        SendMessageW.restype = ctypes.wintypes.LPARAM

        # size=0,0 lets Windows pick the best icon size from the .ico
        hicon = LoadImageW(None, icon_path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE)
        if not hicon:
            return False

        # Keep a reference to avoid premature cleanup; we intentionally don't DestroyIcon
        # because Tk/Windows may still be using it.
        if not hasattr(root, "_seabee_hicons"):
            root._seabee_hicons = []  # type: ignore[attr-defined]
        root._seabee_hicons.append(hicon)  # type: ignore[attr-defined]

        SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon)
        SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon)
        return True
    except Exception as e:
        print(f"[SeaBee FieldUploader] Windows taskbar icon failed: {e}", flush=True)
        return False


def set_window_icon(root: tk.Tk) -> None:
    icon_candidates: list[str] = []

    # 1) Legacy/zip/source runs: top-level resources/ (older layout)
    icon_candidates.append(get_icon_path())

    # 2) Current repo layout: app/seabee.ico
    icon_candidates.append(get_legacy_or_app_icon_path())

    # 3) For uvx/pip installs: package data under the app package
    try:
        icon_res = importlib.resources.files("app").joinpath("seabee.ico")
        if icon_res.is_file():
            with importlib.resources.as_file(icon_res) as icon_file:
                icon_candidates.append(str(icon_file))
    except Exception as e:
        log_debug(f"Icon discovery failed: {e}")

    for path in icon_candidates:
        try:
            if path and os.path.isfile(path):
                root.iconbitmap(path)
                _try_set_windows_taskbar_icon(root, path)
                return
        except Exception as e:
            log_debug(f"Failed to set icon from {path!r}: {e}")


DEFAULTS_TEMPLATE_TEXT = """# defaults.txt
theme=Seabirds
organisation=NINA
creator_name=
project=SEAPOP 3B - Kartlegging av hekkebestander
"""

RCLONE_TEMPLATE_TEXT = """# Template rclone config for SeaBee FieldUploader
#
# Fill in the values below.

[minio]
type = s3
provider = Minio
env_auth = false
access_key_id = <ACCESS_KEY_ID>
secret_access_key = <SECRET_ACCESS_KEY>
endpoint = https://<MINIO_HOST>
"""

BUCKET_TEMPLATE_TEXT = f"""# bucket.conf
# Controls where uploads go in rclone.
#
# Keys are case-insensitive.

REMOTE_NAME={DEFAULT_REMOTE_NAME}
BUCKET_NAME={DEFAULT_BUCKET_NAME}
OBJECT_PREFIX={DEFAULT_OBJECT_PREFIX}
"""


def get_user_config_dir() -> str:
    if sys.platform.startswith("win"):
        return _get_user_config_dir_windows()

    base = os.environ.get("XDG_CONFIG_HOME")
    if not base:
        base = os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "seabee-fielduploader")


def open_file_for_edit(path: str) -> None:
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
        return
    # Best-effort for mac/linux
    try:
        subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


def ensure_appdata_file(filename: str, template_filename: str | None) -> str:
    target_dir = get_user_config_dir()
    _safe_makedirs(target_dir)

    target_path = os.path.join(target_dir, filename)
    if os.path.isfile(target_path):
        log_debug(f"Config exists: {target_path}")
        return target_path

    if template_filename:
        template_path = os.path.join(get_resources_dir(), template_filename)
        if os.path.isfile(template_path):
            try:
                shutil.copyfile(template_path, target_path)
                log_debug(f"Config created from template: {target_path} (template={template_path})")
                return target_path
            except Exception as e:
                log_debug(f"Failed copying template to {target_path}: {e}")

    try:
        with open(target_path, "w", encoding="utf-8") as f:
            if filename.lower() == "defaults.txt":
                f.write(DEFAULTS_TEMPLATE_TEXT)
            elif filename.lower() == "rclone.conf":
                f.write(RCLONE_TEMPLATE_TEXT)
            elif filename.lower() == "bucket.conf":
                f.write(BUCKET_TEMPLATE_TEXT)
            else:
                f.write("")
        log_debug(f"Config created (embedded template): {target_path}")
    except Exception as e:
        log_debug(f"Failed writing {target_path}: {e}")
    return target_path


def bootstrap_appdata_files() -> None:
    _migrate_config_dir_if_needed()
    log_debug("Bootstrapping per-user config files")
    log_debug(f"APPDATA={os.environ.get('APPDATA')!r} USERPROFILE={os.environ.get('USERPROFILE')!r}")
    if sys.platform.startswith("win"):
        log_debug(f"windows store python: {_is_windows_store_python()}")
        log_debug(f"windows env roaming base: {_get_windows_env_roaming_base()}")
        log_debug(f"windows real roaming base: {_get_windows_real_roaming_base()}")
        log_debug(f"windows store cache roaming base: {_get_windows_store_cache_roaming_base()!r}")
        log_debug(f"windows log base: {_get_windows_log_base()}")
    log_debug(f"User config dir: {get_user_config_dir()}")
    log_debug(f"App root dir: {get_app_root_dir()}")
    log_debug(f"Resources dir: {get_resources_dir()}")

    # Create files on first startup to make them easy to find/edit.
    ensure_appdata_file("defaults.txt", "defaults.txt")
    ensure_appdata_file("rclone.conf", "rclone.conf.template")
    ensure_appdata_file("bucket.conf", "bucket.conf.template")


def write_diagnostics_snapshot() -> None:
    cfg_dir = get_user_config_dir()
    log_debug("--- Diagnostics snapshot ---")
    log_debug(f"cwd={os.getcwd()}")
    log_debug(f"os.name={os.name} sys.platform={sys.platform}")
    log_debug(f"sys.version={sys.version.replace(os.linesep, ' ')}")
    log_debug(f"sys.executable={sys.executable}")
    log_debug(f"frozen={getattr(sys, 'frozen', False)}")
    log_debug(
        "env "
        + " ".join(
            [
                f"APPDATA={os.environ.get('APPDATA')!r}",
                f"LOCALAPPDATA={os.environ.get('LOCALAPPDATA')!r}",
                f"USERPROFILE={os.environ.get('USERPROFILE')!r}",
                f"XDG_CONFIG_HOME={os.environ.get('XDG_CONFIG_HOME')!r}",
            ]
        )
    )
    log_debug(f"get_user_config_dir()={cfg_dir}")
    for name in ["defaults.txt", "rclone.conf", "bucket.conf"]:
        p = os.path.join(cfg_dir, name)
        try:
            exists = os.path.isfile(p)
            size = os.path.getsize(p) if exists else 0
            log_debug(f"file {name}: exists={exists} path={p} size={size}")
        except Exception as e:
            log_debug(f"file {name}: error checking {p}: {e}")

    try:
        if os.path.isdir(cfg_dir):
            items = sorted(os.listdir(cfg_dir))
            log_debug(f"config dir listing ({cfg_dir}): {items}")
        else:
            log_debug(f"config dir missing: {cfg_dir}")
    except Exception as e:
        log_debug(f"config dir listing failed: {e}")


def parse_kv_file(path: str) -> dict[str, str]:
    data: dict[str, str] = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                data[k.strip().lower()] = v.strip()
    except Exception:
        pass
    return data


def load_bucket_config() -> tuple[str, str, str]:
    path = ensure_appdata_file("bucket.conf", "bucket.conf.template")
    cfg = parse_kv_file(path)
    remote = cfg.get("remote_name", DEFAULT_REMOTE_NAME)
    bucket = cfg.get("bucket_name", DEFAULT_BUCKET_NAME)
    prefix = cfg.get("object_prefix", DEFAULT_OBJECT_PREFIX)
    if prefix and not prefix.endswith("/"):
        prefix = prefix + "/"
    return remote, bucket, prefix


def format_command_for_display(argv: list[str]) -> str:
    if sys.platform.startswith("win"):
        return subprocess.list2cmdline(argv)
    return shlex.join(argv)


def resolve_rclone_exe() -> str | None:
    env_path = os.environ.get("SEABEE_RCLONE_EXE") or os.environ.get("RCLONE_EXE")
    if env_path and os.path.isfile(env_path):
        return env_path

    local_name = "rclone.exe" if sys.platform.startswith("win") else "rclone"

    # Prefer per-user app directory
    appdata_candidate = os.path.join(get_user_config_dir(), local_name)
    if os.path.isfile(appdata_candidate):
        return appdata_candidate

    # Next to EXE / in app root
    app_root_candidate = os.path.join(get_app_root_dir(), local_name)
    if os.path.isfile(app_root_candidate):
        return app_root_candidate

    which = shutil.which(local_name) or shutil.which("rclone")
    return which


def resolve_rclone_conf() -> str | None:
    env_path = os.environ.get("SEABEE_RCLONE_CONFIG") or os.environ.get("RCLONE_CONFIG")
    if env_path and os.path.isfile(env_path):
        return env_path

    candidates: list[str] = []

    # Preferred: app-specific config dir
    candidates.append(os.path.join(get_user_config_dir(), "rclone.conf"))

    # Standard rclone config locations
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if appdata:
            candidates.append(os.path.join(appdata, "rclone", "rclone.conf"))
    else:
        candidates.append(os.path.join(os.path.expanduser("~"), ".config", "rclone", "rclone.conf"))

    # Legacy: next to EXE / app root
    candidates.append(os.path.join(get_app_root_dir(), "rclone.conf"))

    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def resolve_defaults_path() -> str:
    # Always use per-user config path for defaults
    return os.path.join(get_user_config_dir(), "defaults.txt")


def parse_defaults_file(path: str) -> dict:
    defs: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    defs[k.strip()] = v.strip()
    except Exception:
        pass
    return defs


def write_defaults_file(path: str, theme: str, organisation: str, creator_name: str, project: str) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("# defaults.txt\n")
            f.write(f"theme={theme}\n")
            f.write(f"organisation={organisation}\n")
            f.write(f"creator_name={creator_name}\n")
            f.write(f"project={project}\n")
        try:
            exists = os.path.isfile(path)
            size = os.path.getsize(path) if exists else 0
            log_debug(f"defaults write ok: path={path} exists={exists} size={size}")
        except Exception as e:
            log_debug(f"defaults write ok but stat failed: path={path} err={e}")
    except Exception as e:
        log_debug(f"defaults write FAILED: path={path} err={e}")
        raise


def ensure_defaults_ready() -> dict:
    defaults_path = resolve_defaults_path()
    if not os.path.isfile(defaults_path):
        ensure_appdata_file("defaults.txt", "defaults.txt")
    return parse_defaults_file(defaults_path)


class S3UploaderApp(ttk.Frame):
    def __init__(self, master: tk.Tk):
        super().__init__(master, padding=15)
        self.grid(sticky="NSEW")
        master.title("SeaBee FieldUploader")
        master.resizable(False, False)
        master.maxsize(650, master.winfo_screenheight())

        style = ttk.Style(master)
        style.theme_use("clam")
        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("TEntry", padding=4)
        style.configure("TButton", padding=6)

        self.remote_name, self.bucket_name, self.object_prefix = load_bucket_config()

        defs = ensure_defaults_ready()
        theme_default = defs.get("theme", "Seabirds")
        org_default = defs.get("organisation", "NINA")
        creator_default = defs.get("creator_name", "")
        project_default = defs.get("project", "")

        self.theme_var = tk.StringVar(master=self, value=theme_default)
        self.org_var = tk.StringVar(master=self, value=org_default)
        self.creator_var = tk.StringVar(master=self, value=creator_default)
        self.project_var = tk.StringVar(master=self, value=project_default)

        fields = [
            ("Theme:", self.theme_var),
            ("Organisation:", self.org_var),
            ("Creator name:", self.creator_var),
            ("Project:", self.project_var),
        ]
        for i, (lbl, var) in enumerate(fields):
            ttk.Label(self, text=lbl).grid(row=i, column=0, sticky="E", pady=4)
            ttk.Entry(self, textvariable=var, width=45).grid(
                row=i, column=1, columnspan=2, sticky="EW", pady=4
            )

        ttk.Button(self, text="Edit defaults.txt", command=self.edit_defaults).grid(
            row=4, column=0, sticky="W", pady=(6, 0)
        )
        ttk.Button(self, text="Save as defaults", command=self.save_defaults).grid(
            row=4, column=1, sticky="W", pady=(6, 0)
        )
        ttk.Button(self, text="Edit rclone.conf", command=self.edit_rclone_conf).grid(
            row=4, column=2, sticky="E", pady=(6, 0)
        )

        ttk.Label(self, text="Folder to upload:").grid(row=5, column=0, sticky="E", pady=(12, 4))
        self.folder_var = tk.StringVar(master=self)
        ttk.Entry(self, textvariable=self.folder_var, width=45).grid(
            row=5, column=1, sticky="EW", pady=(12, 4)
        )
        ttk.Button(self, text="Browse…", command=self.select_folder).grid(
            row=5, column=2, padx=5, pady=(12, 4)
        )

        ttk.Button(self, text="Upload to S3", command=self.start_upload).grid(
            row=6, column=1, pady=(10, 0)
        )

        self.status_var = tk.StringVar(master=self, value="Idle")
        self.speed_var = tk.StringVar(master=self, value="")
        self.eta_var = tk.StringVar(master=self, value="")

        ttk.Label(self, textvariable=self.status_var, wraplength=620).grid(
            row=7, column=0, columnspan=3, sticky="W", pady=(15, 2)
        )
        ttk.Label(self, textvariable=self.speed_var, wraplength=620).grid(
            row=8, column=0, columnspan=3, sticky="W"
        )
        ttk.Label(self, textvariable=self.eta_var, wraplength=620).grid(
            row=9, column=0, columnspan=3, sticky="W"
        )

        self.columnconfigure(1, weight=1)

        self._rclone_exe: str | None = None
        self._rclone_conf: str | None = None

    def save_defaults(self) -> None:
        defaults_path = ensure_appdata_file("defaults.txt", "defaults.txt")
        write_defaults_file(
            defaults_path,
            theme=self.theme_var.get(),
            organisation=self.org_var.get(),
            creator_name=self.creator_var.get(),
            project=self.project_var.get(),
        )
        messagebox.showinfo("Defaults saved", f"Saved defaults to:\n{defaults_path}")

    def edit_defaults(self) -> None:
        defaults_path = ensure_appdata_file("defaults.txt", "defaults.txt")
        try:
            open_file_for_edit(defaults_path)
        except Exception as e:
            messagebox.showerror("Open failed", f"Could not open defaults.txt: {e}")

    def edit_rclone_conf(self) -> None:
        conf_path = ensure_appdata_file("rclone.conf", "rclone.conf.template")
        try:
            open_file_for_edit(conf_path)
        except Exception as e:
            messagebox.showerror("Open failed", f"Could not open rclone.conf: {e}")

    def select_folder(self) -> None:
        fld = filedialog.askdirectory()
        if fld:
            self.folder_var.set(fld)

    def ensure_rclone_ready(self) -> bool:
        rclone_exe = resolve_rclone_exe()
        if not rclone_exe:
            messagebox.showerror(
                "Missing rclone",
                "Could not find rclone executable.\n\n"
                "Fix one of these:\n"
                "- Place rclone.exe next to the program\n"
                "- Copy rclone.exe to %APPDATA%\\SeaBee-FieldUploader\\rclone.exe\n"
                "- Put rclone on PATH\n"
                "- Set SEABEE_RCLONE_EXE to the full path",
            )
            return False

        rclone_conf = resolve_rclone_conf()
        if not rclone_conf:
            conf_path = ensure_appdata_file("rclone.conf", "rclone.conf.template")
            try:
                open_file_for_edit(conf_path)
            except Exception:
                pass

            messagebox.showinfo(
                "Edit rclone.conf",
                "A new rclone.conf was created from the template.\n\n"
                "Please fill in the credentials, save the file, then click Upload again.",
            )
            return False

        self._rclone_exe = rclone_exe
        self._rclone_conf = rclone_conf
        return True

    def start_upload(self) -> None:
        fld = self.folder_var.get().strip()
        if not fld or not os.path.isdir(fld):
            messagebox.showwarning("Select Folder", "Please choose a valid folder first.")
            return

        if not self.ensure_rclone_ready():
            return

        threading.Thread(target=self.upload_folder, args=(fld,), daemon=True).start()

    def run_rclone_with_progress(self, source: str, dest: str, include_yaml_only: bool = False) -> None:
        if not self._rclone_exe or not self._rclone_conf:
            raise RuntimeError("rclone not initialized")

        command = [
            self._rclone_exe,
            "copy",
            source,
            dest,
            "--config",
            self._rclone_conf,
            "--progress",
            "--exclude",
            "$RECYCLE.BIN/**",
        ]
        if include_yaml_only:
            command += ["--include", "*.yaml"]

        print(
            "\n[SeaBee FieldUploader] Running rclone command:\n" + format_command_for_display(command) + "\n",
            flush=True,
        )

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        assert process.stdout is not None
        for line in process.stdout:
            line = line.strip()
            match = re.search(
                r"Transferred:\s+([\d.]+\s\w+)\s*/\s*([\d.]+\s\w+),.*?([\d.]+\s\w+/s),\s*ETA\s*([\dhms]+)",
                line,
            )
            if match:
                transferred = match.group(1)
                total = match.group(2)
                speed = match.group(3)
                eta = match.group(4)
                self.speed_var.set(f"Speed: {speed}")
                self.eta_var.set(f"ETA: {eta}")
                self.status_var.set(f"Transferred: {transferred} / {total}")

            if os.environ.get("SEABEE_RCLONE_DEBUG"):
                print(line, flush=True)

        process.wait()

        if process.returncode and process.returncode != 0:
            raise RuntimeError(f"rclone failed with exit code {process.returncode}")

    def upload_folder(self, folder: str) -> None:
        try:
            files_at_root = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
            if files_at_root:
                ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                pkg_name = f"fielduploader_upload_{ts}"
                pkg_path = os.path.join(folder, pkg_name)
                os.makedirs(pkg_path, exist_ok=True)
                for fname in files_at_root:
                    shutil.move(os.path.join(folder, fname), os.path.join(pkg_path, fname))

            yaml_filename = "fielduploads.seabee.yaml"
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

            base_meta = {
                "theme": self.theme_var.get(),
                "organisation": self.org_var.get(),
                "creator_name": self.creator_var.get(),
                "project": self.project_var.get(),
            }

            for root, dirs, files in os.walk(folder):
                if os.path.abspath(root) == os.path.abspath(folder):
                    continue

                if "$RECYCLE.BIN" in root.upper():
                    continue

                nfiles = count_files_in_folder(root, yaml_filename)
                if nfiles == 0:
                    continue

                yaml_path = os.path.join(root, yaml_filename)

                existing = safe_load_yaml(yaml_path) if os.path.exists(yaml_path) else {}
                old_nfiles = existing.get("nfiles")

                if os.path.exists(yaml_path) and old_nfiles == nfiles:
                    continue

                meta = dict(base_meta)
                meta["nfiles"] = nfiles
                meta["lastupdated"] = now_iso

                yaml_text = yaml.dump(meta, sort_keys=False, allow_unicode=True)
                with open(yaml_path, "w", encoding="utf-8") as yf:
                    yf.write(yaml_text)

            self.status_var.set("Uploading YAML config files via rclone…")
            self.run_rclone_with_progress(
                folder,
                f"{self.remote_name}:{self.bucket_name}/{self.object_prefix}",
                include_yaml_only=True,
            )

            self.status_var.set("Uploading all files via rclone…")
            self.run_rclone_with_progress(
                folder,
                f"{self.remote_name}:{self.bucket_name}/{self.object_prefix}",
                include_yaml_only=False,
            )

            self.status_var.set("✅ Upload complete.")
            messagebox.showinfo("Upload Complete", "All files uploaded successfully via rclone.")
        except Exception as e:
            self.status_var.set("❌ Upload failed.")
            try:
                messagebox.showerror("Upload Failed", f"Upload failed.\n\n{e}")
            except Exception:
                pass


def main() -> None:
    # Establish log destination early; helps when config resolution is broken.
    log_debug(f"debug log path: {_debug_log_path()!r}")
    bootstrap_appdata_files()
    write_diagnostics_snapshot()

    # Helps Windows taskbar grouping + icon behavior when running via python/pythonw.
    _try_set_windows_appusermodel_id("NINA.SeaBee.FieldUploader")

    root = tk.Tk()
    set_window_icon(root)
    S3UploaderApp(root)

    # Re-apply once after the window is mapped; this often fixes taskbar icon.
    root.after(200, lambda: set_window_icon(root))
    root.mainloop()
