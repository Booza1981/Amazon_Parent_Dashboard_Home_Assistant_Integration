# Amazon Parental Dashboard Controller

Control and monitor your Amazon Parental Dashboard remotely through Home Assistant using MQTT. This integration runs as a Docker daemon, providing real-time synchronization and remote control of screen time limits and device blocking.

## Features

###  Real-Time Monitoring
- **Screen Time Usage**: Track daily and weekly usage statistics
- **Viewing History**: See what content has been watched (last 31 activities)
- **Time Limit Configuration**: Monitor current screen time limits for all days
- **Device Status**: Check which devices are active or blocked

###  Remote Control via Home Assistant
- **Daily Time Limit Switches**: Enable/disable time limits for each day of the week
- **Per-Day Screen Time**: Adjust allowed minutes for individual days (0-480 minutes)
- **Bulk Controls**: Set screen time for all days, school nights, or weekends at once
- **Device Blocking**: Pause/resume internet access for specific durations

###  Automatic Synchronization
- **Continuous Daemon**: Runs as a Docker container with automatic data sync
- **MQTT Auto-Discovery**: Entities automatically appear in Home Assistant
- **Configurable Interval**: Set sync frequency (default: 5 minutes)

###  Automatic Cookie Management
- **Auto-Save**: Cookies automatically saved after successful operations
- **Auto-Refresh**: Session refreshed when cookies near expiry (< 4 hours)
- **Web UI**: Browser-based interface for cookie status and manual refresh (port 5000)
- **Upload Interface**: Easy cookie upload from any device on your network
- **Graceful Error Handling**: Automatic retry on authentication failures

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- MQTT broker running (e.g., Mosquitto)
- Home Assistant with MQTT integration configured
- Amazon Parental Dashboard account

### Installation

**Step 1: Clone the repository**
```bash
git clone https://github.com/Booza1981/Amazon_Parent_Dashboard_Home_Assistant_Integration.git
cd Amazon_Parent_Dashboard_Home_Assistant_Integration
```

**Step 2: Authenticate with Amazon (one-time setup)**

Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

Run authentication:
```bash
python amazon_parental/refresh_cookies.py
```

This opens a browser window. Log in to your Amazon account, then press Enter. Your cookies will be saved to `amazon_parental/cookies.json`.

**Important**: Keep `amazon_parental/cookies.json` secure - it contains your authentication credentials!

**Step 3: Configure MQTT settings**

Edit `docker-compose.yml` and update the environment variables:
```yaml
environment:
  MQTT_BROKER: "192.168.1.100"    # Your MQTT broker IP
  MQTT_PORT: "1883"
  MQTT_USERNAME: "your-username"  # Leave empty if no auth
  MQTT_PASSWORD: "your-password"  # Leave empty if no auth
  CHILD_NAME: "child"             # Friendly name for MQTT topics
  SYNC_INTERVAL: "300"            # Sync every 5 minutes
```

**Step 4: Start the Docker container**
```bash
docker-compose up -d
docker-compose logs -f
```

The container will start with:
- MQTT connection to Home Assistant
- Automatic data synchronization
- Cookie management web UI on port 5000

**Step 5: Access the Cookie Management Web UI (Optional)**

Visit `http://YOUR_SERVER_IP:5000` from any device on your network to:
- View cookie expiry status
- Manually trigger session refresh
- Upload new cookies when needed

**Step 6: Check Home Assistant**

New entities should appear automatically under MQTT integration.

## Home Assistant Entities

### Sensors
- `sensor.{child}_screen_time` - Usage statistics (today, yesterday, this week)
- `sensor.{child}_latest_viewing` - Most recent viewing activity

### Daily Time Limit Switches (7 entities)
- `switch.{child}_limit_monday` through `switch.{child}_limit_sunday`

### Daily Screen Time Controls (7 entities)
- `number.{child}_minutes_monday` through `number.{child}_minutes_sunday`
- Set allowed screen time in minutes (0-480, step: 15)

### Bulk Time Limit Controls
- `number.{child}_bulk_all_days` - Set all 7 days to same value
- `number.{child}_bulk_school_nights` - Set Sun-Thu (school nights)
- `number.{child}_bulk_weekend` - Set Fri-Sat (weekend)

Replace `{child}` with the name you configured in `CHILD_NAME`.

## Usage Examples

### Manual Device Blocking
```bash
# Block for 2 hours
python amazon_parental/control.py pause --duration 2

# Block for 30 minutes
python amazon_parental/control.py pause --duration 0.5

# Resume/unblock
python amazon_parental/control.py resume
```

### Home Assistant Automation Example
```yaml
automation:
  - alias: "Set School Night Screen Time"
    trigger:
      - platform: time
        at: "18:00:00"
    condition:
      - condition: time
        weekday: [sun, mon, tue, wed, thu]
    action:
      - service: number.set_value
        target:
          entity_id: number.child_bulk_school_nights
        data:
          value: 120  # 2 hours
```

## Docker Management

```bash
# View logs
docker-compose logs -f

# Restart (after uploading new cookies)
docker-compose restart

# Stop
docker-compose down

# Rebuild after code changes
docker-compose build
docker-compose up -d
```

## Cookie Management

### Automatic Cookie Refresh

The system automatically:
- Saves cookies after successful API calls (every 5 minutes)
- Checks cookie expiry before each sync
- Triggers auto-refresh when cookies expire within 4 hours
- Retries failed requests after refreshing session

### Web UI (Port 5000)

Access the cookie management interface at `http://YOUR_SERVER_IP:5000`:

**Features:**
- 📊 Real-time cookie status display
- ⏰ Expiry countdown for critical cookies
- 🔄 One-click manual refresh button
- 📤 Drag-and-drop cookie upload
- 🎨 Mobile-friendly responsive design

### When to Upload New Cookies

Upload fresh cookies via the web UI when:
- You see HTTP 401 errors in logs
- Web UI shows "Cookies Expired" status
- Schedule changes in Home Assistant fail
- After extended container downtime

### Option 1: Upload via Web UI (Recommended)

1. **On a machine with a browser**, refresh cookies:
   ```bash
   python amazon_parental/refresh_cookies.py
   ```

2. **Visit** `http://YOUR_SERVER_IP:5000` from any device

3. **Click** "Upload cookies.json"

4. **Select** the `amazon_parental/cookies.json` file

5. **Restart** the container to apply:
   ```bash
   docker-compose restart
   ```

### Option 2: Direct Copy

```bash
# After refreshing cookies locally
docker cp ./amazon_parental/cookies.json amazon-parental-dashboard:/app/amazon_parental/cookies.json
docker-compose restart
```

## Headless Linux Server Setup

If you're running this on a headless Linux server (no GUI), you need to generate the cookies file on a machine with a desktop/browser first, then transfer it to your server.

### Option 1: Generate Cookies on Your Windows/Mac Computer (Easiest)

**On your local computer (Windows/Mac):**

1. Clone the repository:
   ```bash
   git clone https://github.com/Booza1981/Amazon_Parent_Dashboard_Home_Assistant_Integration.git
   cd Amazon_Parent_Dashboard_Home_Assistant_Integration
   ```

2. Set up Python environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   playwright install chromium
   ```

3. Generate cookies:
   ```bash
   python amazon_parental/refresh_cookies.py
   ```
   - A browser window will open
   - Log in to your Amazon account
   - Complete any 2FA challenges
   - Wait until you see the parental dashboard
   - Return to terminal and press Enter
   - The file `amazon_parental/cookies.json` will be created

4. Transfer cookies to your Linux server:
   ```bash
   # Using scp (replace with your server details)
   scp amazon_parental/cookies.json user@your-server-ip:/path/to/amazon-parental-dashboard/amazon_parental/
   
   # Or using rsync
   rsync -avz amazon_parental/cookies.json user@your-server-ip:/path/to/amazon-parental-dashboard/amazon_parental/
   ```

**On your Linux server:**

5. Verify the cookies file is present:
   ```bash
   cd /path/to/amazon-parental-dashboard
   ls -la amazon_parental/cookies.json
   ```

6. Set proper permissions:
   ```bash
   chmod 600 amazon_parental/cookies.json
   ```

7. Start the Docker container:
   ```bash
   docker-compose up -d
   ```

### Option 2: Use X11 Forwarding (Linux to Linux)

If you're connecting from another Linux machine with a desktop:

1. SSH to your server with X11 forwarding:
   ```bash
   ssh -X user@your-server-ip
   ```

2. On the server, set up the environment:
   ```bash
   cd /path/to/amazon-parental-dashboard
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   playwright install chromium
   
   # Install required system dependencies
   playwright install-deps chromium
   ```

3. Generate cookies (browser will display on your local machine):
   ```bash
   python amazon_parental/refresh_cookies.py
   ```

4. Start Docker:
   ```bash
   docker-compose up -d
   ```

### Option 3: Browser on Another Machine + Manual Cookie Export

If you can't run the script but have access to a browser:

1. **In your browser**, go to: https://parents.amazon.co.uk
2. Log in to Amazon
3. Open browser DevTools (F12)
4. Go to Application/Storage → Cookies
5. Find these important cookies and copy their values:
   - `session-id`
   - `session-id-time`
   - `session-token`
   - `ubid-acbuk`
   - `at-acbuk`
   - `x-acbuk`

6. **On your server**, create `amazon_parental/cookies.json` manually:
   ```bash
   nano amazon_parental/cookies.json
   ```

7. Paste this template and fill in your cookie values:
   ```json
   {
     "cookies": [
       {
         "name": "session-id",
         "value": "YOUR_SESSION_ID_HERE",
         "domain": ".amazon.co.uk",
         "path": "/",
         "expires": -1,
         "httpOnly": true,
         "secure": true,
         "sameSite": "Lax"
       },
       {
         "name": "session-token",
         "value": "YOUR_SESSION_TOKEN_HERE",
         "domain": ".amazon.co.uk",
         "path": "/",
         "expires": -1,
         "httpOnly": true,
         "secure": true,
         "sameSite": "Lax"
       },
       {
         "name": "ubid-acbuk",
         "value": "YOUR_UBID_HERE",
         "domain": ".amazon.co.uk",
         "path": "/",
         "expires": -1,
         "httpOnly": true,
         "secure": true,
         "sameSite": "Lax"
       }
     ]
   }
   ```
   
8. Save and set permissions:
   ```bash
   chmod 600 amazon_parental/cookies.json
   ```

### When Cookies Expire

Amazon cookies typically last 24-48 hours. The system handles this automatically:

1. **Auto-refresh**: When cookies are within 4 hours of expiry, the system attempts automatic refresh
2. **Manual upload**: If auto-refresh fails, upload fresh cookies via web UI at `http://YOUR_SERVER_IP:5000`
3. **Monitoring**: Check logs for cookie status: `docker-compose logs -f`

**Signs cookies need refresh:**
- `❌ API call failed -> HTTP 401` in logs
- `⚠️ Cookies expired` in web UI
- Home Assistant controls stop working

### Security Tips for Linux Servers

- **Restrict file permissions**: `chmod 600 amazon_parental/cookies.json`
- **Don't commit cookies**: The file is already in `.gitignore`
- **Use SSH key authentication** when transferring cookies
- **Consider encrypted transfer**: Use `scp` or `rsync` over SSH
- **Firewall your MQTT broker**: Limit access to trusted IPs only

## Troubleshooting

### HTTP 401 Errors

**Cause**: Amazon session cookies have expired or are invalid.

**Solution**:

1. **Check web UI**: Visit `http://YOUR_SERVER_IP:5000` to see cookie status

2. **Upload fresh cookies**:
   - Refresh cookies on a machine with browser
   - Upload via web UI
   - Restart container: `docker-compose restart`

3. **Check logs**: `docker-compose logs -f | grep -E "401|Cookie|Login"`

**Note**: Auto-refresh handles most cases. Manual upload only needed if auto-refresh fails.

### Entities Not Appearing in Home Assistant

1. Check MQTT connection: `docker-compose logs | grep "Connected to MQTT"`
2. Verify MQTT discovery is enabled in Home Assistant
3. Check MQTT broker credentials in docker-compose.yml
4. Restart: `docker-compose restart`

### Web UI Not Accessible

1. Verify port is exposed: `docker-compose ps` (should show `0.0.0.0:5000->5000/tcp`)
2. Check firewall: Allow port 5000 on your server
3. Access from same network: `http://SERVER_IP:5000`

### Schedule Changes Not Working

1. Check container logs for errors
2. Verify cookies are valid (check web UI)
3. Ensure child ID was detected: Look for `✅ Logged in successfully` in logs
4. Restart after uploading fresh cookies

## Project Structure

```
amazon-parental-dashboard/
 amazon_parental/          # Amazon integration package
    __init__.py
    control.py
    data_extractor.py      # Enhanced with auto-save & refresh
    refresh_cookies.py
    cookies.json           # (gitignored)
 tests/
    __init__.py
    test_integration.py
 cookie_refresh_server.py  # Flask web UI for cookie management
 config.example.yaml       # Template configuration
 dashboard_to_homeassistant.py  # Main daemon with auto-refresh
 mqtt_publisher.py
 docker-compose.yml        # Exposes ports 5000 (web UI)
 Dockerfile
 setup.py
 requirements.txt
 restart.sh                # Quick restart script
 LICENSE
 CONTRIBUTING.md
 TROUBLESHOOTING.md
 README.md
```

## Security Notes

- **cookies.json**: Contains authentication credentials - never commit to git
- **MQTT credentials**: Use strong passwords and consider TLS encryption
- **Docker**: Container runs as non-root user for security

## License

MIT License - feel free to use and modify for your own parental control needs.

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Acknowledgments

- [Playwright](https://playwright.dev/) - Browser automation
- [Paho MQTT](https://www.eclipse.org/paho/) - MQTT client
- [Home Assistant](https://www.home-assistant.io/) - Home automation platform

## Support

If you encounter issues:
1. Check the web UI: `http://YOUR_SERVER_IP:5000` for cookie status
2. Review Docker logs: `docker-compose logs -f`
3. Check the troubleshooting section above
4. Verify MQTT connection in Home Assistant
5. Ensure cookies are valid (upload fresh ones if needed)
6. Open an issue on GitHub with logs and error details

**Monitoring Tips:**
- **Good signs**: `✅ Logged in successfully`, `💾 Cookies saved`, `✅ Sync complete`
- **Warning signs**: `⚠️ Cookies expiring soon` (auto-handled)
- **Action needed**: `❌ HTTP 401`, `🔑 Please refresh cookies manually`
