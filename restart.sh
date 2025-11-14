#!/bin/bash
# Quick restart script after uploading new cookies

echo "🔄 Restarting Amazon Parental Dashboard with fresh cookies..."
docker-compose restart
echo "✅ Container restarted!"
echo ""
echo "Check logs with: docker-compose logs -f"
