#!/usr/bin/env python3
"""Revalidate emails due for 60-day check."""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from validator import EmailValidator
from config import get_logger

logger = get_logger(__name__)


def main():
    """Run 60-day revalidation on due emails."""
    print("=" * 60)
    print("EMAIL REVALIDATION - 60 DAY CHECK")
    print("=" * 60)
    
    try:
        # Always use Hunter.io for revalidation (automated)
        use_hunter = True
        
        # Initialize validator
        print(f"\nInitializing validator (Hunter.io: enabled)...")
        validator = EmailValidator(use_hunter=use_hunter)
        
        # Run revalidation
        print("\nChecking for emails due for 60-day revalidation...")
        
        stats = validator.revalidate_due_emails()
        
        if stats['emails_revalidated'] == 0:
            print("\n✅ No emails due for revalidation today.")
        else:
            # Print report
            print("\n" + "=" * 60)
            print(validator.get_validation_report())
            
            print("\n✅ Revalidation complete!")
            
            # Show summary
            print(f"\n📊 Summary:")
            print(f"  - Emails revalidated: {stats['emails_revalidated']}")
            print(f"  - Still valid: {stats['valid_count']}")
            print(f"  - Now invalid: {stats['invalid_count']}")
            
            if stats['error_count'] > 0:
                print(f"  - Errors: {stats['error_count']}")
            
            if stats['hunter_credits_used'] > 0:
                print(f"\n💳 Hunter.io credits used: {stats['hunter_credits_used']}")
        
    except KeyboardInterrupt:
        print("\n\n❌ Revalidation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.error(f"Revalidation failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()