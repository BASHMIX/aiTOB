# Role
You are a Senior Full-Stack Developer and Architect. You are building an AI Tournament Organizer for Street Fighter 6. 

# Task
Phase 1: Setup the Monorepo structure, the SQLite database, and the Start.gg OAuth 2.0 Authentication system.

# Project Structure
Create the following directory structure:
/root
  /backend
    /core           # Database and Shared Logic
    /api            # FastAPI server (OAuth & Dashboard API)
    /bot            # Discord Bot logic
    /assets         # To store processed avatars (500x500)
  /frontend         # (Placeholder for now)
  .env              # Environment variables

# Requirements for Phase 1:

1. **Database (SQLite + aiosqlite):**
   - Create a `players` table: `discord_id` (PK), `startgg_id`, `gamer_tag`, `cfn_id`, `country`, `team`, `avatar_path`, `is_verified` (bool).

2. **FastAPI Server (The OAuth Gateway):**
   - Read Start.gg Client ID and Secret from `AiBotStart.ggApiToken.txt` or `.env`.
   - Implement `GET /login`: Redirects user to Start.gg OAuth page.
   - Implement `GET /callback`: 
     - Receives the code from Start.gg.
     - Exchanges it for an Access Token.
     - Fetches the user's Profile (ID and Tag) from Start.gg API.
     - Updates/Creates the player record in SQLite.
     - Redirects the user to a "Success" page or sends a message to Discord.

3. **Discord Bot (The Onboarding):**
   - Use `discord.py`.
   - Create a command or button in a specific channel named "Registration".
   - When clicked, it sends a DM to the user with their unique `/login` link for Start.gg OAuth.
   - Once the user completes OAuth, the bot should detect the update and ask the user (in DM) to provide their **CFN ID** and **Upload their Avatar**.

4. **Image Processing Skill:**
   - Use `Pillow`. Create a utility function to:
     - Accept an image from Discord.
     - Center-crop it to a square.
     - Resize it to exactly 500x500 pixels.
     - Save it as `backend/assets/avatars/{startgg_id}.png`.

# Instructions
- Use `python-dotenv` for configuration.
- Use `httpx` for async API calls to Start.gg.
- Ensure all database operations are asynchronous.
- Write clean, modular code. Start by generating the `.env` template and the `database.py` file.