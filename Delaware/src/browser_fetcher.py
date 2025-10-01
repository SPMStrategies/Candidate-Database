"""Browser-based fetcher for Delaware candidate data using Playwright.

This module uses Playwright with stealth techniques to fetch candidate data
from Delaware's Cloudflare-protected election website.
"""

import asyncio
import logging
import random
import time
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime, timedelta

from playwright.async_api import async_playwright, Page, Browser
from playwright_stealth import stealth_async
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import DELAWARE_URLS, DATA_DIR

logger = logging.getLogger(__name__)


class DelawareBrowserFetcher:
    """Fetch Delaware candidate data using browser automation."""
    
    def __init__(self):
        """Initialize the browser fetcher."""
        self.ua = UserAgent()
        self.browser: Optional[Browser] = None
        self.fetched_html: Dict[str, str] = {}
        
    async def setup_browser(self) -> Browser:
        """
        Set up Playwright browser with stealth settings.
        
        Returns:
            Configured browser instance
        """
        playwright = await async_playwright().start()
        
        # Use Chromium with specific args to avoid detection
        browser = await playwright.chromium.launch(
            headless=False,  # Headless mode is more detectable
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-accelerated-2d-canvas',
                '--disable-gpu',
                '--window-size=1920,1080',
                '--start-maximized'
            ]
        )
        
        return browser
    
    async def create_page(self, browser: Browser) -> Page:
        """
        Create a new page with stealth settings.
        
        Args:
            browser: Browser instance
            
        Returns:
            Configured page
        """
        # Random viewport size
        viewport_width = random.randint(1366, 1920)
        viewport_height = random.randint(768, 1080)
        
        context = await browser.new_context(
            viewport={'width': viewport_width, 'height': viewport_height},
            user_agent=self.ua.random,
            locale='en-US',
            timezone_id='America/New_York',
            permissions=['geolocation'],
            geolocation={'latitude': 39.7391, 'longitude': -75.5398},  # Delaware
            color_scheme='light',
            device_scale_factor=1,
            has_touch=False,
            ignore_https_errors=True
        )
        
        # Add common browser headers
        await context.set_extra_http_headers({
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        })
        
        page = await context.new_page()
        
        # Apply stealth techniques
        await stealth_async(page)
        
        # Additional evasion techniques
        await page.evaluate("""
            // Override navigator properties
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            
            // Add chrome object
            window.chrome = {runtime: {}};
            
            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)
        
        return page
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def fetch_page(self, url: str, page: Page) -> Optional[str]:
        """
        Fetch a single page with retry logic.
        
        Args:
            url: URL to fetch
            page: Playwright page instance
            
        Returns:
            HTML content or None if failed
        """
        try:
            logger.info(f"Fetching {url}")
            
            # Random delay before navigation
            await asyncio.sleep(random.uniform(2, 5))
            
            # Navigate to the page
            response = await page.goto(
                url,
                wait_until='networkidle',
                timeout=60000
            )
            
            if not response:
                logger.error(f"No response from {url}")
                return None
            
            # Wait for potential Cloudflare challenge
            await asyncio.sleep(random.uniform(5, 10))
            
            # Check if we hit Cloudflare challenge
            content = await page.content()
            if "Checking your browser" in content or "Just a moment" in content:
                logger.info("Cloudflare challenge detected, waiting...")
                
                # Wait for challenge to complete
                try:
                    await page.wait_for_selector('table', timeout=30000)
                except:
                    # Try waiting for any main content
                    await asyncio.sleep(10)
                
                # Get content after challenge
                content = await page.content()
            
            # Simulate human behavior - scroll and mouse movements
            await self.simulate_human_behavior(page)
            
            # Final content
            content = await page.content()
            
            # Verify we got actual content, not Cloudflare page
            if len(content) > 1000 and "elections.delaware.gov" not in content.lower():
                logger.warning(f"May have received Cloudflare block page for {url}")
                # Try one more time with longer delay
                await asyncio.sleep(random.uniform(10, 20))
                content = await page.content()
            
            logger.info(f"Successfully fetched {len(content)} bytes from {url}")
            return content
            
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            raise
    
    async def simulate_human_behavior(self, page: Page):
        """
        Simulate human-like behavior on the page.
        
        Args:
            page: Playwright page instance
        """
        try:
            # Random mouse movements
            for _ in range(random.randint(2, 5)):
                x = random.randint(100, 800)
                y = random.randint(100, 600)
                await page.mouse.move(x, y)
                await asyncio.sleep(random.uniform(0.1, 0.5))
            
            # Random scroll
            scroll_distance = random.randint(100, 500)
            await page.evaluate(f"window.scrollBy(0, {scroll_distance})")
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Scroll back
            await page.evaluate(f"window.scrollBy(0, -{scroll_distance//2})")
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
        except Exception as e:
            logger.debug(f"Error simulating behavior: {e}")
    
    async def fetch_all(self) -> Dict[str, str]:
        """
        Fetch all Delaware candidate pages.
        
        Returns:
            Dictionary mapping election type to HTML content
        """
        browser = None
        results = {}
        
        try:
            browser = await self.setup_browser()
            page = await self.create_page(browser)
            
            for election_type, url in DELAWARE_URLS.items():
                try:
                    # Check cache first
                    cache_file = DATA_DIR / f"{election_type}_cache.html"
                    if cache_file.exists():
                        # Check if cache is less than 24 hours old
                        cache_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
                        if cache_age < timedelta(hours=24):
                            logger.info(f"Using cached data for {election_type}")
                            with open(cache_file, 'r', encoding='utf-8') as f:
                                results[election_type] = f.read()
                            continue
                    
                    # Fetch fresh data
                    html = await self.fetch_page(url, page)
                    
                    if html:
                        results[election_type] = html
                        
                        # Save to cache
                        cache_file.parent.mkdir(parents=True, exist_ok=True)
                        with open(cache_file, 'w', encoding='utf-8') as f:
                            f.write(html)
                        logger.info(f"Saved {election_type} to cache")
                        
                        # Also save as the expected filename for the regular fetcher
                        expected_file = DATA_DIR / f"{election_type}_candidates_2026.html"
                        with open(expected_file, 'w', encoding='utf-8') as f:
                            f.write(html)
                    else:
                        logger.error(f"Failed to fetch {election_type} from {url}")
                        
                except Exception as e:
                    logger.error(f"Error fetching {election_type}: {e}")
                    
                # Delay between pages
                await asyncio.sleep(random.uniform(5, 10))
            
        finally:
            if browser:
                await browser.close()
        
        return results


async def fetch_delaware_with_browser() -> Dict[str, str]:
    """
    Main entry point for browser-based fetching.
    
    Returns:
        Dictionary of HTML content by election type
    """
    fetcher = DelawareBrowserFetcher()
    return await fetcher.fetch_all()


def main():
    """Run the browser fetcher."""
    import sys
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("Starting Delaware browser fetcher")
    
    try:
        # Run async fetcher
        results = asyncio.run(fetch_delaware_with_browser())
        
        logger.info(f"Fetched {len(results)} pages:")
        for election_type, html in results.items():
            logger.info(f"  {election_type}: {len(html)} bytes")
        
        if not results:
            logger.error("No pages fetched successfully")
            sys.exit(1)
        
        logger.info("Browser fetch completed successfully")
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()