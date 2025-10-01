"""Fetch Delaware candidate data from HTML sources."""

import re
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
from bs4 import BeautifulSoup
import requests
from .models import DelawareCandidateRaw
from .config import DATA_DIR, DELAWARE_URLS

logger = logging.getLogger(__name__)


class DelawareFetcher:
    """Fetch and parse Delaware candidate data."""
    
    def __init__(self):
        """Initialize fetcher."""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.candidates = []
    
    def fetch_from_file(self, file_path: Path) -> Optional[str]:
        """
        Read HTML from a local file.
        
        Args:
            file_path: Path to HTML file
            
        Returns:
            HTML content or None
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.info(f"Read HTML from {file_path}")
            return content
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return None
    
    def fetch_from_url(self, url: str) -> Optional[str]:
        """
        Attempt to fetch HTML from URL.
        Note: This may fail due to Cloudflare protection.
        
        Args:
            url: URL to fetch
            
        Returns:
            HTML content or None
        """
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Check if we got Cloudflare challenge
            if "cf-browser-verification" in response.text or "Just a moment" in response.text:
                logger.warning(f"Cloudflare protection detected on {url}")
                logger.info("Please download HTML manually and place in data/ directory")
                return None
            
            logger.info(f"Successfully fetched {url}")
            return response.text
            
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    def parse_candidate_table(self, html: str, election_type: str) -> List[DelawareCandidateRaw]:
        """
        Parse candidate data from Delaware HTML table.
        
        Args:
            html: HTML content
            election_type: Type of election (primary, general, school_board)
            
        Returns:
            List of raw candidate data
        """
        candidates = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # Delaware typically uses tables for candidate lists
        # Look for tables with candidate information
        tables = soup.find_all('table')
        
        for table in tables:
            # Skip navigation or layout tables
            if not table.find('tr'):
                continue
            
            rows = table.find_all('tr')
            
            # Try to identify header row to understand column structure
            headers = []
            header_row = rows[0] if rows else None
            if header_row:
                headers = [th.get_text(strip=True).lower() for th in header_row.find_all(['th', 'td'])]
            
            # Process data rows
            for row in rows[1:]:  # Skip header
                cells = row.find_all(['td', 'th'])
                if not cells:
                    continue
                
                # Extract data based on position or headers
                candidate_data = self.extract_candidate_from_row(cells, headers, election_type)
                if candidate_data:
                    candidates.append(candidate_data)
        
        # If no tables found, try to parse other structures
        if not candidates:
            candidates = self.parse_candidate_list(soup, election_type)
        
        logger.info(f"Parsed {len(candidates)} candidates from {election_type} HTML")
        return candidates
    
    def extract_candidate_from_row(self, cells: List, headers: List[str], 
                                  election_type: str) -> Optional[DelawareCandidateRaw]:
        """
        Extract candidate data from table row.
        
        Args:
            cells: Table cells
            headers: Header names (if available)
            election_type: Type of election
            
        Returns:
            Raw candidate data or None
        """
        if len(cells) < 2:  # Need at least name and office
            return None
        
        # Map headers to indices
        header_map = {header: i for i, header in enumerate(headers)} if headers else {}
        
        # Try to extract based on headers or position
        candidate = DelawareCandidateRaw(
            name="",
            office="",
            election_type=election_type
        )
        
        # Common patterns in Delaware data
        if 'candidate' in header_map or 'name' in header_map:
            idx = header_map.get('candidate', header_map.get('name'))
            candidate.name = cells[idx].get_text(strip=True) if idx < len(cells) else ""
        elif len(cells) > 0:
            # Assume first cell is name
            candidate.name = cells[0].get_text(strip=True)
        
        if 'office' in header_map or 'position' in header_map:
            idx = header_map.get('office', header_map.get('position'))
            candidate.office = cells[idx].get_text(strip=True) if idx < len(cells) else ""
        elif len(cells) > 1:
            # Assume second cell is office
            candidate.office = cells[1].get_text(strip=True)
        
        # Extract other fields if available
        if 'district' in header_map:
            idx = header_map['district']
            candidate.district = cells[idx].get_text(strip=True) if idx < len(cells) else None
        
        if 'county' in header_map:
            idx = header_map['county']
            candidate.county = cells[idx].get_text(strip=True) if idx < len(cells) else None
        
        if 'email' in header_map:
            idx = header_map['email']
            text = cells[idx].get_text(strip=True) if idx < len(cells) else ""
            # Extract email from text or link
            email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
            if email_match:
                candidate.email = email_match.group()
        
        if 'phone' in header_map:
            idx = header_map['phone']
            text = cells[idx].get_text(strip=True) if idx < len(cells) else ""
            # Extract phone number
            phone_match = re.search(r'[\d\-\(\)\s]+', text)
            if phone_match and len(phone_match.group()) >= 10:
                candidate.phone = phone_match.group()
        
        # Only return if we have minimum required data
        if candidate.name and candidate.office:
            return candidate
        
        return None
    
    def parse_candidate_list(self, soup: BeautifulSoup, election_type: str) -> List[DelawareCandidateRaw]:
        """
        Parse candidates from non-table structures.
        
        Args:
            soup: BeautifulSoup object
            election_type: Type of election
            
        Returns:
            List of candidates
        """
        candidates = []
        
        # Look for common patterns in Delaware HTML
        # Sometimes candidates are in lists or divs
        
        # Pattern 1: Lists (ul/ol)
        for ul in soup.find_all(['ul', 'ol']):
            for li in ul.find_all('li'):
                text = li.get_text(strip=True)
                # Try to parse candidate info from list item
                candidate = self.parse_candidate_text(text, election_type)
                if candidate:
                    candidates.append(candidate)
        
        # Pattern 2: Divs with specific classes
        for div in soup.find_all('div', class_=re.compile('candidate|nominee|filing')):
            text = div.get_text(strip=True)
            candidate = self.parse_candidate_text(text, election_type)
            if candidate:
                candidates.append(candidate)
        
        return candidates
    
    def parse_candidate_text(self, text: str, election_type: str) -> Optional[DelawareCandidateRaw]:
        """
        Parse candidate information from text.
        
        Args:
            text: Text containing candidate info
            election_type: Type of election
            
        Returns:
            Raw candidate data or None
        """
        if not text or len(text) < 5:
            return None
        
        # Common patterns:
        # "John Doe - State Senate District 5"
        # "Jane Smith for County Council"
        # "Bob Johnson, Register of Wills"
        
        # Try dash separator
        if ' - ' in text:
            parts = text.split(' - ', 1)
            return DelawareCandidateRaw(
                name=parts[0].strip(),
                office=parts[1].strip(),
                election_type=election_type
            )
        
        # Try "for" separator
        if ' for ' in text:
            parts = text.split(' for ', 1)
            return DelawareCandidateRaw(
                name=parts[0].strip(),
                office=parts[1].strip(),
                election_type=election_type
            )
        
        # Try comma separator
        if ', ' in text:
            parts = text.split(', ', 1)
            # Check if second part looks like an office
            if any(word in parts[1].lower() for word in ['council', 'senate', 'house', 'judge', 'sheriff']):
                return DelawareCandidateRaw(
                    name=parts[0].strip(),
                    office=parts[1].strip(),
                    election_type=election_type
                )
        
        return None
    
    def fetch_all_candidates(self) -> List[DelawareCandidateRaw]:
        """
        Fetch candidates from all Delaware sources.
        
        Returns:
            List of all candidates
        """
        all_candidates = []
        
        # First, try browser-based fetching if files don't exist
        self._try_browser_fetch()
        
        for election_type, url in DELAWARE_URLS.items():
            logger.info(f"Processing {election_type} candidates")
            
            # First try local file
            file_name = f"{election_type}_candidates_2026.html"
            file_path = DATA_DIR / file_name
            
            html = None
            if file_path.exists():
                logger.info(f"Using local file: {file_path}")
                html = self.fetch_from_file(file_path)
            else:
                logger.info(f"Attempting to fetch from: {url}")
                html = self.fetch_from_url(url)
                
                # Save to file if successful
                if html and not "Just a moment" in html:
                    try:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(html)
                        logger.info(f"Saved HTML to {file_path}")
                    except Exception as e:
                        logger.error(f"Error saving HTML: {e}")
            
            if html:
                candidates = self.parse_candidate_table(html, election_type)
                all_candidates.extend(candidates)
            else:
                logger.warning(f"No data available for {election_type}")
                logger.info(f"Try running: python Delaware/src/browser_fetcher.py")
        
        logger.info(f"Total candidates fetched: {len(all_candidates)}")
        return all_candidates
    
    def _try_browser_fetch(self):
        """
        Try to use browser fetcher if files don't exist.
        """
        # Check if any files are missing
        missing = []
        for election_type in DELAWARE_URLS.keys():
            file_path = DATA_DIR / f"{election_type}_candidates_2026.html"
            if not file_path.exists():
                missing.append(election_type)
        
        if missing:
            logger.info(f"Missing files for: {missing}")
            try:
                # Try to import and run browser fetcher
                import asyncio
                from .browser_fetcher import fetch_delaware_with_browser
                
                logger.info("Attempting browser-based fetch...")
                results = asyncio.run(fetch_delaware_with_browser())
                logger.info(f"Browser fetch returned {len(results)} pages")
                
            except ImportError:
                logger.info("Browser fetcher not available. Install with:")
                logger.info("  pip install -r Delaware/requirements_browser.txt")
                logger.info("  python Delaware/setup_playwright.py")
            except Exception as e:
                logger.warning(f"Browser fetch failed: {e}")


def fetch_delaware_candidates() -> List[DelawareCandidateRaw]:
    """
    Main function to fetch Delaware candidates.
    
    Returns:
        List of raw candidate data
    """
    # Try cloudscraper first (bypasses Cloudflare)
    try:
        from .cloudscraper_fetcher import fetch_with_cloudscraper
        logger.info("Using cloudscraper to fetch candidates")
        
        results = fetch_with_cloudscraper()
        all_candidates = []
        for election_type, candidates in results.items():
            all_candidates.extend(candidates)
        
        if all_candidates:
            logger.info(f"Cloudscraper fetched {len(all_candidates)} candidates")
            return all_candidates
    except ImportError:
        logger.warning("Cloudscraper not available. Install with: pip install cloudscraper")
    except Exception as e:
        logger.warning(f"Cloudscraper fetch failed: {e}")
    
    # Fall back to regular fetcher
    logger.info("Falling back to regular fetcher")
    fetcher = DelawareFetcher()
    return fetcher.fetch_all_candidates()