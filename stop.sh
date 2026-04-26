#!/bin/bash
# Stop Hermes Always On watchdog

echo "Stopping Hermes Always On..."

if pkill -f "watchdog.py"; then
    echo "Stopped."
else
    echo "Not running."
fi
