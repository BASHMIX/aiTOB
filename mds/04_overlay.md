# Role
You are an Expert Frontend Engineer specializing in Real-time Broadcaster Tools and CSS Engine design.

# Task
Upgrade the current static `overlay.html` into a Dynamic Coordinate-Based System with a WYSIWYG Editor. The system must support Google Fonts integration and real-time WebSocket syncing.

# 1. The State Schema (JSON)
The entire overlay must be driven by a single "OverlayState" object. Example structure:
{
  "background_url": "...",
  "global_font_url": "https://fonts.googleapis.com/css2?family=Cairo:wght@200..1000&display=swap",
  "global_font_family": "'Cairo', sans-serif",
  "elements": {
    "p1_name": { "x": 100, "y": 200, "fontSize": "32px", "color": "#ffffff", "text": "Gamer1", "visible": true },
    "p1_score": { "x": 150, "y": 250, "fontSize": "48px", "color": "#ff0000", "text": "0", "visible": true },
    "tournament_round": { "x": 960, "y": 50, "fontSize": "24px", "color": "#aaaaaa", "text": "Winners Semis", "visible": true }
  }
}

# 2. Admin Editor Interface (`/admin/editor`)
Create a dashboard page that allows me to:
- **Canvas View:** A 1920x1080 workspace where I can see all elements.
- **Drag & Drop:** Use a library (like `interact.js` or `react-rnd`) to move elements on the canvas. Their (X, Y) coordinates should update in the State.
- **Font Settings:**
    - An input field to paste a **Google Fonts URL** (e.g., the Cairo link).
    - An input for the **Font Family name** (e.g., 'Cairo').
    - The editor must dynamically inject this font so I can preview it.
- **Styling Panel:** When an element is selected, show controls to change its Color, Font Size, and visibility.
- **Manual Override:** Inputs to manually change the text (Player names, Team, etc.).
- **Sync Button:** A button (or auto-sync) to send the current state JSON to the Backend via WebSockets.

# 3. OBS Overlay View (`/obs`)
Create a clean HTML/JS page for OBS:
- **Zero Configuration:** This page only listens to the WebSocket.
- **Dynamic Font Injection:** When a `global_font_url` is received in the JSON, the page must:
    - Check if a `<link>` with this ID exists; if not, create it and append it to `<head>`.
    - Apply the `global_font_family` to the body or specific elements.
- **Absolute Rendering:** Render all elements as `div` or `span` with `position: absolute`, using the (X, Y) from the JSON.
- **Smooth Transitions:** Use CSS `transition: all 0.3s ease;` so that when coordinates or scores change, they "slide" or "fade" into place instead of flickering.

# 4. Backend (FastAPI + WebSockets)
- Create a WebSocket endpoint `/ws/overlay`.
- **Broadcaster logic:** Any state update sent from the `/admin/editor` must be broadcasted to all connected `/obs` clients.
- **Persistence:** Save the current OverlayState (JSON) to a local file (`overlay_config.json`) so it persists even if the server restarts.

# Instructions
Start by implementing the State Schema and the logic to dynamically inject Google Fonts into the head of the document. Then, build the Draggable Editor.