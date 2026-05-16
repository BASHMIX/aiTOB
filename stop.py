#!/usr/bin/env python3
"""
stop.py — Graceful shutdown script for the AI Tournament Organizer Bot.
Reads .pids.json and terminates all service process trees.
"""
import os
import sys
import json
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
PIDS_FILE = os.path.join(ROOT, ".pids.json")

RESET  = "\033[0m"
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
BOLD   = "\033[1m"

def cprint(color, prefix, text):
    print(f"{color}{BOLD}[{prefix}]{RESET} {text}", flush=True)

def stop():
    try:
        import psutil
    except ImportError:
        cprint(RED, "STOP", "psutil not installed. Run: pip install psutil")
        sys.exit(1)

    if not os.path.exists(PIDS_FILE):
        cprint(YELLOW, "STOP", "No .pids.json found — nothing to stop.")
        return

    with open(PIDS_FILE, "r") as f:
        pids = json.load(f)

    if not pids:
        cprint(YELLOW, "STOP", "No PIDs found in .pids.json")
        os.remove(PIDS_FILE)
        return

    for name, pid in pids.items():
        cprint(YELLOW, name, f"Stopping PID {pid}…")
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)

            # Terminate children first
            for child in children:
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass

            # Terminate parent
            try:
                parent.terminate()
            except psutil.NoSuchProcess:
                cprint(YELLOW, name, f"Process {pid} already stopped.")
                continue

            # Wait for graceful exit
            gone, alive = psutil.wait_procs([parent] + children, timeout=5)

            # Force kill anything still alive
            for proc in alive:
                try:
                    cprint(RED, name, f"Force killing PID {proc.pid}")
                    proc.kill()
                except psutil.NoSuchProcess:
                    pass

            cprint(GREEN, name, f"Stopped (PID {pid})")
        except psutil.NoSuchProcess:
            cprint(YELLOW, name, f"PID {pid} not found — already stopped.")
        except Exception as e:
            cprint(RED, name, f"Error stopping PID {pid}: {e}")

    # Clean up PID file
    if os.path.exists(PIDS_FILE):
        os.remove(PIDS_FILE)
        cprint(GREEN, "STOP", "Cleaned up .pids.json")

    cprint(GREEN, "STOP", "All services stopped.")

if __name__ == "__main__":
    stop()
