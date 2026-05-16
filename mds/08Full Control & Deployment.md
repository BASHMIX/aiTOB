# Role
You are a Senior DevOps and Full-Stack Architect. Your task is to build a complete execution and deployment ecosystem for this project.

# Task 1: Comprehensive Project Analysis
First, scan the entire codebase to identify:
1. Entry points for: FastAPI (Backend), Discord Bot, and the Frontend framework.
2. Necessary Environment Variables in `.env`.
3. All dependencies required for `requirements.txt` and `package.json`.

# Task 2: Local Management Scripts (`run.py` & `stop.py`)
Create two robust Python scripts:
- **`run.py`**:
    - **Port Management:** Automatically kill any process on ports 8000 and 5173 before startup.
    - **Multi-Service Launch:** Run Backend, Bot, and Frontend concurrently.
    - **Advanced Logs Management:** Aggregate logs from all three services into the terminal. Each line MUST be prefixed and color-coded: `[API]` (Cyan), `[BOT]` (Magenta), `[WEB]` (Yellow).
    - **PID Persistence:** Save all PIDs to `.pids.json`.
- **`stop.py`**:
    - Use `psutil` to gracefully terminate the entire process tree for the PIDs in `.pids.json`.
    - Ensure a "Force Kill" fallback if processes don't exit gracefully.

# Task 3: Production Deployment (Docker)
Create the necessary configuration for a production environment:
- **`Dockerfile`**: A multi-stage build or separate Dockerfiles for Backend and Frontend.
- **`docker-compose.yml`**: 
    - Orchestrate the Backend, Bot, and Frontend.
    - Setup **Volumes** for `assets/avatars` and the SQLite database to ensure data persistence.
    - Include a restart policy (`restart: always`).

# Task 4: Documentation & Metadata
- Generate a `requirements.txt` including all discovered backend dependencies (plus `psutil` and `httpx`).
- Update or create a `.env.template` with all the necessary keys (Start.gg, Discord, etc.).

# Instructions for the Agent:
1. Confirm the paths you've detected for the services first.
2. Provide the code for `run.py` and `stop.py`.
3. Provide the `Dockerfile` and `docker-compose.yml`.
4. Tell me exactly how to run the system in both "Local Mode" and "Docker Mode".