"""Database operations for email validation."""

import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from uuid import UUID
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY, get_logger

logger = get_logger(__name__)


class EmailDatabase:
    """Handle database operations for email validation."""
    
    def __init__(self):
        """Initialize database connection."""
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("Supabase credentials not found in environment")
        
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Connected to Supabase")
    
    def get_all_candidate_emails(self) -> List[Tuple[str, str, str]]:
        """Get all unique emails from candidates table.
        
        Returns:
            List of tuples (candidate_id, email, full_name)
        """
        try:
            result = self.client.table('candidates')\
                .select('id, contact_email, full_name')\
                .not_.is_('contact_email', 'null')\
                .execute()
            
            emails = []
            for row in result.data:
                if row['contact_email']:  # Double-check not null/empty
                    emails.append((
                        row['id'],
                        row['contact_email'].strip().lower(),
                        row['full_name']
                    ))
            
            logger.info(f"Found {len(emails)} candidate emails")
            return emails
            
        except Exception as e:
            logger.error(f"Error fetching candidate emails: {e}")
            return []
    
    def get_unvalidated_emails(self) -> List[Tuple[str, str, str]]:
        """Get candidate emails that have never been validated.
        
        Returns:
            List of tuples (candidate_id, email, full_name)
        """
        try:
            # Get all candidate emails
            all_emails = self.get_all_candidate_emails()
            
            # Get already validated emails
            validated_result = self.client.table('email_validations')\
                .select('email_address')\
                .execute()
            
            validated_emails = {row['email_address'].lower() 
                              for row in validated_result.data}
            
            # Find unvalidated emails
            unvalidated = [
                (cid, email, name) 
                for cid, email, name in all_emails
                if email.lower() not in validated_emails
            ]
            
            logger.info(f"Found {len(unvalidated)} unvalidated emails")
            return unvalidated
            
        except Exception as e:
            logger.error(f"Error fetching unvalidated emails: {e}")
            return []
    
    def get_emails_due_for_revalidation(self) -> List[Dict]:
        """Get emails due for 60-day revalidation.
        
        Returns:
            List of validation records due for recheck
        """
        try:
            now = datetime.now().isoformat()
            
            result = self.client.table('email_validations')\
                .select('*')\
                .lte('next_validation_due', now)\
                .execute()
            
            due_emails = result.data
            logger.info(f"Found {len(due_emails)} emails due for revalidation")
            return due_emails
            
        except Exception as e:
            logger.error(f"Error fetching emails due for revalidation: {e}")
            return []
    
    def save_validation(self, validation_data: Dict) -> bool:
        """Save or update email validation result.
        
        Args:
            validation_data: Dictionary with validation results
            
        Returns:
            True if successful
        """
        try:
            email = validation_data['email_address'].lower()
            
            # Check if validation exists
            existing = self.client.table('email_validations')\
                .select('id')\
                .eq('email_address', email)\
                .execute()
            
            # Prepare data for insert/update
            data = {
                'email_address': email,
                'candidate_id': validation_data.get('candidate_id'),
                'is_valid': validation_data.get('is_valid'),
                'validation_method': validation_data.get('validation_method'),
                'confidence_score': validation_data.get('confidence_score'),
                'syntax_valid': validation_data.get('syntax_valid'),
                'dns_valid': validation_data.get('dns_valid'),
                'mx_records_found': validation_data.get('mx_records_found'),
                'is_disposable': validation_data.get('is_disposable', False),
                'is_role_account': validation_data.get('is_role_account', False),
                'hunter_status': validation_data.get('hunter_status'),
                'hunter_score': validation_data.get('hunter_score'),
                'hunter_result': json.dumps(validation_data.get('hunter_result')) if validation_data.get('hunter_result') else None,
                'hunter_regexp': validation_data.get('hunter_regexp'),
                'hunter_gibberish': validation_data.get('hunter_gibberish'),
                'validation_error': validation_data.get('validation_error'),
                'last_validated_at': datetime.now().isoformat(),
                'next_validation_due': (datetime.now() + timedelta(days=60)).isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            if existing.data:
                # Update existing validation
                data['validation_count'] = existing.data[0].get('validation_count', 0) + 1
                
                result = self.client.table('email_validations')\
                    .update(data)\
                    .eq('id', existing.data[0]['id'])\
                    .execute()
                
                logger.info(f"Updated validation for {email}")
            else:
                # Insert new validation
                data['first_validated_at'] = datetime.now().isoformat()
                data['validation_count'] = 1
                data['created_at'] = datetime.now().isoformat()
                
                result = self.client.table('email_validations')\
                    .insert(data)\
                    .execute()
                
                logger.info(f"Created new validation for {email}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving validation: {e}")
            return False
    
    def create_validation_run(self, run_type: str, triggered_by: str) -> Optional[str]:
        """Create a new validation run record.
        
        Args:
            run_type: Type of run (all, new, revalidation, manual)
            triggered_by: Who triggered (github_action, manual, post_ingest)
            
        Returns:
            Run ID if successful
        """
        try:
            data = {
                'run_type': run_type,
                'triggered_by': triggered_by,
                'started_at': datetime.now().isoformat()
            }
            
            result = self.client.table('email_validation_runs')\
                .insert(data)\
                .execute()
            
            run_id = result.data[0]['id']
            logger.info(f"Created validation run {run_id} (type: {run_type})")
            return run_id
            
        except Exception as e:
            logger.error(f"Error creating validation run: {e}")
            return None
    
    def update_validation_run(self, run_id: str, stats: Dict) -> bool:
        """Update validation run with statistics.
        
        Args:
            run_id: Run ID to update
            stats: Statistics dictionary
            
        Returns:
            True if successful
        """
        try:
            data = {
                'completed_at': datetime.now().isoformat(),
                'total_emails_checked': stats.get('total_emails_checked', 0),
                'new_emails_validated': stats.get('new_emails_validated', 0),
                'emails_revalidated': stats.get('emails_revalidated', 0),
                'valid_count': stats.get('valid_count', 0),
                'invalid_count': stats.get('invalid_count', 0),
                'error_count': stats.get('error_count', 0),
                'hunter_credits_used': stats.get('hunter_credits_used', 0),
                'error_log': stats.get('error_log')
            }
            
            result = self.client.table('email_validation_runs')\
                .update(data)\
                .eq('id', run_id)\
                .execute()
            
            logger.info(f"Updated validation run {run_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating validation run: {e}")
            return False
    
    def get_validation_statistics(self) -> Dict:
        """Get overall email validation statistics.
        
        Returns:
            Dictionary with statistics
        """
        try:
            # Get total candidates with emails
            total_result = self.client.table('candidates')\
                .select('id', count='exact')\
                .not_.is_('contact_email', 'null')\
                .execute()
            
            # Get validation counts
            valid_result = self.client.table('email_validations')\
                .select('id', count='exact')\
                .eq('is_valid', True)\
                .execute()
            
            invalid_result = self.client.table('email_validations')\
                .select('id', count='exact')\
                .eq('is_valid', False)\
                .execute()
            
            disposable_result = self.client.table('email_validations')\
                .select('id', count='exact')\
                .eq('is_disposable', True)\
                .execute()
            
            role_result = self.client.table('email_validations')\
                .select('id', count='exact')\
                .eq('is_role_account', True)\
                .execute()
            
            stats = {
                'total_candidates_with_email': total_result.count,
                'total_validated': valid_result.count + invalid_result.count,
                'valid_emails': valid_result.count,
                'invalid_emails': invalid_result.count,
                'disposable_emails': disposable_result.count,
                'role_accounts': role_result.count,
                'validation_coverage': round(
                    ((valid_result.count + invalid_result.count) / total_result.count * 100)
                    if total_result.count > 0 else 0,
                    1
                )
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting validation statistics: {e}")
            return {}
    
    def get_invalid_emails_report(self, limit: int = 100) -> List[Dict]:
        """Get report of invalid emails with details.
        
        Args:
            limit: Maximum number of records to return
            
        Returns:
            List of invalid email records with candidate info
        """
        try:
            result = self.client.table('email_validations')\
                .select('*, candidates!inner(full_name, source_state, office_name)')\
                .eq('is_valid', False)\
                .limit(limit)\
                .execute()
            
            return result.data
            
        except Exception as e:
            logger.error(f"Error getting invalid emails report: {e}")
            return []


def test_database_connection():
    """Test database connection and basic operations."""
    try:
        db = EmailDatabase()
        
        # Test getting candidate emails
        emails = db.get_all_candidate_emails()
        print(f"Found {len(emails)} candidate emails")
        
        if emails:
            print(f"Sample email: {emails[0]}")
        
        # Test getting statistics
        stats = db.get_validation_statistics()
        print("\nValidation Statistics:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        return True
        
    except Exception as e:
        print(f"Database test failed: {e}")
        return False


if __name__ == "__main__":
    test_database_connection()