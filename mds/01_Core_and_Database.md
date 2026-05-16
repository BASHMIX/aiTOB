# Role
You are an Expert Senior Python Backend Developer specializing in `discord.py` (Asynchronous programming), `SQLite`, and complex GraphQL APIs.

# Project Context
We are building an AI Tournament Organizer for a Street Fighter 6 online tournament. 
This is Phase 1: Setting up the project structure, Database, Discord Bot core, and Start.gg API integration.

# Required Tech Stack
- Python 3.10+
- `discord.py` (for the bot)
- `aiosqlite` (Async SQLite database to avoid blocking the Discord event loop)
- `httpx` or `aiohttp` (Async HTTP requests for Start.gg API)
- `python-dotenv` (for loading API keys)

# Task 1: Database Setup (`database.py`)
Create an async SQLite database setup.
- Table name: `players`
- Columns: 
  - `discord_id` (TEXT, Primary Key)
  - `startgg_id` (TEXT, Unique)
  - `startgg_tag` (TEXT)
  - `cfn_id` (TEXT) # Capcom Fighters Network ID for SF6
- Write async helper functions: `register_player()`, `get_player_by_discord()`, `get_player_by_startgg()`.

# Task 2: Start.gg API Wrapper (`startgg_api.py`)
Create an async class `StartGGClient`. Read the `STARTGG_TOKEN` from `.env`.
Implement the following GraphQL operations using `httpx`:
1. `get_ready_matches(tournament_slug: str)`: 
   - Write a GraphQL Query to fetch sets in the tournament where `state: 2` (called/ready to play).
   - Return a list of dictionaries containing: `set_id`, `entrant1_id`, `entrant2_id`.
2. `report_match_result(set_id: int, winner_id: int, score: str)`:
   - Write a GraphQL Mutation using `reportBracketSet`.
3. `mark_set_dq(set_id: int, missing_entrant_id: int)`:
   - Write a GraphQL Mutation to DQ the missing player and advance the other.
*Constraint:* Implement a delay or rate-limit handler (Start.gg allows max 80 requests per 60 seconds).

# Task 3: Discord Bot Core (`main.py` & `/cogs/registration.py`)
1. Setup the basic `discord.py` bot with Slash Commands enabled.
2. Create a slash command: `/link [startgg_id] [cfn_id]`.
   - **Logic:** When a user runs this, the bot fetches their Discord ID, saves the `startgg_id` and `cfn_id` into the SQLite DB using the functions from Task 1.
   - **Response:** "✅ Successfully linked your Start.gg account and SF6 CFN ID."

# Output Requirements
Generate the code for these 3 files. Ensure all code is modular, well-commented, and handles exceptions (like database lock errors or API timeouts).