#!/usr/bin/env python3
"""Validate all candidate emails in the database."""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from validator import EmailValidator
from config import get_logger

logger = get_logger(__name__)


def main():
    """Run validation on all emails."""
    print("=" * 60)
    print("EMAIL VALIDATION - ALL EMAILS")
    print("=" * 60)
    
    try:
        # Check if we should use Hunter.io
        use_hunter = input("\nUse Hunter.io API for validation? (y/n): ").lower() == 'y'
        
        if use_hunter:
            print("\n⚠️  WARNING: This will use Hunter.io credits!")
            confirm = input("Continue? (y/n): ").lower()
            if confirm != 'y':
                print("Cancelled.")
                return
        
        # Initialize validator
        print(f"\nInitializing validator (Hunter.io: {'enabled' if use_hunter else 'disabled'})...")
        validator = EmailValidator(use_hunter=use_hunter)
        
        # Run validation
        print("\nStarting validation of all emails...")
        print("This may take several minutes...\n")
        
        stats = validator.validate_all_emails()
        
        # Print report
        print("\n" + "=" * 60)
        print(validator.get_validation_report())
        
        print("\n✅ Validation complete!")
        
        # Show summary
        if stats['error_count'] > 0:
            print(f"\n⚠️  {stats['error_count']} errors encountered")
            print("Check logs for details.")
        
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