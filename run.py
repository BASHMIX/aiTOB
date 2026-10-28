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
from urllib.parse import quote, urlsplit, urlunsplit

from dotenv import load_dotenv

# The desktop launcher is the service boundary. Load the ignored local
# development values first (including the integration key), then the explicit
# runtime profile. Child API/Bot processes inherit this single environment.
# Tests that deliberately verify a missing DATABASE_URL set
# ``AITOB_SKIP_ENV_FILES=1`` so dotenv cannot mask the failure.
if os.getenv("AITOB_SKIP_ENV_FILES", "").strip() != "1":
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env.production"), override=True)

domain = os.getenv("DOMAIN", "").strip() or os.getenv("APP_DOMAIN", "").strip()
if domain:
    os.environ.setdefault("DOMAIN", domain)
    os.environ.setdefault("APP_DOMAIN", domain)
    os.environ.setdefault("API_BASE_URL", f"https://{domain}")
    os.environ.setdefault("APP_PUBLIC_URL", f"https://{domain}")
    os.environ.setdefault("FRONTEND_BASE_URL", f"https://{domain}")
    os.environ.setdefault("ALLOWED_ORIGINS", f"https://{domain}")
    os.environ.setdefault("DISCORD_OAUTH_REDIRECT_URI", f"https://{domain}/api/integrations/discord/callback")

runtime_database_name = os.getenv("AITOB_POSTGRES_DB", "").strip()
database_url = os.getenv("DATABASE_URL", "").strip()
if runtime_database_name and database_url.lower().startswith(("postgres://", "postgresql://")):
    parsed_database_url = urlsplit(database_url)
    # Local Docker development keeps the role password in the service-level
    # POSTGRES_PASSWORD variable.  A stale password embedded in an older
    # DATABASE_URL must not silently send the API to an unauthenticated/empty
    # target.  Align only the explicitly selected local Docker endpoint; an
    # externally managed PostgreSQL URL remains untouched.
    service_password = os.getenv("POSTGRES_PASSWORD", "").strip()
    if service_password and parsed_database_url.hostname in {"127.0.0.1", "localhost"} and parsed_database_url.port == 5433:
        host = parsed_database_url.hostname
        parsed_database_url = parsed_database_url._replace(
            netloc=f"aitob:{quote(service_password, safe='')}@{host}:5433"
        )
    os.environ["DATABASE_URL"] = urlunsplit(
        (parsed_database_url.scheme, parsed_database_url.netloc,
         "/" + runtime_database_name, parsed_database_url.query,
         parsed_database_url.fragment)
    )

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
class PortInUseError(RuntimeError):
    """A requested development port is owned by a non-aiTOB process."""


def _is_project_process(proc) -> bool:
    """Return True only when a process is rooted in this checkout.

    Port ownership on Windows may be reported through Docker/WSL relay
    processes. Those are host infrastructure, not stale aiTOB children, and
    terminating them can take PostgreSQL down with the API port.
    """
    project_root = os.path.normcase(os.path.abspath(ROOT))
    locations: list[str] = []
    for getter in (getattr(proc, "cwd", None), getattr(proc, "exe", None)):
        if callable(getter):
            try:
                locations.append(str(getter()))
            except Exception:
                pass
    try:
        command_line = " ".join(str(part) for part in proc.cmdline())
    except Exception:
        command_line = ""
    if project_root in os.path.normcase(command_line):
        return True
    return any(
        project_root in os.path.normcase(os.path.abspath(value))
        for value in locations
        if value
    )


def kill_port(port: int):
    """Terminate stale aiTOB children, but never foreign/system processes."""
    try:
        import psutil
    except ImportError:
        cprint(RED, "SYS", "psutil not installed — skipping port cleanup")
        return

    foreign_owners: set[tuple[int, str]] = set()
    killed_pids: set[int] = set()
    protected_names = {
        "com.docker.backend.exe", "docker desktop.exe", "wslrelay.exe",
        "wslhost.exe", "system", "system idle process",
    }
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            # PID 0 is Windows' System Idle Process. It can appear in a socket
            # scan but is not a process we can or should terminate.
            if proc.pid == 0:
                continue
            # psutil 6.0 renamed Process.connections() -> Process.net_connections().
            # Try the new name first, fall back to the old one for older psutil.
            try:
                conns = proc.net_connections(kind='inet')
            except (AttributeError, TypeError):
                conns = proc.connections(kind='inet')
            for conn in conns:
                if conn.laddr and conn.laddr.port == port and proc.pid not in killed_pids:
                    proc_name = str(proc.info.get('name') or "unknown")
                    if proc_name.lower() in protected_names or not _is_project_process(proc):
                        foreign_owners.add((proc.pid, proc_name))
                        continue
                    cprint(YELLOW, "SYS", f"Killing existing process {proc.info['name']} on port {port} (PID {proc.pid})")
                    proc.kill()
                    killed_pids.add(proc.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
            pass
    if foreign_owners:
        owners = ", ".join(f"{name} (PID {pid})" for pid, name in sorted(foreign_owners))
        raise PortInUseError(
            f"Port {port} is owned by {owners}. Stop the owning service explicitly; "
            "run.py will not terminate Docker, WSL, or unrelated applications."
        )

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
        "cmd": [PYTHON, "-m", "backend.api.uvicorn_runner", "--reload", "--host", "0.0.0.0", "--port", "8000"],
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
    # Validate the source of truth before starting any child. The API, bot and
    # workers must fail together rather than selecting an implicit fallback.
    try:
        from backend.core.storage import require_runtime_database
        require_runtime_database()
    except RuntimeError as exc:
        cprint(RED, "SYS", str(exc))
        sys.exit(2)
    # Lightweight flag parsing — keep the script dependency-free.
    no_frontend = "--no-frontend" in sys.argv
    detached = "--detached" in sys.argv
    # Default to the documented :8000 API while allowing an explicit local
    # alternate port when Compose already owns :8000. Vite receives the same
    # value and proxies API/WebSocket traffic to that process.
    try:
        api_port = int(os.getenv("AITOB_API_PORT", "8000"))
    except ValueError:
        cprint(RED, "SYS", "AITOB_API_PORT must be an integer")
        sys.exit(2)
    if not 1 <= api_port <= 65535:
        cprint(RED, "SYS", "AITOB_API_PORT must be between 1 and 65535")
        sys.exit(2)
    # Local API/Bot traffic must stay on the same process boundary as Vite.
    # Deployments that intentionally use an external Hub URL must opt in
    # explicitly; a stale external value must not produce a 530 on local WS.
    if os.getenv("AITOB_ALLOW_EXTERNAL_API_BASE_URL", "").strip().lower() not in {"1", "true", "yes", "on"}:
        os.environ["API_BASE_URL"] = f"http://127.0.0.1:{api_port}"

    cprint(GREEN, "SYS", "Starting AI Tournament Organizer…")
    cprint(GREEN, "SYS", f"Python: {PYTHON}")
    cprint(GREEN, "SYS", f"Root:   {ROOT}")
    if no_frontend:
        cprint(YELLOW, "SYS", "Frontend (VITE) disabled via --no-frontend")
    if detached:
        cprint(YELLOW, "SYS", "Detached mode: services will keep running after this launcher exits")
    print()

    # Select services (optionally skipping the React dev server).
    services = [s for s in SERVICES if not (no_frontend and s["name"] == "VITE")]

    # Free the ports we're about to bind.
    try:
        kill_port(api_port)
        if not no_frontend:
            kill_port(5173)
    except PortInUseError as exc:
        cprint(RED, "SYS", str(exc))
        sys.exit(3)

    pids = {}
    threads = []

    for svc in services:
        cmd = svc["cmd"]
        # Uvicorn's Windows reload supervisor creates a second process which
        # can outlive a detached launcher. Background desktop runs value a
        # stable lifecycle over hot reload; keep reload for normal `run.py`.
        if svc["name"] == "API":
            cmd = list(cmd)
            if detached:
                cmd = [part for part in cmd if part != "--reload"]
            cmd[cmd.index("--port") + 1] = str(api_port)
        cprint(svc["color"], svc["name"], f"Starting: {' '.join(cmd[-2:])}")
        try:
            popen_args = {
                "cwd": svc.get("cwd", ROOT),
                "env": {
                    **os.environ,
                    "PYTHONUNBUFFERED": "1",
                    "PYTHONIOENCODING": "utf-8",
                    "AITOB_API_PORT": str(api_port),
                },
            }
            if detached:
                # A child writing into the launcher's PIPE dies when the temporary
                # terminal closes. Give it its own process group and discard logs
                # so a local desktop launch remains alive after Codex returns.
                popen_args.update({
                    "stdout": subprocess.DEVNULL,
                    "stderr": subprocess.STDOUT,
                    "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
                })
            else:
                popen_args.update({"stdout": subprocess.PIPE, "stderr": subprocess.STDOUT})
            proc = subprocess.Popen(cmd, **popen_args)
            processes.append(proc)
            pids[svc["name"]] = proc.pid
            if not detached:
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
    cprint(GREEN, "SYS", f"API        -> http://localhost:{api_port}")
    cprint(GREEN, "SYS", "Admin Hub  -> http://localhost:5173/admin/hub")
    cprint(GREEN, "SYS", "Editor     -> http://localhost:5173/admin/editor")
    cprint(GREEN, "SYS", "OBS        -> http://localhost:5173/obs")
    cprint(YELLOW, "SYS", "Press Ctrl+C to stop all services.")
    print()

    if detached:
        cprint(GREEN, "SYS", "Detached launcher complete. Use `python stop.py` to stop services.")
        sys.exit(0)

    # Wait for all processes to finish (keeps main thread alive)
    for proc in processes:
        proc.wait()
