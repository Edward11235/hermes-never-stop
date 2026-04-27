#!/usr/bin/env python3
"""
Hermes Always On - Watchdog

Keeps Hermes AI agent running by detecting when it stops responding.
Uses a simple, reliable method: check if the latest session JSON file changes.

Logic:
    - Hermes writes to ~/.hermes/sessions/*.json as it works
    - If the latest JSON file is being modified, Hermes is alive
    - If it stops changing for too long, Hermes is stuck/dead
    - Send a message to wake it up

Usage:
    python watchdog.py           # Run in foreground (Ctrl+C to stop)
    python watchdog.py --status  # Check if running
    python watchdog.py --stop    # Stop background instance
    python watchdog.py --test    # Test sending a message

Config:
    Edit config.ini to customize timeout, interval, and message.
"""

import os
import sys
import time
import signal
import subprocess
import configparser
from datetime import datetime
from pathlib import Path


def get_config() -> dict:
    """Load configuration from config.ini."""
    config_path = Path(__file__).parent / "config.ini"
    
    defaults = {
        "timeout": 120,        # Seconds without change before sending message
        "interval": 30,        # Seconds between checks
        "message": "hey don't stop hermes",
    }
    
    if config_path.exists():
        try:
            parser = configparser.ConfigParser()
            parser.read(config_path)
            if "watchdog" in parser:
                section = parser["watchdog"]
                if "timeout" in section:
                    defaults["timeout"] = int(section["timeout"])
                if "interval" in section:
                    defaults["interval"] = int(section["interval"])
                if "message" in section:
                    defaults["message"] = section["message"]
        except Exception:
            pass
    
    return defaults


class Watchdog:
    """Simple watchdog for Hermes agent using session file changes."""
    
    def __init__(self, config: dict):
        self.timeout = config["timeout"]
        self.interval = config["interval"]
        self.message = config["message"]
        
        self.sessions_dir = Path.home() / ".hermes" / "sessions"
        self.log_file = Path(__file__).parent / "watchdog.log"
        self.running = True
        
        # Track the last known mtime of the latest session file
        self.last_mtime = 0
        self.last_size = 0
        self.stuck_since = None  # When we first detected no change
        self.initialized = False  # First check just sets baseline, doesn't trigger anything
        
        # Handle Ctrl+C gracefully
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)
    
    def _shutdown(self, signum, frame):
        """Graceful shutdown on Ctrl+C."""
        self.log("\n" + "=" * 50)
        self.log("Watchdog stopped by user (Ctrl+C)")
        self.log("=" * 50)
        self.running = False
        sys.exit(0)
    
    def log(self, msg: str):
        """Log message with timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {msg}"
        print(line)
        try:
            with open(self.log_file, "a") as f:
                f.write(line + "\n")
        except Exception:
            pass
    
    def get_latest_session_file(self) -> Path | None:
        """Find the most recently modified session JSON file."""
        try:
            if not self.sessions_dir.exists():
                return None
            
            # Find all session_*.json files
            session_files = list(self.sessions_dir.glob("session_*.json"))
            
            if not session_files:
                # Fall back to any *.json files
                session_files = list(self.sessions_dir.glob("*.json"))
            
            if not session_files:
                return None
            
            # Return the most recently modified one
            return max(session_files, key=lambda f: f.stat().st_mtime)
        
        except Exception as e:
            self.log(f"Error finding session file: {e}")
            return None
    
    def check_session_changed(self) -> tuple[bool, float, int, Path | None]:
        """
        Check if the latest session file has changed since last check.
        
        Returns:
            (changed, mtime, size, session_file)
        """
        session_file = self.get_latest_session_file()
        
        if not session_file:
            return False, 0, 0, None
        
        try:
            stat = session_file.stat()
            mtime = stat.st_mtime
            size = stat.st_size
            
            # Check if either mtime or size changed
            changed = (mtime != self.last_mtime) or (size != self.last_size)
            
            return changed, mtime, size, session_file
        
        except Exception as e:
            self.log(f"Error checking session file: {e}")
            return False, 0, 0, session_file
    
    def send_message(self) -> bool:
        """
        Send message via xdotool keyboard injection.
        
        Uses xdotool to type the message into all terminal windows.
        This works with prompt_toolkit-based applications like Hermes.
        """
        try:
            # Find all gnome-terminal windows
            result = subprocess.run(
                ["xdotool", "search", "--class", "gnome-terminal"],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode != 0:
                self.log("No terminal windows found")
                return False
            
            windows = [w for w in result.stdout.strip().split("\n") if w]
            
            if not windows:
                self.log("No terminal windows found")
                return False
            
            self.log(f"Found {len(windows)} terminal window(s)")
            
            success = False
            for win_id in windows:
                try:
                    # Focus the window (required for xdotool type to work)
                    subprocess.run(
                        ["xdotool", "windowfocus", "--sync", win_id],
                        capture_output=True, text=True, timeout=2
                    )
                    time.sleep(0.05)
                    
                    # Type the message
                    type_result = subprocess.run(
                        ["xdotool", "type", self.message],
                        capture_output=True, text=True, timeout=10
                    )
                    
                    if type_result.returncode != 0:
                        continue
                    
                    time.sleep(0.05)
                    
                    # Press Enter
                    key_result = subprocess.run(
                        ["xdotool", "key", "Return"],
                        capture_output=True, text=True, timeout=5
                    )
                    
                    if key_result.returncode == 0:
                        self.log(f"Sent '{self.message}' to window {win_id}")
                        success = True
                    
                except subprocess.TimeoutExpired:
                    continue
                except Exception as e:
                    self.log(f"Error with window {win_id}: {e}")
                    continue
            
            return success
        
        except FileNotFoundError:
            self.log("xdotool not found - install with: sudo apt install xdotool")
        except subprocess.TimeoutExpired:
            self.log("xdotool timeout")
        except Exception as e:
            self.log(f"xdotool error: {e}")
        
        return False
    
    def run(self):
        """Main watchdog loop."""
        self.log("=" * 50)
        self.log("Hermes Always On - Watchdog Started")
        self.log("=" * 50)
        self.log(f"Sessions dir: {self.sessions_dir}")
        self.log(f"Timeout: {self.timeout}s ({self.timeout // 60} min)")
        self.log(f"Check interval: {self.interval}s")
        self.log(f"Message: '{self.message}'")
        self.log("Press Ctrl+C to stop")
        self.log("=" * 50)
        
        while self.running:
            # Check if session file changed
            changed, mtime, size, session_file = self.check_session_changed()
            
            if session_file:
                session_name = session_file.name
                
                # First check: just set baseline, don't trigger anything
                if not self.initialized:
                    self.last_mtime = mtime
                    self.last_size = size
                    self.initialized = True
                    mtime_str = datetime.fromtimestamp(mtime).strftime("%H:%M:%S")
                    self.log(f"INIT - {session_name} (baseline: {mtime_str}, size: {size})")
                    time.sleep(self.interval)
                    continue
                
                if changed:
                    # Session file changed - Hermes is alive!
                    self.last_mtime = mtime
                    self.last_size = size
                    self.stuck_since = None
                    
                    mtime_str = datetime.fromtimestamp(mtime).strftime("%H:%M:%S")
                    self.log(f"ALIVE - {session_name} modified at {mtime_str} (size: {size})")
                
                else:
                    # No change detected
                    if self.stuck_since is None:
                        # First time detecting no change
                        self.stuck_since = time.time()
                        self.log(f"NO CHANGE - {session_name} (size: {size})")
                    else:
                        # How long has it been stuck?
                        stuck_duration = int(time.time() - self.stuck_since)
                        
                        if stuck_duration >= self.timeout:
                            # TIMEOUT - Hermes is stuck!
                            self.log("=" * 50)
                            self.log(f">>> STUCK for {stuck_duration}s - SENDING MESSAGE <<<")
                            self.log("=" * 50)
                            
                            self.send_message()
                            
                            # Reset stuck timer after sending
                            self.stuck_since = time.time()
                        else:
                            # Not yet timeout threshold
                            self.log(f"NO CHANGE - {session_name} (stuck: {stuck_duration}s / {self.timeout}s)")
            else:
                self.log("No session file found - is Hermes running?")
            
            # Wait for next check
            time.sleep(self.interval)


def check_status():
    """Check if watchdog is running."""
    print("=" * 50)
    print("Hermes Always On - Status")
    print("=" * 50)
    
    result = subprocess.run(
        ["pgrep", "-f", "watchdog.py"],
        capture_output=True, text=True
    )
    
    if result.returncode == 0:
        pids = [p for p in result.stdout.strip().split("\n") if p and p != str(os.getpid())]
        if pids:
            print(f"Status: RUNNING (PID: {', '.join(pids)})")
            print()
            print("Recent logs:")
            log_file = Path(__file__).parent / "watchdog.log"
            if log_file.exists():
                subprocess.run(["tail", "-10", str(log_file)])
            return
    
    print("Status: NOT RUNNING")
    print()
    print("To start: python watchdog.py")


def stop_watchdog():
    """Stop running watchdog instances."""
    print("Stopping Hermes Always On...")
    
    result = subprocess.run(
        ["pgrep", "-f", "watchdog.py"],
        capture_output=True, text=True
    )
    
    if result.returncode == 0:
        pids = [p for p in result.stdout.strip().split("\n") if p and p != str(os.getpid())]
        if pids:
            for pid in pids:
                subprocess.run(["kill", pid])
                print(f"Stopped PID {pid}")
            print("Done.")
            return
    
    print("Not running.")


def test_send():
    """Test sending a message."""
    print("=" * 50)
    print("TEST MODE - Sending message immediately")
    print("=" * 50)
    config = get_config()
    watchdog = Watchdog(config)
    success = watchdog.send_message()
    print(f"\nResult: {'SUCCESS' if success else 'FAILED'}")


def main():
    """Main entry point."""
    # Check command line arguments
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg in ["--status", "status"]:
            check_status()
            return
        elif arg in ["--stop", "stop"]:
            stop_watchdog()
            return
        elif arg in ["--test", "test"]:
            test_send()
            return
        elif arg in ["--help", "-h", "help"]:
            print(__doc__)
            return
        else:
            print(f"Unknown argument: {arg}")
            print("Use --help for usage")
            return
    
    # Run the watchdog
    config = get_config()
    watchdog = Watchdog(config)
    watchdog.run()


if __name__ == "__main__":
    main()
