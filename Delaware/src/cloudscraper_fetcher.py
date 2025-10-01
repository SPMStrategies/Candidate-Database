#!/usr/bin/env python3
"""Fetch Delaware candidate data using cloudscraper to bypass Cloudflare."""

import logging
import time
import random
from pathlib import Path
from typing import Optional, Dict, List
import cloudscraper
from bs4 import BeautifulSoup

from .config import DELAWARE_URLS, DATA_DIR
from .models import DelawareCandidateRaw

logger = logging.getLogger(__name__)


class DelawareCloudscraperFetcher:
    """Fetch Delaware data using cloudscraper."""
    
    def __init__(self):
        """Initialize cloudscraper."""
        # Create scraper with browser settings
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            },
            delay=10  # Delay between requests
        )
        
        # Add additional headers
        self.scraper.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def fetch_url(self, url: str, max_retries: int = 3) -> Optional[str]:
        """
        Fetch a URL using cloudscraper.
        
        Args:
            url: URL to fetch
            max_retries: Maximum number of retries
            
        Returns:
            HTML content or None
        """
        for attempt in range(max_retries):
            try:
                logger.info(f"Fetching {url} (attempt {attempt + 1}/{max_retries})")
                
                # Add random delay between retries
                if attempt > 0:
                    delay = random.uniform(5, 15)
                    logger.info(f"Waiting {delay:.1f} seconds before retry...")
                    time.sleep(delay)
                
                response = self.scraper.get(url, timeout=30)
                
                if response.status_code == 200:
                    content = response.text
                    
                    # Check if we got real content or Cloudflare challenge
                    if len(content) > 10000:  # Expect real pages to be larger
                        logger.info(f"Successfully fetched {len(content)} bytes")
                        return content
                    elif "Just a moment" in content or "Checking your browser" in content:
                        logger.warning(f"Cloudflare challenge detected (attempt {attempt + 1})")
                        continue
                    else:
                        logger.warning(f"Response too small: {len(content)} bytes")
                        continue
                        
                elif response.status_code == 403:
                    logger.error(f"Access forbidden (403) - Cloudflare block detected")
                    
                elif response.status_code == 503:
                    logger.warning(f"Service unavailable (503) - Likely Cloudflare challenge")
                    
                else:
                    logger.error(f"HTTP {response.status_code}: {response.reason}")
                    
            except cloudscraper.exceptions.CloudflareChallengeError as e:
                logger.error(f"Cloudflare challenge error: {e}")
                
            except Exception as e:
                logger.error(f"Error fetching {url}: {e}")
        
        logger.error(f"Failed to fetch {url} after {max_retries} attempts")
        return None
    
    def parse_candidates_from_html(self, html: str, election_type: str) -> List[DelawareCandidateRaw]:
        """
        Parse candidates from HTML content.
        
        Args:
            html: HTML content
            election_type: Type of election
            
        Returns:
            List of candidates
        """
        candidates = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # Look for tables containing candidate data
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            
            for row in rows:
                cells = row.find_all('td')
                
                # Delaware format: Office | County | Party | Candidate Name
                if len(cells) >= 4:
                    office_text = cells[0].get_text(strip=True)
                    county_text = cells[1].get_text(strip=True)
                    party_text = cells[2].get_text(strip=True)
                    
                    # Extract candidate name from the span
                    name_span = cells[3].find('span', class_='main-span')
                    if name_span:
                        # Remove the chevron icon text
                        name_text = name_span.get_text(strip=True)
                        # Remove any trailing icons or symbols
                        import re
                        name_text = re.sub(r'[^\w\s\.\-\']', '', name_text).strip()
                    else:
                        name_text = cells[3].get_text(strip=True)
                    
                    # Skip if this looks like a header
                    if any(header in office_text.lower() for header in ['office', 'position', 'title']):
                        continue
                    
                    # Create candidate if we have valid data
                    if name_text and len(name_text) > 2:
                        # Extract district number from office if present
                        district = None
                        if 'District' in office_text:
                            import re
                            district_match = re.search(r'District\s+(\d+)', office_text)
                            if district_match:
                                district = district_match.group(1)
                        
                        candidate = DelawareCandidateRaw(
                            name=name_text,
                            office=office_text,
                            district=district,
                            county=county_text if county_text else None,
                            party=party_text if party_text else None,
                            election_type=election_type
                        )
                        
                        candidates.append(candidate)
                        logger.debug(f"Found candidate: {candidate.name} ({candidate.party}) for {candidate.office} in {candidate.county}")
        
        logger.info(f"Parsed {len(candidates)} candidates from {election_type} HTML")
        return candidates
    
    def fetch_all(self) -> Dict[str, List[DelawareCandidateRaw]]:
        """
        Fetch all Delaware candidate pages.
        
        Returns:
            Dictionary mapping election type to list of candidates
        """
        all_results = {}
        
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        for election_type, url in DELAWARE_URLS.items():
            # Check cache first
            cache_file = DATA_DIR / f"{election_type}_candidates_2026.html"
            
            html_content = None
            
            # Try to use cached file if recent
            if cache_file.exists():
                age_hours = (time.time() - cache_file.stat().st_mtime) / 3600
                if age_hours < 24:
                    logger.info(f"Using cached {election_type} data ({age_hours:.1f} hours old)")
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        html_content = f.read()
            
            # Fetch fresh if no cache
            if not html_content:
                html_content = self.fetch_url(url)
                
                if html_content and len(html_content) > 10000:
                    # Save to cache
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        f.write(html_content)
                    logger.info(f"Saved {election_type} to {cache_file}")
            
            # Parse candidates from HTML
            if html_content:
                candidates = self.parse_candidates_from_html(html_content, election_type)
                all_results[election_type] = candidates
            else:
                logger.error(f"No content available for {election_type}")
                all_results[election_type] = []
            
            # Delay between requests
            if election_type != list(DELAWARE_URLS.keys())[-1]:  # Not the last one
                delay = random.uniform(5, 10)
                logger.info(f"Waiting {delay:.1f} seconds before next request...")
                time.sleep(delay)
        
        return all_results


def fetch_with_cloudscraper() -> Dict[str, List[DelawareCandidateRaw]]:
    """Main entry point for cloudscraper fetching."""
    fetcher = DelawareCloudscraperFetcher()
    return fetcher.fetch_all()


def main():
    """Run the cloudscraper fetcher."""
    import sys
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    logger.info("Starting Delaware cloudscraper fetcher")
    
    try:
        results = fetch_with_cloudscraper()
        
        total_candidates = sum(len(candidates) for candidates in results.values())
        
        logger.info(f"\nResults:")
        for election_type, candidates in results.items():
            logger.info(f"  {election_type}: {len(candidates)} candidates")
            
            # Show first few candidates as examples
            for candidate in candidates[:3]:
                logger.info(f"    - {candidate.name} for {candidate.office}")
        
        if total_candidates > 0:
            logger.info(f"\n✅ Successfully fetched {total_candidates} total candidates")
            sys.exit(0)
        else:
            logger.error("No candidates found")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()