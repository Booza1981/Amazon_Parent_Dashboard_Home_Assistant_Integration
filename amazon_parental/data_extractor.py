"""
Amazon Parental Dashboard Data Extractor

Extracts analytics and control data from the Amazon Parental Dashboard
using discovered API endpoints.

Discovered API Endpoints:
- GET /ajax/get-weekly-activities-v2 - Viewing history and usage statistics
- GET /ajax/get-adjusted-time-limits - Time limit configuration
- PUT /ajax/set-time-limit-v2 - Update time limit configuration
- PUT /ajax/set-offscreen-time - Block devices for a specified duration
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json
from pathlib import Path
from playwright.sync_api import Playwright, sync_playwright, Page, Request, Response

SCRIPT_DIR = Path(__file__).parent
COOKIES_FILE = SCRIPT_DIR / "cookies.json"
BASE_URL = "https://parents.amazon.co.uk"


def normalize_day_name(day: str) -> str:
    """
    Normalize day name to match Amazon's format (capitalized).
    
    Args:
        day: Day name in any case (e.g., 'monday', 'Monday', 'MONDAY')
        
    Returns:
        Capitalized day name (e.g., 'Monday')
    """
    return day.capitalize()


class DashboardDataExtractor:
    """
    Extracts analytics data from Amazon Parental Dashboard using direct API calls.
    
    This implementation uses Playwright to make authenticated API requests
    to the discovered Amazon endpoints.
    """
    
    def __init__(self, playwright: Playwright, headless: bool = True):
        """Initialize the data extractor."""
        self.browser = playwright.chromium.launch(headless=headless)
        self.context = None
        self.page = None
        self.child_id = None  # Will be auto-detected
        self.last_cookie_save = None  # Track when cookies were last saved
        
    def login(self):
        """Login using saved cookies and auto-detect child ID."""
        if not Path(COOKIES_FILE).exists():
            raise FileNotFoundError(
                f"Cookies file not found at {COOKIES_FILE}. "
                "Please run the control.py script first to login."
            )
        
        print("Loading cookies from file...")
        self.context = self.browser.new_context(storage_state=COOKIES_FILE)
        self.page = self.context.new_page()
        
        # Navigate and wait for page to be fully loaded
        print("Navigating to dashboard...")
        self.page.goto(f"{BASE_URL}/intro", wait_until="networkidle")
        
        # Wait a moment for any dynamic content to load
        self.page.wait_for_timeout(2000)
        
        # Auto-detect child ID using multiple methods
        # Method 1: Check current URL (after any redirects)
        try:
            current_url = self.page.url
            if "childDirectedId=" in current_url:
                self.child_id = current_url.split("childDirectedId=")[1].split("&")[0]
                print(f"✅ Logged in successfully (child ID from URL: {self.child_id[:20]}...)")
                return
        except Exception as e:
            print(f"⚠️  Could not extract child ID from URL: {e}")
        
        # Method 2: Try to get from get-household API
        try:
            household = self._api_call("GET", "/ajax/get-household")
            if household and "members" in household:
                children = [m for m in household["members"] if m.get("role") == "CHILD"]
                if children:
                    self.child_id = children[0]["directedId"]
                    child_name = children[0].get('firstName', 'Unknown')
                    print(f"✅ Logged in successfully (child ID from API: {child_name})")
                    return
        except Exception as e:
            print(f"⚠️  Could not get child ID from household API: {e}")
        
        # Method 3: Try navigating to settings and extracting from there
        try:
            # Look for child profile links on the page
            self.page.wait_for_selector('a[href*="childDirectedId="]', timeout=5000)
            child_links = self.page.query_selector_all('a[href*="childDirectedId="]')
            if child_links:
                href = child_links[0].get_attribute('href')
                if "childDirectedId=" in href:
                    self.child_id = href.split("childDirectedId=")[1].split("&")[0]
                    print(f"✅ Logged in successfully (child ID from page links: {self.child_id[:20]}...)")
                    return
        except Exception as e:
            print(f"⚠️  Could not extract child ID from page links: {e}")
        
        # If all methods fail
        print("⚠️  Warning: Could not auto-detect child ID")
        print("   You will need to specify child_id manually when calling methods")
        print("   Tip: Check the URL after navigating to your child's dashboard")
        
        # Save cookies after successful login
        self.save_cookies()
    
    def save_cookies(self):
        """Save current browser cookies to file for persistence."""
        if not self.context:
            return
        
        try:
            self.context.storage_state(path=COOKIES_FILE)
            self.last_cookie_save = datetime.now()
            print(f"💾 Cookies saved at {self.last_cookie_save.strftime('%H:%M:%S')}")
        except Exception as e:
            print(f"⚠️  Failed to save cookies: {e}")
    
    def check_cookie_expiry(self) -> Dict[str, Any]:
        """
        Check cookie expiry status.
        
        Returns:
            Dictionary with:
            - expired: bool - if any critical cookies are expired
            - expiring_soon: bool - if cookies expire within 4 hours
            - details: dict - expiry info for each critical cookie
        """
        if not self.context:
            return {"expired": True, "expiring_soon": True, "details": {}}
        
        try:
            cookies = self.context.cookies()
            critical_cookies = ['ft-session', 'ft-panda-csrf-token', 'at-acbuk']
            now = datetime.now().timestamp()
            four_hours = 4 * 60 * 60
            
            result = {
                "expired": False,
                "expiring_soon": False,
                "details": {}
            }
            
            for cookie in cookies:
                if cookie['name'] in critical_cookies:
                    expires = cookie.get('expires', 0)
                    time_left = expires - now
                    
                    result['details'][cookie['name']] = {
                        "expires": datetime.fromtimestamp(expires).isoformat() if expires else None,
                        "seconds_left": time_left if expires else None
                    }
                    
                    if expires and time_left < 0:
                        result['expired'] = True
                    elif expires and time_left < four_hours:
                        result['expiring_soon'] = True
            
            return result
        except Exception as e:
            print(f"⚠️  Error checking cookie expiry: {e}")
            return {"expired": False, "expiring_soon": False, "details": {}}
    
    def auto_refresh_session(self) -> bool:
        """
        Attempt to refresh the session by navigating to the dashboard.
        This works if cookies are still valid but close to expiry.
        
        Returns:
            True if refresh was successful, False otherwise
        """
        if not self.page:
            print("⚠️  No page available for refresh")
            return False
        
        try:
            print("🔄 Attempting to auto-refresh session...")
            # Navigate to dashboard to trigger cookie refresh
            self.page.goto(f"{BASE_URL}/intro", wait_until="networkidle")
            self.page.wait_for_timeout(2000)
            
            # Save the refreshed cookies
            self.save_cookies()
            
            # Check if refresh was successful
            expiry_status = self.check_cookie_expiry()
            if not expiry_status['expired']:
                print("✅ Session auto-refreshed successfully")
                return True
            else:
                print("⚠️  Session refresh failed - cookies still expired")
                return False
        except Exception as e:
            print(f"❌ Error during auto-refresh: {e}")
            return False
    
    def _get_csrf_token(self) -> Optional[str]:
        """Extract CSRF token from page cookies."""
        try:
            cookies = self.context.cookies()
            for cookie in cookies:
                if cookie['name'] == 'ft-panda-csrf-token':
                    return cookie['value']
        except Exception as e:
            print(f"⚠️  Could not get CSRF token: {e}")
        return None
    
    def _api_call(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make an authenticated API call to Amazon's dashboard.
        
        Args:
            method: HTTP method (GET, POST, PUT)
            endpoint: API endpoint path
            data: Optional JSON data for POST/PUT requests
            
        Returns:
            Parsed JSON response or None if failed
        """
        url = f"{BASE_URL}{endpoint}"
        
        # Get CSRF token for write operations
        csrf_token = self._get_csrf_token() if method in ["POST", "PUT"] else None
        
        # Prepare headers
        headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
        }
        if csrf_token:
            headers["x-amzn-csrf"] = csrf_token
        
        # Serialize data to JSON string for POST/PUT
        json_data = json.dumps(data) if data else None
        
        try:
            if method == "GET":
                response = self.page.request.get(url, headers=headers)
            elif method == "POST":
                response = self.page.request.post(url, data=json_data, headers=headers)
            elif method == "PUT":
                response = self.page.request.put(url, data=json_data, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            if response.status == 200:
                try:
                    # Save cookies after successful API call (every 5 minutes)
                    if self.last_cookie_save is None or \
                       (datetime.now() - self.last_cookie_save).total_seconds() > 300:
                        self.save_cookies()
                    return response.json()
                except:
                    # Some endpoints return empty body or non-JSON on success
                    return {}
            elif response.status == 401:
                # Authentication failed - try to auto-refresh session
                print("⚠️  Authentication failed (401) - attempting auto-refresh...")
                if self.auto_refresh_session():
                    # Retry the request once after refresh
                    print(f"🔄 Retrying {method} {endpoint}...")
                    try:
                        if method == "GET":
                            response = self.page.request.get(url, headers=headers)
                        elif method == "POST":
                            response = self.page.request.post(url, data=json_data, headers=headers)
                        elif method == "PUT":
                            response = self.page.request.put(url, data=json_data, headers=headers)
                        
                        if response.status == 200:
                            return response.json() if response.text() else {}
                    except:
                        pass
                
                print(f"❌ API call failed after refresh: {method} {endpoint} -> HTTP 401")
                print(f"   🔑 Please refresh cookies manually via web UI at http://YOUR_IP:5000")
                return None
            else:
                print(f"⚠️  API call failed: {method} {endpoint} -> HTTP {response.status}")
                try:
                    response_text = response.text()
                    print(f"   Response body: {response_text[:500]}")
                    
                    # Try to parse as JSON for better error messages
                    try:
                        error_json = json.loads(response_text)
                        if "message" in error_json:
                            print(f"   Error message: {error_json['message']}")
                        if "errors" in error_json:
                            print(f"   Errors: {error_json['errors']}")
                    except:
                        pass
                except:
                    print(f"   Could not read response body")
                
                # Log request details for debugging
                if data:
                    print(f"   Request payload: {json.dumps(data)[:500]}")
                
                return None
        except Exception as e:
            print(f"❌ Error calling API {endpoint}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_usage_statistics(self, child_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract usage statistics for a child from weekly activities API.
        
        Args:
            child_id: Optional child identifier (uses auto-detected if not provided)
        
        Returns:
            Dictionary containing:
            - today_minutes: Screen time today
            - week_minutes: Screen time this week
            - weekly_breakdown: List of daily usage for the week
            - content_breakdown: Usage by content type
        """
        cid = child_id or self.child_id
        if not cid:
            print("❌ No child ID available")
            return {}
        
        # Calculate time range (last 7 days)
        now = datetime.now()
        end_time = int(now.timestamp())
        start_time = int((now - timedelta(days=7)).timestamp())
        
        # Call the weekly activities API (POST request)
        # Requires: childDirectedId, startTime, endTime, aggregationInterval, timeZone
        data = {
            "childDirectedId": cid,
            "startTime": start_time,
            "endTime": end_time,
            "aggregationInterval": 86400,  # 1 day in seconds
            "timeZone": "Europe/London"  # Adjust if needed
        }
        activities = self._api_call("POST", "/ajax/get-weekly-activities-v2", data=data)
        
        if not activities or "activityV2Data" not in activities:
            print("⚠️  No activity data returned")
            return {
                "today_minutes": 0,
                "week_minutes": 0,
                "weekly_breakdown": [],
                "content_breakdown": {},
                "timestamp": datetime.now().isoformat()
            }
        
        # Parse the activity data
        activity_data = activities["activityV2Data"]
        
        # activityV2Data is an array of categories (APP, VIDEO, BOOK, etc.)
        # Each category has aggregatedDuration (total minutes) and intervals (daily breakdown)
        weekly_breakdown = []
        total_week_minutes = 0
        today_minutes = 0
        today_timestamp = int(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
        
        # Dictionary to accumulate minutes by day
        daily_totals = {}
        
        if isinstance(activity_data, list):
            for category_data in activity_data:
                category = category_data.get("category", "Unknown")
                category_seconds = category_data.get("aggregatedDuration", 0)
                category_minutes = category_seconds / 60  # Convert seconds to minutes
                total_week_minutes += category_minutes
                
                # Process intervals (daily breakdown)
                for interval in category_data.get("intervals", []):
                    interval_start = interval.get("startTime", 0)
                    interval_seconds = interval.get("aggregatedDuration", 0)
                    interval_minutes = interval_seconds / 60  # Convert seconds to minutes
                    
                    # Convert timestamp to date
                    interval_date = datetime.fromtimestamp(interval_start).strftime("%Y-%m-%d")
                    
                    # Accumulate minutes for this day
                    if interval_date not in daily_totals:
                        daily_totals[interval_date] = 0
                    daily_totals[interval_date] += interval_minutes
                    
                    # Check if this is today
                    if interval_start >= today_timestamp:
                        today_minutes += interval_minutes
        
        # Convert daily totals to list
        for date, minutes in sorted(daily_totals.items()):
            weekly_breakdown.append({
                "date": date,
                "minutes": minutes
            })
        
        return {
            "today_minutes": today_minutes,
            "week_minutes": total_week_minutes,
            "weekly_breakdown": weekly_breakdown,
            "raw_data": activity_data,  # Include raw data for debugging
            "timestamp": datetime.now().isoformat()
        }
    
    def get_viewing_history(self, child_id: Optional[str] = None, 
                           days: int = 7) -> List[Dict[str, Any]]:
        """
        Extract viewing history for a child from weekly activities API.
        
        Args:
            child_id: Optional child identifier (uses auto-detected if not provided)
            days: Number of days of history to retrieve (currently gets full week)
        
        Returns:
            List of dictionaries, each containing:
            - content_title: Name of content watched
            - content_type: Type (video, app, game, book, etc.)
            - duration_minutes: How long it was used
            - date: Date accessed
        """
        cid = child_id or self.child_id
        if not cid:
            print("❌ No child ID available")
            return []
        
        # Calculate time range
        now = datetime.now()
        end_time = int(now.timestamp())
        start_time = int((now - timedelta(days=days)).timestamp())
        
        # Call the weekly activities API
        data = {
            "childDirectedId": cid,
            "startTime": start_time,
            "endTime": end_time,
            "aggregationInterval": 86400,
            "timeZone": "Europe/London"
        }
        activities = self._api_call("POST", "/ajax/get-weekly-activities-v2", data=data)
        
        if not activities or "activityV2Data" not in activities:
            print("⚠️  No activity data returned")
            return []
        
        # Parse viewing history from activity data
        viewing_history = []
        activity_data = activities["activityV2Data"]
        
        # activityV2Data is an array of categories with intervals containing aggregatedActivityResults
        if isinstance(activity_data, list):
            for category_data in activity_data:
                category = category_data.get("category", "Unknown")
                
                # Process each interval (day)
                for interval in category_data.get("intervals", []):
                    interval_start = interval.get("startTime", 0)
                    interval_date = datetime.fromtimestamp(interval_start).strftime("%Y-%m-%d")
                    
                    # Extract individual activities
                    for activity in interval.get("aggregatedActivityResults", []):
                        attributes = activity.get("attributes", {})
                        duration_seconds = activity.get("activityDuration", 0)
                        
                        viewing_history.append({
                            "content_title": attributes.get("TITLE", "Unknown"),
                            "content_type": category,
                            "duration_minutes": round(duration_seconds / 60, 1),  # Convert to minutes
                            "duration_seconds": duration_seconds,
                            "date": interval_date,
                            "last_accessed": datetime.fromtimestamp(activity.get("lastActivityTimeStamp", 0)).isoformat() if activity.get("lastActivityTimeStamp") else None,
                            "thumbnail": attributes.get("THUMBNAIL_URL"),
                            "activity_count": activity.get("activityCount", 0)
                        })
        
        return viewing_history
    
    def get_device_status(self, child_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get status of devices from activity data.
        
        Args:
            child_id: Optional child identifier (uses auto-detected if not provided)
        
        Returns:
            List of dictionaries with device information extracted from activities
        """
        # Note: There doesn't appear to be a dedicated devices API
        # Device info would need to be extracted from activity data or other sources
        cid = child_id or self.child_id
        if not cid:
            print("❌ No child ID available")
            return []
        
        # Could parse from activity data if available
        print("ℹ️  Device status extraction not fully implemented yet")
        return []
    
    def get_time_limits(self, child_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get configured time limits for a child.
        
        Args:
            child_id: Optional child identifier (uses auto-detected if not provided)
        
        Returns:
            Dictionary containing:
            - period_configurations: List of day configurations with limits and curfews
            - daily_limits: Simplified dict of {day: minutes_allowed}
            - curfews: Simplified dict of {day: {start, end, enabled}}
        """
        cid = child_id or self.child_id
        if not cid:
            print("❌ No child ID available")
            return {}
        
        # Call the get-adjusted-time-limits API
        limits = self._api_call("GET", f"/ajax/get-adjusted-time-limits?childDirectedId={cid}")
        
        if not limits or "periodConfigurations" not in limits:
            print("⚠️  No time limit data returned")
            return {}
        
        # Parse into easier format
        daily_limits = {}
        schedules = {}  # Usage schedule (when tablet can be used)
        
        for day_config in limits["periodConfigurations"]:
            day_name = day_config.get("name", "Unknown")
            enabled = day_config.get("enabled", False)
            
            # Extract time limit
            time_limits = day_config.get("timeLimits", {})
            content_limits_enabled = time_limits.get("contentTimeLimitsEnabled", False)
            minutes = time_limits.get("contentTimeLimits", {}).get("ALL", 1440) if content_limits_enabled else None
            
            daily_limits[day_name] = {
                "enabled": enabled,
                "minutes": minutes
            }
            
            # Extract schedule (curfew = when they CANNOT use, inverse is when they CAN)
            curfew_list = day_config.get("curfewConfigList", [])
            if curfew_list:
                curfew = curfew_list[0]
                schedules[day_name] = {
                    "schedule_enabled": curfew.get("enabled", False),
                    "allowed_start": curfew.get("start", "00:00"),  # Can use FROM this time
                    "allowed_end": curfew.get("end", "23:59"),      # Can use UNTIL this time (bedtime)
                    "description": f"Allowed {curfew.get('start', '00:00')} - {curfew.get('end', '23:59')}" if curfew.get("enabled") else "No schedule"
                }
        
        return {
            "period_configurations": limits["periodConfigurations"],  # Raw data
            "daily_limits": daily_limits,
            "schedules": schedules,  # When tablet can be used each day
            "timestamp": datetime.now().isoformat()
        }
    
    def set_time_limits(self, period_configurations: List[Dict[str, Any]], 
                       child_id: Optional[str] = None) -> bool:
        """
        Update time limit configuration for a child.
        
        Args:
            period_configurations: Full week configuration (from get_time_limits)
            child_id: Optional child identifier (uses auto-detected if not provided)
        
        Returns:
            True if successful, False otherwise
        """
        cid = child_id or self.child_id
        if not cid:
            print("❌ No child ID available")
            return False
        
        # Build the request payload
        payload = {
            "childDirectedId": cid,
            "periodConfigurations": period_configurations
        }
        
        # Call the set-time-limit-v2 API
        result = self._api_call("PUT", "/ajax/set-time-limit-v2", data=payload)
        
        if result is not None:
            print("✅ Time limits updated successfully")
            return True
        else:
            print("❌ Failed to update time limits")
            return False
    
    def toggle_daily_limit(self, day_name: str, enabled: bool, 
                          child_id: Optional[str] = None) -> bool:
        """
        Toggle a specific day's time limit on or off.
        
        Args:
            day_name: Day of week (monday, Monday, etc. - case insensitive)
            enabled: True to enable limits, False to disable
            child_id: Optional child identifier
            
        Returns:
            True if successful, False otherwise
        """
        # Normalize day name to match Amazon's format
        day_name = normalize_day_name(day_name)
        
        # Get current config
        current_limits = self.get_time_limits(child_id)
        if not current_limits or "period_configurations" not in current_limits:
            print("❌ Could not retrieve current time limits")
            return False
        
        # Modify the specific day
        period_configs = current_limits["period_configurations"]
        for day_config in period_configs:
            if day_config["name"] == day_name:
                day_config["enabled"] = enabled
                day_config["time"] = int(datetime.now().timestamp() * 1000)
                break
        
        # Update
        return self.set_time_limits(period_configs, child_id)
    
    def set_daily_screen_time(self, day_name: str, minutes: int,
                             child_id: Optional[str] = None) -> bool:
        """
        Set screen time limit for a specific day.
        
        Args:
            day_name: Day of week (monday, Monday, etc. - case insensitive)
            minutes: Screen time allowed in minutes
            child_id: Optional child identifier
            
        Returns:
            True if successful, False otherwise
        """
        # Normalize day name to match Amazon's format
        day_name = normalize_day_name(day_name)
        
        # Get current config
        current_limits = self.get_time_limits(child_id)
        if not current_limits or "period_configurations" not in current_limits:
            print("❌ Could not retrieve current time limits")
            return False
        
        # Modify the specific day
        period_configs = current_limits["period_configurations"]
        for day_config in period_configs:
            if day_config["name"] == day_name:
                day_config["timeLimits"]["contentTimeLimitsEnabled"] = True
                day_config["timeLimits"]["contentTimeLimits"]["ALL"] = minutes
                day_config["time"] = int(datetime.now().timestamp() * 1000)
                break
        
        # Update
        return self.set_time_limits(period_configs, child_id)
    
    def set_daily_schedule(self, day_name: str, start_time: str, end_time: str,
                          enabled: bool = True, child_id: Optional[str] = None) -> bool:
        """
        Set the allowed usage schedule (curfew) for a specific day.
        
        Args:
            day_name: Day of week (monday, Monday, etc. - case insensitive)
            start_time: Start time in HH:MM format (e.g., "08:00") - when tablet can be used FROM
            end_time: End time in HH:MM format (e.g., "19:00") - when tablet can be used UNTIL (bedtime)
            enabled: Whether to enable this schedule
            child_id: Optional child identifier
            
        Returns:
            True if successful, False otherwise
        """
        # Normalize day name
        day_name = normalize_day_name(day_name)
        
        # Get current config
        current_limits = self.get_time_limits(child_id)
        if not current_limits or "period_configurations" not in current_limits:
            print("❌ Could not retrieve current time limits")
            return False
        
        # Modify the specific day's schedule
        period_configs = current_limits["period_configurations"]
        for day_config in period_configs:
            if day_config["name"] == day_name:
                # Update or create curfew config
                curfew_list = day_config.get("curfewConfigList", [])
                if curfew_list:
                    # Update existing curfew
                    curfew_list[0]["start"] = start_time
                    curfew_list[0]["end"] = end_time
                    curfew_list[0]["enabled"] = enabled
                else:
                    # Create new curfew
                    day_config["curfewConfigList"] = [{
                        "start": start_time,
                        "end": end_time,
                        "enabled": enabled,
                        "type": None
                    }]
                day_config["time"] = int(datetime.now().timestamp() * 1000)
                break
        
        # Update
        return self.set_time_limits(period_configs, child_id)
    
    def toggle_daily_schedule(self, day_name: str, enabled: bool,
                             child_id: Optional[str] = None) -> bool:
        """
        Toggle a specific day's usage schedule on or off without changing the times.
        
        Args:
            day_name: Day of week (monday, Monday, etc. - case insensitive)
            enabled: True to enable schedule, False to disable
            child_id: Optional child identifier
            
        Returns:
            True if successful, False otherwise
        """
        # Normalize day name
        day_name = normalize_day_name(day_name)
        
        # Get current config
        current_limits = self.get_time_limits(child_id)
        if not current_limits or "period_configurations" not in current_limits:
            print("❌ Could not retrieve current time limits")
            return False
        
        # Modify the specific day's schedule
        period_configs = current_limits["period_configurations"]
        for day_config in period_configs:
            if day_config["name"] == day_name:
                curfew_list = day_config.get("curfewConfigList", [])
                if curfew_list:
                    curfew_list[0]["enabled"] = enabled
                else:
                    # Create default schedule if none exists
                    day_config["curfewConfigList"] = [{
                        "start": "00:00",
                        "end": "23:59",
                        "enabled": enabled,
                        "type": None
                    }]
                day_config["time"] = int(datetime.now().timestamp() * 1000)
                break
        
        # Update
        return self.set_time_limits(period_configs, child_id)
    
    def set_offscreen_time(self, duration_hours: float, 
                          child_id: Optional[str] = None) -> bool:
        """
        Block/pause all devices for a specified duration using the set-offscreen-time API.
        This is the API-based alternative to the button-based pause_devices method.
        
        Args:
            duration_hours: Duration in hours to block devices (can be fractional, e.g. 0.5 for 30 minutes)
            child_id: Optional child identifier
            
        Returns:
            True if successful, False otherwise
        """
        cid = child_id or self.child_id
        if not cid:
            print("❌ No child ID available")
            return False
        
        # According to the API attachment, expirationTimeInSeconds is a duration from now, not an absolute timestamp
        # The attachment shows: "expirationTimeInSeconds: 3600" for 1 hour
        expiration_seconds = int(duration_hours * 3600)
        
        # Build the request payload - using list format as shown in attachment
        payload = {
            "directedIds": [cid],
            "expirationTimeInSeconds": expiration_seconds
        }
        
        print(f"⏸️  Blocking devices for {duration_hours} hour(s) ({expiration_seconds} seconds)...")
        
        # Call the set-offscreen-time API (POST method)
        result = self._api_call("POST", "/ajax/set-offscreen-time", data=payload)
        
        if result is not None:
            print("✅ Devices blocked successfully")
            return True
        else:
            print("❌ Failed to block devices")
            return False
    
    def clear_offscreen_time(self, child_id: Optional[str] = None) -> bool:
        """
        Unblock/resume all devices by clearing the offscreen time.
        
        Args:
            child_id: Optional child identifier
            
        Returns:
            True if successful, False otherwise
        """
        cid = child_id or self.child_id
        if not cid:
            print("❌ No child ID available")
            return False
        
        # Set expiration to 0 or 1 second to immediately unblock
        payload = {
            "directedIds": [cid],
            "expirationTimeInSeconds": 0
        }
        
        print("▶️  Unblocking devices...")
        
        result = self._api_call("POST", "/ajax/set-offscreen-time", data=payload)
        
        if result is not None:
            print("✅ Devices unblocked successfully")
            return True
        else:
            print("❌ Failed to unblock devices")
            return False
    
    def set_screen_time_bulk(self, days: List[str], minutes: int,
                            child_id: Optional[str] = None) -> bool:
        """
        Set screen time limit for multiple days at once.
        
        Args:
            days: List of day names (e.g., ["Monday", "Tuesday", "Wednesday"])
            minutes: Screen time allowed in minutes
            child_id: Optional child identifier
            
        Returns:
            True if successful, False otherwise
        """
        # Get current config
        current_limits = self.get_time_limits(child_id)
        if not current_limits or "period_configurations" not in current_limits:
            print("❌ Could not retrieve current time limits")
            return False
        
        # Normalize day names
        normalized_days = [normalize_day_name(day) for day in days]
        
        # Modify the specified days
        period_configs = current_limits["period_configurations"]
        for day_config in period_configs:
            if day_config["name"] in normalized_days:
                day_config["timeLimits"]["contentTimeLimitsEnabled"] = True
                day_config["timeLimits"]["contentTimeLimits"]["ALL"] = minutes
                day_config["time"] = int(datetime.now().timestamp() * 1000)
        
        # Update
        success = self.set_time_limits(period_configs, child_id)
        if success:
            print(f"✅ Updated screen time to {minutes} minutes for: {', '.join(normalized_days)}")
        return success
    
    def set_screen_time_all_days(self, minutes: int,
                                 child_id: Optional[str] = None) -> bool:
        """
        Set screen time limit for all days of the week.
        
        Args:
            minutes: Screen time allowed in minutes
            child_id: Optional child identifier
            
        Returns:
            True if successful, False otherwise
        """
        all_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        return self.set_screen_time_bulk(all_days, minutes, child_id)
    
    def set_screen_time_school_nights(self, minutes: int,
                                     child_id: Optional[str] = None) -> bool:
        """
        Set screen time limit for school nights (Sunday through Thursday).
        
        Args:
            minutes: Screen time allowed in minutes
            child_id: Optional child identifier
            
        Returns:
            True if successful, False otherwise
        """
        school_nights = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"]
        return self.set_screen_time_bulk(school_nights, minutes, child_id)
    
    def set_screen_time_weekend(self, minutes: int,
                               child_id: Optional[str] = None) -> bool:
        """
        Set screen time limit for weekend/non-school nights (Friday and Saturday).
        
        Args:
            minutes: Screen time allowed in minutes
            child_id: Optional child identifier
            
        Returns:
            True if successful, False otherwise
        """
        weekend = ["Friday", "Saturday"]
        return self.set_screen_time_bulk(weekend, minutes, child_id)
    
    def get_children_profiles(self) -> List[Dict[str, Any]]:
        """
        Get list of children profiles from household API.
        
        Returns:
            List of dictionaries, each containing:
            - child_id: Unique child identifier (directedId)
            - child_name: Child's name
            - avatar_uri: URL to profile image
            - role: Should be "CHILD"
        """
        household = self._api_call("GET", "/ajax/get-household")
        
        if not household or "members" not in household:
            print("⚠️  No household data returned")
            return []
        
        # Filter for children only
        children = []
        for member in household["members"]:
            if member.get("role") == "CHILD":
                children.append({
                    "child_id": member.get("directedId"),
                    "child_name": member.get("firstName"),
                    "avatar_uri": member.get("avatarUri"),
                    "role": member.get("role")
                })
        
        return children
    
    def extract_all_data(self, child_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract all available data from the dashboard.
        
        Args:
            child_id: Optional child identifier (uses auto-detected if not provided)
        
        Returns:
            Comprehensive dictionary with all extracted data
        """
        print("🔄 Extracting all data from Amazon Parental Dashboard...")
        
        cid = child_id or self.child_id
        
        data = {
            "timestamp": datetime.now().isoformat(),
            "children": self.get_children_profiles(),
            "usage": self.get_usage_statistics(cid),
            "viewing_history": self.get_viewing_history(cid),
            "time_limits": self.get_time_limits(cid)
        }
        
        print("✅ Data extraction complete")
        return data
    
    def close(self):
        """Clean up resources."""
        if self.context:
            self.context.close()
        self.browser.close()


# CLI interface for testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Extract data from Amazon Parental Dashboard")
    parser.add_argument("--headed", action="store_true", help="Run in headed mode for debugging")
    parser.add_argument("--output", type=str, default="dashboard_data.json",
                       help="Output file for extracted data")
    parser.add_argument("--child-id", type=str, help="Specific child ID to extract data for")
    args = parser.parse_args()
    
    print("🚀 Amazon Parental Dashboard Data Extractor")
    print("="*60)
    
    with sync_playwright() as p:
        extractor = DashboardDataExtractor(p, headless=not args.headed)
        try:
            extractor.login()
            data = extractor.extract_all_data(child_id=args.child_id)
            
            # Save to file
            output_file = Path(args.output)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            print(f"\n💾 Data saved to {output_file}")
            print(f"\n📊 Summary:")
            print(f"   Children: {len(data.get('children', []))}")
            print(f"   Today's usage: {data.get('usage', {}).get('today_minutes', 0)} minutes")
            print(f"   Week's usage: {data.get('usage', {}).get('week_minutes', 0)} minutes")
            print(f"   Viewing history items: {len(data.get('viewing_history', []))}")
            
            # Show time limits summary
            limits = data.get('time_limits', {}).get('daily_limits', {})
            schedules = data.get('time_limits', {}).get('schedules', {})
            if limits:
                print(f"\n⏰ Time Limits & Schedules:")
                for day, config in limits.items():
                    status = "✅ Enabled" if config.get('enabled') else "❌ Disabled"
                    minutes = config.get('minutes')
                    limit_str = f"{minutes} min" if minutes else "No limit"
                    
                    # Add schedule info
                    schedule = schedules.get(day, {})
                    schedule_str = schedule.get('description', 'No schedule')
                    
                    print(f"   {day}: {status} ({limit_str}) | {schedule_str}")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            extractor.close()
