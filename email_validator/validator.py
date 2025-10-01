"""Main email validation orchestrator."""

import time
from typing import Dict, Optional, List, Tuple
from hunter_client import HunterClient
from free_validators import FreeValidators
from database import EmailDatabase
from config import VALIDATION_SETTINGS, get_logger

logger = get_logger(__name__)


class EmailValidator:
    """Orchestrate email validation using free checks and Hunter.io."""
    
    def __init__(self, use_hunter: bool = True):
        """Initialize validator.
        
        Args:
            use_hunter: Whether to use Hunter.io API for validation
        """
        self.free_validator = FreeValidators()
        self.hunter_client = HunterClient() if use_hunter else None
        self.db = EmailDatabase()
        self.use_hunter = use_hunter
        
        # Statistics tracking
        self.stats = {
            'total_emails_checked': 0,
            'new_emails_validated': 0,
            'emails_revalidated': 0,
            'valid_count': 0,
            'invalid_count': 0,
            'error_count': 0,
            'hunter_credits_used': 0,
            'errors': []
        }
        
        logger.info(f"EmailValidator initialized (Hunter.io: {'enabled' if use_hunter else 'disabled'})")
    
    def validate_email(self, 
                      email: str, 
                      candidate_id: Optional[str] = None,
                      candidate_name: Optional[str] = None,
                      is_revalidation: bool = False) -> Dict:
        """Validate a single email address.
        
        Args:
            email: Email address to validate
            candidate_id: Associated candidate ID
            candidate_name: Candidate name for logging
            is_revalidation: Whether this is a 60-day revalidation
            
        Returns:
            Dictionary with validation results
        """
        logger.info(f"Validating email: {email} (Candidate: {candidate_name or 'Unknown'})")
        self.stats['total_emails_checked'] += 1
        
        if is_revalidation:
            self.stats['emails_revalidated'] += 1
        else:
            self.stats['new_emails_validated'] += 1
        
        try:
            # Step 1: Run free validation checks
            free_results = self.free_validator.validate_all(email)
            
            validation_data = {
                'email_address': email,
                'candidate_id': candidate_id,
                'syntax_valid': free_results['syntax_valid'],
                'dns_valid': free_results['dns_valid'],
                'mx_records_found': free_results.get('mx_records_found', free_results['dns_valid']),
                'is_disposable': free_results['is_disposable'],
                'is_role_account': free_results['is_role_account'],
                'validation_method': 'free_checks'
            }
            
            # Check if free validation failed
            if not free_results['syntax_valid']:
                validation_data['is_valid'] = False
                validation_data['validation_error'] = 'Invalid email syntax'
                logger.info(f"Email {email} failed syntax validation")
                
            elif free_results['has_typo']:
                validation_data['is_valid'] = False
                validation_data['validation_error'] = f"Likely typo (suggest: {free_results['suggested_email']})"
                logger.info(f"Email {email} has likely typo")
                
            elif not free_results['dns_valid']:
                validation_data['is_valid'] = False
                validation_data['validation_error'] = 'Domain does not exist or has no mail server'
                logger.info(f"Email {email} failed DNS validation")
                
            elif free_results['is_disposable']:
                validation_data['is_valid'] = False
                validation_data['validation_error'] = 'Disposable/temporary email address'
                logger.info(f"Email {email} is disposable")
                
            else:
                # Free checks passed, now use Hunter.io if available
                if self.use_hunter and self.hunter_client:
                    logger.info(f"Using Hunter.io to verify {email}")
                    hunter_result = self.hunter_client.verify_email(email)
                    self.stats['hunter_credits_used'] += 1
                    
                    if 'error' not in hunter_result:
                        data = hunter_result.get('data', {})
                        
                        validation_data.update({
                            'validation_method': 'hunter_api',
                            'hunter_status': data.get('status'),
                            'hunter_score': data.get('score', 0),
                            'hunter_result': hunter_result,
                            'hunter_regexp': data.get('regexp'),
                            'hunter_gibberish': data.get('gibberish'),
                            'confidence_score': data.get('score', 0) / 100.0
                        })
                        
                        # Determine validity based on Hunter.io result
                        status = data.get('status', 'unknown')
                        score = data.get('score', 0)
                        
                        if status == 'valid' and score >= 70:
                            validation_data['is_valid'] = True
                            logger.info(f"Email {email} validated by Hunter.io (score: {score})")
                        elif status in ['invalid', 'disposable']:
                            validation_data['is_valid'] = False
                            validation_data['validation_error'] = f"Hunter.io: {status}"
                            logger.info(f"Email {email} marked invalid by Hunter.io: {status}")
                        elif status == 'accept_all':
                            # Accept-all domains always accept mail, hard to validate
                            validation_data['is_valid'] = True  # Cautiously mark as valid
                            validation_data['validation_error'] = 'Accept-all domain (uncertain deliverability)'
                            logger.warning(f"Email {email} is on accept-all domain")
                        elif status == 'webmail':
                            # Webmail addresses (gmail, yahoo) are generally valid if they passed other checks
                            validation_data['is_valid'] = score >= 50
                            logger.info(f"Email {email} is webmail (score: {score})")
                        else:
                            # Unknown or risky
                            validation_data['is_valid'] = False
                            validation_data['validation_error'] = f"Uncertain: {status}"
                            logger.warning(f"Email {email} has uncertain status: {status}")
                    else:
                        # Hunter.io API error
                        logger.error(f"Hunter.io error for {email}: {hunter_result['error']}")
                        # Fall back to free checks result
                        validation_data['is_valid'] = True  # Passed free checks
                        validation_data['confidence_score'] = 0.6
                else:
                    # No Hunter.io, use free checks only
                    validation_data['is_valid'] = True  # Passed all free checks
                    validation_data['confidence_score'] = 0.7
                    logger.info(f"Email {email} passed free validation checks")
            
            # Update statistics
            if validation_data['is_valid']:
                self.stats['valid_count'] += 1
            else:
                self.stats['invalid_count'] += 1
            
            # Save to database
            self.db.save_validation(validation_data)
            
            return validation_data
            
        except Exception as e:
            logger.error(f"Error validating {email}: {e}")
            self.stats['error_count'] += 1
            self.stats['errors'].append(f"{email}: {str(e)}")
            
            # Save error state
            error_data = {
                'email_address': email,
                'candidate_id': candidate_id,
                'is_valid': None,
                'validation_error': str(e),
                'validation_method': 'error'
            }
            self.db.save_validation(error_data)
            
            return error_data
    
    def validate_batch(self, 
                      emails: List[Tuple[str, str, str]], 
                      is_revalidation: bool = False) -> Dict:
        """Validate a batch of emails.
        
        Args:
            emails: List of tuples (candidate_id, email, candidate_name)
            is_revalidation: Whether this is a 60-day revalidation
            
        Returns:
            Statistics dictionary
        """
        total = len(emails)
        logger.info(f"Starting batch validation of {total} emails")
        
        for i, (candidate_id, email, name) in enumerate(emails, 1):
            if i % 10 == 0:
                logger.info(f"Progress: {i}/{total} emails processed")
            
            self.validate_email(email, candidate_id, name, is_revalidation)
            
            # Small delay to be nice to services
            time.sleep(0.1)
        
        logger.info(f"Batch validation complete: {self.stats}")
        return self.stats
    
    def validate_all_emails(self) -> Dict:
        """Validate all candidate emails in the database.
        
        Returns:
            Statistics dictionary
        """
        logger.info("Starting validation of all candidate emails")
        
        # Create validation run
        run_id = self.db.create_validation_run('all', 'manual')
        
        # Get all candidate emails
        emails = self.db.get_all_candidate_emails()
        
        if not emails:
            logger.warning("No candidate emails found")
            return self.stats
        
        # Validate in batches
        batch_size = VALIDATION_SETTINGS['batch_size']
        for i in range(0, len(emails), batch_size):
            batch = emails[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1} ({len(batch)} emails)")
            self.validate_batch(batch)
        
        # Update run with statistics
        if run_id:
            self.db.update_validation_run(run_id, self.stats)
        
        return self.stats
    
    def validate_new_emails(self) -> Dict:
        """Validate only unvalidated emails.
        
        Returns:
            Statistics dictionary
        """
        logger.info("Starting validation of new/unvalidated emails")
        
        # Create validation run
        run_id = self.db.create_validation_run('new', 'manual')
        
        # Get unvalidated emails
        emails = self.db.get_unvalidated_emails()
        
        if not emails:
            logger.info("No unvalidated emails found")
            return self.stats
        
        logger.info(f"Found {len(emails)} unvalidated emails")
        
        # Validate all
        self.validate_batch(emails, is_revalidation=False)
        
        # Update run with statistics
        if run_id:
            self.db.update_validation_run(run_id, self.stats)
        
        return self.stats
    
    def revalidate_due_emails(self) -> Dict:
        """Revalidate emails due for 60-day check.
        
        Returns:
            Statistics dictionary
        """
        logger.info("Starting 60-day email revalidation")
        
        # Create validation run
        run_id = self.db.create_validation_run('revalidation', 'scheduled')
        
        # Get emails due for revalidation
        due_validations = self.db.get_emails_due_for_revalidation()
        
        if not due_validations:
            logger.info("No emails due for revalidation")
            return self.stats
        
        logger.info(f"Found {len(due_validations)} emails due for revalidation")
        
        # Convert to expected format
        emails = [
            (val['candidate_id'], val['email_address'], None)
            for val in due_validations
        ]
        
        # Revalidate all
        self.validate_batch(emails, is_revalidation=True)
        
        # Update run with statistics
        if run_id:
            self.db.update_validation_run(run_id, self.stats)
        
        return self.stats
    
    def get_validation_report(self) -> str:
        """Generate a validation report.
        
        Returns:
            Report as string
        """
        stats = self.db.get_validation_statistics()
        
        report = f"""
Email Validation Report
=======================

Overall Statistics:
- Total candidates with email: {stats.get('total_candidates_with_email', 0)}
- Total validated: {stats.get('total_validated', 0)}
- Validation coverage: {stats.get('validation_coverage', 0)}%

Validation Results:
- Valid emails: {stats.get('valid_emails', 0)}
- Invalid emails: {stats.get('invalid_emails', 0)}
- Disposable emails: {stats.get('disposable_emails', 0)}
- Role accounts: {stats.get('role_accounts', 0)}

Current Session:
- Emails checked: {self.stats['total_emails_checked']}
- New validations: {self.stats['new_emails_validated']}
- Revalidations: {self.stats['emails_revalidated']}
- Valid: {self.stats['valid_count']}
- Invalid: {self.stats['invalid_count']}
- Errors: {self.stats['error_count']}
- Hunter.io credits used: {self.stats['hunter_credits_used']}
"""
        
        if self.stats['errors']:
            report += "\nErrors encountered:\n"
            for error in self.stats['errors'][:10]:  # Show first 10 errors
                report += f"  - {error}\n"
        
        return report


def test_single_email():
    """Test validation of a single email."""
    validator = EmailValidator(use_hunter=True)
    
    test_email = "test@example.com"
    result = validator.validate_email(test_email)
    
    print(f"Validation result for {test_email}:")
    print(f"  Valid: {result.get('is_valid')}")
    print(f"  Method: {result.get('validation_method')}")
    print(f"  Error: {result.get('validation_error')}")
    
    if result.get('hunter_score') is not None:
        print(f"  Hunter.io score: {result['hunter_score']}")


if __name__ == "__main__":
    test_single_email()