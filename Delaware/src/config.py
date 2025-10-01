"""Configuration for Delaware candidate data ingestion."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

# Create directories if they don't exist
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# Database Configuration (shared with Maryland)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Delaware-specific URLs
DELAWARE_URLS = {
    "school_board": "https://elections.delaware.gov/candidates/candidatelist/sb_fcddt_2026.shtml",
    "primary": "https://elections.delaware.gov/candidates/candidatelist/prim_fcddt_2026.shtml", 
    "general": "https://elections.delaware.gov/candidates/candidatelist/genl_fcddt_2026.shtml"
}

# Election Configuration
ELECTION_YEAR = 2026
SOURCE_STATE = "DE"
SOURCE_NAME = "STATE"  # Using same enum as Maryland for consistency

# Runtime Configuration
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Data Processing Configuration
# Delaware typically doesn't provide party affiliation for many offices
DEFAULT_VALUES = {
    "party": None,  # Delaware often doesn't track this
    "state": "DE",
    "election_year": ELECTION_YEAR,
    "source_state": SOURCE_STATE
}

# Office name mappings (if needed)
# NOTE: We keep Delaware's exact office names, no normalization
OFFICE_LEVEL_KEYWORDS = {
    "federal": ["president", "senate", "congress", "representative"],
    "state": ["governor", "lieutenant governor", "attorney general", "treasurer", 
              "auditor", "insurance commissioner", "state senate", "state house"],
    "local": ["county", "mayor", "council", "commissioner", "sheriff", "clerk"],
    "judicial": ["judge", "justice", "court"],
    "other": ["school board", "board of education"]
}