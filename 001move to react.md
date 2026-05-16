# Role
You are a Senior Frontend Architect and UI Developer specializing in Pixel-Perfect Migrations. Your mission is to migrate the current Jinja2 frontend to a modern React SPA using a "Strangler Fig Pattern" (building the new system alongside the old one without breaking or deleting the current HTML/Jinja2 files).

# Phase 1: Code Discovery & Component Planning
1. Analyze the current FastAPI backend (routes, models, and WebSocket logic).
2. Deeply analyze the existing Jinja2 templates (`/templates`) and CSS files (`/static`). Pay close attention to layouts, exact pixel dimensions, colors, and grid systems.
3. Based on this, list the required React Components and Features needed. 
*(Do not write code yet. Just show me your proposed component tree using the Feature-based architecture).*

# Phase 2: React Infrastructure Setup (Parallel Environment)
Once I approve the component tree, set up the foundation:
1. Create a completely isolated directory named `/frontend-react` at the root.
2. Initialize a new Vite + React project inside it.
3. **Tech Stack & PIXEL-PERFECT Styling Enforcement:**
   - Use `TailwindCSS`. You MUST configure `tailwind.config.js` to include the exact custom colors, fonts, and specific pixel breakpoints used in the legacy CSS.
   - For components, use arbitrary values (e.g., `w-[300px]`, `p-[15px]`) or custom theme extensions if the legacy design relies on exact pixel measurements. The goal is a **1:1 visual clone** of the current Jinja2 UI.
   - You may use `shadcn/ui` for complex interactive behaviors (like Modals or Selects) but override their default styles to exactly match the legacy design.
   - Implement a Dark/Light mode toggle that respects the legacy color palette.
   - State Management: `Zustand`.
   - API Calls: `axios` pointing to `http://localhost:8000`.

# Phase 3: Architecture & Organization
Strictly follow a Feature-Based folder structure inside `/frontend-react/src`:
- `/components` (Global UI).
- `/features` (Domain-specific logic inferred from Phase 1).
- `/services` (Isolated API and WebSocket handlers).
- `/hooks` (Custom hooks).

# Phase 4: Backend CORS & Proxy Integration
- Update FastAPI `main.py` to include `CORSMiddleware`, allowing `http://localhost:5173`.
- Configure `vite.config.js` to proxy `/api` and WebSockets to `localhost:8000`.
- Update `run.py` to also launch `npm run dev` inside `/frontend-react`.

# Instructions
Start with **Phase 1**. Output the proposed Feature-based Component Tree based on your reading of the backend and the legacy UI. Wait for my approval before proceeding to the code.