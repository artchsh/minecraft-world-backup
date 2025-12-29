# Minecraft World Backup

A simple Python application to backup folders (designed for Minecraft worlds) to both local storage and FTP server.

## Features

- Backup any folder to a zip archive
- Store backups locally with configurable max count
- Upload backups to FTP server with configurable max count
- Automatic cleanup of old backups (oldest removed first)
- Configurable via JSON config file

## Installation

```bash
uv sync
```

## Configuration

Edit `config.json` to configure your backup settings:

```json
{
    "source_folder": "C:/path/to/minecraft/world",
    "local_backup": {
        "enabled": true,
        "folder": "C:/path/to/local/backups",
        "max_backups": 10
    },
    "ftp_backup": {
        "enabled": true,
        "host": "ftp.example.com",
        "port": 21,
        "username": "your_username",
        "password": "your_password",
        "folder": "/backups/minecraft",
        "max_backups": 10
    }
}
```

### Configuration Options

| Option | Description |
|--------|-------------|
| `source_folder` | Path to the folder you want to backup |
| `local_backup.enabled` | Enable/disable local backups |
| `local_backup.folder` | Path to store local backups |
| `local_backup.max_backups` | Maximum number of local backups to keep |
| `ftp_backup.enabled` | Enable/disable FTP backups |
| `ftp_backup.host` | FTP server hostname |
| `ftp_backup.port` | FTP server port (default: 21) |
| `ftp_backup.username` | FTP username |
| `ftp_backup.password` | FTP password |
| `ftp_backup.folder` | Remote folder path for backups |
| `ftp_backup.max_backups` | Maximum number of FTP backups to keep |

## Usage

```bash
uv run main.py
```

## Linux (Minecraft Server)

For Linux Minecraft servers, update `config.json`:

```json
{
    "source_folder": "/home/minecraft/server/world",
    "local_backup": {
        "enabled": true,
        "folder": "/home/minecraft/backups",
        "max_backups": 10
    },
    ...
}
```

You can also set up a cron job to run backups automatically:

```bash
# Run backup every 6 hours
0 */6 * * * cd /path/to/minecraft-world-backup && uv run main.py
```
