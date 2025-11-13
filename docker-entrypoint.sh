#!/bin/sh
# Docker entrypoint script
# Runs either the cookie setup UI or the main dashboard integration

if [ "$SETUP_MODE" = "true" ]; then
    echo "🔐 Starting in SETUP MODE - Cookie Authentication UI"
    echo "📱 Access the setup page at: http://localhost:8080"
    echo ""
    exec python -u cookie_auth_ui.py
else
    echo "🚀 Starting in NORMAL MODE - Dashboard Integration"
    echo ""
    
    # Check if cookies exist
    if [ ! -f "/app/amazon_parental/cookies.json" ]; then
        echo "⚠️  WARNING: No cookies.json found!"
        echo "   Please run in SETUP_MODE first or provide cookies.json"
        echo ""
        echo "   To run setup mode:"
        echo "   docker run -e SETUP_MODE=true -p 8080:8080 [image]"
        echo ""
        exit 1
    fi
    
    # Run the main integration
    exec python -u dashboard_to_homeassistant.py \
        --broker "$MQTT_BROKER" \
        --port "$MQTT_PORT" \
        ${MQTT_USERNAME:+--username "$MQTT_USERNAME"} \
        ${MQTT_PASSWORD:+--password "$MQTT_PASSWORD"} \
        --child-name "$CHILD_NAME" \
        --interval "$SYNC_INTERVAL"
fi
