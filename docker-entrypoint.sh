#!/bin/sh
set -e

echo "=================================================="
echo "  MiroFish starting..."
echo "=================================================="

# Start Flask backend
cd /app/backend
.venv/bin/python run.py &
BACKEND_PID=$!

# Start nginx (frontend + API proxy)
nginx -g "daemon off;" &
NGINX_PID=$!

echo "=================================================="
echo "  MiroFish is running"
echo "  UI:      http://0.0.0.0:3000"
echo "  API:     http://0.0.0.0:5001"
echo "=================================================="

# Wait for either process to exit
wait -n $BACKEND_PID $NGINX_PID 2>/dev/null || wait $BACKEND_PID $NGINX_PID
