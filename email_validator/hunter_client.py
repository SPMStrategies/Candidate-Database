"""Hunter.io API client for email validation."""

import os
import time
import requests
from typing import Dict, Optional
from ratelimit import limits, sleep_and_retry
from config import HUNTER_API_KEY, HUNTER_API_BASE, HUNTER_RATE_LIMIT_PER_SECOND, get_logger

logger = get_logger(__name__)


class HunterClient:
    """Client for Hunter.io email verification API."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Hunter client.
        
        Args:
            api_key: Hunter.io API key (defaults to env variable)
        """
        self.api_key = api_key or HUNTER_API_KEY
        if not self.api_key:
            raise ValueError("Hunter.io API key not found. Set HUNTER_API_KEY in .env file")
        
        self.base_url = HUNTER_API_BASE
        self.session = requests.Session()
        self.credits_used = 0
        self.last_quota_check = None
        self.remaining_credits = None
    
    @sleep_and_retry
    @limits(calls=HUNTER_RATE_LIMIT_PER_SECOND, period=1)
    def verify_email(self, email: str) -> Dict:
        """Verify an email address using Hunter.io.
        
        Args:
            email: Email address to verify
            
        Returns:
            Dict with verification results
            
        Example response:
        {
            "data": {
                "status": "valid",  # valid, invalid, accept_all, webmail, disposable
                "result": "deliverable",  # deliverable, undeliverable, risky
                "score": 95,  # 0-100 confidence score
                "_deprecation_notice": "...",
                "email": "john.doe@example.com",
                "regexp": true,  # matches expected pattern
                "gibberish": false,  # detected as random string
                "disposable": false,
                "webmail": false,
                "mx_records": true,
                "smtp_server": true,
                "smtp_check": true,
                "accept_all": false,
                "block": false,
                "sources": []
            },
            "meta": {
                "params": {...}
            }
        }
        """
        try:
            logger.info(f"Verifying email with Hunter.io: {email}")
            
            response = self.session.get(
                f"{self.base_url}/email-verifier",
                params={
                    'email': email,
                    'api_key': self.api_key
                },
                timeout=30
            )
            
            # Check for rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                logger.warning(f"Rate limited. Waiting {retry_after} seconds...")
                time.sleep(retry_after)
                return self.verify_email(email)  # Retry
            
            response.raise_for_status()
            result = response.json()
            
            # Track credit usage
            self.credits_used += 1
            
            # Extract quota information if present
            if 'meta' in result and 'quota' in result['meta']:
                self.remaining_credits = result['meta']['quota']['remaining']
                logger.info(f"Hunter.io credits remaining: {self.remaining_credits}")
            
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error verifying email {email}: {e}")
            return {
                'error': str(e),
                'data': {
                    'status': 'unknown',
                    'score': 0,
                    'result': 'unknown'
                }
            }
    
    def get_account_info(self) -> Dict:
        """Get Hunter.io account information including credit balance.
        
        Returns:
            Dict with account info
        """
        try:
            response = self.session.get(
                f"{self.base_url}/account",
                params={'api_key': self.api_key},
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            if 'data' in result:
                self.remaining_credits = result['data']['requests']['searches']['available']
                logger.info(f"Hunter.io account - Credits available: {self.remaining_credits}")
            
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting account info: {e}")
            return {'error': str(e)}
    
    def check_credits(self) -> int:
        """Check remaining Hunter.io credits.
        
        Returns:
            Number of remaining credits, or -1 if unable to check
        """
        account_info = self.get_account_info()
        
        if 'data' in account_info:
            searches = account_info['data']['requests']['searches']['available']
            verifications = account_info['data']['requests']['verifications']['available']
            logger.info(f"Hunter.io credits - Searches: {searches}, Verifications: {verifications}")
            return verifications
        
        return -1
    
    def batch_verify(self, emails: list, delay: float = 0.1) -> Dict[str, Dict]:
        """Verify multiple emails with rate limiting.
        
        Args:
            emails: List of email addresses
            delay: Delay between requests (in addition to rate limiting)
            
        Returns:
            Dict mapping email to verification result
        """
        results = {}
        total = len(emails)
        
        logger.info(f"Starting batch verification of {total} emails")
        
        for i, email in enumerate(emails, 1):
            if i % 10 == 0:
                logger.info(f"Progress: {i}/{total} emails verified")
            
            results[email] = self.verify_email(email)
            
            # Additional delay to be nice to the API
            if delay > 0:
                time.sleep(delay)
        
        logger.info(f"Batch verification complete. Credits used: {self.credits_used}")
        return results


def test_hunter_connection():
    """Test Hunter.io API connection and return account info."""
    try:
        client = HunterClient()
        account = client.get_account_info()
        
        if 'data' in account:
            data = account['data']
            print("Hunter.io connection successful!")
            print(f"Email: {data.get('email')}")
            print(f"Plan: {data.get('plan_name')}")
            print(f"Verification credits: {data['requests']['verifications']['available']}")
            print(f"Search credits: {data['requests']['searches']['available']}")
            return True
        else:
            print("Failed to connect to Hunter.io")
            print(account.get('error', 'Unknown error'))
            return False
            
    except Exception as e:
        print(f"Error testing Hunter.io connection: {e}")
        return False


if __name__ == "__main__":
    # Test the connection when run directly
    test_hunter_connection()