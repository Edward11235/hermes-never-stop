#!/usr/bin/env python3
"""
Hermes Always On - Watchdog

A simple watchdog that keeps Hermes AI agent running.
Sends a message when Hermes appears stuck.

Usage:
    python watchdog.py           # Run in foreground (Ctrl+C to stop)
    python watchdog.py --status  # Check if running
    python watchdog.py --stop    # Stop background instance

Config:
    Edit config.ini to customize timeout, interval, and message.
"""

import os
import sys
import time
import signal
import subprocess
import configparser
from datetime import datetime, timedelta
from pathlib import Path


def get_config() -> dict:
    """Load configuration from config.ini."""
    config_path = Path(__file__).parent / "config.ini"
    
    defaults = {
        "timeout": 120,
        "interval": 30,
        "method": "signal",
        "message": "hey don't stop hermes",
        "api_url": "http://localhost:8080"
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
                if "method" in section:
                    defaults["method"] = section["method"]
                if "api_url" in section:
                    defaults["api_url"] = section["api_url"]
                if "message" in section:
                    defaults["message"] = section["message"]
        except Exception:
            pass
    
    return defaults


class Watchdog:
    """Simple watchdog for Hermes agent."""
    
    def __init__(self, config: dict):
        self.timeout = config["timeout"]
        self.interval = config["interval"]
        self.method = config["method"]
        self.message = config["message"]
        self.api_url = config["api_url"]
        
        # Use Hermes's state.db as activity indicator (gets updated on each message)
        self.state_db = Path.home() / ".hermes" / "state.db"
        self.marker_file = Path.home() / ".hermes" / "activity_marker"
        self.marker_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Create marker file for backwards compatibility
        if not self.marker_file.exists():
            self.marker_file.touch()
        
        self.log_file = Path(__file__).parent / "watchdog.log"
        self.running = True
        
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
    
    def _is_hermes_active(self) -> tuple[bool, str]:
        """Check if Hermes process is actively running.
        
        Returns (is_active, reason) tuple.
        
        To be considered "active", Hermes must have BOTH:
        1. CPU activity (process is doing work)
        2. Marker file updates (Hermes is making progress)
        
        If CPU is active but marker file is stale, Hermes is likely stuck
        on an error or waiting for input.
        """
        try:
            # Find Hermes process
            result = subprocess.run(
                ["pgrep", "-f", "hermes"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0:
                return False, "no process"
            
            pids = [p for p in result.stdout.strip().split("\n") if p]
            if not pids:
                return False, "no process"
            
            # Check if any Hermes process has recent CPU activity
            cpu_active = False
            for pid in pids[:3]:
                try:
                    # Read /proc/[pid]/stat to get CPU times
                    stat_file = f"/proc/{pid}/stat"
                    if os.path.exists(stat_file):
                        with open(stat_file, 'r') as f:
                            stat_data = f.read()
                        
                        # Parse utime and stime (fields 14 and 15 after the comm field)
                        # Format: pid (comm) state ppid ... utime stime ...
                        parts = stat_data.split()
                        if len(parts) >= 17:
                            # Store current CPU time for comparison
                            utime = int(parts[13])
                            stime = int(parts[14])
                            total_time = utime + stime
                            
                            # Check if we have a previous reading
                            cache_file = self.marker_file.parent / f"cpu_time_{pid}"
                            if cache_file.exists():
                                try:
                                    with open(cache_file, 'r') as f:
                                        prev_time = int(f.read().strip())
                                    
                                    # If CPU time increased, process is using CPU
                                    if total_time > prev_time:
                                        cpu_active = True
                                        # Update cache
                                        with open(cache_file, 'w') as f:
                                            f.write(str(total_time))
                                        break  # Found active CPU
                                except (ValueError, IOError):
                                    pass
                            
                            # Store current CPU time
                            with open(cache_file, 'w') as f:
                                f.write(str(total_time))
                except (OSError, IOError, ProcessLookupError):
                    pass
            
            if not cpu_active:
                return False, "no CPU activity"
            
            # CPU is active - now check if Hermes is making progress
            # Use state.db mtime as the real activity indicator
            # (Hermes updates this on each message processed)
            if self.state_db.exists():
                state_age = time.time() - self.state_db.stat().st_mtime
                if state_age < self.timeout:
                    # state.db is recent - Hermes is making progress
                    return True, "CPU + state.db"
                else:
                    # CPU active but state.db stale - Hermes is stuck!
                    return False, f"stuck (state.db {int(state_age)}s old)"
            else:
                # No state.db - fall back to marker file
                marker_age = time.time() - self.marker_file.stat().st_mtime
                if marker_age < self.timeout:
                    return True, "CPU + marker"
                else:
                    return False, f"stuck (marker {int(marker_age)}s old)"
                
        except Exception as e:
            return False, f"error: {e}"
    
    def get_last_update(self) -> datetime:
        """Get last modification time of marker file."""
        try:
            mtime = self.marker_file.stat().st_mtime
            return datetime.fromtimestamp(mtime)
        except Exception:
            return datetime.now() - timedelta(hours=1)
    
    def _is_user_typing(self) -> bool:
        """Check if user is actively typing in the terminal.
        
        Detects recent keyboard activity by checking:
        1. If there's a /dev/input/by-path/*-event-kbd device with recent activity
        2. If the Hermes terminal has recent activity (TTY stat)
        
        Returns True if user has typed something in the last 10 seconds.
        """
        try:
            # Method 1: Check keyboard device activity (requires permissions)
            import glob
            kbd_devices = glob.glob("/dev/input/by-path/*-event-kbd")
            if kbd_devices:
                for dev in kbd_devices[:3]:
                    try:
                        stat = os.stat(dev)
                        age = time.time() - stat.st_atime
                        if age < 10:
                            return True
                    except (OSError, PermissionError):
                        pass
            
            # Method 2: Check Hermes terminal TTY activity
            result = subprocess.run(
                ["pgrep", "-f", "hermes"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                pids = result.stdout.strip().split("\n")
                for pid in pids[:3]:
                    if pid:
                        try:
                            tty_result = subprocess.run(
                                ["ps", "-o", "tty=", "-p", pid],
                                capture_output=True, text=True, timeout=5
                            )
                            if tty_result.returncode == 0:
                                tty = tty_result.stdout.strip()
                                if tty and tty != "?" and tty.startswith("pts/"):
                                    tty_dev = f"/dev/{tty}"
                                    if os.path.exists(tty_dev):
                                        stat = os.stat(tty_dev)
                                        age = time.time() - stat.st_atime
                                        if age < 10:
                                            return True
                        except (OSError, subprocess.TimeoutExpired):
                            pass
        except Exception:
            pass
        
        return False
    
    def _find_terminal_windows(self) -> list[str]:
        """Find all terminal windows that could be running Hermes.
        
        Returns a list of window IDs to try sending to.
        We send to ALL terminal windows because we can't reliably map
        TTY to X11 window in gnome-terminal.
        """
        windows = []
        try:
            # Find all gnome-terminal windows
            gt_result = subprocess.run(
                ["xdotool", "search", "--class", "gnome-terminal"],
                capture_output=True, text=True, timeout=5
            )
            if gt_result.returncode == 0:
                windows = [w for w in gt_result.stdout.strip().split("\n") if w]
                if windows:
                    self.log(f"Found {len(windows)} terminal window(s)")
                    return windows
                            
        except Exception as e:
            self.log(f"Window search error: {e}")
        
        return windows
    
    def send_continue_signal(self) -> bool:
        """Send message via xdotool keyboard injection.
        
        Uses xdotool to synthesize keyboard events that prompt_toolkit
        will receive as real input. This is the only reliable method
        for injecting text into prompt_toolkit-based applications.
        
        Sends to ALL terminal windows to ensure Hermes receives the message.
        """
        # Note: _is_user_typing() disabled - TTY access time is unreliable
        # if self._is_user_typing():
        #     self.log("User is typing - skipping message")
        #     return False
        
        try:
            windows = self._find_terminal_windows()
            if not windows:
                self.log("Could not find any terminal windows")
                return False
            
            success = False
            for win_id in windows:
                # Focus the window first (required for xdotool type to work)
                subprocess.run(
                    ["xdotool", "windowfocus", "--sync", win_id],
                    capture_output=True, text=True, timeout=2
                )
                time.sleep(0.05)
                
                # Type the message (xdotool type handles spaces and special chars)
                type_result = subprocess.run(
                    ["xdotool", "type", self.message],
                    capture_output=True, text=True, timeout=10
                )
                
                if type_result.returncode != 0:
                    continue
                
                # Small delay before pressing Enter
                time.sleep(0.05)
                
                # Press Enter to submit
                key_result = subprocess.run(
                    ["xdotool", "key", "Return"],
                    capture_output=True, text=True, timeout=5
                )
                
                if key_result.returncode == 0:
                    self.log(f"Sent '{self.message}' to window {win_id}")
                    success = True
                else:
                    self.log(f"Failed to send to window {win_id}")
            
            return success
                
        except subprocess.TimeoutExpired:
            self.log("xdotool timeout")
        except FileNotFoundError:
            self.log("xdotool not found - install with: sudo apt install xdotool")
        except Exception as e:
            self.log(f"xdotool error: {e}")
            
        return False
    
    def send_continue_file(self) -> bool:
        """Write message to input file."""
        if self._is_user_typing():
            self.log("User is typing - skipping message")
            return False
        
        input_file = Path.home() / ".hermes" / "input"
        try:
            input_file.parent.mkdir(parents=True, exist_ok=True)
            with open(input_file, "a") as f:
                f.write(f"{self.message}\n")
            self.log(f"Wrote '{self.message}' to {input_file}")
            return True
        except Exception as e:
            self.log(f"File write failed: {e}")
        return False
    
    def send_continue_api(self) -> bool:
        """Send message via API."""
        try:
            import requests
            resp = requests.post(
                f"{self.api_url}/continue",
                json={"message": self.message},
                timeout=5
            )
            if resp.status_code in [200, 201, 202]:
                self.log(f"Sent '{self.message}' via API")
                return True
        except Exception as e:
            self.log(f"API failed: {e}")
        return False
    
    def send_continue(self):
        """Send message using configured method."""
        self.log("=" * 50)
        self.log(f">>> SENDING: {self.message} <<<")
        self.log("=" * 50)
        
        if self.method == "signal":
            self.send_continue_signal()
        elif self.method == "file":
            self.send_continue_file()
        elif self.method == "api":
            self.send_continue_api()
    
    def run(self):
        """Main watchdog loop."""
        self.log("=" * 50)
        self.log("Hermes Always On - Watchdog Started")
        self.log(f"Timeout: {self.timeout}s ({self.timeout // 60} min)")
        self.log(f"Check interval: {self.interval}s")
        self.log(f"Method: {self.method}")
        self.log(f"Message: '{self.message}'")
        self.log(f"Marker: {self.marker_file}")
        self.log("Press Ctrl+C to stop")
        self.log("=" * 50)
        
        while self.running:
            # First check if Hermes is actively working (CPU activity + marker updates)
            hermes_active, active_reason = self._is_hermes_active()
            
            last_update = self.get_last_update()
            age = datetime.now() - last_update
            age_seconds = int(age.total_seconds())
            
            if hermes_active:
                status = f"ACTIVE ({active_reason})"
                # Don't send message - Hermes is working
                self.log(f"Hermes is active [{status}]")
            elif age_seconds < self.timeout:
                status = "ACTIVE"
                self.log(f"Last update: {age_seconds}s ago [{status}]")
            else:
                status = "STALLED"
                self.log(f"Last update: {age_seconds}s ago [{status}] ({active_reason})")
                self.send_continue()
            
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
                subprocess.run(["tail", "-5", str(log_file)])
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


def main():
    """Main entry point."""
    # Check command line arguments
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--status" or arg == "status":
            check_status()
            return
        elif arg == "--stop" or arg == "stop":
            stop_watchdog()
            return
        elif arg == "--test" or arg == "test":
            # Test mode: send message immediately
            print("=" * 50)
            print("TEST MODE - Sending message immediately")
            print("=" * 50)
            config = get_config()
            watchdog = Watchdog(config)
            success = watchdog.send_continue_signal()
            print(f"\nResult: {'SUCCESS' if success else 'FAILED'}")
            return
        elif arg in ["--help", "-h", "help"]:
            print(__doc__)
            print("\nCommands:")
            print("  python watchdog.py          Run watchdog (Ctrl+C to stop)")
            print("  python watchdog.py --test   Send message immediately (test mode)")
            print("  python watchdog.py --status Check if running")
            print("  python watchdog.py --stop   Stop running instance")
            return
    
    # Run the watchdog
    config = get_config()
    watchdog = Watchdog(config)
    watchdog.run()


if __name__ == "__main__":
    main()
