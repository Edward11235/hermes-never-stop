#!/bin/bash
# Start Hermes Always On watchdog in background

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Starting Hermes Always On..."

if pgrep -f "watchdog.py" > /dev/null; then
    echo "Already running!"
    exit 1
fi

cd "$PROJECT_DIR"
nohup python3 watchdog.py > /dev/null 2>&1 &

echo "Started with PID $!"
echo "Logs: $PROJECT_DIR/watchdog.log"
