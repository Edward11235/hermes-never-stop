#!/usr/bin/env python3
import os
import subprocess

print("=== TTY Detection Test ===")

# Method 1: os.ttyname
try:
    my_tty = os.ttyname(0)
    print(f"os.ttyname(0): {my_tty}")
except OSError:
    my_tty = None
    print("os.ttyname(0): None (no TTY)")

# Method 2: Check parent's TTY
ppid = os.getppid()
result = subprocess.run(['ps', '-o', 'tty=', '-p', str(ppid)], capture_output=True, text=True)
parent_tty = result.stdout.strip()
print(f"Parent PID {ppid} TTY: {parent_tty}")

# Method 3: Check /proc/self/fd/0
try:
    link = os.readlink('/proc/self/fd/0')
    print(f"/proc/self/fd/0 -> {link}")
except:
    print("/proc/self/fd/0: cannot read")

print(f"\nResult: watchdog_tty = {parent_tty if parent_tty != '?' else my_tty}")
