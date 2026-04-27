# Development Guide - Hermes Always On

This document is for AI agents (or humans) who want to understand, maintain, or extend this project.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     WATCHDOG LOOP                            │
│                                                              │
│  1. Find latest session_*.json in ~/.hermes/sessions/       │
│  2. Check if mtime or size changed since last check         │
│  3. If changed → ALIVE, reset stuck timer                    │
│  4. If not changed → increment stuck time                    │
│  5. If stuck time >= timeout → send message via xdotool     │
│  6. Sleep for interval, repeat                               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### Why Session Files?

Previous versions tried to detect "alive" by:
- Checking CPU time from `/proc/[pid]/stat`
- Checking `state.db` modification
- Checking marker files
- Detecting user typing

All of these had problems:
- CPU can be high even when stuck on an error
- state.db isn't always updated reliably
- Marker files require Hermes to touch them
- User typing detection was unreliable

**Session files are the answer because:**
- Hermes writes to them on every message exchange
- They contain the actual conversation state
- Easy to verify: `ls -la ~/.hermes/sessions/`
- No cooperation needed from Hermes

### Why xdotool?

Hermes CLI uses `prompt_toolkit` which reads from the terminal TTY. Normal file writes or API calls don't work. xdotool synthesizes real keyboard events that prompt_toolkit receives.

### Why Check Both mtime AND size?

- mtime alone: could change from metadata updates (access time, etc.)
- size alone: could stay same while content changes
- Both together: reliable indicator of actual content changes

## Code Structure

### Main Components

```python
class Watchdog:
    def __init__(config)           # Load config, setup paths
    def get_latest_session_file()   # Find most recent session JSON
    def check_session_changed()     # Compare mtime/size to last check
    def send_message()              # xdotool keyboard injection
    def run()                       # Main loop
```

### Configuration

```python
def get_config() -> dict:
    # Returns: {"timeout": 120, "interval": 30, "message": "..."}
```

### CLI Commands

```python
def check_status()   # --status: check if running
def stop_watchdog()  # --stop: kill background process
def test_send()      # --test: test xdotool sending
```

## Session File Format

Session files are JSON with naming pattern:
```
session_YYYYMMDD_HHMMSS_HASH.json
```

Example:
```
session_20260427_095351_c27540.json
```

The watchdog finds the most recently modified one using:
```python
max(session_files, key=lambda f: f.stat().st_mtime)
```

## Extending the Watchdog

### Add a New Notification Method

1. Add method to `send_message()` or create new method:
```python
def send_message_slack(self) -> bool:
    # Post to Slack webhook
    ...
```

2. Add config option in `config.ini`
3. Add logic in `run()` to call the new method

### Support Different Terminal Emulators

Modify `_send_message()` to search for different window classes:
```python
# Current: gnome-terminal
result = subprocess.run(["xdotool", "search", "--class", "gnome-terminal"], ...)

# For konsole (KDE):
result = subprocess.run(["xdotool", "search", "--class", "konsole"], ...)

# For alacritty:
result = subprocess.run(["xdotool", "search", "--class", "Alacritty"], ...)
```

### Add Multiple Detection Methods

Create a new check function:
```python
def check_api_heartbeat(self) -> bool:
    # Check if Hermes API endpoint responds
    ...
```

Then in `run()`:
```python
session_alive = self.check_session_changed()
api_alive = self.check_api_heartbeat()
is_alive = session_alive or api_alive
```

## Testing

### Manual Testing

```bash
# Test xdotool sending (should type into your terminal)
python watchdog.py --test

# Run in foreground to see logs
python watchdog.py

# Check status
python watchdog.py --status
```

### Simulating "Stuck"

1. Start Hermes normally
2. Start watchdog
3. Don't send any messages to Hermes
4. Wait for `timeout` seconds
5. Watchdog should send the message

### Checking Session Files

```bash
# List all session files with modification times
ls -la ~/.hermes/sessions/

# Watch the latest file change in real-time
watch -n 1 'ls -la ~/.hermes/sessions/ | tail -5'

# Check file is being written to
stat ~/.hermes/sessions/session_*.json
```

## Known Limitations

1. **Terminal focus required** - xdotool needs to focus the window before typing. This means the terminal will briefly flash to the foreground when sending.

2. **All terminals receive message** - The watchdog sends to ALL gnome-terminal windows because it can't determine which one is running Hermes.

3. **No Hermes cooperation** - Hermes doesn't know about the watchdog. It just sees keyboard input.

4. **GNOME Terminal specific** - Currently hardcoded to `gnome-terminal` window class.

## Future Improvements

1. **Configurable terminal class** - Add to config.ini
2. **Specific window targeting** - Find the Hermes window by process ID
3. **Multiple notification methods** - Slack, Discord, email
4. **Grace period after send** - Don't send again immediately after a send
5. **Smart message selection** - Different messages for different stuck durations

## Debugging

### Enable Verbose Logging

The watchdog logs to both stdout and `watchdog.log`. Check the log:
```bash
tail -f watchdog.log
```

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| "No session file found" | Hermes not running | Start Hermes first |
| "xdotool not found" | Not installed | `sudo apt install xdotool` |
| Message not received | Wrong terminal class | Check terminal emulator |
| False "stuck" detection | timeout too low | Increase in config.ini |

## File Locations

```
~/Desktop/hermes_never_stop/
├── watchdog.py          # Main script (this is all you need)
├── config.ini           # User configuration
├── scripts/
│   ├── start.sh         # Convenience: start in background
│   ├── stop.sh          # Convenience: stop background
│   └── status.sh        # Convenience: check status
├── README.md            # User documentation
├── DEVELOPMENT.md       # This file
└── LICENSE              # MIT
```

Note: `watchdog.log` is created at runtime in the project directory.

## Dependencies

- Python 3.10+ (uses `Path | None` type hints)
- xdotool (for keyboard injection)
- Standard library only (no pip packages required)

## Contributing

1. Keep it simple - the whole point is reliable detection
2. Test with actual Hermes sessions
3. Update this DEVELOPMENT.md if you change architecture
4. The main logic should stay in one file (`watchdog.py`)
