#!/usr/bin/env python3
"""Validate only new/unvalidated emails."""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from validator import EmailValidator
from config import get_logger

logger = get_logger(__name__)


def main():
    """Run validation on new/unvalidated emails only."""
    print("=" * 60)
    print("EMAIL VALIDATION - NEW EMAILS ONLY")
    print("=" * 60)
    
    try:
        # Default to using Hunter.io for automated runs
        use_hunter = True
        
        # Check if running interactively
        if sys.stdin.isatty():
            use_hunter_input = input("\nUse Hunter.io API for validation? (y/n) [y]: ").lower()
            use_hunter = use_hunter_input != 'n'
        
        # Initialize validator
        print(f"\nInitializing validator (Hunter.io: {'enabled' if use_hunter else 'disabled'})...")
        validator = EmailValidator(use_hunter=use_hunter)
        
        # Run validation
        print("\nChecking for unvalidated emails...")
        
        stats = validator.validate_new_emails()
        
        if stats['new_emails_validated'] == 0:
            print("\n✅ No new emails to validate. All emails are up to date!")
        else:
            # Print report
            print("\n" + "=" * 60)
            print(validator.get_validation_report())
            
            print("\n✅ Validation complete!")
            
            # Show summary
            print(f"\n📊 Summary:")
            print(f"  - New emails validated: {stats['new_emails_validated']}")
            print(f"  - Valid: {stats['valid_count']}")
            print(f"  - Invalid: {stats['invalid_count']}")
            
            if stats['error_count'] > 0:
                print(f"  - Errors: {stats['error_count']}")
            
            if use_hunter and stats['hunter_credits_used'] > 0:
                print(f"\n💳 Hunter.io credits used: {stats['hunter_credits_used']}")
        
    except KeyboardInterrupt:
        print("\n\n❌ Validation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.error(f"Validation failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()