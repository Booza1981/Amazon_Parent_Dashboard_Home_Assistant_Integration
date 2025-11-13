import argparse
import json
import os
import re
from pathlib import Path
from playwright.sync_api import Playwright, sync_playwright, expect
import sys

# Import the data extractor for API-based controls
sys.path.insert(0, str(Path(__file__).parent.parent))
from amazon_parental.data_extractor import DashboardDataExtractor

SCRIPT_DIR = Path(__file__).parent
COOKIES_FILE = SCRIPT_DIR / "cookies.json"
BASE_URL = "https://parents.amazon.co.uk"

class AmazonParentalDashboard:
    def __init__(self, playwright: Playwright, headless: bool = True, use_api: bool = True):
        self.browser = playwright.chromium.launch(headless=headless)
        self.context = None
        self.page = None
        self.use_api = use_api  # Use API methods instead of button clicks when True

    def login(self):
        if Path(COOKIES_FILE).exists():
            print("Loading cookies from file...")
            self.context = self.browser.new_context(storage_state=COOKIES_FILE)
            self.page = self.context.new_page()
            self.page.goto(f"{BASE_URL}/intro")
            # Check if login was successful by looking for a known element
            try:
                expect(self.page.get_by_role("button", name="Pause/Resume Devices")).to_be_visible(timeout=10000)
                print("Login successful using cookies.")
                return
            except Exception:
                print("Cookie login failed. Proceeding with manual login.")
                # If cookie login fails, create a new context
                self.context.close()
                self.context = self.browser.new_context()
                self.page = self.context.new_page()
        else:
            self.context = self.browser.new_context()
            self.page = self.context.new_page()

        print("Performing manual login. Please follow the prompts in the browser.")
        self.page.goto(f"{BASE_URL}/intro")
        self.page.get_by_role("button", name="Sign in").click()
        
        print("Please fill in your email and password in the browser.")
        # Wait for the user to manually log in.
        # Successful login is determined by the presence of the "Pause/Resume Devices" button.
        expect(self.page.get_by_role("button", name="Pause/Resume Devices")).to_be_visible(timeout=300000) # 5 minutes timeout for manual login
        
        print("Login successful. Saving cookies...")
        self.context.storage_state(path=COOKIES_FILE)
        print(f"Cookies saved to {COOKIES_FILE}")

    def pause_devices(self, duration: float = 1):
        """
        Pause/block devices for a specified duration.
        
        Args:
            duration: Duration in hours (can be fractional, e.g., 0.5 for 30 minutes)
        """
        if self.use_api:
            # Use API-based method (preferred) - directly call with existing page context
            child_id = self._get_child_id()
            if not child_id:
                print("⚠️  Could not detect child ID, falling back to button method")
                self.use_api = False
            else:
                # Create a minimal extractor instance using our existing browser context
                from amazon_parental.data_extractor import DashboardDataExtractor
                import sys
                
                # Temporarily create an extractor that shares our browser/page
                class QuickExtractor:
                    def __init__(self, page, child_id):
                        self.page = page
                        self.context = page.context
                        self.child_id = child_id
                    
                    def _get_csrf_token(self):
                        try:
                            cookies = self.context.cookies()
                            for cookie in cookies:
                                if cookie['name'] == 'ft-panda-csrf-token':
                                    return cookie['value']
                        except:
                            return None
                    
                    def _api_call(self, method, endpoint, data=None):
                        from datetime import datetime
                        import json
                        url = f"{BASE_URL}{endpoint}"
                        csrf_token = self._get_csrf_token() if method in ["POST", "PUT"] else None
                        headers = {
                            "accept": "application/json, text/plain, */*",
                            "content-type": "application/json",
                        }
                        if csrf_token:
                            headers["x-amzn-csrf"] = csrf_token
                        json_data = json.dumps(data) if data else None
                        
                        if method == "POST":
                            response = self.page.request.post(url, data=json_data, headers=headers)
                        else:
                            return None
                        
                        return response.json() if response.status == 200 else None
                    
                    def set_offscreen_time(self, duration_hours):
                        expiration_seconds = int(duration_hours * 3600)
                        payload = {
                            "directedIds": [self.child_id],
                            "expirationTimeInSeconds": expiration_seconds
                        }
                        print(f"⏸️  Blocking devices for {duration_hours} hour(s) ({expiration_seconds} seconds)...")
                        result = self._api_call("POST", "/ajax/set-offscreen-time", data=payload)
                        return result is not None
                
                ext = QuickExtractor(self.page, child_id)
                if ext.set_offscreen_time(duration):
                    print("✅ Devices blocked successfully")
                    return True
                else:
                    print("⚠️  API method failed, falling back to button method")
                    self.use_api = False
        
        if not self.use_api:
            # Use legacy button-clicking method
            if not 1 <= duration <= 12:
                raise ValueError("Duration must be between 1 and 12 hours for button-based method.")
            
            duration_int = int(duration)
            print(f"Pausing devices for {duration_int} hour(s) using button method...")
            self.page.get_by_role("button", name="Pause/Resume Devices").click()
            self.page.get_by_text("hour").click()
            option_name = f"{duration_int} hour" if duration_int == 1 else f"{duration_int} hours"
            self.page.get_by_role("option", name=option_name, exact=True).click()
            self.page.get_by_role("button", name="Pause Devices").click()
            self.page.get_by_role("button", name="OK").click()
            print("Devices paused successfully.")

    def resume_devices(self):
        """Resume/unblock devices."""
        if self.use_api:
            # Use API-based method (preferred)
            child_id = self._get_child_id()
            if not child_id:
                print("⚠️  Could not detect child ID, falling back to button method")
                self.use_api = False
            else:
                # Use the same QuickExtractor approach
                import json
                csrf_token = None
                try:
                    cookies = self.context.cookies()
                    for cookie in cookies:
                        if cookie['name'] == 'ft-panda-csrf-token':
                            csrf_token = cookie['value']
                except:
                    pass
                
                url = f"{BASE_URL}/ajax/set-offscreen-time"
                headers = {
                    "accept": "application/json, text/plain, */*",
                    "content-type": "application/json",
                }
                if csrf_token:
                    headers["x-amzn-csrf"] = csrf_token
                
                payload = {"directedIds": [child_id], "expirationTimeInSeconds": 0}
                json_data = json.dumps(payload)
                
                print("▶️  Unblocking devices...")
                response = self.page.request.post(url, data=json_data, headers=headers)
                
                if response.status == 200:
                    print("✅ Devices unblocked successfully")
                    return True
                else:
                    print("⚠️  API method failed, falling back to button method")
                    self.use_api = False
        
        if not self.use_api:
            # Use legacy button-clicking method
            print("Resuming devices using button method...")
            self.page.get_by_role("button", name="Pause/Resume Devices").click()
            self.page.get_by_role("button", name="Resume", exact=True).click()
            self.page.get_by_role("button", name="OK").click()
            print("Devices resumed successfully.")
    
    def _get_child_id(self):
        """Extract child ID from current page URL or find it on the page."""
        # Try URL first (after any redirects)
        current_url = self.page.url
        if "childDirectedId=" in current_url:
            return current_url.split("childDirectedId=")[1].split("&")[0]
        
        # Wait a moment for page to fully load and then try to find it in page links
        try:
            # Wait for any links with childDirectedId to appear
            self.page.wait_for_selector('a[href*="childDirectedId="]', timeout=3000)
            child_links = self.page.query_selector_all('a[href*="childDirectedId="]')
            if child_links:
                href = child_links[0].get_attribute('href')
                if "childDirectedId=" in href:
                    return href.split("childDirectedId=")[1].split("&")[0]
        except:
            pass
        
        return None

    def close(self):
        if self.context:
            self.context.close()
        self.browser.close()

def main():
    parser = argparse.ArgumentParser(description="Amazon Parental Dashboard Control")
    parser.add_argument("action", choices=["pause", "resume"], help="Action to perform")
    parser.add_argument("--duration", type=float, default=1, 
                       help="Duration in hours to pause the device. Can be fractional (e.g., 0.5 for 30 minutes). Default is 1.")
    parser.add_argument("--headed", action="store_true", help="Run in headed mode for debugging.")
    parser.add_argument("--use-buttons", action="store_true", 
                       help="Use button-clicking method instead of faster API calls (slower but more visual).")
    args = parser.parse_args()

    # If using API method, use the data extractor directly (faster and more reliable)
    if not args.use_buttons:
        from amazon_parental.data_extractor import DashboardDataExtractor
        with sync_playwright() as p:
            extractor = DashboardDataExtractor(p, headless=not args.headed)
            try:
                extractor.login()
                if args.action == "pause":
                    success = extractor.set_offscreen_time(args.duration)
                    if not success:
                        print("✅ Device blocking completed")
                elif args.action == "resume":
                    success = extractor.clear_offscreen_time()
                    if not success:
                        print("✅ Device unblocking completed")
            finally:
                extractor.close()
    else:
        # Use button method
        with sync_playwright() as p:
            dashboard = AmazonParentalDashboard(p, headless=not args.headed, use_api=False)
            try:
                dashboard.login()
                if args.action == "pause":
                    dashboard.pause_devices(args.duration)
                elif args.action == "resume":
                    dashboard.resume_devices()
            finally:
                dashboard.close()

if __name__ == "__main__":
    main()
