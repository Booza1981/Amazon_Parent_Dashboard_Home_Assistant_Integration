"""
Simple script to refresh Amazon Parental Dashboard cookies.
Opens a browser, lets you log in, then saves the cookies.
"""

import json
from pathlib import Path
from playwright.sync_api import sync_playwright

SCRIPT_DIR = Path(__file__).parent
COOKIES_FILE = SCRIPT_DIR / "cookies.json"
BASE_URL = "https://parents.amazon.co.uk"

def main():
    print("🔐 Amazon Parental Dashboard Cookie Refresh")
    print("=" * 60)
    print("This will open a browser for you to log in.")
    print("After logging in successfully, press Enter in this terminal.")
    print("=" * 60 + "\n")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        # Navigate to the dashboard
        print(f"Opening {BASE_URL}...")
        page.goto(f"{BASE_URL}/intro")
        
        print("\n📋 Instructions:")
        print("1. Click 'Sign in' in the browser")
        print("2. Enter your Amazon credentials")
        print("3. Complete any 2FA if required")
        print("4. Wait until you see the dashboard")
        print("5. Come back here and press Enter")
        print()
        
        # Wait for user to confirm they've logged in
        input("Press Enter after you've successfully logged in...")
        
        # Save cookies
        print("\n💾 Saving cookies...")
        context.storage_state(path=COOKIES_FILE)
        
        print(f"✅ Cookies saved to {COOKIES_FILE}")
        print("You can now close the browser window.")
        
        input("\nPress Enter to close the browser...")
        
        browser.close()
        print("\n✅ Done! You can now run data_extractor.py")

if __name__ == "__main__":
    main()
