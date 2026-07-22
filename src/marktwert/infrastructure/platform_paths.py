"""Operating-system-specific local application paths."""

import os
import sys
from pathlib import Path

APPLICATION_DIRECTORY_NAME = "MarktWert"


def default_data_directory() -> Path:
    """Return the user-local data directory without creating it."""
    home = Path.home()
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else home / "AppData" / "Local"
        return base / APPLICATION_DIRECTORY_NAME
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / APPLICATION_DIRECTORY_NAME
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg_data_home) if xdg_data_home else home / ".local" / "share"
    return base / APPLICATION_DIRECTORY_NAME.casefold()
