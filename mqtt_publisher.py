"""
MQTT Publisher for Home Assistant Integration

This module will publish Amazon Parental Dashboard data to MQTT topics
that Home Assistant can consume for monitoring and automation.
"""

import json
import paho.mqtt.client as mqtt
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

class HomeAssistantMQTT:
    """
    Publishes parental control data to Home Assistant via MQTT.
    
    Topic structure:
    - homeassistant/sensor/{child_name}_usage/config - Sensor configuration
    - homeassistant/sensor/{child_name}_usage/state - Current usage data
    - homeassistant/binary_sensor/{child_name}_device_{device_id}/config - Device config
    - homeassistant/binary_sensor/{child_name}_device_{device_id}/state - Device blocked state
    - homeassistant/sensor/{child_name}_viewing/state - Recent viewing activity
    """
    
    def __init__(self, broker: str = "localhost", port: int = 1883, 
                 username: Optional[str] = None, password: Optional[str] = None):
        """Initialize MQTT client."""
        self.client = mqtt.Client()
        self.broker = broker
        self.port = port
        
        if username and password:
            self.client.username_pw_set(username, password)
        
        # Set up callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        
    def _on_connect(self, client, userdata, flags, rc):
        """Callback for when client connects to broker."""
        if rc == 0:
            print(f"✅ Connected to MQTT broker at {self.broker}:{self.port}")
        else:
            print(f"❌ Failed to connect to MQTT broker. Return code: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback for when client disconnects."""
        if rc != 0:
            print(f"⚠️  Unexpected disconnection from MQTT broker")
    
    def connect(self):
        """Connect to the MQTT broker."""
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            return True
        except Exception as e:
            print(f"❌ Error connecting to MQTT broker: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from the MQTT broker."""
        self.client.loop_stop()
        self.client.disconnect()
    
    def publish_usage_config(self, child_name: str):
        """
        Publish Home Assistant discovery config for usage sensor.
        This creates a sensor in Home Assistant automatically.
        """
        config_topic = f"homeassistant/sensor/{child_name}_usage/config"
        state_topic = f"homeassistant/sensor/{child_name}_usage/state"
        
        config = {
            "name": f"Screen Time Today",
            "state_topic": state_topic,
            "unit_of_measurement": "minutes",
            "value_template": "{{ value_json.today_minutes }}",
            "json_attributes_topic": state_topic,
            "icon": "mdi:chart-timeline-variant",
            "unique_id": f"{child_name}_screen_time",
            "device": {
                "identifiers": [f"parental_control_{child_name}_monitoring"],
                "name": f"{child_name.title()} - Monitoring",
                "manufacturer": "Amazon Parental Dashboard",
                "model": "Screen Time"
            }
        }
        
        self.client.publish(config_topic, json.dumps(config), retain=True)
        print(f"📤 Published usage config for {child_name}")
    
    def publish_usage_state(self, child_name: str, usage_data: Dict[str, Any]):
        """
        Publish current usage statistics.
        
        Args:
            child_name: Name of the child
            usage_data: Dictionary containing:
                - today_minutes: Today's screen time in minutes
                - week_minutes: This week's total in minutes
                - limit_minutes: Daily limit in minutes
                - remaining_minutes: Remaining time today
                - last_active: Timestamp of last activity
        """
        state_topic = f"homeassistant/sensor/{child_name}_usage/state"
        
        payload = {
            "today_minutes": usage_data.get("today_minutes", 0),
            "week_minutes": usage_data.get("week_minutes", 0),
            "limit_minutes": usage_data.get("limit_minutes", 0),
            "remaining_minutes": usage_data.get("remaining_minutes", 0),
            "last_active": usage_data.get("last_active", datetime.now().isoformat()),
            "updated": datetime.now().isoformat()
        }
        
        self.client.publish(state_topic, json.dumps(payload))
        print(f"📤 Published usage state for {child_name}: {payload['today_minutes']} min today")
    
    def publish_device_config(self, child_name: str, device_id: str, device_name: str):
        """
        Publish Home Assistant discovery config for device binary sensor.
        Shows whether a device is blocked/paused.
        """
        config_topic = f"homeassistant/binary_sensor/{child_name}_device_{device_id}/config"
        state_topic = f"homeassistant/binary_sensor/{child_name}_device_{device_id}/state"
        
        config = {
            "name": f"{child_name.title()} - {device_name}",
            "state_topic": state_topic,
            "payload_on": "blocked",
            "payload_off": "active",
            "device_class": "lock",
            "icon": "mdi:tablet",
            "unique_id": f"{child_name}_device_{device_id}",
            "device": {
                "identifiers": [f"parental_control_{child_name}"],
                "name": f"{child_name.title()}'s Devices",
                "manufacturer": "Amazon Parental Dashboard",
                "model": "Parental Control"
            }
        }
        
        self.client.publish(config_topic, json.dumps(config), retain=True)
        print(f"📤 Published device config for {device_name}")
    
    def publish_device_state(self, child_name: str, device_id: str, is_blocked: bool):
        """
        Publish device blocked/active state.
        
        Args:
            child_name: Name of the child
            device_id: Unique device identifier
            is_blocked: True if device is currently blocked/paused
        """
        state_topic = f"homeassistant/binary_sensor/{child_name}_device_{device_id}/state"
        state = "blocked" if is_blocked else "active"
        
        self.client.publish(state_topic, state)
        print(f"📤 Published device state: {device_id} = {state}")
    
    def publish_viewing_activity(self, child_name: str, activity_data: Dict[str, Any]):
        """
        Publish viewing history/activity data.
        
        Args:
            child_name: Name of the child
            activity_data: Dictionary containing:
                - content_title: What was watched
                - content_type: Type (video, app, etc.)
                - duration_minutes: How long
                - timestamp: When it was accessed
        """
        state_topic = f"homeassistant/sensor/{child_name}_viewing/state"
        
        payload = {
            "content_title": activity_data.get("content_title", "Unknown"),
            "content_type": activity_data.get("content_type", "Unknown"),
            "duration_minutes": activity_data.get("duration_minutes", 0),
            "timestamp": activity_data.get("timestamp", datetime.now().isoformat()),
            "updated": datetime.now().isoformat()
        }
        
        self.client.publish(state_topic, json.dumps(payload))
        print(f"📤 Published viewing activity: {payload['content_title']}")
    
    def publish_daily_limit_switch_config(self, child_name: str, day_name: str):
        """
        Publish Home Assistant discovery config for daily limit switch.
        This creates a switch to enable/disable time limits for a specific day.
        
        Args:
            child_name: Name of the child
            day_name: Day of week (Monday, Tuesday, etc.)
        """
        day_lower = day_name.lower()
        config_topic = f"homeassistant/switch/{child_name}_limit_{day_lower}/config"
        state_topic = f"homeassistant/switch/{child_name}_limit_{day_lower}/state"
        command_topic = f"homeassistant/switch/{child_name}_limit_{day_lower}/set"
        
        config = {
            "name": f"{day_name} - Enabled",
            "state_topic": state_topic,
            "command_topic": command_topic,
            "payload_on": "ON",
            "payload_off": "OFF",
            "state_on": "ON",
            "state_off": "OFF",
            "icon": "mdi:timer-outline",
            "unique_id": f"{child_name}_limit_{day_lower}",
            "device": {
                "identifiers": [f"parental_control_{child_name}_limits"],
                "name": f"{child_name.title()} - Daily Limits",
                "manufacturer": "Amazon Parental Dashboard",
                "model": "Screen Time Limits"
            }
        }
        
        self.client.publish(config_topic, json.dumps(config), retain=True)
        print(f"📤 Published switch config for {child_name} {day_name}")
    
    def publish_daily_limit_switch_state(self, child_name: str, day_name: str, enabled: bool):
        """
        Publish state of daily limit switch.
        
        Args:
            child_name: Name of the child
            day_name: Day of week
            enabled: True if time limit is enabled for this day
        """
        day_lower = day_name.lower()
        state_topic = f"homeassistant/switch/{child_name}_limit_{day_lower}/state"
        state = "ON" if enabled else "OFF"
        
        self.client.publish(state_topic, state, retain=True)
        print(f"📤 Published switch state: {day_name} = {state}")
    
    def subscribe_daily_limit_commands(self, child_name: str, callback):
        """
        Subscribe to command topics for daily limit switches.
        
        Args:
            child_name: Name of the child
            callback: Function to call when command received (child_name, day_name, enabled)
        """
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        
        for day in days:
            command_topic = f"homeassistant/switch/{child_name}_limit_{day}/set"
            self.client.subscribe(command_topic)
            print(f"📥 Subscribed to {command_topic}")
        
        # Store callback for message handler
        self._limit_callback = callback
        # Set unified message handler
        self.client.on_message = self._on_message_unified

    
    def publish_screen_time_number_config(self, child_name: str, day_name: str):
        """
        Publish Home Assistant discovery config for screen time number input.
        This creates a number slider to set daily screen time limit in minutes.
        
        Args:
            child_name: Name of the child
            day_name: Day of week (Monday, Tuesday, etc.)
        """
        day_lower = day_name.lower()
        config_topic = f"homeassistant/number/{child_name}_minutes_{day_lower}/config"
        state_topic = f"homeassistant/number/{child_name}_minutes_{day_lower}/state"
        command_topic = f"homeassistant/number/{child_name}_minutes_{day_lower}/set"
        
        config = {
            "name": f"{day_name} - Minutes",
            "state_topic": state_topic,
            "command_topic": command_topic,
            "min": 0,
            "max": 480,  # 8 hours in minutes (more reasonable max)
            "step": 15,  # 15 minute increments
            "unit_of_measurement": "min",
            "icon": "mdi:clock-time-four-outline",
            "unique_id": f"{child_name}_minutes_{day_lower}",
            "device": {
                "identifiers": [f"parental_control_{child_name}_limits"],
                "name": f"{child_name.title()} - Daily Limits",
                "manufacturer": "Amazon Parental Dashboard",
                "model": "Screen Time Limits"
            }
        }
        
        self.client.publish(config_topic, json.dumps(config), retain=True)
        print(f"📤 Published number config for {child_name} {day_name}")
    
    def publish_screen_time_number_state(self, child_name: str, day_name: str, minutes: int):
        """
        Publish state of screen time number input.
        
        Args:
            child_name: Name of the child
            day_name: Day of week
            minutes: Screen time limit in minutes
        """
        day_lower = day_name.lower()
        state_topic = f"homeassistant/number/{child_name}_minutes_{day_lower}/state"
        
        self.client.publish(state_topic, str(minutes), retain=True)
        print(f"📤 Published number state: {day_name} = {minutes} min")
    
    def subscribe_screen_time_commands(self, child_name: str, callback):
        """
        Subscribe to command topics for screen time number inputs.
        
        Args:
            child_name: Name of the child
            callback: Function to call when command received (child_name, day_name, minutes)
        """
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        
        for day in days:
            command_topic = f"homeassistant/number/{child_name}_minutes_{day}/set"
            self.client.subscribe(command_topic)
            print(f"📥 Subscribed to {command_topic}")
        
        # Store callback for message handler
        self._minutes_callback = callback
        # Set unified message handler
        self.client.on_message = self._on_message_unified
    
    def _on_message_unified(self, client, userdata, msg):
        """Unified message handler for all MQTT commands."""
        topic = msg.topic
        payload = msg.payload.decode()
        
        # Route to appropriate handler based on topic
        if "/switch/" in topic:
            self._handle_switch_command(topic, payload)
        elif "/number/" in topic:
            self._handle_number_command(topic, payload)
        elif "/text/" in topic:
            self._handle_text_command(topic, payload)
        elif "/button/" in topic:
            self._handle_button_command(topic, payload)
    
    def _handle_switch_command(self, topic, payload):
        """Handle incoming switch commands for daily limits and schedules."""
        # Parse topic to extract child and day
        # Format: homeassistant/switch/{child}_limit_{day}/set
        # or:     homeassistant/switch/{child}_schedule_{day}/set
        parts = topic.split('/')
        if len(parts) >= 3 and parts[1] == "switch":
            enabled = (payload == "ON")
            
            # Check if it's a limit switch
            if "_limit_" in parts[2]:
                entity_parts = parts[2].split('_limit_')
                if len(entity_parts) == 2:
                    child_name = entity_parts[0]
                    day_name = entity_parts[1]
                    
                    print(f"📥 Received command: {child_name} {day_name} = {enabled}")
                    
                    if hasattr(self, '_limit_callback'):
                        self._limit_callback(child_name, day_name.title(), enabled)
            
            # Check if it's a schedule switch
            elif "_schedule_" in parts[2]:
                entity_parts = parts[2].split('_schedule_')
                if len(entity_parts) == 2:
                    child_name = entity_parts[0]
                    day_name = entity_parts[1]
                    
                    print(f"📥 Received schedule command: {child_name} {day_name} = {enabled}")
                    
                    if hasattr(self, '_schedule_callback'):
                        self._schedule_callback(child_name, day_name.title(), enabled)
    
    def _handle_number_command(self, topic, payload):
        """Handle incoming number commands for screen time."""
        # Parse topic to extract child and day or bulk control
        # Format: homeassistant/number/{child}_minutes_{day}/set
        # or:     homeassistant/number/{child}_bulk_{control}/set
        parts = topic.split('/')
        if len(parts) >= 3 and parts[1] == "number":
            # Check if it's a bulk control
            if "_bulk_" in parts[2]:
                entity_parts = parts[2].split('_bulk_')
                if len(entity_parts) == 2:
                    child_name = entity_parts[0]
                    control_type = entity_parts[1]
                    try:
                        minutes = int(float(payload))
                        print(f"📥 Received bulk command: {child_name} {control_type} = {minutes} min")
                        
                        if hasattr(self, '_bulk_callback'):
                            self._bulk_callback(child_name, control_type, minutes)
                    except ValueError:
                        print(f"⚠️  Invalid minutes value: {payload}")
            # Individual day control
            else:
                entity_parts = parts[2].split('_minutes_')
                if len(entity_parts) == 2:
                    child_name = entity_parts[0]
                    day_name = entity_parts[1]
                    try:
                        minutes = int(float(payload))
                        print(f"📥 Received command: {child_name} {day_name} = {minutes} min")
                        
                        if hasattr(self, '_minutes_callback'):
                            self._minutes_callback(child_name, day_name.title(), minutes)
                    except ValueError:
                        print(f"⚠️  Invalid minutes value: {payload}")
                
                # Check if it's a block duration number
                elif "_block_duration" in parts[2]:
                    entity_parts = parts[2].split('_block_duration')
                    if len(entity_parts) >= 1:
                        child_name = entity_parts[0]
                        try:
                            minutes = int(float(payload))
                            print(f"📥 Received block duration: {child_name} = {minutes} min")
                            
                            if hasattr(self, '_block_duration_callback'):
                                self._block_duration_callback(child_name, minutes)
                        except ValueError:
                            print(f"⚠️  Invalid minutes value: {payload}")
    
    def _handle_text_command(self, topic, payload):
        """Handle incoming text commands for schedule times."""
        # Parse topic to extract child, day, and time type
        # Format: homeassistant/text/{child}_schedule_{day}_{start|end}/set
        parts = topic.split('/')
        if len(parts) >= 3 and parts[1] == "text":
            if "_schedule_" in parts[2]:
                # Extract components
                entity = parts[2]
                # Split by '_schedule_' to get child name
                child_parts = entity.split('_schedule_')
                if len(child_parts) == 2:
                    child_name = child_parts[0]
                    # Remaining part has day_timeType format
                    day_time = child_parts[1]
                    # Find if it ends with _start or _end
                    if day_time.endswith('_start'):
                        day_name = day_time[:-6]  # Remove '_start'
                        time_type = 'start'
                    elif day_time.endswith('_end'):
                        day_name = day_time[:-4]  # Remove '_end'
                        time_type = 'end'
                    else:
                        return
                    
                    print(f"📥 Received schedule time: {child_name} {day_name} {time_type} = {payload}")
                    
                    if hasattr(self, '_schedule_time_callback'):
                        self._schedule_time_callback(child_name, day_name.title(), time_type, payload)
    
    def _handle_button_command(self, topic, payload):
        """Handle incoming button press commands."""
        # Parse topic to extract child and button type
        # Format: homeassistant/button/{child}_block/set
        # or:     homeassistant/button/{child}_unblock/set
        parts = topic.split('/')
        if len(parts) >= 3 and parts[1] == "button":
            if "_block" in parts[2]:
                entity_parts = parts[2].split('_block')
                if len(entity_parts) >= 1:
                    child_name = entity_parts[0]
                    print(f"📥 Received block command for {child_name}")
                    
                    if hasattr(self, '_block_callback'):
                        self._block_callback(child_name)
            
            elif "_unblock" in parts[2]:
                entity_parts = parts[2].split('_unblock')
                if len(entity_parts) >= 1:
                    child_name = entity_parts[0]
                    print(f"📥 Received unblock command for {child_name}")
                    
                    if hasattr(self, '_unblock_callback'):
                        self._unblock_callback(child_name)
    
    def publish_bulk_control_config(self, child_name: str):
        """
        Publish Home Assistant discovery configs for bulk time limit controls.
        Creates number inputs for setting all days, school nights, or weekends at once.
        
        Args:
            child_name: Name of the child
        """
        controls = [
            ("all_days", "All Days"),
            ("school_nights", "School Nights (Sun-Thu)"),
            ("weekend", "Weekend (Fri-Sat)")
        ]
        
        for control_id, control_label in controls:
            config_topic = f"homeassistant/number/{child_name}_bulk_{control_id}/config"
            state_topic = f"homeassistant/number/{child_name}_bulk_{control_id}/state"
            command_topic = f"homeassistant/number/{child_name}_bulk_{control_id}/set"
            
            config = {
                "name": f"🔧 {control_label}",
                "state_topic": state_topic,
                "command_topic": command_topic,
                "min": 0,
                "max": 480,
                "step": 15,
                "unit_of_measurement": "min",
                "icon": "mdi:playlist-edit",
                "unique_id": f"{child_name}_bulk_{control_id}",
                "device": {
                    "identifiers": [f"parental_control_{child_name}_limits"],
                    "name": f"{child_name.title()} - Daily Limits",
                    "manufacturer": "Amazon Parental Dashboard",
                    "model": "Screen Time Limits"
                }
            }
            
            self.client.publish(config_topic, json.dumps(config), retain=True)
            print(f"📤 Published bulk control config for {child_name} {control_label}")
    
    def subscribe_bulk_control_commands(self, child_name: str, callback):
        """
        Subscribe to command topics for bulk time limit controls.
        
        Args:
            child_name: Name of the child
            callback: Function to call when command received (child_name, control_type, minutes)
                     control_type will be 'all_days', 'school_nights', or 'weekend'
        """
        controls = ["all_days", "school_nights", "weekend"]
        
        for control in controls:
            command_topic = f"homeassistant/number/{child_name}_bulk_{control}/set"
            self.client.subscribe(command_topic)
            print(f"📥 Subscribed to {command_topic}")
        
        # Store callback for message handler
        self._bulk_callback = callback
    
    def publish_schedule_switch_config(self, child_name: str, day_name: str):
        """
        Publish Home Assistant discovery config for daily usage schedule switch.
        This controls whether the allowed usage time window (curfew) is enforced.
        
        Args:
            child_name: Name of the child
            day_name: Day of week
        """
        day_lower = day_name.lower()
        config_topic = f"homeassistant/switch/{child_name}_schedule_{day_lower}/config"
        state_topic = f"homeassistant/switch/{child_name}_schedule_{day_lower}/state"
        command_topic = f"homeassistant/switch/{child_name}_schedule_{day_lower}/set"
        
        config = {
            "name": f"{day_name} - Enabled",
            "state_topic": state_topic,
            "command_topic": command_topic,
            "payload_on": "ON",
            "payload_off": "OFF",
            "state_on": "ON",
            "state_off": "OFF",
            "icon": "mdi:calendar-clock",
            "unique_id": f"{child_name}_schedule_{day_lower}",
            "device": {
                "identifiers": [f"parental_control_{child_name}_schedules"],
                "name": f"{child_name.title()} - Schedules (Curfew)",
                "manufacturer": "Amazon Parental Dashboard",
                "model": "Usage Schedules"
            }
        }
        
        self.client.publish(config_topic, json.dumps(config), retain=True)
        print(f"📤 Published schedule switch config for {child_name} {day_name}")
    
    def publish_schedule_switch_state(self, child_name: str, day_name: str, enabled: bool):
        """
        Publish state of daily usage schedule switch.
        
        Args:
            child_name: Name of the child
            day_name: Day of week
            enabled: True if schedule is enabled for this day
        """
        day_lower = day_name.lower()
        state_topic = f"homeassistant/switch/{child_name}_schedule_{day_lower}/state"
        state = "ON" if enabled else "OFF"
        
        self.client.publish(state_topic, state, retain=True)
        print(f"📤 Published schedule switch state: {day_name} = {state}")
    
    def subscribe_schedule_switch_commands(self, child_name: str, callback):
        """
        Subscribe to command topics for schedule switches.
        
        Args:
            child_name: Name of the child
            callback: Function to call when command received (child_name, day_name, enabled)
        """
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        
        for day in days:
            command_topic = f"homeassistant/switch/{child_name}_schedule_{day}/set"
            self.client.subscribe(command_topic)
            print(f"📥 Subscribed to {command_topic}")
        
        # Store callback for message handler
        self._schedule_callback = callback
    
    def publish_schedule_time_config(self, child_name: str, day_name: str, time_type: str):
        """
        Publish Home Assistant discovery config for schedule time input (start or end time).
        
        Args:
            child_name: Name of the child
            day_name: Day of week
            time_type: Either "start" or "end"
        """
        day_lower = day_name.lower()
        config_topic = f"homeassistant/text/{child_name}_schedule_{day_lower}_{time_type}/config"
        state_topic = f"homeassistant/text/{child_name}_schedule_{day_lower}_{time_type}/state"
        command_topic = f"homeassistant/text/{child_name}_schedule_{day_lower}_{time_type}/set"
        
        label = "Start" if time_type == "start" else "End"
        icon = "mdi:clock-start" if time_type == "start" else "mdi:clock-end"
        
        config = {
            "name": f"{day_name} - {label}",
            "state_topic": state_topic,
            "command_topic": command_topic,
            "icon": icon,
            "pattern": "^([01]?[0-9]|2[0-3]):[0-5][0-9]$",  # HH:MM validation
            "unique_id": f"{child_name}_schedule_{day_lower}_{time_type}",
            "device": {
                "identifiers": [f"parental_control_{child_name}_schedules"],
                "name": f"{child_name.title()} - Schedules (Curfew)",
                "manufacturer": "Amazon Parental Dashboard",
                "model": "Usage Schedules"
            }
        }
        
        self.client.publish(config_topic, json.dumps(config), retain=True)
        print(f"📤 Published schedule {time_type} time config for {child_name} {day_name}")
    
    def publish_schedule_time_state(self, child_name: str, day_name: str, time_type: str, time_value: str):
        """
        Publish state of schedule time input.
        
        Args:
            child_name: Name of the child
            day_name: Day of week
            time_type: Either "start" or "end"
            time_value: Time in HH:MM format
        """
        day_lower = day_name.lower()
        state_topic = f"homeassistant/text/{child_name}_schedule_{day_lower}_{time_type}/state"
        
        self.client.publish(state_topic, time_value, retain=True)
        print(f"📤 Published schedule {time_type} time: {day_name} = {time_value}")
    
    def subscribe_schedule_time_commands(self, child_name: str, callback):
        """
        Subscribe to command topics for schedule time inputs.
        
        Args:
            child_name: Name of the child
            callback: Function to call when command received (child_name, day_name, time_type, time_value)
        """
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        
        for day in days:
            for time_type in ["start", "end"]:
                command_topic = f"homeassistant/text/{child_name}_schedule_{day}_{time_type}/set"
                self.client.subscribe(command_topic)
                print(f"📥 Subscribed to {command_topic}")
        
        # Store callback for message handler
        self._schedule_time_callback = callback
    
    def publish_block_button_config(self, child_name: str):
        """
        Publish Home Assistant discovery config for ad-hoc block button.
        
        Args:
            child_name: Name of the child
        """
        config_topic = f"homeassistant/button/{child_name}_block/config"
        command_topic = f"homeassistant/button/{child_name}_block/set"
        
        config = {
            "name": f"⛔ Block Now",
            "command_topic": command_topic,
            "payload_press": "PRESS",
            "icon": "mdi:cancel",
            "unique_id": f"{child_name}_block_button",
            "device": {
                "identifiers": [f"parental_control_{child_name}_actions"],
                "name": f"{child_name.title()} - Quick Actions",
                "manufacturer": "Amazon Parental Dashboard",
                "model": "Device Control"
            }
        }
        
        self.client.publish(config_topic, json.dumps(config), retain=True)
        print(f"📤 Published block button config for {child_name}")
    
    def publish_unblock_button_config(self, child_name: str):
        """
        Publish Home Assistant discovery config for ad-hoc unblock button.
        
        Args:
            child_name: Name of the child
        """
        config_topic = f"homeassistant/button/{child_name}_unblock/config"
        command_topic = f"homeassistant/button/{child_name}_unblock/set"
        
        config = {
            "name": f"✅ Unblock Now",
            "command_topic": command_topic,
            "payload_press": "PRESS",
            "icon": "mdi:lock-open-check",
            "unique_id": f"{child_name}_unblock_button",
            "device": {
                "identifiers": [f"parental_control_{child_name}_actions"],
                "name": f"{child_name.title()} - Quick Actions",
                "manufacturer": "Amazon Parental Dashboard",
                "model": "Device Control"
            }
        }
        
        self.client.publish(config_topic, json.dumps(config), retain=True)
        print(f"📤 Published unblock button config for {child_name}")
    
    def publish_block_duration_config(self, child_name: str):
        """
        Publish Home Assistant discovery config for block duration number input.
        
        Args:
            child_name: Name of the child
        """
        config_topic = f"homeassistant/number/{child_name}_block_duration/config"
        state_topic = f"homeassistant/number/{child_name}_block_duration/state"
        command_topic = f"homeassistant/number/{child_name}_block_duration/set"
        
        config = {
            "name": f"Block Duration",
            "state_topic": state_topic,
            "command_topic": command_topic,
            "min": 5,
            "max": 720,  # 12 hours
            "step": 5,
            "unit_of_measurement": "min",
            "icon": "mdi:timer-sand",
            "unique_id": f"{child_name}_block_duration",
            "device": {
                "identifiers": [f"parental_control_{child_name}_actions"],
                "name": f"{child_name.title()} - Quick Actions",
                "manufacturer": "Amazon Parental Dashboard",
                "model": "Device Control"
            }
        }
        
        self.client.publish(config_topic, json.dumps(config), retain=True)
        print(f"📤 Published block duration config for {child_name}")
    
    def publish_block_duration_state(self, child_name: str, minutes: int):
        """
        Publish state of block duration number input.
        
        Args:
            child_name: Name of the child
            minutes: Block duration in minutes
        """
        state_topic = f"homeassistant/number/{child_name}_block_duration/state"
        
        self.client.publish(state_topic, str(minutes), retain=True)
        print(f"📤 Published block duration: {minutes} min")
    
    def subscribe_block_commands(self, child_name: str, block_callback, unblock_callback, duration_callback):
        """
        Subscribe to command topics for blocking controls.
        
        Args:
            child_name: Name of the child
            block_callback: Function to call when block button pressed (child_name)
            unblock_callback: Function to call when unblock button pressed (child_name)
            duration_callback: Function to call when duration changed (child_name, minutes)
        """
        # Block button
        block_topic = f"homeassistant/button/{child_name}_block/set"
        self.client.subscribe(block_topic)
        print(f"📥 Subscribed to {block_topic}")
        
        # Unblock button
        unblock_topic = f"homeassistant/button/{child_name}_unblock/set"
        self.client.subscribe(unblock_topic)
        print(f"📥 Subscribed to {unblock_topic}")
        
        # Duration number input
        duration_topic = f"homeassistant/number/{child_name}_block_duration/set"
        self.client.subscribe(duration_topic)
        print(f"📥 Subscribed to {duration_topic}")
        
        # Store callbacks for message handler
        self._block_callback = block_callback
        self._unblock_callback = unblock_callback
        self._block_duration_callback = duration_callback


# Example usage
if __name__ == "__main__":
    # This is just a template showing how to use the MQTT publisher
    # Real data will come from the Amazon dashboard extraction
    
    mqtt_client = HomeAssistantMQTT(
        broker="localhost",  # Change to your MQTT broker
        port=1883,
        # username="your_username",  # Uncomment if using authentication
        # password="your_password"
    )
    
    if mqtt_client.connect():
        # Example: Set up a child's usage sensor
        child = "sadie"
        mqtt_client.publish_usage_config(child)
        
        # Example: Publish current usage data
        usage = {
            "today_minutes": 45,
            "week_minutes": 320,
            "limit_minutes": 120,
            "remaining_minutes": 75,
            "last_active": datetime.now().isoformat()
        }
        mqtt_client.publish_usage_state(child, usage)
        
        # Example: Set up time limit controls for each day
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for day in days:
            # Create switch to enable/disable daily limit
            mqtt_client.publish_daily_limit_switch_config(child, day)
            mqtt_client.publish_daily_limit_switch_state(child, day, enabled=True)
            
            # Create number input to set screen time minutes
            mqtt_client.publish_screen_time_number_config(child, day)
            mqtt_client.publish_screen_time_number_state(child, day, minutes=180)
        
        # Example: Set up device sensor
        mqtt_client.publish_device_config(child, "fire_tablet_01", "Fire Tablet")
        mqtt_client.publish_device_state(child, "fire_tablet_01", is_blocked=False)
        
        # Example: Publish viewing activity
        activity = {
            "content_title": "Peppa Pig - The Boat Pond",
            "content_type": "VIDEO",
            "duration_minutes": 12.6,
            "timestamp": datetime.now().isoformat()
        }
        mqtt_client.publish_viewing_activity(child, activity)
        
        print("\n✅ Example MQTT messages published!")
        print("Check Home Assistant -> Settings -> Devices & Services -> MQTT")
        print(f"\n📱 Entities created:")
        print(f"   - Sensor: {child.title()} Screen Time")
        print(f"   - Switches: {child.title()} [Day] Limit (x7)")
        print(f"   - Numbers: {child.title()} [Day] Screen Time (x7)")
        print(f"   - Binary Sensor: {child.title()} - Fire Tablet")
        print(f"   - Sensor: {child.title()} Viewing")
        
        mqtt_client.disconnect()
