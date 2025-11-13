"""
Amazon Parental Dashboard to Home Assistant Integration

This script runs as a daemon to continuously sync data between Amazon Parental
Dashboard and Home Assistant via MQTT. It provides:

1. Data Monitoring: Usage stats, viewing history, time limits
2. Time Limit Controls: Toggle daily limits and adjust screen time minutes
3. Device Management: Block/unblock devices (uses existing functionality)

Usage:
    python dashboard_to_homeassistant.py --broker 192.168.1.100 --interval 300

Architecture:
- DashboardDataExtractor: Fetches data from Amazon API via Playwright
- HomeAssistantMQTT: Publishes to MQTT and handles command subscriptions
- DashboardIntegration: Orchestrates sync loop and command handlers
"""

import argparse
import time
import sys
import threading
import queue
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from amazon_parental.data_extractor import DashboardDataExtractor
from mqtt_publisher import HomeAssistantMQTT


class DashboardIntegration:
    """
    Main integration orchestrator that:
    1. Periodically fetches data from Amazon Dashboard
    2. Publishes data to Home Assistant via MQTT
    3. Listens for control commands from Home Assistant
    4. Updates Amazon Dashboard when controls are changed
    """
    
    def __init__(self, mqtt_broker: str, mqtt_port: int = 1883,
                 mqtt_username: str = None, mqtt_password: str = None,
                 child_name: str = "daughter"):
        """Initialize the integration."""
        self.child_name = child_name
        self.mqtt_client = HomeAssistantMQTT(
            broker=mqtt_broker,
            port=mqtt_port,
            username=mqtt_username,
            password=mqtt_password
        )
        self.last_run = None
        self.playwright_instance = None
        self.extractor = None
        self.extractor_lock = threading.Lock()
        # Command queue for thread-safe command handling
        self.command_queue = queue.Queue()
        
    def _ensure_extractor(self):
        """Ensure we have a valid extractor instance."""
        if self.extractor is None:
            self.playwright_instance = sync_playwright().start()
            self.extractor = DashboardDataExtractor(self.playwright_instance, headless=True)
            self.extractor.login()
        return self.extractor
    
    def _close_extractor(self):
        """Close the extractor and playwright instance."""
        if self.extractor:
            self.extractor.close()
            self.extractor = None
        if self.playwright_instance:
            self.playwright_instance.stop()
            self.playwright_instance = None
    
    def setup_home_assistant_entities(self):
        """
        Send MQTT discovery messages to set up Home Assistant entities.
        Only needs to be done once or when configuration changes.
        """
        print("\n🏠 Setting up Home Assistant entities...")
        
        # Set up usage sensor
        self.mqtt_client.publish_usage_config(self.child_name)
        
        # Set up time limit controls (7 switches + 7 number inputs)
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        for day in days:
            self.mqtt_client.publish_daily_limit_switch_config(self.child_name, day)
            self.mqtt_client.publish_screen_time_number_config(self.child_name, day)
        
        # Set up bulk controls (all days, school nights, weekend)
        self.mqtt_client.publish_bulk_control_config(self.child_name)
        
        # Set up schedule/curfew controls (7 switches + 14 time inputs)
        for day in days:
            self.mqtt_client.publish_schedule_switch_config(self.child_name, day)
            self.mqtt_client.publish_schedule_time_config(self.child_name, day, 'start')
            self.mqtt_client.publish_schedule_time_config(self.child_name, day, 'end')
        
        # Set up ad-hoc blocking controls
        self.mqtt_client.publish_block_button_config(self.child_name)
        self.mqtt_client.publish_unblock_button_config(self.child_name)
        self.mqtt_client.publish_block_duration_config(self.child_name)
        # Default block duration to 60 minutes
        self.mqtt_client.publish_block_duration_state(self.child_name, 60)
        self.block_duration_minutes = 60  # Store current block duration
        
        # Subscribe to control commands
        self.mqtt_client.subscribe_daily_limit_commands(self.child_name, self._handle_limit_toggle)
        self.mqtt_client.subscribe_screen_time_commands(self.child_name, self._handle_screen_time_change)
        self.mqtt_client.subscribe_bulk_control_commands(self.child_name, self._handle_bulk_control)
        self.mqtt_client.subscribe_schedule_switch_commands(self.child_name, self._handle_schedule_toggle)
        self.mqtt_client.subscribe_schedule_time_commands(self.child_name, self._handle_schedule_time_change)
        self.mqtt_client.subscribe_block_commands(self.child_name, self._handle_block, self._handle_unblock, self._handle_block_duration)
        
        print("✅ Home Assistant entities configured")
    
    def _handle_limit_toggle(self, child_name: str, day_name: str, enabled: bool):
        """
        Handle daily limit toggle command from Home Assistant.
        Called when user toggles a daily limit switch.
        Queues the command for processing in the main thread.
        """
        print(f"\n🎚️  Received limit toggle: {child_name} - {day_name} - {'ON' if enabled else 'OFF'}")
        self.command_queue.put(('toggle_limit', child_name, day_name, enabled))
    
    def _handle_screen_time_change(self, child_name: str, day_name: str, minutes: int):
        """
        Handle screen time change command from Home Assistant.
        Called when user adjusts the screen time number input.
        Queues the command for processing in the main thread.
        """
        print(f"\n⏱️  Received screen time change: {child_name} - {day_name} - {minutes} minutes")
        self.command_queue.put(('set_screen_time', child_name, day_name, minutes))
    
    def _handle_bulk_control(self, child_name: str, control_type: str, minutes: int):
        """
        Handle bulk screen time change command from Home Assistant.
        Called when user adjusts bulk control number inputs.
        Queues the command for processing in the main thread.
        
        Args:
            child_name: Name of the child
            control_type: Type of bulk control ('all_days', 'school_nights', 'weekend')
            minutes: Screen time limit in minutes
        """
        print(f"\n📅 Received bulk control: {child_name} - {control_type} - {minutes} minutes")
        self.command_queue.put(('bulk_control', child_name, control_type, minutes))
    
    def _handle_schedule_toggle(self, child_name: str, day_name: str, enabled: bool):
        """
        Handle schedule toggle command from Home Assistant.
        Called when user toggles a schedule switch.
        """
        print(f"\n📅 Received schedule toggle: {child_name} - {day_name} - {'ON' if enabled else 'OFF'}")
        self.command_queue.put(('toggle_schedule', child_name, day_name, enabled))
    
    def _handle_schedule_time_change(self, child_name: str, day_name: str, time_type: str, time_value: str):
        """
        Handle schedule time change command from Home Assistant.
        Called when user changes start or end time for a day's schedule.
        """
        print(f"\n🕐 Received schedule time change: {child_name} - {day_name} - {time_type} = {time_value}")
        self.command_queue.put(('set_schedule_time', child_name, day_name, time_type, time_value))
    
    def _handle_block(self, child_name: str):
        """
        Handle block button press from Home Assistant.
        Blocks devices for the configured duration.
        """
        print(f"\n🚫 Received block command for {child_name}")
        self.command_queue.put(('block', child_name))
    
    def _handle_unblock(self, child_name: str):
        """
        Handle unblock button press from Home Assistant.
        Immediately unblocks devices.
        """
        print(f"\n✅ Received unblock command for {child_name}")
        self.command_queue.put(('unblock', child_name))
    
    def _handle_block_duration(self, child_name: str, minutes: int):
        """
        Handle block duration change from Home Assistant.
        Updates the stored duration for future block commands.
        """
        print(f"\n⏱️  Block duration changed: {minutes} minutes")
        self.block_duration_minutes = minutes
        self.mqtt_client.publish_block_duration_state(child_name, minutes)
    
    def _process_commands(self):
        """
        Process all queued commands from MQTT callbacks.
        Called in main thread where Playwright is safe to use.
        """
        while not self.command_queue.empty():
            try:
                command = self.command_queue.get_nowait()
                command_type = command[0]
                
                if command_type == 'toggle_limit':
                    _, child_name, day_name, enabled = command
                    try:
                        extractor = self._ensure_extractor()
                        extractor.toggle_daily_limit(day_name, enabled)
                        self.mqtt_client.publish_daily_limit_switch_state(child_name, day_name, enabled)
                        print(f"✅ Updated Amazon: {day_name} limit {'enabled' if enabled else 'disabled'}")
                    except Exception as e:
                        print(f"❌ Error toggling limit: {e}")
                        # Revert the switch state in Home Assistant
                        self.mqtt_client.publish_daily_limit_switch_state(child_name, day_name, not enabled)
                        
                elif command_type == 'set_screen_time':
                    _, child_name, day_name, minutes = command
                    try:
                        extractor = self._ensure_extractor()
                        success = extractor.set_daily_screen_time(day_name, minutes)
                        if success:
                            self.mqtt_client.publish_screen_time_number_state(child_name, day_name, minutes)
                            print(f"✅ Updated Amazon: {day_name} set to {minutes} minutes")
                        else:
                            print(f"⚠️  Failed to update {day_name} - check logs for API errors")
                    except Exception as e:
                        print(f"❌ Error setting screen time: {e}")
                        import traceback
                        traceback.print_exc()
                
                elif command_type == 'bulk_control':
                    _, child_name, control_type, minutes = command
                    try:
                        extractor = self._ensure_extractor()
                        
                        # Call appropriate bulk method
                        if control_type == 'all_days':
                            success = extractor.set_screen_time_all_days(minutes)
                        elif control_type == 'school_nights':
                            success = extractor.set_screen_time_school_nights(minutes)
                        elif control_type == 'weekend':
                            success = extractor.set_screen_time_weekend(minutes)
                        else:
                            print(f"⚠️  Unknown bulk control type: {control_type}")
                            success = False
                        
                        if success:
                            # Update all affected days in Home Assistant
                            days_map = {
                                'all_days': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
                                'school_nights': ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday'],
                                'weekend': ['Friday', 'Saturday']
                            }
                            for day in days_map.get(control_type, []):
                                self.mqtt_client.publish_screen_time_number_state(child_name, day, minutes)
                            print(f"✅ Bulk update successful: {control_type} = {minutes} minutes")
                        else:
                            print(f"⚠️  Failed bulk update for {control_type} - check logs for API errors")
                    except Exception as e:
                        print(f"❌ Error with bulk control: {e}")
                        import traceback
                        traceback.print_exc()
                
                elif command_type == 'toggle_schedule':
                    _, child_name, day_name, enabled = command
                    try:
                        extractor = self._ensure_extractor()
                        success = extractor.toggle_daily_schedule(day_name, enabled)
                        if success:
                            self.mqtt_client.publish_schedule_switch_state(child_name, day_name, enabled)
                            print(f"✅ Updated Amazon: {day_name} schedule {'enabled' if enabled else 'disabled'}")
                        else:
                            # Revert state
                            self.mqtt_client.publish_schedule_switch_state(child_name, day_name, not enabled)
                    except Exception as e:
                        print(f"❌ Error toggling schedule: {e}")
                        self.mqtt_client.publish_schedule_switch_state(child_name, day_name, not enabled)
                
                elif command_type == 'set_schedule_time':
                    _, child_name, day_name, time_type, time_value = command
                    try:
                        extractor = self._ensure_extractor()
                        # Get current schedule to preserve the other time
                        limits = extractor.get_time_limits()
                        if limits and day_name in limits.get('schedules', {}):
                            schedule = limits['schedules'][day_name]
                            current_start = schedule.get('allowed_start', '00:00')
                            current_end = schedule.get('allowed_end', '23:59')
                            current_enabled = schedule.get('schedule_enabled', False)
                            
                            # Update the changed time
                            if time_type == 'start':
                                new_start = time_value
                                new_end = current_end
                            else:  # time_type == 'end'
                                new_start = current_start
                                new_end = time_value
                            
                            # Apply the update
                            success = extractor.set_daily_schedule(day_name, new_start, new_end, current_enabled)
                            if success:
                                self.mqtt_client.publish_schedule_time_state(child_name, day_name, time_type, time_value)
                                print(f"✅ Updated Amazon: {day_name} {time_type} time = {time_value}")
                            else:
                                print(f"⚠️  Failed to update {day_name} {time_type} time")
                        else:
                            print(f"⚠️  Could not retrieve current schedule for {day_name}")
                    except Exception as e:
                        print(f"❌ Error setting schedule time: {e}")
                        import traceback
                        traceback.print_exc()
                
                elif command_type == 'block':
                    _, child_name = command
                    try:
                        extractor = self._ensure_extractor()
                        duration_hours = self.block_duration_minutes / 60
                        success = extractor.set_offscreen_time(duration_hours)
                        if success:
                            print(f"✅ Blocked devices for {self.block_duration_minutes} minutes")
                        else:
                            print(f"⚠️  Failed to block devices")
                    except Exception as e:
                        print(f"❌ Error blocking devices: {e}")
                        import traceback
                        traceback.print_exc()
                
                elif command_type == 'unblock':
                    _, child_name = command
                    try:
                        extractor = self._ensure_extractor()
                        success = extractor.clear_offscreen_time()
                        if success:
                            print(f"✅ Unblocked devices")
                        else:
                            print(f"⚠️  Failed to unblock devices")
                    except Exception as e:
                        print(f"❌ Error unblocking devices: {e}")
                        import traceback
                        traceback.print_exc()
                        
            except queue.Empty:
                break
            except Exception as e:
                print(f"❌ Error processing command: {e}")
    
    def sync_data(self):
        """
        Extract data from Amazon Dashboard and publish to MQTT.
        This runs periodically to keep Home Assistant in sync.
        """
        print(f"\n🔄 Syncing data at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
        
        with self.extractor_lock:
            try:
                extractor = self._ensure_extractor()
                
                # Get usage statistics
                usage = extractor.get_usage_statistics()
                if usage:
                    self.mqtt_client.publish_usage_state(self.child_name, usage)
                    print(f"   📊 Usage: {usage.get('today_minutes', 0):.0f}m today, {usage.get('week_minutes', 0):.0f}m this week")
                
                # Get viewing history
                viewing = extractor.get_viewing_history(days=7)
                if viewing and len(viewing) > 0:
                    latest = viewing[0]
                    self.mqtt_client.publish_viewing_activity(self.child_name, latest)
                    print(f"   📺 Latest: {latest.get('content_title', 'Unknown')}")
                
                # Get and publish time limits and schedules
                limits = extractor.get_time_limits()
                if limits:
                    daily_limits = limits.get('daily_limits', {})
                    schedules = limits.get('schedules', {})
                    
                    # Publish daily limits
                    for day, config in daily_limits.items():
                        enabled = config.get('enabled', False)
                        minutes = config.get('minutes', 0)
                        self.mqtt_client.publish_daily_limit_switch_state(self.child_name, day, enabled)
                        self.mqtt_client.publish_screen_time_number_state(self.child_name, day, minutes)
                    
                    # Publish schedules
                    for day, schedule in schedules.items():
                        schedule_enabled = schedule.get('schedule_enabled', False)
                        start_time = schedule.get('allowed_start', '00:00')
                        end_time = schedule.get('allowed_end', '23:59')
                        self.mqtt_client.publish_schedule_switch_state(self.child_name, day, schedule_enabled)
                        self.mqtt_client.publish_schedule_time_state(self.child_name, day, 'start', start_time)
                        self.mqtt_client.publish_schedule_time_state(self.child_name, day, 'end', end_time)
                    
                    print(f"   ⏰ Time limits: {sum(1 for c in daily_limits.values() if c.get('enabled'))} days enabled")
                
                self.last_run = datetime.now()
                print(f"✅ Sync complete at {self.last_run.strftime('%H:%M:%S')}")
                
            except Exception as e:
                print(f"❌ Error during sync: {e}")
                # Try to recover by recreating extractor on next sync
                self._close_extractor()
    
    def run_continuous(self, interval_seconds: int = 300):
        """
        Run continuous sync loop with MQTT command handling.
        
        Args:
            interval_seconds: How often to sync data (default: 5 minutes)
        """
        if not self.mqtt_client.connect():
            print("❌ Failed to connect to MQTT broker. Exiting.")
            return
        
        # Set up Home Assistant entities and command subscriptions
        self.setup_home_assistant_entities()
        
        # Start MQTT loop in background thread for command handling
        self.mqtt_client.client.loop_start()
        
        print(f"\n🔁 Starting continuous sync (every {interval_seconds} seconds)")
        print("   - Monitoring: Usage, viewing history, time limits")
        print("   - Controls: Daily limit switches, screen time adjustments")
        print("Press Ctrl+C to stop\n")
        
        try:
            # Do initial sync
            self.sync_data()
            
            while True:
                # Process any pending commands from MQTT
                with self.extractor_lock:
                    self._process_commands()
                
                # Wait for next sync (check for commands more frequently)
                for _ in range(interval_seconds):
                    time.sleep(1)
                    # Process commands every second to be responsive
                    with self.extractor_lock:
                        self._process_commands()
                
                # Do periodic sync
                self.sync_data()
                
        except KeyboardInterrupt:
            print("\n\n👋 Stopping integration...")
        finally:
            self.mqtt_client.client.loop_stop()
            self._close_extractor()
            self.mqtt_client.disconnect()
    
    def run_once(self):
        """Run a single sync and exit (for testing)."""
        if not self.mqtt_client.connect():
            print("❌ Failed to connect to MQTT broker. Exiting.")
            return
        
        try:
            self.setup_home_assistant_entities()
            self.sync_data()
        finally:
            self._close_extractor()
            self.mqtt_client.disconnect()


def main():
    parser = argparse.ArgumentParser(
        description="Amazon Parental Dashboard to Home Assistant Integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run once to test
  python dashboard_to_homeassistant.py --broker 192.168.1.100 --once
  
  # Run continuously, syncing every 5 minutes
  python dashboard_to_homeassistant.py --broker 192.168.1.100 --interval 300
  
  # With MQTT authentication
  python dashboard_to_homeassistant.py --broker 192.168.1.100 \\
      --username mqtt_user --password mqtt_pass --interval 600
        """
    )
    
    parser.add_argument("--broker", required=True, 
                       help="MQTT broker hostname or IP address")
    parser.add_argument("--port", type=int, default=1883,
                       help="MQTT broker port (default: 1883)")
    parser.add_argument("--username", help="MQTT username (if required)")
    parser.add_argument("--password", help="MQTT password (if required)")
    parser.add_argument("--child-name", default="daughter",
                       help="Child's name for MQTT topics (default: daughter)")
    parser.add_argument("--interval", type=int, default=300,
                       help="Sync interval in seconds (default: 300 = 5 minutes)")
    parser.add_argument("--once", action="store_true",
                       help="Run once and exit (for testing)")
    
    args = parser.parse_args()
    
    print("="*60)
    print("🚀 Amazon Dashboard → Home Assistant Integration")
    print("="*60)
    print(f"MQTT Broker: {args.broker}:{args.port}")
    print(f"Child Name: {args.child_name}")
    if args.once:
        print("Mode: Single run")
    else:
        print(f"Mode: Continuous (every {args.interval} seconds)")
    print("="*60)
    
    # Create integration
    integration = DashboardIntegration(
        mqtt_broker=args.broker,
        mqtt_port=args.port,
        mqtt_username=args.username,
        mqtt_password=args.password,
        child_name=args.child_name
    )
    
    # Run
    if args.once:
        integration.run_once()
    else:
        integration.run_continuous(args.interval)


if __name__ == "__main__":
    main()
