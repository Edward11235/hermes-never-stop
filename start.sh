#!/bin/bash
# Start Hermes Always On watchdog in background

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Starting Hermes Always On..."

if pgrep -f "watchdog.py" > /dev/null; then
    echo "Already running!"
    exit 1
fi

cd "$SCRIPT_DIR"
nohup python3 watchdog.py > /dev/null 2>&1 &

echo "Started with PID $!"
echo "Logs: $SCRIPT_DIR/watchdog.log"
