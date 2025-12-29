import os
import shutil
import ftplib
import time
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

from dotenv import load_dotenv
from colorama import init, Fore, Style

# Initialize colorama for cross-platform color support
init(autoreset=True)

# --- Configuration Management ---

@dataclass
class BackupConfig:
    source_folder: Path
    
    # Local Config
    local_enabled: bool
    local_folder: Path
    local_max: int
    local_interval: int  # Seconds
    
    # FTP Config
    ftp_enabled: bool
    ftp_host: str
    ftp_port: int
    ftp_user: str
    ftp_pass: str
    ftp_folder: str
    ftp_max: int
    ftp_interval: int  # Seconds

    @staticmethod
    def get_bool(var: str, default: bool = False) -> bool:
        val = os.getenv(var)
        return str(val).lower() in ("1", "true", "yes", "on") if val else default

    @classmethod
    def load_from_env(cls):
        load_dotenv()
        
        source = os.getenv("SOURCE_FOLDER")
        if not source:
            raise ValueError("SOURCE_FOLDER is not defined in .env")

        return cls(
            source_folder=Path(source),
            
            local_enabled=cls.get_bool("LOCAL_BACKUP_ENABLED", True),
            local_folder=Path(os.getenv("LOCAL_BACKUP_FOLDER", "./backups")),
            local_max=int(os.getenv("LOCAL_BACKUP_MAX", 10)),
            local_interval=int(os.getenv("LOCAL_BACKUP_DELAY_MINUTES", 60)) * 60,
            
            ftp_enabled=cls.get_bool("FTP_BACKUP_ENABLED", False),
            ftp_host=os.getenv("FTP_HOST", ""),
            ftp_port=int(os.getenv("FTP_PORT", 21)),
            ftp_user=os.getenv("FTP_USERNAME", ""),
            ftp_pass=os.getenv("FTP_PASSWORD", ""),
            ftp_folder=os.getenv("FTP_FOLDER", "/"),
            ftp_max=int(os.getenv("FTP_BACKUP_MAX", 10)),
            ftp_interval=int(os.getenv("FTP_BACKUP_DELAY_MINUTES", 60)) * 60,
        )

# --- Logging Helpers ---

class Logger:
    @staticmethod
    def info(msg: str):
        print(f"{Fore.CYAN}[INFO] {Style.RESET_ALL}{msg}")

    @staticmethod
    def success(msg: str):
        print(f"{Fore.GREEN}[SUCCESS] {Style.RESET_ALL}{msg}")

    @staticmethod
    def warning(msg: str):
        print(f"{Fore.YELLOW}[WARNING] {Style.RESET_ALL}{msg}")

    @staticmethod
    def error(msg: str):
        print(f"{Fore.RED}[ERROR] {Style.RESET_ALL}{msg}")

    @staticmethod
    def header(msg: str):
        print(f"\n{Style.BRIGHT}{Fore.MAGENTA}{'='*50}")
        print(f"{msg.center(50)}")
        print(f"{'='*50}{Style.RESET_ALL}")

# --- Core Logic ---

class BackupManager:
    def __init__(self, config: BackupConfig):
        self.cfg = config
        self.temp_dir = Path("temp_backups")
        self.last_local_run = 0.0
        self.last_ftp_run = 0.0

    def create_zip(self, backup_name: str) -> Path:
        """Compresses the source directory into a temporary zip file."""
        self.temp_dir.mkdir(exist_ok=True)
        archive_path = self.temp_dir / backup_name
        
        Logger.info(f"Compressing: {self.cfg.source_folder}...")
        shutil.make_archive(str(archive_path), "zip", self.cfg.source_folder)
        
        zip_path = Path(f"{str(archive_path)}.zip")
        Logger.success(f"Archive created: {zip_path.name} ({zip_path.stat().st_size / 1024 / 1024:.2f} MB)")
        return zip_path

    def cleanup_temp(self, zip_path: Path):
        """Removes the temporary zip file and directory."""
        if zip_path.exists():
            zip_path.unlink()
        if self.temp_dir.exists() and not any(self.temp_dir.iterdir()):
            self.temp_dir.rmdir()

    def process_local(self, zip_path: Path):
        """Handles local backup rotation and copying."""
        if not self.cfg.local_enabled:
            return

        try:
            Logger.info(f"{Style.BRIGHT}Starting Local Backup...")
            self.cfg.local_folder.mkdir(parents=True, exist_ok=True)
            
            # Rotation
            backups = sorted(self.cfg.local_folder.glob("backup_*.zip"), key=lambda f: f.stat().st_mtime)
            while len(backups) >= self.cfg.local_max:
                oldest = backups.pop(0)
                oldest.unlink()
                Logger.warning(f"Rotated local backup: {oldest.name}")

            # Copy
            dest = self.cfg.local_folder / zip_path.name
            shutil.copy2(zip_path, dest)
            Logger.success(f"Saved locally to: {dest}")
            self.last_local_run = time.time()

        except Exception as e:
            Logger.error(f"Local backup failed: {e}")

    def process_ftp(self, zip_path: Path):
        """Handles FTP upload and remote rotation."""
        if not self.cfg.ftp_enabled:
            return

        Logger.info(f"{Style.BRIGHT}Starting FTP Backup...")
        
        try:
            with ftplib.FTP() as ftp:
                ftp.connect(self.cfg.ftp_host, self.cfg.ftp_port)
                ftp.login(self.cfg.ftp_user, self.cfg.ftp_pass)
                Logger.info(f"Connected to FTP: {self.cfg.ftp_host}")

                # Navigate/Create Folder
                try:
                    ftp.cwd(self.cfg.ftp_folder)
                except ftplib.error_perm:
                    ftp.mkd(self.cfg.ftp_folder)
                    ftp.cwd(self.cfg.ftp_folder)

                # Rotation (Get list, sort by name since name contains timestamp)
                files = [f for f in ftp.nlst() if f.startswith("backup_") and f.endswith(".zip")]
                files.sort() 

                while len(files) >= self.cfg.ftp_max:
                    oldest = files.pop(0)
                    ftp.delete(oldest)
                    Logger.warning(f"Rotated FTP backup: {oldest}")

                # Upload
                with open(zip_path, "rb") as f:
                    ftp.storbinary(f"STOR {zip_path.name}", f)
                
                Logger.success(f"Uploaded to FTP: {zip_path.name}")
                self.last_ftp_run = time.time()

        except Exception as e:
            Logger.error(f"FTP backup failed: {e}")

    def run_loop(self):
        Logger.header("Minecraft Backup System Started")
        Logger.info(f"Source: {self.cfg.source_folder}")
        Logger.info(f"Local: {'Enabled' if self.cfg.local_enabled else 'Disabled'} ({self.cfg.local_interval//60}m)")
        Logger.info(f"FTP:   {'Enabled' if self.cfg.ftp_enabled else 'Disabled'} ({self.cfg.ftp_interval//60}m)")

        while True:
            now = time.time()
            do_local = self.cfg.local_enabled and (now - self.last_local_run >= self.cfg.local_interval)
            do_ftp = self.cfg.ftp_enabled and (now - self.last_ftp_run >= self.cfg.ftp_interval)

            if do_local or do_ftp:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = f"backup_{timestamp}"
                
                Logger.header(f"Backup Cycle: {timestamp}")
                
                zip_path = None
                try:
                    zip_path = self.create_zip(backup_name)
                    
                    if do_local:
                        self.process_local(zip_path)
                    
                    if do_ftp:
                        self.process_ftp(zip_path)
                        
                except Exception as e:
                    Logger.error(f"Critical error during compression: {e}")
                finally:
                    if zip_path:
                        self.cleanup_temp(zip_path)
                        Logger.info("Cleaned up temporary files")
            
            # Wait Logic
            next_local = (self.last_local_run + self.cfg.local_interval) if self.cfg.local_enabled else float('inf')
            next_ftp = (self.last_ftp_run + self.cfg.ftp_interval) if self.cfg.ftp_enabled else float('inf')
            
            seconds_until_next = max(5, int(min(next_local, next_ftp) - time.time()))
            
            # Simple countdown or just sleep
            # print(f"Sleeping for {seconds_until_next}s...", end='\r')
            time.sleep(seconds_until_next)

# --- Entry Point ---

def main():
    try:
        config = BackupConfig.load_from_env()
        if not config.source_folder.exists():
            Logger.error(f"Source folder not found: {config.source_folder}")
            return
            
        manager = BackupManager(config)
        manager.run_loop()
        
    except ValueError as e:
        Logger.error(str(e))
    except KeyboardInterrupt:
        print()
        Logger.warning("Backup process stopped by user.")

if __name__ == "__main__":
    main()