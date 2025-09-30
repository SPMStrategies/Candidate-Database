"""Fetch candidate data from Maryland Board of Elections."""

import pandas as pd
import requests
from typing import Tuple, Optional
from io import StringIO
from tenacity import retry, stop_after_attempt, wait_exponential
from .config import (
    MARYLAND_STATE_CSV, 
    MARYLAND_LOCAL_CSV,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    setup_logging
)

logger = setup_logging(__name__)


class MarylandDataFetcher:
    """Fetches candidate data from Maryland BOE website."""
    
    def __init__(self):
        self.state_url = MARYLAND_STATE_CSV
        self.local_url = MARYLAND_LOCAL_CSV
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Maryland-Candidate-Database-Updater/1.0'
        })
    
    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def _fetch_csv(self, url: str, description: str) -> pd.DataFrame:
        """
        Fetch CSV from URL with retry logic.
        
        Args:
            url: URL to fetch
            description: Description for logging
            
        Returns:
            DataFrame with CSV data
        """
        logger.info(f"Fetching {description} from {url}")
        
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            
            # Parse CSV
            csv_content = StringIO(response.text)
            df = pd.read_csv(csv_content, encoding='utf-8', on_bad_lines='skip')
            
            logger.info(f"Successfully fetched {description}: {len(df)} records")
            return df
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching {description}: {e}")
            raise
        except pd.errors.ParserError as e:
            logger.error(f"Error parsing CSV for {description}: {e}")
            raise
    
    def fetch_state_candidates(self) -> pd.DataFrame:
        """
        Fetch state-level candidates (federal and state offices).
        
        Returns:
            DataFrame with state candidate data
        """
        return self._fetch_csv(self.state_url, "state candidates")
    
    def fetch_local_candidates(self) -> pd.DataFrame:
        """
        Fetch local candidates (county and municipal offices).
        
        Returns:
            DataFrame with local candidate data
        """
        return self._fetch_csv(self.local_url, "local candidates")
    
    def fetch_all_candidates(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Fetch both state and local candidates.
        
        Returns:
            Tuple of (state_df, local_df)
        """
        state_df = self.fetch_state_candidates()
        local_df = self.fetch_local_candidates()
        return state_df, local_df
    
    def fetch_combined_candidates(self) -> pd.DataFrame:
        """
        Fetch and combine state and local candidates into single DataFrame.
        
        Returns:
            Combined DataFrame with all candidates
        """
        state_df, local_df = self.fetch_all_candidates()
        
        # Standardize column names (Maryland uses inconsistent naming)
        def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
            """Standardize column names to lowercase with underscores."""
            df.columns = [
                col.strip().lower().replace(' ', '_').replace('/', '_')
                for col in df.columns
            ]
            return df
        
        state_df = standardize_columns(state_df)
        local_df = standardize_columns(local_df)
        
        # Add source column to track origin
        state_df['data_source'] = 'state'
        local_df['data_source'] = 'local'
        
        # Combine dataframes
        combined_df = pd.concat([state_df, local_df], ignore_index=True)
        
        logger.info(f"Combined data: {len(combined_df)} total candidates")
        logger.info(f"  State: {len(state_df)} candidates")
        logger.info(f"  Local: {len(local_df)} candidates")
        
        return combined_df
    
    def close(self):
        """Close the session."""
        self.session.close()


def fetch_maryland_candidates() -> pd.DataFrame:
    """
    Main function to fetch all Maryland candidates.
    
    Returns:
        DataFrame with all Maryland candidates
    """
    fetcher = MarylandDataFetcher()
    try:
        return fetcher.fetch_combined_candidates()
    finally:
        fetcher.close()


if __name__ == "__main__":
    # Test fetching
    df = fetch_maryland_candidates()
    print(f"Fetched {len(df)} candidates")
    print(f"Columns: {list(df.columns)}")
    print(f"Sample data:\n{df.head()}")