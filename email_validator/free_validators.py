"""Free email validation checks (no API required)."""

import re
import dns.resolver
import requests
from typing import Tuple, Optional, Set
from email_validator import validate_email, EmailNotValidError
from config import (
    COMMON_TYPOS, 
    ROLE_PREFIXES, 
    DISPOSABLE_DOMAINS_URL,
    get_logger
)

logger = get_logger(__name__)


class FreeValidators:
    """Free email validation checks using DNS and pattern matching."""
    
    def __init__(self):
        """Initialize free validators."""
        self.disposable_domains = self._load_disposable_domains()
        self.role_prefixes = ROLE_PREFIXES
        self.common_typos = COMMON_TYPOS
        logger.info(f"Loaded {len(self.disposable_domains)} disposable domains")
    
    def _load_disposable_domains(self) -> Set[str]:
        """Load list of disposable email domains.
        
        Returns:
            Set of disposable domain names
        """
        try:
            logger.info("Fetching disposable domains list...")
            response = requests.get(DISPOSABLE_DOMAINS_URL, timeout=30)
            response.raise_for_status()
            domains = set(response.json())
            logger.info(f"Successfully loaded {len(domains)} disposable domains")
            return domains
        except Exception as e:
            logger.error(f"Failed to load disposable domains: {e}")
            # Return a minimal set of known disposable domains as fallback
            return {
                '10minutemail.com', 'guerrillamail.com', 'mailinator.com',
                'tempmail.com', 'throwaway.email', 'yopmail.com',
                'fakeinbox.com', 'trashmail.com', 'maildrop.cc',
                'dispostable.com', 'tempr.email', 'throwawaymail.com'
            }
    
    def validate_syntax(self, email: str) -> Tuple[bool, Optional[str]]:
        """Validate email syntax using RFC standards.
        
        Args:
            email: Email address to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # email-validator library checks RFC compliance
            validation = validate_email(email, check_deliverability=False)
            normalized = validation.normalized
            
            # Check if normalized version differs (indicates likely typo)
            if normalized != email.lower():
                logger.info(f"Email normalization: {email} -> {normalized}")
            
            return True, None
            
        except EmailNotValidError as e:
            return False, str(e)
    
    def check_typos(self, email: str) -> Tuple[bool, Optional[str]]:
        """Check for common email typos.
        
        Args:
            email: Email address to check
            
        Returns:
            Tuple of (has_typo, suggested_correction)
        """
        if '@' not in email:
            return True, None
        
        domain = email.split('@')[1].lower()
        
        if domain in self.common_typos:
            correct_domain = self.common_typos[domain]
            suggested_email = email.split('@')[0] + '@' + correct_domain
            logger.info(f"Typo detected: {email} -> suggested: {suggested_email}")
            return True, suggested_email
        
        return False, None
    
    def validate_dns(self, email: str) -> Tuple[bool, Optional[str]]:
        """Check if email domain has valid DNS and MX records.
        
        Args:
            email: Email address to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if '@' not in email:
            return False, "Invalid email format"
        
        domain = email.split('@')[1]
        
        try:
            # Check for MX records (mail exchange)
            mx_records = dns.resolver.resolve(domain, 'MX')
            if mx_records:
                logger.debug(f"Found {len(mx_records)} MX records for {domain}")
                return True, None
            else:
                return False, "No MX records found"
                
        except dns.resolver.NXDOMAIN:
            return False, "Domain does not exist"
        except dns.resolver.NoAnswer:
            # Try A record as fallback (some domains use A records for mail)
            try:
                a_records = dns.resolver.resolve(domain, 'A')
                if a_records:
                    logger.debug(f"No MX but found A records for {domain}")
                    return True, "No MX records but A records exist"
                else:
                    return False, "No DNS records found"
            except:
                return False, "No DNS records found"
        except Exception as e:
            logger.error(f"DNS validation error for {domain}: {e}")
            return False, f"DNS lookup failed: {str(e)}"
    
    def is_disposable(self, email: str) -> bool:
        """Check if email uses a disposable/temporary domain.
        
        Args:
            email: Email address to check
            
        Returns:
            True if disposable domain
        """
        if '@' not in email:
            return False
        
        domain = email.split('@')[1].lower()
        
        # Check main domain
        if domain in self.disposable_domains:
            logger.info(f"Disposable domain detected: {domain}")
            return True
        
        # Check subdomains (e.g., user@mail.disposable.com)
        parts = domain.split('.')
        for i in range(len(parts)):
            subdomain = '.'.join(parts[i:])
            if subdomain in self.disposable_domains:
                logger.info(f"Disposable subdomain detected: {subdomain}")
                return True
        
        return False
    
    def is_role_account(self, email: str) -> bool:
        """Check if email is a role/generic account.
        
        Args:
            email: Email address to check
            
        Returns:
            True if role account
        """
        if '@' not in email:
            return False
        
        local_part = email.split('@')[0].lower()
        
        # Remove common separators for comparison
        normalized = local_part.replace('-', '').replace('_', '').replace('.', '')
        
        for prefix in self.role_prefixes:
            if local_part.startswith(prefix) or normalized.startswith(prefix):
                logger.info(f"Role account detected: {email} (prefix: {prefix})")
                return True
        
        return False
    
    def validate_all(self, email: str) -> dict:
        """Run all free validation checks on an email.
        
        Args:
            email: Email address to validate
            
        Returns:
            Dict with all validation results
        """
        results = {
            'email': email,
            'syntax_valid': False,
            'dns_valid': False,
            'has_typo': False,
            'suggested_email': None,
            'is_disposable': False,
            'is_role_account': False,
            'errors': []
        }
        
        # Syntax validation
        syntax_valid, syntax_error = self.validate_syntax(email)
        results['syntax_valid'] = syntax_valid
        if not syntax_valid:
            results['errors'].append(f"Syntax: {syntax_error}")
            return results  # No point checking further if syntax is invalid
        
        # Typo check
        has_typo, suggested = self.check_typos(email)
        results['has_typo'] = has_typo
        results['suggested_email'] = suggested
        if has_typo:
            results['errors'].append(f"Likely typo, suggest: {suggested}")
        
        # DNS validation
        dns_valid, dns_error = self.validate_dns(email)
        results['dns_valid'] = dns_valid
        results['mx_records_found'] = dns_valid  # For compatibility
        if not dns_valid:
            results['errors'].append(f"DNS: {dns_error}")
        
        # Disposable check
        results['is_disposable'] = self.is_disposable(email)
        if results['is_disposable']:
            results['errors'].append("Disposable email domain")
        
        # Role account check
        results['is_role_account'] = self.is_role_account(email)
        if results['is_role_account']:
            results['errors'].append("Role/generic account")
        
        # Overall validity
        results['is_valid_free_checks'] = (
            syntax_valid and 
            dns_valid and 
            not has_typo and 
            not results['is_disposable']
        )
        
        return results


def test_free_validators():
    """Test free validators with sample emails."""
    validator = FreeValidators()
    
    test_emails = [
        'john.doe@gmail.com',  # Valid
        'info@example.com',  # Role account
        'test@gmial.com',  # Typo
        'user@10minutemail.com',  # Disposable
        'invalid.email',  # Invalid syntax
        'test@nonexistentdomain12345.com',  # No DNS
    ]
    
    for email in test_emails:
        print(f"\nTesting: {email}")
        results = validator.validate_all(email)
        print(f"  Valid: {results['is_valid_free_checks']}")
        if results['errors']:
            print(f"  Errors: {', '.join(results['errors'])}")
        if results['suggested_email']:
            print(f"  Suggested: {results['suggested_email']}")


if __name__ == "__main__":
    test_free_validators()