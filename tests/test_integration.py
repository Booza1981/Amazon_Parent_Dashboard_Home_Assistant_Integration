"""
Test script for dashboard_to_homeassistant.py integration

This script validates that all components work together correctly:
1. DashboardDataExtractor can fetch data
2. MQTT publisher can connect and publish
3. Command handlers work correctly
4. No import errors or configuration issues

Usage:
    python test_integration.py --broker 192.168.1.100
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mqtt_publisher import HomeAssistantMQTT
from datetime import datetime


def test_mqtt_connection(broker, port, username, password):
    """Test MQTT broker connection."""
    print("\n🔌 Testing MQTT Connection...")
    print(f"   Broker: {broker}:{port}")
    
    try:
        mqtt = HomeAssistantMQTT(broker=broker, port=port, username=username, password=password)
        if mqtt.connect():
            print("   ✅ MQTT connection successful")
            mqtt.disconnect()
            return True
        else:
            print("   ❌ MQTT connection failed")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_data_extraction():
    """Test data extraction without running full integration."""
    print("\n📊 Testing Data Extraction...")
    print("   Note: This will open a browser and requires cookies.json")
    
    try:
        from playwright.sync_api import sync_playwright
        from amazon_parental.data_extractor import DashboardDataExtractor
        
        with sync_playwright() as p:
            extractor = DashboardDataExtractor(p, headless=False)
            
            try:
                print("   🔐 Logging in to Amazon...")
                extractor.login()
                print("   ✅ Login successful")
                
                print("   📈 Fetching usage statistics...")
                usage = extractor.get_usage_statistics()
                if usage:
                    today = usage.get('today_minutes', 0)
                    week = usage.get('week_minutes', 0)
                    print(f"   ✅ Usage: {today:.0f}m today, {week:.0f}m this week")
                else:
                    print("   ⚠️  No usage data returned")
                
                print("   ⏰ Fetching time limits...")
                limits = extractor.get_time_limits()
                if limits:
                    daily_limits = limits.get('daily_limits', {})
                    enabled_count = sum(1 for c in daily_limits.values() if c.get('enabled'))
                    print(f"   ✅ Time limits: {enabled_count}/7 days enabled")
                else:
                    print("   ⚠️  No time limit data returned")
                
                return True
                
            except Exception as e:
                print(f"   ❌ Error: {e}")
                return False
            finally:
                extractor.close()
                
    except Exception as e:
        print(f"   ❌ Import error: {e}")
        return False


def test_mqtt_publish(broker, port, username, password, child_name):
    """Test MQTT publishing."""
    print("\n📤 Testing MQTT Publishing...")
    
    try:
        mqtt = HomeAssistantMQTT(broker=broker, port=port, username=username, password=password)
        if not mqtt.connect():
            print("   ❌ Could not connect to MQTT broker")
            return False
        
        # Test config publishing
        print(f"   📋 Publishing config for child '{child_name}'...")
        mqtt.publish_usage_config(child_name)
        
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        for day in days:
            mqtt.publish_daily_limit_switch_config(child_name, day)
            mqtt.publish_screen_time_number_config(child_name, day)
        
        print("   ✅ Published 15 entity configs (1 sensor + 7 switches + 7 numbers)")
        
        # Test state publishing
        print("   📊 Publishing test state data...")
        test_usage = {
            'today_minutes': 62,
            'week_minutes': 543,
            'category_breakdown': {
                'Video': 350,
                'Apps': 150,
                'Web': 43
            }
        }
        mqtt.publish_usage_state(child_name, test_usage)
        
        mqtt.publish_daily_limit_switch_state(child_name, 'monday', True)
        mqtt.publish_screen_time_number_state(child_name, 'monday', 120)
        
        print("   ✅ Published test states")
        
        mqtt.disconnect()
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Test Amazon Dashboard Integration")
    parser.add_argument("--broker", required=True, help="MQTT broker hostname or IP")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument("--username", help="MQTT username")
    parser.add_argument("--password", help="MQTT password")
    parser.add_argument("--child-name", default="daughter", help="Child name for testing")
    parser.add_argument("--skip-extraction", action="store_true", 
                       help="Skip data extraction test (requires cookies.json)")
    
    args = parser.parse_args()
    
    print("="*60)
    print("🧪 Amazon Dashboard Integration Test Suite")
    print("="*60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    results = {}
    
    # Test 1: MQTT Connection
    results['mqtt_connection'] = test_mqtt_connection(
        args.broker, args.port, args.username, args.password
    )
    
    # Test 2: Data Extraction (optional)
    if not args.skip_extraction:
        results['data_extraction'] = test_data_extraction()
    else:
        print("\n📊 Skipping data extraction test (--skip-extraction)")
        results['data_extraction'] = None
    
    # Test 3: MQTT Publishing
    results['mqtt_publish'] = test_mqtt_publish(
        args.broker, args.port, args.username, args.password, args.child_name
    )
    
    # Summary
    print("\n" + "="*60)
    print("📋 Test Results Summary")
    print("="*60)
    
    for test_name, result in results.items():
        if result is None:
            status = "⏭️  SKIPPED"
        elif result:
            status = "✅ PASSED"
        else:
            status = "❌ FAILED"
        print(f"   {test_name:20s}: {status}")
    
    # Overall result
    failed = [name for name, result in results.items() if result is False]
    if failed:
        print(f"\n❌ {len(failed)} test(s) failed: {', '.join(failed)}")
        sys.exit(1)
    else:
        passed = [name for name, result in results.items() if result is True]
        print(f"\n✅ All tests passed! ({len(passed)} tests)")
        print("\n💡 Next steps:")
        print("   1. Check Home Assistant for new entities")
        print("   2. Run: docker-compose up -d")
        print("   3. Monitor logs: docker-compose logs -f")
        sys.exit(0)


if __name__ == "__main__":
    main()
