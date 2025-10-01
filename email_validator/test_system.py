#!/usr/bin/env python3
"""Test the email validation system."""

import sys
from hunter_client import HunterClient, test_hunter_connection
from free_validators import FreeValidators
from database import EmailDatabase
from validator import EmailValidator
from config import get_logger

logger = get_logger(__name__)


def test_components():
    """Test individual components of the system."""
    print("=" * 60)
    print("EMAIL VALIDATION SYSTEM TEST")
    print("=" * 60)
    
    all_tests_passed = True
    
    # Test 1: Hunter.io connection
    print("\n1. Testing Hunter.io connection...")
    try:
        if test_hunter_connection():
            print("   ✅ Hunter.io connection successful")
        else:
            print("   ❌ Hunter.io connection failed")
            all_tests_passed = False
    except Exception as e:
        print(f"   ❌ Hunter.io test failed: {e}")
        all_tests_passed = False
    
    # Test 2: Free validators
    print("\n2. Testing free validators...")
    try:
        validator = FreeValidators()
        
        # Test syntax validation
        valid_email = "test@example.com"
        invalid_email = "not-an-email"
        
        syntax_valid, _ = validator.validate_syntax(valid_email)
        syntax_invalid, _ = validator.validate_syntax(invalid_email)
        
        if syntax_valid and not syntax_invalid:
            print("   ✅ Syntax validation working")
        else:
            print("   ❌ Syntax validation not working correctly")
            all_tests_passed = False
        
        # Test typo detection
        typo_email = "test@gmial.com"
        has_typo, suggested = validator.check_typos(typo_email)
        
        if has_typo and suggested == "test@gmail.com":
            print("   ✅ Typo detection working")
        else:
            print("   ❌ Typo detection not working correctly")
            all_tests_passed = False
        
        # Test disposable detection
        disposable_email = "test@10minutemail.com"
        is_disposable = validator.is_disposable(disposable_email)
        
        if is_disposable:
            print("   ✅ Disposable email detection working")
        else:
            print("   ❌ Disposable email detection not working")
            all_tests_passed = False
        
        # Test role account detection
        role_email = "info@example.com"
        is_role = validator.is_role_account(role_email)
        
        if is_role:
            print("   ✅ Role account detection working")
        else:
            print("   ❌ Role account detection not working")
            all_tests_passed = False
            
    except Exception as e:
        print(f"   ❌ Free validators test failed: {e}")
        all_tests_passed = False
    
    # Test 3: Database connection
    print("\n3. Testing database connection...")
    try:
        db = EmailDatabase()
        
        # Try to get statistics
        stats = db.get_validation_statistics()
        
        print("   ✅ Database connection successful")
        print(f"   📊 Current stats: {stats.get('total_candidates_with_email', 0)} candidates with emails")
        
    except Exception as e:
        print(f"   ❌ Database test failed: {e}")
        all_tests_passed = False
    
    # Test 4: Full validation pipeline (without Hunter.io)
    print("\n4. Testing validation pipeline (free checks only)...")
    try:
        validator = EmailValidator(use_hunter=False)
        
        # Test a known good email format
        test_email = "john.doe@gmail.com"
        result = validator.validate_email(test_email)
        
        if result.get('syntax_valid'):
            print("   ✅ Validation pipeline working")
            print(f"   📧 Test email result: Valid={result.get('is_valid')}")
        else:
            print("   ❌ Validation pipeline not working")
            all_tests_passed = False
            
    except Exception as e:
        print(f"   ❌ Validation pipeline test failed: {e}")
        all_tests_passed = False
    
    # Summary
    print("\n" + "=" * 60)
    if all_tests_passed:
        print("✅ All tests passed! System is ready.")
    else:
        print("❌ Some tests failed. Please check the configuration.")
    print("=" * 60)
    
    return all_tests_passed


def test_sample_emails():
    """Test validation on sample emails."""
    print("\n" + "=" * 60)
    print("SAMPLE EMAIL VALIDATION TEST")
    print("=" * 60)
    
    # Sample emails to test
    test_emails = [
        ("valid@gmail.com", "Valid Gmail"),
        ("john.smith@maryland.gov", "Government email"),
        ("info@campaign2024.org", "Role account"),
        ("test@gmial.com", "Typo in domain"),
        ("user@10minutemail.com", "Disposable email"),
        ("invalid.email", "Invalid syntax"),
        ("test@nonexistent-domain-12345.com", "Non-existent domain"),
    ]
    
    print("\nTesting sample emails (free checks only):")
    print("-" * 40)
    
    validator = EmailValidator(use_hunter=False)
    
    for email, description in test_emails:
        print(f"\n📧 {email} ({description})")
        
        result = validator.validate_email(email)
        
        print(f"   Valid: {result.get('is_valid')}")
        if result.get('validation_error'):
            print(f"   Issue: {result['validation_error']}")
        
        if result.get('is_disposable'):
            print("   ⚠️  Disposable email")
        if result.get('is_role_account'):
            print("   ⚠️  Role account")


def main():
    """Run all tests."""
    try:
        # Run component tests
        if not test_components():
            print("\n⚠️  Fix component issues before proceeding.")
            sys.exit(1)
        
        # Run sample email tests
        test_sample_emails()
        
        # Offer to test with real data
        print("\n" + "=" * 60)
        response = input("\nWould you like to validate a few real candidate emails? (y/n): ")
        
        if response.lower() == 'y':
            print("\nFetching a sample of candidate emails...")
            db = EmailDatabase()
            emails = db.get_all_candidate_emails()[:5]  # Get first 5
            
            if emails:
                print(f"Found {len(emails)} sample emails")
                use_hunter = input("Use Hunter.io for these? (y/n): ").lower() == 'y'
                
                validator = EmailValidator(use_hunter=use_hunter)
                
                for candidate_id, email, name in emails:
                    print(f"\n📧 {name}: {email}")
                    result = validator.validate_email(email, candidate_id, name)
                    print(f"   Valid: {result.get('is_valid')}")
                    if result.get('hunter_score') is not None:
                        print(f"   Hunter.io score: {result['hunter_score']}")
            else:
                print("No candidate emails found in database")
        
        print("\n✅ Testing complete!")
        
    except KeyboardInterrupt:
        print("\n\n❌ Testing cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        logger.error(f"Test failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()