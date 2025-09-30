"""Configuration management for Maryland candidate update system."""

import os
import logging
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Paths
BASE_DIR = Path(__file__).parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Supabase Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables")

# Maryland BOE URLs
MARYLAND_STATE_CSV = os.getenv(
    "MARYLAND_STATE_CSV",
    "https://elections.maryland.gov/elections/2026/Primary_candidates/gen_cand_lists_2026_1_ALL.csv"
)
MARYLAND_LOCAL_CSV = os.getenv(
    "MARYLAND_LOCAL_CSV", 
    "https://elections.maryland.gov/elections/2026/Primary_candidates/gen_cand_lists_2026_1_by_county_ALL.csv"
)

# Runtime Configuration
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG" if DEBUG else "INFO")

# Election Configuration
ELECTION_YEAR = 2026
SOURCE_NAME = "maryland_boe"

# Deduplication Configuration
EXACT_MATCH_THRESHOLD = 100  # Exact match
HIGH_CONFIDENCE_THRESHOLD = 95  # Auto-accept
REVIEW_THRESHOLD = 85  # Manual review needed
# Below REVIEW_THRESHOLD = create new candidate

# HTTP Configuration
REQUEST_TIMEOUT = 30  # seconds
MAX_RETRIES = 3

# Logging Configuration
def setup_logging(name: Optional[str] = None) -> logging.Logger:
    """Set up logging configuration."""
    logger = logging.getLogger(name or __name__)
    
    if not logger.handlers:
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, LOG_LEVEL))
        
        # File handler
        log_file = LOG_DIR / f"maryland_update_{Path(__file__).stem}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        logger.setLevel(logging.DEBUG)
    
    return logger

# Create default logger
logger = setup_logging()