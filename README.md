# Hermes Always On

A watchdog that automatically keeps your Hermes AI agent running when it gets stuck.

## Quick Start

```bash
# Just run it - that's it!
python watchdog.py

# Press Ctrl+C to stop
```

**That's all you need!** The watchdog runs in foreground, press Ctrl+C to stop.

## Commands

```bash
python watchdog.py           # Run watchdog (Ctrl+C to stop)
python watchdog.py --test    # Send message immediately (test mode)
python watchdog.py --status  # Check if running
python watchdog.py --stop    # Stop background instance
python watchdog.py --help    # Show help
```

## Configuration

Edit `config.ini` to customize:

```ini
[watchdog]
# How long to wait before sending message (seconds)
timeout = 120

# How often to check for activity (seconds)
interval = 30

# Method: signal (xdotool), file, or api
method = signal

# The message to send when Hermes is stalled
message = hey don't stop hermes
```

### Custom Messages

Change `message` to anything:

```ini
message = continue
message = what are you doing?
message = /status
message = please keep working
```

## How It Works

1. **Monitors activity** - Watches `~/.hermes/activity_marker` file
2. **Detects stall** - When no activity for `timeout` seconds
3. **Injects message** - Uses xdotool to type message and press Enter

### Message Injection

The watchdog uses `xdotool` to synthesize keyboard events:
1. Finds all terminal windows
2. Focuses each terminal
3. Types the message
4. Presses Enter

This works reliably with `prompt_toolkit`-based applications like Hermes CLI.

## Requirements

- Python 3.6+
- Linux with X11
- `xdotool` (install: `sudo apt install xdotool`)
- Hermes CLI running in a terminal

No Python dependencies!

## ⚠️ Important Caveat: Broadcast to All Terminals

**The watchdog sends the message to ALL terminal windows, not just Hermes.**

Why? Because there's no reliable way to map a specific TTY (where Hermes runs) to an X11 window ID in `gnome-terminal`. The terminal server is a single process managing multiple windows, and the D-Bus interface doesn't expose window IDs.

**What this means:**
- If you have 3 terminal windows open, all 3 will receive the message
- The message will appear in your other terminals as typed text
- This is harmless but may look surprising

**Why this is acceptable:**
- The message is just text - it won't execute commands in other terminals
- It only happens when Hermes is stalled (not constantly)
- It's better to over-deliver than miss the Hermes terminal
- No false negatives: Hermes always receives the message

If you only have one terminal running Hermes, this isn't an issue at all.

## Example Output

```
[2026-04-26 12:00:00] Hermes Always On - Watchdog Started
[2026-04-26 12:00:00] Timeout: 120s (2 min)
[2026-04-26 12:00:00] Message: 'hey don't stop hermes'
[2026-04-26 12:00:00] Press Ctrl+C to stop
[2026-04-26 12:00:30] Last update: 30s ago [ACTIVE]
[2026-04-26 12:02:30] Last update: 150s ago [STALLED]
[2026-04-26 12:02:30] >>> SENDING: hey don't stop hermes <<<
[2026-04-26 12:02:30] Found 3 terminal window(s)
[2026-04-26 12:02:30] Sent 'hey don't stop hermes' to window 41943041
[2026-04-26 12:02:30] Sent 'hey don't stop hermes' to window 42003689
[2026-04-26 12:02:30] Sent 'hey don't stop hermes' to window 42045987
^C
[2026-04-26 12:03:00] Watchdog stopped by user (Ctrl+C)
```

## Background Running (Optional)

If you want to run in background:

```bash
# Start in background
nohup python watchdog.py > /dev/null 2>&1 &

# Check status
python watchdog.py --status

# Stop
python watchdog.py --stop
```

Or use the shell scripts:
```bash
./start.sh   # Start in background
./status.sh  # Check status
./stop.sh    # Stop
```

## Troubleshooting

### "xdotool not found"

```bash
sudo apt install xdotool
```

### Watchdog sends message too often

Increase `timeout` in `config.ini`:
```ini
timeout = 300  # 5 minutes
```

### Message not received by Hermes

Make sure:
1. Hermes is running in a terminal window
2. The terminal window is visible (not minimized)
3. X11 is running (not a headless server)

## License

MIT License
