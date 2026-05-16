# Role
You are a Lead DevOps Engineer. Your goal is to create a seamless "Start and Stop" system for this specific project.

# Task 1: Project Analysis
First, scan the current directory structure to identify:
1. The exact entry point for the FastAPI backend (e.g., `backend/api/main.py`).
2. The exact entry point for the Discord Bot (e.g., `backend/bot/main.py`).
3. The frontend directory and the package manager used (npm/yarn/pnpm).

# Task 2: Create `run.py`
Create a master startup script that:
- **Port Cleanup:** Checks if ports 8000 (API) and 5173 (Frontend) are already in use and kills those processes before starting.
- **Concurrent Startup:** Starts the Backend (using uvicorn), the Discord Bot (using python), and the Frontend (using npm run dev) as background sub-processes.
- **Logging:** Aggregates logs from all three services into the current terminal, prefixing each line with `[API]`, `[BOT]`, or `[WEB]` for easy debugging.
- **PID Persistence:** Saves the PIDs of all started processes into a `.pids.json` file.
- **Auto-stop:** If the user presses Ctrl+C, it should automatically trigger the logic of `stop.py` to ensure no orphaned processes are left running.

# Task 3: Create `stop.py`
Create a shutdown script that:
- Reads the `.pids.json` file.
- Uses the `psutil` library to gracefully terminate the entire process tree (parent and all children) for each saved PID.
- Forces a kill if a process doesn't stop within 5 seconds.
- Deletes the `.pids.json` file after successful cleanup.

# Constraints
- Use `psutil` for cross-platform process management (Windows/Linux/Mac).
- Ensure the scripts use the correct Virtual Environment (`venv`) if it exists in the project.
- Write the scripts in a way that they work regardless of whether the user is in the root directory or inside a subfolder (use absolute paths or smart path detection).

# Instructions
Before writing code, tell me the paths you identified for the API, Bot, and Frontend to confirm you understand the current structure.