import os
import tempfile
import glob
import shutil
from typing import Optional
from utils.logging_utils import setup_logging

logger = setup_logging()

def get_latest_file(directory: str) -> Optional[str]:
    valid_extensions = ('.jpg', '.jpeg', '.png', '.mp4', '.mov')
    logger.debug(f"Scanning directory {directory} for media files")
    media_files = [
        f for f in glob.glob(os.path.join(directory, "*"))
        if f.lower().endswith(valid_extensions)
    ]
    if not media_files:
        logger.warning(f"No valid media files found in {directory}")
        return None
    latest_file = max(media_files, key=os.path.getmtime)
    logger.debug(f"Latest file found: {latest_file}")
    return latest_file

def create_temp_dir(prefix: str) -> str:
    temp_dir = tempfile.mkdtemp(prefix=prefix)
    logger.info(f"Created temporary directory: {temp_dir}")
    return temp_dir

def cleanup_temp_dir(directory: str):
    if os.path.exists(directory):
        logger.info(f"Cleaning up temporary directory: {directory}")
        shutil.rmtree(directory)
    else:
        logger.warning(f"Directory {directory} does not exist, skipping cleanup")
