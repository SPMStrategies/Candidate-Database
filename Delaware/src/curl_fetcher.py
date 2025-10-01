#!/usr/bin/env python3
"""Simple curl-based fetcher as a fallback option."""

import subprocess
import time
import random
from pathlib import Path
import logging
from typing import Optional

from .config import DELAWARE_URLS, DATA_DIR

logger = logging.getLogger(__name__)


def fetch_with_curl(url: str) -> Optional[str]:
    """
    Fetch URL using curl with browser-like headers.
    
    Args:
        url: URL to fetch
        
    Returns:
        HTML content or None
    """
    # Build curl command with browser headers
    curl_cmd = [
        'curl',
        '-s',  # Silent
        '-L',  # Follow redirects
        '--compressed',  # Accept compressed responses
        '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        '-H', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        '-H', 'Accept-Language: en-US,en;q=0.9',
        '-H', 'Accept-Encoding: gzip, deflate, br',
        '-H', 'DNT: 1',
        '-H', 'Connection: keep-alive',
        '-H', 'Upgrade-Insecure-Requests: 1',
        '-H', 'Sec-Fetch-Dest: document',
        '-H', 'Sec-Fetch-Mode: navigate',
        '-H', 'Sec-Fetch-Site: none',
        '-H', 'Sec-Fetch-User: ?1',
        '-H', 'Cache-Control: max-age=0',
        '--cookie-jar', '/tmp/delaware_cookies.txt',
        '--cookie', '/tmp/delaware_cookies.txt',
        url
    ]
    
    try:
        logger.info(f"Fetching {url} with curl...")
        result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            content = result.stdout
            
            # Check if we got Cloudflare challenge
            if "Checking your browser" in content or "Just a moment" in content:
                logger.warning("Cloudflare challenge detected")
                
                # Try again with a delay
                time.sleep(random.uniform(5, 10))
                result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=30)
                content = result.stdout
            
            if len(content) > 1000:
                logger.info(f"Successfully fetched {len(content)} bytes")
                return content
            else:
                logger.warning(f"Response too small: {len(content)} bytes")
                return None
        else:
            logger.error(f"Curl failed with code {result.returncode}")
            return None
            
    except subprocess.TimeoutExpired:
        logger.error("Curl request timed out")
        return None
    except Exception as e:
        logger.error(f"Error running curl: {e}")
        return None


def fetch_all_delaware_pages():
    """Fetch all Delaware pages using curl."""
    
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    for election_type, url in DELAWARE_URLS.items():
        file_path = DATA_DIR / f"{election_type}_candidates_2026.html"
        
        # Skip if file exists and is recent
        if file_path.exists():
            age_hours = (time.time() - file_path.stat().st_mtime) / 3600
            if age_hours < 24:
                logger.info(f"Skipping {election_type} - file is {age_hours:.1f} hours old")
                continue
        
        logger.info(f"Fetching {election_type} from {url}")
        html = fetch_with_curl(url)
        
        if html:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html)
            logger.info(f"Saved to {file_path}")
        else:
            logger.error(f"Failed to fetch {election_type}")
        
        # Delay between requests
        time.sleep(random.uniform(3, 8))
    
    # Check results
    html_files = list(DATA_DIR.glob("*.html"))
    logger.info(f"Found {len(html_files)} HTML files in data directory")
    return len(html_files) > 0


def main():
    """Run the curl fetcher."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    success = fetch_all_delaware_pages()
    
    if success:
        logger.info("Curl fetch completed successfully")
        return 0
    else:
        logger.error("Curl fetch failed")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())