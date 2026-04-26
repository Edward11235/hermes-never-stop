#!/bin/bash
# Check Hermes Always On watchdog status

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Hermes Always On Status ==="

# Check if running
if pgrep -f "watchdog.py" > /dev/null; then
    PID=$(pgrep -f "watchdog.py")
    echo "Status: RUNNING (PID: $PID)"
    
    # Show last 5 log lines
    echo ""
    echo "Recent activity:"
    tail -5 "$SCRIPT_DIR/watchdog.log" 2>/dev/null || echo "No logs yet"
    
    # Show Hermes terminal
    HERMES_PID=$(pgrep -f "hermes" | head -1)
    if [ -n "$HERMES_PID" ]; then
        TTY=$(ps -o tty= -p "$HERMES_PID" 2>/dev/null)
        echo ""
        echo "Hermes terminal: /dev/$TTY"
    fi
else
    echo "Status: NOT RUNNING"
    echo ""
    echo "To start: ./start.sh"
fi