# Troubleshooting Guide

## Common Issues and Solutions

### Issue: HTTP 401 Errors / "Child ID not detected"

**Symptoms:**
```
⚠️  API call failed: GET /ajax/get-household -> HTTP 401
⚠️  Warning: Could not auto-detect child ID
```

**Cause:** Amazon session cookies have expired.

**Solution:** Refresh the cookies by running a manual login:

```bash
# Option 1: Use control.py with headed mode
python amazon/control.py pause --duration 1 --headed

# Option 2: Use refresh_cookies.py (if available)
python amazon/refresh_cookies.py

# Option 3: Delete cookies and run control.py
# This will prompt for manual login
rm amazon/cookies.json  # On Linux/Mac
del amazon\cookies.json  # On Windows
python amazon/control.py pause --duration 1 --headed
```

**How it works:**
1. Opens browser window (headed mode)
2. You manually sign in to Amazon
3. Cookies are saved to `amazon/cookies.json`
4. Future operations use these cookies

**Note:** Cookies typically last several days but may expire sooner if:
- Amazon detects unusual activity
- You log in from another device/location
- Security settings are strict

---

### Issue: Docker Container Can't Access Cookies

**Symptoms:**
```
FileNotFoundError: Cookies file not found
```

**Cause:** Cookies not mounted into Docker container or haven't been created yet.

**Solution:**

1. **Create cookies on host first:**
   ```bash
   python amazon/control.py pause --duration 1 --headed
   ```

2. **Verify cookies exist:**
   ```bash
   ls amazon/cookies.json  # Should show the file
   ```

3. **Check Docker volume mount:**
   ```yaml
   # In docker-compose.yml, verify this line exists:
   volumes:
     - ./amazon/cookies.json:/app/amazon/cookies.json:ro
   ```

4. **Restart container:**
   ```bash
   docker-compose restart
   ```

---

### Issue: Time Limit Updates Fail

**Symptoms:**
```
⚠️  API call failed: PUT /ajax/set-time-limit-v2 -> HTTP 400/403/500
```

**Possible Causes:**
1. **Invalid payload format** - Amazon changed their API
2. **Rate limiting** - Too many requests too quickly
3. **Session expired** - Need to refresh cookies
4. **CSRF token missing** - Check token generation

**Diagnostic Steps:**

1. **Check the error details** (new in v2.0):
   ```
   Response body: {...}  # Shows what Amazon returned
   Request payload: {...}  # Shows what we sent
   ```

2. **Verify cookies are valid:**
   ```bash
   python amazon/data_extractor.py --headed
   # If this works, cookies are good
   ```

3. **Try a simple update first:**
   ```python
   # Test with just one day
   extractor.set_daily_screen_time("Monday", 120)
   ```

4. **Check Amazon's web interface:**
   - Log in manually to parents.amazon.co.uk
   - Try changing time limits there
   - If that fails too, Amazon may be having issues

---

### Issue: Home Assistant Entities Not Appearing

**Symptoms:**
- New bulk controls don't show up
- Individual day controls missing

**Solutions:**

1. **Check MQTT connection:**
   ```bash
   docker logs amazon-parental-dashboard | grep "Connected to MQTT"
   # Should see: ✅ Connected to MQTT broker
   ```

2. **Verify discovery messages:**
   - Go to Home Assistant → Settings → Devices & Services → MQTT
   - Click "Configure" → "Listen to a topic"
   - Topic: `homeassistant/number/#`
   - You should see messages when container starts

3. **Force entity refresh:**
   ```bash
   # Restart the integration
   docker-compose restart
   
   # Wait 30 seconds for discovery
   sleep 30
   
   # Check Home Assistant → Settings → Devices & Services → MQTT → Devices
   # Look for "Daughter's Controls"
   ```

4. **Check for conflicts:**
   - Old entities with same name may block new ones
   - Delete old entities: Settings → Devices & Services → MQTT → Entities
   - Restart integration

---

### Issue: Bulk Updates Don't Work

**Symptoms:**
- Individual days update fine
- Bulk controls (all days, school nights) fail

**Diagnostic:**
```python
# Test manually
from playwright.sync_api import sync_playwright
from amazon.data_extractor import DashboardDataExtractor

with sync_playwright() as p:
    ext = DashboardDataExtractor(p, headless=True)
    ext.login()
    
    # Get current config first
    current = ext.get_time_limits()
    print(f"Child ID: {ext.child_id}")
    print(f"Days configured: {list(current['daily_limits'].keys())}")
    
    # Try bulk update
    success = ext.set_screen_time_school_nights(120)
    print(f"Success: {success}")
    
    ext.close()
```

**Common issues:**
- Child ID not detected → Refresh cookies
- Day names don't match → Check capitalization (should be "Monday", not "monday")
- API returns error → Check error details in logs

---

### Issue: Device Blocking Doesn't Work

**Symptoms:**
```
❌ Failed to block devices
⚠️  API call failed: PUT /ajax/set-offscreen-time -> HTTP 4XX
```

**Diagnostic:**

1. **Test with control.py:**
   ```bash
   python amazon/control.py pause --duration 0.25 --headed
   # Watch for errors in browser console
   ```

2. **Check child ID:**
   ```python
   # Make sure child_id is detected
   extractor.login()
   print(f"Child ID: {extractor.child_id}")
   ```

3. **Verify API payload:**
   Look for this in logs:
   ```
   Request payload: {"childDirectedId": "...", "expirationTimeInSeconds": ...}
   ```

4. **Try button method as fallback:**
   ```bash
   python amazon/control.py pause --duration 1 --use-buttons
   ```

---

## Getting Help

### Enable Debug Logging

1. **For data extractor:**
   ```bash
   python amazon/data_extractor.py --headed
   # Headed mode lets you see what's happening
   ```

2. **For Docker container:**
   ```bash
   # Follow logs in real-time
   docker logs -f amazon-parental-dashboard
   
   # Increase verbosity (if needed, edit docker-compose.yml):
   environment:
     - PYTHONUNBUFFERED=1
   ```

### Collect Diagnostic Info

Before asking for help, gather:

1. **Error messages from logs:**
   ```bash
   docker logs amazon-parental-dashboard 2>&1 | tail -100
   ```

2. **Cookie status:**
   ```bash
   ls -lh amazon/cookies.json
   # Check file exists and modification time
   ```

3. **Test child ID detection:**
   ```bash
   python -c "
   from playwright.sync_api import sync_playwright
   from amazon.data_extractor import DashboardDataExtractor
   with sync_playwright() as p:
       e = DashboardDataExtractor(p, headless=True)
       e.login()
       print(f'Child ID: {e.child_id}')
       e.close()
   "
   ```

4. **Home Assistant MQTT logs:**
   - Settings → System → Logs
   - Filter for "mqtt"

---

## Prevention Tips

### Keep Cookies Fresh

Add a cron job or Home Assistant automation to refresh cookies weekly:

```yaml
# automation.yaml
automation:
  - alias: "Refresh Amazon Cookies Weekly"
    trigger:
      platform: time
        at: "03:00:00"
    condition:
      condition: time
        weekday:
          - sun
    action:
      service: shell_command.refresh_amazon_cookies

# configuration.yaml
shell_command:
  refresh_amazon_cookies: "docker exec -it amazon-parental-dashboard python amazon/refresh_cookies.py"
```

### Monitor for Errors

Create a Home Assistant sensor to track integration health:

```yaml
# configuration.yaml
mqtt:
  sensor:
    - name: "Amazon Integration Status"
      state_topic: "homeassistant/sensor/daughter_usage/state"
      value_template: >
        {% if value_json.updated %}
          {{ ((as_timestamp(now()) - as_timestamp(value_json.updated)) / 60) | round(0) }} minutes ago
        {% else %}
          Unknown
        {% endif %}
```

Alert if no updates for > 15 minutes:

```yaml
automation:
  - alias: "Amazon Integration Health Check"
    trigger:
      platform: state
        entity_id: sensor.amazon_integration_status
    condition:
      condition: template
        value_template: "{{ trigger.to_state.state | int > 15 }}"
    action:
      service: notify.mobile_app
        data:
          message: "Amazon parental dashboard integration may be down"
```

---

## Known Limitations

1. **Cookie Expiration:** Amazon cookies expire periodically. Manual refresh required.

2. **API Rate Limits:** Making too many updates quickly may trigger rate limiting.

3. **Time Limit API:** The `set-time-limit-v2` API is occasionally unreliable. Amazon may be working on this endpoint.

4. **Child Profile Changes:** If you add/remove children, you may need to restart the integration.

5. **Time Zone:** Integration assumes UK timezone. Adjust in code if different.

---

## Advanced Debugging

### Inspect API Calls

Watch API traffic:

```python
def debug_api_calls():
    from playwright.sync_api import sync_playwright
    from amazon.data_extractor import DashboardDataExtractor
    
    def log_request(request):
        if '/ajax/' in request.url:
            print(f"→ {request.method} {request.url}")
    
    def log_response(response):
        if '/ajax/' in response.url:
            print(f"← {response.status} {response.url}")
            try:
                print(f"  {response.text()[:200]}")
            except:
                pass
    
    with sync_playwright() as p:
        ext = DashboardDataExtractor(p, headless=False)
        ext.page.on('request', log_request)
        ext.page.on('response', log_response)
        
        ext.login()
        ext.set_daily_screen_time("Monday", 120)
        input("Press Enter to close...")
        ext.close()

# Run it
debug_api_calls()
```

### Test MQTT Manually

```bash
# Subscribe to all topics
mosquitto_sub -h 192.168.1.100 -u your-username -P your-password -t "homeassistant/#" -v

# Publish a test command
mosquitto_pub -h 192.168.1.100 -u your-username -P your-password \
  -t "homeassistant/number/daughter_minutes_monday/set" \
  -m "120"
```
