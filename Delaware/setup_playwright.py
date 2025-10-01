#!/usr/bin/env python3
"""Setup script for Playwright browsers."""

import subprocess
import sys


def install_playwright():
    """Install Playwright and its browsers."""
    print("Installing Playwright dependencies...")
    
    try:
        # Install Python package
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements_browser.txt"])
        print("✅ Installed Python packages")
        
        # Install Playwright browsers
        print("\nInstalling Playwright browsers...")
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        print("✅ Installed Chromium browser")
        
        # Install system dependencies (if needed)
        print("\nInstalling system dependencies...")
        subprocess.check_call([sys.executable, "-m", "playwright", "install-deps", "chromium"])
        print("✅ Installed system dependencies")
        
        print("\n🎉 Playwright setup complete!")
        print("\nYou can now run the browser fetcher:")
        print("  python Delaware/src/browser_fetcher.py")
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error during installation: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure you have pip installed")
        print("2. On Linux/Mac, you may need sudo for system dependencies:")
        print("   sudo $(which python) -m playwright install-deps chromium")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    install_playwright()