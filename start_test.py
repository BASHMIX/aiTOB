#!/usr/bin/env python3
"""start_test.py — E2E testing wrapper for the AI Tournament Organizer.

Start / stop / restart the whole stack (API + Bot + optional frontend) in one
command, and reset player state between runs so you can re-test the bio-code
verification + broadcast-avatar flows without rebuilding a tournament.

The actual concurrent launch is delegated to run.py (single source of truth);
this script only adds lifecycle control and the DB reset recipes.

Usage:
  python start_test.py start                 # launch the stack
  python start_test.py stop                  # kill the stack, free ports
  python start_test.py restart               # stop -> start
  python start_test.py reset                 # stop -> soft-reset players -> start
  python start_test.py reset-db              # reset the DB only (no start/stop)

Common flags:
  --no-frontend            Skip the React dev server (Hub is FastAPI-served).
  --players "id1,id2"      Scope the reset to specific Discord IDs (default: all).
  --wipe                   DELETE player rows + pending codes (full new-player test)
                           instead of the soft reset.
  --matches                Also clear local hub tracking (active_matches +
                           planned_streams).
  --yes                    Skip the confirmation prompt for destructive ops.
"""
import os
import sys
import json
import sqlite3
import argparse
import subprocess

# ── Paths ────────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
RUN_PY = os.path.join(ROOT, "run.py")
PIDS_FILE = os.path.join(ROOT, ".pids.json")

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

if sys.platform == "win32":
    PYTHON = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
else:
    PYTHON = os.path.join(ROOT, ".venv", "bin", "python")
if not os.path.exists(PYTHON):
    PYTHON = sys.executable

# Resolve the SQLite path the app uses (honor DB_PATH; relative => under ROOT).
_db_env = os.getenv("DB_PATH", os.path.join("backend", "core", "database.sqlite"))
DB_PATH = _db_env if os.path.isabs(_db_env) else os.path.join(ROOT, _db_env)

PORTS = [8000, 5173]  # API, Vite

# ── Colors ───────────────────────────────────────────────────────────────
RESET, CYAN, MAGENTA, YELLOW, RED, GREEN, BOLD = (
    "\033[0m", "\033[96m", "\033[95m", "\033[93m", "\033[91m", "\033[92m", "\033[1m"
)


def cprint(color: str, prefix: str, text: str):
    print(f"{color}{BOLD}[{prefix}]{RESET} {text}", flush=True)


# ── Stop / port cleanup ──────────────────────────────────────────────────
def _kill_tree(pid: int):
    try:
        import psutil
    except ImportError:
        return
    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return
    children = parent.children(recursive=True)
    for c in children:
        try:
            c.terminate()
        except Exception:
            pass
    try:
        parent.terminate()
    except Exception:
        pass
    _gone, alive = psutil.wait_procs([parent] + children, timeout=5)
    for p in alive:
        try:
            p.kill()
        except Exception:
            pass


def _free_ports(ports):
    try:
        import psutil
    except ImportError:
        cprint(RED, "SYS", "psutil not installed — skipping port cleanup")
        return
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            try:
                conns = proc.net_connections(kind="inet")
            except (AttributeError, TypeError):
                conns = proc.connections(kind="inet")
            for conn in conns:
                if conn.laddr and conn.laddr.port in ports:
                    cprint(YELLOW, "SYS", f"Freeing port {conn.laddr.port} — killing {proc.info['name']} (PID {proc.pid})")
                    proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
            pass


def stop():
    """Terminate everything from .pids.json (and their children), then free ports."""
    killed = 0
    if os.path.exists(PIDS_FILE):
        try:
            with open(PIDS_FILE) as f:
                pids = json.load(f)
            for name, pid in pids.items():
                cprint(YELLOW, "SYS", f"Stopping {name} (PID {pid})…")
                _kill_tree(int(pid))
                killed += 1
        except Exception as e:
            cprint(RED, "SYS", f"Could not read {PIDS_FILE}: {e}")
        try:
            os.remove(PIDS_FILE)
        except OSError:
            pass
    # Belt-and-suspenders: free the well-known ports even if no PID file existed.
    _free_ports(PORTS)
    cprint(GREEN, "SYS", f"Stopped {killed} tracked service(s); ports freed.")


# ── DB reset ─────────────────────────────────────────────────────────────
def _player_filter(player_ids):
    """Return (where_sql, params) for an optional discord_id IN (...) filter."""
    if not player_ids:
        return "", []
    placeholders = ",".join("?" for _ in player_ids)
    return f" WHERE discord_id IN ({placeholders})", list(player_ids)


def reset_db(player_ids=None, wipe=False, matches=False, assume_yes=False):
    """Reset player (and optionally match) state for a fresh test loop."""
    if not os.path.exists(DB_PATH):
        cprint(YELLOW, "SYS", f"No DB at {DB_PATH} — nothing to reset (it'll be created on next start).")
        return

    scope = f"players {player_ids}" if player_ids else "ALL players"
    actions = []
    if wipe:
        actions.append(f"DELETE {scope} + their pending verification codes")
    else:
        actions.append(f"SOFT-RESET {scope} (avatar=NULL, is_verified=0, step=avatar_upload)")
    if matches:
        actions.append("DELETE all active_matches + planned_streams")

    destructive = wipe or matches
    cprint(CYAN, "DB", f"Target: {DB_PATH}")
    for a in actions:
        cprint(CYAN, "DB", f"  • {a}")
    if destructive and not assume_yes:
        resp = input("This deletes rows. Continue? [y/N] ").strip().lower()
        if resp not in ("y", "yes"):
            cprint(YELLOW, "DB", "Aborted — no changes made.")
            return

    where, params = _player_filter(player_ids)
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        if wipe:
            cur.execute(f"DELETE FROM players{where}", params)
            cprint(GREEN, "DB", f"Deleted {cur.rowcount} player row(s).")
            # pending_verifications keys on discord_id too.
            try:
                cur.execute(f"DELETE FROM pending_verifications{where}", params)
                cprint(GREEN, "DB", f"Deleted {cur.rowcount} pending verification(s).")
            except sqlite3.OperationalError:
                pass
        else:
            cur.execute(
                "UPDATE players SET avatar_path=NULL, is_verified=0, "
                f"registration_step='avatar_upload'{where}",
                params,
            )
            cprint(GREEN, "DB", f"Soft-reset {cur.rowcount} player row(s).")

        if matches:
            cur.execute("DELETE FROM active_matches")
            cprint(GREEN, "DB", f"Cleared {cur.rowcount} active match(es).")
            try:
                cur.execute("DELETE FROM planned_streams")
                cprint(GREEN, "DB", f"Cleared {cur.rowcount} planned stream(s).")
            except sqlite3.OperationalError:
                pass

        conn.commit()
    finally:
        conn.close()
    cprint(GREEN, "DB", "Reset complete.")


# ── Start ────────────────────────────────────────────────────────────────
def start(no_frontend=False):
    """Launch the stack via run.py in the foreground (color logs + Ctrl+C)."""
    cmd = [PYTHON, RUN_PY]
    if no_frontend:
        cmd.append("--no-frontend")
    cprint(GREEN, "SYS", f"Launching: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, cwd=ROOT)
    except KeyboardInterrupt:
        # run.py installs its own SIGINT handler; this is just a clean exit here.
        pass


# ── CLI ──────────────────────────────────────────────────────────────────
def _add_common(p, with_reset=False):
    p.add_argument("--no-frontend", action="store_true", help="Skip the React dev server.")
    if with_reset:
        p.add_argument("--players", default="", help="Comma-separated Discord IDs to scope the reset.")
        p.add_argument("--wipe", action="store_true", help="Delete players instead of soft reset.")
        p.add_argument("--matches", action="store_true", help="Also clear active_matches + planned_streams.")
        p.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")


def _ids(arg: str):
    return [s.strip() for s in arg.split(",") if s.strip()]


def main():
    parser = argparse.ArgumentParser(description="E2E testing wrapper for the stack.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    _add_common(sub.add_parser("start", help="Launch the stack."))
    sub.add_parser("stop", help="Stop the stack and free ports.")
    _add_common(sub.add_parser("restart", help="Stop then start."))
    _add_common(sub.add_parser("reset", help="Stop, reset player state, then start."), with_reset=True)
    _add_common(sub.add_parser("reset-db", help="Reset the DB only (no start/stop)."), with_reset=True)

    args = parser.parse_args()

    if args.cmd == "start":
        start(args.no_frontend)
    elif args.cmd == "stop":
        stop()
    elif args.cmd == "restart":
        stop()
        start(args.no_frontend)
    elif args.cmd == "reset":
        stop()
        reset_db(_ids(args.players), args.wipe, args.matches, args.yes)
        start(args.no_frontend)
    elif args.cmd == "reset-db":
        if os.path.exists(PIDS_FILE) and not args.yes:
            cprint(YELLOW, "SYS", "Stack appears to be running (.pids.json present). "
                                  "Stop it first to avoid the bot recreating rows, or pass --yes.")
            return
        reset_db(_ids(args.players), args.wipe, args.matches, args.yes)


if __name__ == "__main__":
    main()
