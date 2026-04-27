# Hermes Always On

A watchdog that keeps Hermes AI agent running by detecting when it stops responding.

## How It Works

The watchdog uses a simple, reliable method to detect if Hermes is alive:

1. Hermes writes to `~/.hermes/sessions/*.json` as it processes messages
2. The watchdog finds the latest session file and monitors its modification time and size
3. If the file keeps changing → Hermes is working (ALIVE)
4. If the file stops changing for too long → Hermes is stuck (send message via xdotool)

This approach is reliable because:
- Hermes **must** write to session files to function
- No false positives from CPU spikes or other processes
- Simple to verify manually: `ls -la ~/.hermes/sessions/`

## Installation

Requires `xdotool` for keyboard injection:

```bash
sudo apt install xdotool
```

## Usage

```bash
# Start watchdog (foreground, Ctrl+C to stop)
python watchdog.py

# Or use the convenience scripts
./scripts/start.sh    # Start in background
./scripts/status.sh   # Check status
./scripts/stop.sh     # Stop background instance

# Test message sending
python watchdog.py --test
```

## Configuration

Edit `config.ini` to customize:

```ini
[watchdog]
# Seconds without session file change before sending message
timeout = 120

# How often to check for changes (seconds)
interval = 30

# Message to send when Hermes is stuck
message = continue doing research and writing proof
```

## How It Detects "Stuck"

1. Find the most recently modified `session_*.json` in `~/.hermes/sessions/`
2. Record its modification time (mtime) and file size
3. Check again after `interval` seconds
4. If mtime AND size are unchanged, start counting "stuck" time
5. If stuck time exceeds `timeout`, send message via xdotool
6. Reset stuck timer after sending

## Requirements

- Python 3.10+
- xdotool (for keyboard injection)
- GNOME Terminal (or modify for your terminal emulator)

## Files

```
hermes_never_stop/
├── watchdog.py      # Main watchdog script
├── config.ini       # Configuration
├── scripts/
│   ├── start.sh     # Start in background
│   ├── stop.sh      # Stop background instance
│   └── status.sh    # Check status
├── README.md        # This file
├── DEVELOPMENT.md   # Developer documentation
└── LICENSE          # MIT
```

## Troubleshooting

### "No session file found"

Hermes hasn't created any session files yet. Make sure Hermes is running.

### "xdotool not found"

Install it: `sudo apt install xdotool`

### Message sent but Hermes didn't receive it

The watchdog sends to ALL terminal windows. Make sure Hermes is running in a gnome-terminal window.

## License

MIT
