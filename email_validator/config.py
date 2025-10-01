"""Configuration for email validation system."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# API Keys
HUNTER_API_KEY = os.getenv('HUNTER_API_KEY')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# Hunter.io settings
HUNTER_API_BASE = 'https://api.hunter.io/v2'
HUNTER_RATE_LIMIT_PER_SECOND = 10

# Validation settings
VALIDATION_SETTINGS = {
    'revalidation_days': 60,
    'min_confidence_to_mark_valid': 0.7,  # 70% confidence minimum
    'batch_size': 100,
    'use_hunter_for_all': True,  # Set to False to only use for emails that pass free checks
}

# Free validation checks
FREE_CHECKS = {
    'syntax_validation': True,
    'dns_validation': True,
    'disposable_check': True,
    'role_account_check': True,
    'typo_check': True,
}

# Common email typos to detect
COMMON_TYPOS = {
    'gmial.com': 'gmail.com',
    'gmai.com': 'gmail.com',
    'gmaii.com': 'gmail.com',
    'gnail.com': 'gmail.com',
    'gmil.com': 'gmail.com',
    'gmaill.com': 'gmail.com',
    'yahooo.com': 'yahoo.com',
    'yaho.com': 'yahoo.com',
    'yahou.com': 'yahoo.com',
    'yahho.com': 'yahoo.com',
    'hotmial.com': 'hotmail.com',
    'hotmal.com': 'hotmail.com',
    'hotmil.com': 'hotmail.com',
    'hotnail.com': 'hotmail.com',
    'outlok.com': 'outlook.com',
    'outloook.com': 'outlook.com',
    'aool.com': 'aol.com',
    'aoi.com': 'aol.com',
}

# Role account prefixes
ROLE_PREFIXES = [
    'admin', 'administrator', 'info', 'information',
    'support', 'help', 'contact', 'contacts',
    'sales', 'marketing', 'hello', 'hi',
    'noreply', 'no-reply', 'donotreply', 'do-not-reply',
    'webmaster', 'postmaster', 'hostmaster',
    'abuse', 'spam', 'privacy', 'security',
    'press', 'media', 'pr', 'news',
    'careers', 'jobs', 'hr', 'recruiting',
    'billing', 'accounts', 'payments',
    'feedback', 'enquiries', 'inquiries',
    'office', 'team', 'staff',
]

# Disposable domains list URL
DISPOSABLE_DOMAINS_URL = 'https://raw.githubusercontent.com/disposable/disposable-email-domains/master/domains.json'

# Logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def get_logger(name):
    """Get a configured logger."""
    return logging.getLogger(name)