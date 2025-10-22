"""Fetch candidate data from North Carolina State Board of Elections."""

import pandas as pd
import requests
from typing import Optional
from io import StringIO
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential
from .config import (
    NC_CSV_URL,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    DATA_DIR,
    ELECTION_YEAR,
    setup_logging
)

logger = setup_logging(__name__)


class NorthCarolinaDataFetcher:
    """Fetches candidate data from NC BOE S3 bucket."""

    def __init__(self):
        self.csv_url = NC_CSV_URL
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'NorthCarolina-Candidate-Database-Updater/1.0'
        })
        self.cache_file = DATA_DIR / f"nc_candidates_{ELECTION_YEAR}.csv"

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def _fetch_csv(self, url: str) -> pd.DataFrame:
        """
        Fetch CSV from URL with retry logic.

        Args:
            url: URL to fetch

        Returns:
            DataFrame with CSV data
        """
        logger.info(f"Fetching North Carolina candidates from {url}")

        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()

            # Parse CSV
            csv_content = StringIO(response.text)
            df = pd.read_csv(csv_content, encoding='utf-8', on_bad_lines='skip')

            logger.info(f"Successfully fetched NC data: {len(df)} records")

            # Cache the CSV locally
            df.to_csv(self.cache_file, index=False)
            logger.info(f"Cached data to {self.cache_file}")

            return df

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching NC data: {e}")
            raise
        except pd.errors.ParserError as e:
            logger.error(f"Error parsing CSV: {e}")
            raise

    def fetch_candidates(self, use_cache: bool = False) -> pd.DataFrame:
        """
        Fetch North Carolina candidates.

        Args:
            use_cache: If True and cache exists, use cached data instead of fetching

        Returns:
            DataFrame with candidate data
        """
        # Check if cache exists and should be used
        if use_cache and self.cache_file.exists():
            logger.info(f"Using cached data from {self.cache_file}")
            try:
                df = pd.read_csv(self.cache_file)
                logger.info(f"Loaded {len(df)} candidates from cache")
                return df
            except Exception as e:
                logger.warning(f"Failed to load cache, fetching fresh data: {e}")

        # Fetch fresh data
        df = self._fetch_csv(self.csv_url)

        # Standardize column names
        df = self._standardize_columns(df)

        return df

    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Standardize column names to lowercase with underscores.

        Args:
            df: Input DataFrame

        Returns:
            DataFrame with standardized column names
        """
        df.columns = [
            col.strip().lower().replace(' ', '_').replace('/', '_')
            for col in df.columns
        ]
        return df

    def close(self):
        """Close the session."""
        self.session.close()


def fetch_nc_candidates(use_cache: bool = False) -> pd.DataFrame:
    """
    Main function to fetch all North Carolina candidates.

    Args:
        use_cache: If True, use cached data if available

    Returns:
        DataFrame with all NC candidates
    """
    fetcher = NorthCarolinaDataFetcher()
    try:
        return fetcher.fetch_candidates(use_cache=use_cache)
    finally:
        fetcher.close()


if __name__ == "__main__":
    # Test fetching
    df = fetch_nc_candidates()
    print(f"Fetched {len(df)} candidates")
    print(f"Columns: {list(df.columns)}")
    print(f"Sample data:\n{df.head()}")
