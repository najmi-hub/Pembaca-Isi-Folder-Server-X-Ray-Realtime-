import os
import time
import logging
import threading
from pathlib import Path
from datetime import datetime, timedelta, timezone
from logging.handlers import TimedRotatingFileHandler
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import mysql.connector

# ==========================================
# KONFIGURASI DATABASE PC DASHBOARD
# ==========================================
DB_CONFIG = {
    "host": "192.111.111.69",
    "user": "root",
    "password": "Mitra01!",
    "database": "Dashboard",
    "port": 3306,
    "ssl_disabled": True
}

try:
    JAKARTA_TZ = ZoneInfo("Asia/Jakarta")
except ZoneInfoNotFoundError:
    JAKARTA_TZ = timezone(timedelta(hours=7))


class JakartaFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=JAKARTA_TZ)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.isoformat(timespec="seconds")


# ==========================================
# LOGGING MINGGUAN (RETENSI 12 MINGGU / 3 BULAN)
# ==========================================
APP_DIR = Path(__file__).parent.resolve()
LOG_DIR = APP_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "image_watcher.log"

logger = logging.getLogger("ImageWatcher")
logger.setLevel(logging.INFO)

file_handler = TimedRotatingFileHandler(
    filename=LOG_FILE,
    when="W0",
    interval=1,
    backupCount=12,
    encoding="utf-8"
)
file_handler.suffix = "%Y-%m-%d"
formatter = JakartaFormatter(
    fmt="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(formatter)

if not logger.handlers:
    logger.addHandler(file_handler)


# ==========================================
# LOG HANDLER UNTUK GUI
# ==========================================
class TextHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        def append():
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, msg + '\n')
            self.text_widget.see(tk.END)
            self.text_widget.configure(state='disabled')
        self.text_widget.after(0, append)


# ==========================================
# LOGIKA PEMROSESAN FOLDER & GAMBAR
# ==========================================
def process_scan_folder(folder_path: Path):
    if not folder_path.exists() or not folder_path.is_dir():
        return

    trigger_file = folder_path / "CREATEDIR.NUL"
    wait_count = 0
    while not trigger_file.exists() and wait_count < 3:
        time.sleep(1)
        wait_count += 1

    main_image = ""
    icon_image = ""
    camera_images = []

    try:
        files = list(folder_path.iterdir())
    except Exception as e:
        logger.error(f"Gagal membaca isi folder {folder_path}: {e}")
        return

    for file in files:
        if not file.is_file():
            continue
        
        ext = file.suffix.lower()
        fname = file.name

        if ext == ".img" or fname.upper() == "CREATEDIR.NUL":
            continue

        if ext in [".jpg", ".jpeg", ".png", ".bmp"]:
            if fname.endswith("_icon.jpg") or fname.endswith("_icon.jpeg") or fname.endswith("_icon.png"):
                icon_image = fname
            elif fname.startswith("62001") or "FS" in fname:
                main_image = fname
            else:
                camera_images.append(fname)

    if not main_image and not icon_image and not camera_images:
        return

    folder_name = folder_path.name
    camera_images_str = ",".join(camera_images)
    
    scan_date = datetime.now(JAKARTA_TZ).strftime("%Y-%m-%d")
    try:
        parts = folder_path.parts
        if len(parts) >= 3:
            year_part = parts[-3]
            mmdd_part = parts[-2]
            if len(year_part) == 4 and len(mmdd_part) == 4 and year_part.isdigit() and mmdd_part.isdigit():
                scan_date = f"{year_part}-{mmdd_part[:2]}-{mmdd_part[2:]}"
    except Exception:
        pass

    logger.info(f"Scan Terdeteksi [{folder_name}] | X-Ray: {main_image} | Icon: {icon_image} | Kamera: {len(camera_images)} foto")

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        query = """
            INSERT INTO real_scans (folder_name, folder_path, main_image, icon_image, camera_images, scan_date, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE 
                main_image = VALUES(main_image),
                icon_image = VALUES(icon_image),
                camera_images = VALUES(camera_images);
        """
        cursor.execute(query, (folder_name, str(folder_path), main_image, icon_image, camera_images_str, scan_date))
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"Metadata [{folder_name}] sukses tersimpan ke DB Dashboard.")
    except Exception as e:
        logger.error(f"Gagal mengirim data [{folder_name}] ke DB Dashboard: {e}")


class FolderScanHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            threading.Thread(target=process_scan_folder, args=(Path(event.src_path),), daemon=True).start()
        elif Path(event.src_path).name.upper() == "CREATEDIR.NUL":
            parent_dir = Path(event.src_path).parent
            threading.Thread(target=process_scan_folder, args=(parent_dir,), daemon=True).start()


# ==========================================
# GUI APLIKASI UTAMA
# ==========================================
class ImageWatcherGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Image Server Watcher - PC Server")
        self.root.geometry("720x520")
        
        self.observer = None
        self.watch_dir_var = tk.StringVar(value=r"D:\Image")

        status_frame = ttk.Frame(root, padding=10)
        status_frame.pack(fill=tk.X)

        ttk.Label(status_frame, text="Status Pemantauan:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        self.lbl_status = ttk.Label(status_frame, text="BERHENTI", font=("Arial", 10, "bold"), foreground="red")
        self.lbl_status.pack(side=tk.LEFT)

        dir_frame = ttk.LabelFrame(root, text=" Lokasi Folder Pemantauan ", padding=10)
        dir_frame.pack(fill=tk.X, padx=10, pady=5)

        self.ent_dir = ttk.Entry(dir_frame, textvariable=self.watch_dir_var, font=("Arial", 9))
        self.ent_dir.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        self.btn_browse = ttk.Button(dir_frame, text="Pilih Folder...", command=self.browse_folder)
        self.btn_browse.pack(side=tk.RIGHT)

        btn_frame = ttk.Frame(root, padding=10)
        btn_frame.pack(fill=tk.X)

        self.btn_start = ttk.Button(btn_frame, text="Start Watcher", command=self.start_watcher)
        self.btn_start.pack(side=tk.LEFT, padx=5)

        self.btn_stop = ttk.Button(btn_frame, text="Stop Watcher", command=self.stop_watcher, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=5)

        log_frame = ttk.LabelFrame(root, text=" Log Aktivitas Realtime ", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.txt_log = scrolledtext.ScrolledText(log_frame, state='disabled', height=15, font=("Consolas", 9))
        self.txt_log.pack(fill=tk.BOTH, expand=True)

        gui_handler = TextHandler(self.txt_log)
        gui_handler.setFormatter(formatter)
        logger.addHandler(gui_handler)

        logger.info("Aplikasi Image Server Watcher Siap Digunakan.")

    def browse_folder(self):
        selected = filedialog.askdirectory(initialdir=self.watch_dir_var.get(), title="Pilih Folder Pemantauan X-Ray")
        if selected:
            self.watch_dir_var.set(selected)
            logger.info(f"Target folder diubah ke: {selected}")

    def start_watcher(self):
        target_path = self.watch_dir_var.get().strip()
        watch_path = Path(target_path)
        if not watch_path.exists():
            watch_path.mkdir(parents=True, exist_ok=True)

        self.observer = Observer()
        self.observer.schedule(FolderScanHandler(), path=str(watch_path), recursive=True)
        self.observer.start()

        self.lbl_status.config(text="BERJALAN (MONITORING)", foreground="green")
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.btn_browse.config(state=tk.DISABLED)
        self.ent_dir.config(state=tk.DISABLED)
        logger.info(f"Pemantauan aktif memantau folder: {target_path}")

    def stop_watcher(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None

        self.lbl_status.config(text="BERHENTI", foreground="red")
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.btn_browse.config(state=tk.NORMAL)
        self.ent_dir.config(state=tk.NORMAL)
        logger.info("Pemantauan dihentikan oleh pengguna.")


if __name__ == "__main__":
    root = tk.Tk()
    app = ImageWatcherGUI(root)
    root.mainloop()