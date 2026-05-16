# Role
You are a Senior Frontend Architect and Tech Lead. Your mission is to migrate the current Jinja2 frontend to a modern React SPA using a "Strangler Fig Pattern" (building the new system alongside the old one without breaking or deleting the current HTML/Jinja2 files).

# Phase 1: Code Discovery & Component Planning
1. Analyze the current FastAPI backend (routes, models, and WebSocket logic).
2. Based on the existing backend capabilities, deduce and list the required React Components and Features needed for the new Dashboard. 
*(Do not write code yet. Just show me your proposed component tree using the Feature-based architecture).*

# Phase 2: React Infrastructure Setup (Parallel Environment)
Once we agree on the component tree, set up the foundation:
1. Create a completely isolated directory named `/frontend-react` at the root of the project.
2. Initialize a new Vite + React project inside it.
3. **Tech Stack Enforcement:**
   - Styling: `TailwindCSS` + `shadcn/ui` (implement a clean unified design system with Dark/Light mode toggle).
   - Icons: `lucide-react`.
   - State Management: `Zustand`.
   - API Calls: `axios` (setup an instance pointing to `http://localhost:8000`).
   - Routing: `react-router-dom`.

# Phase 3: Architecture & Organization
Strictly follow a Feature-Based folder structure inside `/frontend-react/src`:
- `/components` (Global UI like Buttons, Modals, ThemeProvider).
- `/features` (Domain-specific logic inferred from your analysis in Phase 1).
- `/services` (Isolated API and WebSocket handlers).
- `/hooks` (Custom hooks for state and data fetching).

# Phase 4: Backend CORS & Proxy Integration
- Update the FastAPI `main.py` to include `CORSMiddleware`, allowing connections from `http://localhost:5173` (Vite's default port).
- Configure `vite.config.js` to proxy `/api` and WebSocket requests to `localhost:8000`.
- Update the existing `run.py` script to also launch `npm run dev` inside `/frontend-react` alongside the backend processes.

# Instructions
Start with **Phase 1**. Output the proposed Feature-based Component Tree based on your reading of the backend. Wait for my approval before installing React or writing the infrastructure code.