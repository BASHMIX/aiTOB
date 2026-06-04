#!/usr/bin/env python3
"""
run.py — Master startup script for the AI Tournament Organizer Bot.
Starts the FastAPI backend and Discord Bot with color-coded aggregated logs.
"""
import os
import sys
import json
import signal
import subprocess
import threading

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')

# ── Paths ────────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))

# Detect virtual environment
if sys.platform == "win32":
    PYTHON = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
    if not os.path.exists(PYTHON):
        PYTHON = sys.executable
else:
    PYTHON = os.path.join(ROOT, ".venv", "bin", "python")
    if not os.path.exists(PYTHON):
        PYTHON = sys.executable

PIDS_FILE = os.path.join(ROOT, ".pids.json")

# ── ANSI Colors ───────────────────────────────────────────────────────────
RESET   = "\033[0m"
CYAN    = "\033[96m"
MAGENTA = "\033[95m"
YELLOW  = "\033[93m"
RED     = "\033[91m"
GREEN   = "\033[92m"
BOLD    = "\033[1m"

def cprint(color: str, prefix: str, text: str):
    print(f"{color}{BOLD}[{prefix}]{RESET} {text}", flush=True)

# ── Port Cleanup ─────────────────────────────────────────────────────────
def kill_port(port: int):
    """Kill any process occupying the given port."""
    try:
        import psutil
    except ImportError:
        cprint(RED, "SYS", "psutil not installed — skipping port cleanup")
        return

    for proc in psutil.process_iter(['pid', 'name']):
        try:
            # psutil 6.0 renamed Process.connections() -> Process.net_connections().
            # Try the new name first, fall back to the old one for older psutil.
            try:
                conns = proc.net_connections(kind='inet')
            except (AttributeError, TypeError):
                conns = proc.connections(kind='inet')
            for conn in conns:
                if conn.laddr and conn.laddr.port == port:
                    cprint(YELLOW, "SYS", f"Killing existing process {proc.info['name']} on port {port} (PID {proc.pid})")
                    proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
            pass

# ── Process Logging Thread ────────────────────────────────────────────────
def stream_output(proc: subprocess.Popen, prefix: str, color: str):
    """Stream subprocess stdout to the terminal with a color prefix."""
    for line in iter(proc.stdout.readline, b''):
        text = line.decode("utf-8", errors="replace").rstrip()
        if text:
            cprint(color, prefix, text)

# ── Services ──────────────────────────────────────────────────────────────
SERVICES = [
    {
        "name": "API",
        "color": CYAN,
        "cmd": [PYTHON, "-m", "uvicorn", "backend.api.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
    },
    {
        "name": "BOT",
        "color": MAGENTA,
        "cmd": [PYTHON, "backend/bot/main.py"],
    },
    {
        "name": "VITE",
        "color": YELLOW,
        "cmd": ["npm.cmd", "run", "dev"] if sys.platform == "win32" else ["npm", "run", "dev"],
        "cwd": os.path.join(ROOT, "frontend-react"),
    },
]

processes: list[subprocess.Popen] = []

def shutdown():
    """Gracefully stop all child processes."""
    cprint(YELLOW, "SYS", "Shutting down all services…")
    try:
        import psutil
        for proc in processes:
            try:
                parent = psutil.Process(proc.pid)
                children = parent.children(recursive=True)
                for child in children:
                    try:
                        child.terminate()
                    except Exception:
                        pass
                parent.terminate()
                try:
                    parent.wait(timeout=5)
                except psutil.TimeoutExpired:
                    parent.kill()
                for child in children:
                    try:
                        child.kill()
                    except Exception:
                        pass
            except (psutil.NoSuchProcess, Exception):
                pass
    except ImportError:
        for proc in processes:
            try:
                proc.terminate()
            except Exception:
                pass

    if os.path.exists(PIDS_FILE):
        os.remove(PIDS_FILE)
    cprint(GREEN, "SYS", "All services stopped. Goodbye!")

def signal_handler(sig, frame):
    shutdown()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# ── Main ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Lightweight flag parsing — keep the script dependency-free.
    no_frontend = "--no-frontend" in sys.argv

    cprint(GREEN, "SYS", "Starting AI Tournament Organizer…")
    cprint(GREEN, "SYS", f"Python: {PYTHON}")
    cprint(GREEN, "SYS", f"Root:   {ROOT}")
    if no_frontend:
        cprint(YELLOW, "SYS", "Frontend (VITE) disabled via --no-frontend")
    print()

    # Select services (optionally skipping the React dev server).
    services = [s for s in SERVICES if not (no_frontend and s["name"] == "VITE")]

    # Free the ports we're about to bind.
    kill_port(8000)
    if not no_frontend:
        kill_port(5173)

    pids = {}
    threads = []

    for svc in services:
        cprint(svc["color"], svc["name"], f"Starting: {' '.join(svc['cmd'][-2:])}")
        try:
            proc = subprocess.Popen(
                svc["cmd"],
                cwd=svc.get("cwd", ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
            )
            processes.append(proc)
            pids[svc["name"]] = proc.pid
            t = threading.Thread(
                target=stream_output,
                args=(proc, svc["name"], svc["color"]),
                daemon=True
            )
            t.start()
            threads.append(t)
        except FileNotFoundError as e:
            cprint(RED, svc["name"], f"Failed to start: {e}")

    # Save PIDs
    with open(PIDS_FILE, "w") as f:
        json.dump(pids, f)

    cprint(GREEN, "SYS", "All services started. PIDs saved to .pids.json")
    cprint(GREEN, "SYS", "Admin Hub  -> http://localhost:8000/admin/hub")
    cprint(GREEN, "SYS", "Editor     -> http://localhost:8000/admin/editor")
    cprint(GREEN, "SYS", "OBS        -> http://localhost:8000/obs")
    cprint(YELLOW, "SYS", "Press Ctrl+C to stop all services.")
    print()

    # Wait for all processes to finish (keeps main thread alive)
    for proc in processes:
        proc.wait()
