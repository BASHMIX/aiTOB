# Role
You are an Expert Full-Stack Developer specializing in Python (FastAPI), WebSockets, React/Vanilla JS, and Esports Broadcast Overlays (OBS).

# Task
Build Phase 3 of the AI Tournament Organizer. Replace the local AHK script idea with a Real-Time Web Dashboard for the Tournament Organizer (TO) and an Overlay for OBS Studio.

# Core Architecture
1. **Backend:** Use `FastAPI` to serve the web pages and handle API requests. Implement WebSockets for real-time UI updates without page reloads.
2. **Views (Routes):**
   - `/admin`: The Control Panel for the TO.
   - `/overlay`: The OBS Browser Source screen (must have a transparent background).

# Requirements

## 1. Start.gg Data Integration
Create new GraphQL queries to fetch detailed tournament data:
- Tournament Name & Event Name.
- Total number of sets/matches.
- Current Round (e.g., "Winners Semi-Final", "Grand Final").
- Player Details: Team Prefix (Sponsor), Player Name, Country/Region code (for flags), and current score.
- Final Standings (fetch from the phase standings when the tournament ends).

## 2. Admin Dashboard (`/admin`)
Build a UI that displays:
- **Tournament Overview:** Title, current progress, total matches.
- **Current Match:** e.g., "[Team1] Gamer1 VS [Team2] Gamer2".
- **Next Match:** e.g., "Gamer3 VS [Winner of Current Match]".
- **Action Button: "Call Next Match Players"**. 
  - *Logic:* Clicking this button sends a request to the LangGraph AI Agent (from Phase 2) to ping Gamer1 and Gamer2 in Discord, telling them to join the stream lobby.
- **Manual Score Override:** Simple input fields to manually update the score on the OBS overlay before pushing it to Start.gg.
- **Standings View:** A table showing the final placements of the tournament.

## 3. OBS Overlay (`/overlay`)
Build a clean, broadcast-ready UI that automatically updates via WebSockets when the Admin changes data:
- **Background:** `background-color: transparent;`
- **Player Cards (Left & Right):** Shows Country Flag (using country code), Team Prefix, Player Name, and current Match Score.
- **Top Bar:** Shows Tournament Name and Current Round (e.g., "Street Fighter 6 Main Event - Top 8").
- **Animations:** Simple CSS transitions when a player's score increases or when names change.

# Constraints
- Use WebSockets to ensure that when the Admin updates the score or loads the next match, the OBS `/overlay` updates instantly.
- Expose an API endpoint in FastAPI (e.g., `POST /trigger_agent`) that the Admin dashboard calls when the "Call Next Match" button is clicked. This will wake up the LangGraph workflow.