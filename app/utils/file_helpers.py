from __future__ import annotations

from pathlib import Path
from loguru import logger

async def delete_temp_files(*paths: Path) -> None:
    """
    Safely delete multiple files from the filesystem.
    
    Args:
        *paths: One or more pathlib.Path objects to delete.
    """
    for path in paths:
        if path and path.exists():
            try:
                path.unlink()
                logger.info(f"Successfully deleted temporary file: {path}")
            except Exception as e:
                logger.error(f"Failed to delete {path}: {e}")
