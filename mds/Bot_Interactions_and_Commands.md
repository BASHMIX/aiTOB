# Tournament Bot Interactions & Commands Documentation

This document outlines all automated interactions and manual commands for the AI Tournament Organizer bot, covering both the Discord integration and the Tournament Hub Admin panel.

## I. Discord Bot (Player-Facing)

The Discord bot serves as the primary interface for players, handling registration, match coordination, and results reporting.

### 1. Registration Flow (DMs)
When a player clicks the "Register" button in the Discord server:
- **Start.gg Linking:** Bot sends a DM with a unique OAuth link.
- **Language Selection:** Upon verification, the bot asks for the player's preferred language (**Arabic** or **English**).
- **CFN ID Collection:** Player provides their Street Fighter 6 CFN ID.
- **Avatar Upload:** Player uploads an avatar image.
    - *Quality Check:* Ensures image dimensions and clarity are sufficient.
    - *Safety Check (AI):* Scans the image for prohibited content or toxicity.
- **Completion:** Once all steps are valid, the player is registered in the local database and synced with Start.gg.

### 2. Match Management (Threads)
When a match is called or activated by an admin:
- **Thread Creation:** Bot creates a private/public thread for the two players.
- **Referee Logic (LangGraph):** The AI referee monitors the thread.
- **Ready Check:** Players are prompted to confirm they are ready.
- **Score Reporting:** Players report their scores directly in the thread (e.g., "I won 2-1").
- **Auto-Verification:** The AI referee compares reports from both players.
    - **Success:** Match is auto-completed, scores reported to Start.gg, and thread locked.
    - **Conflict:** If scores mismatch, an admin is pinged, and the match is flagged in the Hub.

### 3. Prefix Commands (`!`)
| Command | Description |
| :--- | :--- |
| `!setup_registration` | Posts the registration welcome message and buttons in the current channel. |
| `!start_match @opponent` | Manually creates a match thread and starts the AI referee between the caller and the mentioned user. |

---

## II. Hub Bot & AI Agent (Admin-Facing)

The Hub features an AI Agent that allows admins to manage the tournament using natural language or specific command strings.

### 1. Natural Language Agent
Admins can type free-form requests into the Hub's bot input. The agent has access to the following tools:
- `get_active_matches`: Provides a real-time status of all matches in the current tournament.
- `get_players`: Lists all registered users, their Start.gg IDs, and CFN IDs.
- `create_discord_thread`: Manually opens a Discord thread for any pair of players.

### 2. Explicit Admin Commands
These commands can be typed directly into the Hub bot input for instant execution:
| Command | Action |
| :--- | :--- |
| `msg <P1> vs <P2>` | Sends a formatted Arabic match call (📢) to the public Discord channel. |
| `announce <msg>` | Broadcasts a general announcement to the public Discord channel. |
| `call_match <id>` | (Internal) Triggered by the "Call" UI button; starts the Discord DM/Thread flow. |

---

## III. Automated System Interactions

- **Match Completion Announcements:** Every time a match result is verified or manually sent, the bot posts a "Match Completed" summary to Discord.
- **Bot Feed Integration:** All bot activities (notifying players, API errors, thread creations) are streamed to the "Bot Feed" in the Hub UI.
- **Heartbeat System:** The bot updates a "last seen" timestamp in the database every 10 seconds. The Hub UI uses this to display the live **Discord Status** (Online/Offline).
- **Conflict Notifications:** Any disputes reported in Discord threads are immediately flagged in the Hub with a high-priority "Conflict" status for admin resolution.
