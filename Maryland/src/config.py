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

# Debug: Print environment variable status (without values)
print(f"Environment check: SUPABASE_URL={'set' if SUPABASE_URL else 'NOT SET'}")
print(f"Environment check: SUPABASE_KEY={'set' if SUPABASE_KEY else 'NOT SET'}")

if not SUPABASE_URL or not SUPABASE_KEY:
    missing = []
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_KEY:
        missing.append("SUPABASE_KEY")
    raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

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
SOURCE_NAME = "state_filing"  # Generic source name that might be in the enum

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

SOURCE_NAME = "STATE"  # Use the database enum value for ingest_source. Valid values: FEC, STATE, MANUAL, OTHER
# Create default logger
logger = setup_logging()