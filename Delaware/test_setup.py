#!/usr/bin/env python3
"""Test Delaware setup and configuration."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    
    try:
        from src import config
        print("✅ Config module imported")
    except ImportError as e:
        print(f"❌ Failed to import config: {e}")
        return False
    
    try:
        from src.models import DelawareCandidateRaw, TransformedCandidate
        print("✅ Models imported")
    except ImportError as e:
        print(f"❌ Failed to import models: {e}")
        return False
    
    try:
        from src.transformer import DelawareTransformer
        print("✅ Transformer imported")
    except ImportError as e:
        print(f"❌ Failed to import transformer: {e}")
        return False
    
    try:
        from src.fetcher import DelawareFetcher
        print("✅ Fetcher imported")
    except ImportError as e:
        print(f"❌ Failed to import fetcher: {e}")
        return False
    
    try:
        from src.database import DelawareSupabaseClient
        print("✅ Database client imported")
    except ImportError as e:
        print(f"❌ Failed to import database: {e}")
        return False
    
    return True

def test_configuration():
    """Test configuration values."""
    print("\nTesting configuration...")
    
    from src.config import SUPABASE_URL, SUPABASE_KEY, SOURCE_STATE, DELAWARE_URLS
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ Missing Supabase credentials")
        print("   Please set SUPABASE_URL and SUPABASE_KEY in .env file")
        return False
    
    print("✅ Supabase credentials configured")
    print(f"✅ Source state: {SOURCE_STATE}")
    print(f"✅ URLs configured: {list(DELAWARE_URLS.keys())}")
    
    return True

def test_data_directory():
    """Test data directory setup."""
    print("\nTesting data directory...")
    
    from src.config import DATA_DIR, LOG_DIR
    
    if not DATA_DIR.exists():
        print(f"❌ Data directory does not exist: {DATA_DIR}")
        return False
    
    print(f"✅ Data directory exists: {DATA_DIR}")
    
    if not LOG_DIR.exists():
        print(f"❌ Log directory does not exist: {LOG_DIR}")
        return False
    
    print(f"✅ Log directory exists: {LOG_DIR}")
    
    # Check for HTML files
    html_files = list(DATA_DIR.glob("*.html"))
    if html_files:
        print(f"✅ Found {len(html_files)} HTML files in data directory:")
        for f in html_files:
            print(f"   - {f.name}")
    else:
        print("ℹ️ No HTML files found in data directory")
        print("   You'll need to download Delaware HTML files manually due to Cloudflare protection")
        print("   Save them as:")
        print("   - school_board_candidates_2026.html")
        print("   - primary_candidates_2026.html")
        print("   - general_candidates_2026.html")
    
    return True

def test_transformer():
    """Test the transformer with sample data."""
    print("\nTesting transformer...")
    
    from src.transformer import DelawareTransformer
    from src.models import DelawareCandidateRaw
    
    # Create sample candidate
    sample = DelawareCandidateRaw(
        name="John Doe",
        office="State Senate District 5",
        district="5",
        county="New Castle",
        election_type="primary"
    )
    
    transformer = DelawareTransformer()
    result = transformer.transform_candidate(sample)
    
    if result:
        print("✅ Transformer successfully processed sample candidate:")
        print(f"   Name: {result.full_name}")
        print(f"   Office: {result.office_name}")
        print(f"   District: {result.district_number}")
        print(f"   Level: {result.office_level}")
        return True
    else:
        print("❌ Transformer failed to process sample candidate")
        return False

def test_database_connection():
    """Test database connection (read-only)."""
    print("\nTesting database connection...")
    
    try:
        from src.database import DelawareSupabaseClient
        
        client = DelawareSupabaseClient()
        
        # Try to fetch existing candidates (won't modify anything)
        candidates = client.get_delaware_candidates()
        print(f"✅ Database connection successful")
        print(f"   Found {len(candidates)} existing Delaware candidates")
        
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("DELAWARE SETUP TEST")
    print("=" * 60)
    
    tests = [
        ("Imports", test_imports),
        ("Configuration", test_configuration),
        ("Data Directory", test_data_directory),
        ("Transformer", test_transformer),
        ("Database Connection", test_database_connection)
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ Test '{name}' crashed: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{name:20} {status}")
    
    all_passed = all(r for _, r in results)
    
    if all_passed:
        print("\n🎉 All tests passed! Delaware setup is ready.")
        print("\nNext steps:")
        print("1. Download Delaware HTML files if not already done")
        print("2. Run database migrations: add_multi_state_support.sql")
        print("3. Test with: python Delaware/src/main.py --dry-run")
    else:
        print("\n⚠️ Some tests failed. Please fix the issues above.")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())