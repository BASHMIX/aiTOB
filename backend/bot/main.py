import discord
from discord.ext import commands, tasks
import os
import httpx
from dotenv import load_dotenv
import asyncio
from langchain_core.tools import tool

import sys
# Add project root and backend to sys.path
root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(root)
sys.path.append(os.path.join(root, "backend"))
from core.database import init_db, create_or_update_player, get_player
from core.image_utils import process_avatar
from bot.registration import registration_manager
from bot.messages import get_msg
from bot.agent.graph import app, process_message
from bot.agent.hub_agent import build_hub_agent

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
# Note: Other values will be fetched dynamically from the DB via get_connection or the API_BASE_URL env fallback.
API_BASE_URL_ENV = os.getenv("API_BASE_URL", "http://localhost:8000")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await init_db()
    print(f"✅ Bot is online and connected to Discord as {bot.user}")
    from core.database import add_bot_feed
    await add_bot_feed(f"Bot online and connected to Discord as {bot.user.name}", "info")
    if not poll_hub_commands.is_running():
        poll_hub_commands.start()
    if not update_heartbeat.is_running():
        update_heartbeat.start()

    print('------')

@tasks.loop(seconds=10.0)
async def update_heartbeat():
    from core.database import set_setting
    import datetime
    await set_setting("bot_last_seen", datetime.datetime.now().isoformat())

class RegistrationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Register", style=discord.ButtonStyle.primary, custom_id="register_button")
    async def register_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from core.database import get_connection
        discord_id = str(interaction.user.id)
        
        # Check if already registered
        player = await get_player(discord_id)
        if player and player.get("is_verified"):
            await interaction.response.send_message(get_msg("profile_update", player.get("preferred_language", "en")), ephemeral=True)
            return

        # Initialize registration state
        await create_or_update_player(discord_id, registration_step="startgg_linked")
        
        api_base = await get_connection("API_BASE_URL", API_BASE_URL_ENV)
        login_url = f"{api_base}/api/players/login?discord_id={discord_id}"
        
        try:
            embed = discord.Embed(
                title="Tournament Registration",
                description=get_msg("welcome", "en") + "\n\n" + get_msg("startgg_prompt", "en"),
                color=discord.Color.blue()
            )
            await interaction.user.send(embed=embed)
            await interaction.user.send(login_url)
            await interaction.response.send_message("Check your DMs!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("I couldn't send you a DM. Please check your privacy settings.", ephemeral=True)

@bot.command()
async def setup_registration(ctx):
    """Sets up the registration button in the current channel."""
    from core.database import get_setting
    welcome_msg = await get_setting("registration_msg", "Welcome to the AI Tournament Organizer! Click the button below to register.")
    view = RegistrationView()
    await ctx.send(welcome_msg, view=view)

@bot.command()
async def start_match(ctx, opponent: discord.Member):
    """Starts a match thread between the command caller and the opponent."""
    player1 = ctx.author
    player2 = opponent
    
    if player1 == player2:
        await ctx.send("You cannot start a match with yourself!")
        return

    # Create a thread
    thread = await ctx.channel.create_thread(
        name=f"Match: {player1.display_name} vs {player2.display_name}",
        type=discord.ChannelType.public_thread,
        invitable=False
    )
    
    await thread.add_user(player1)
    await thread.add_user(player2)
    
    # Initialize LangGraph state
    config = {"configurable": {"thread_id": str(thread.id)}}
    initial_state = {
        "set_id": thread.id, 
        "thread_id": thread.id,
        "player1_discord": player1.id,
        "player2_discord": player2.id,
        "player1_ready": False,
        "player2_ready": False,
        "chat_history": [],
        "match_status": "playing",
        "winner_id": None,
        "score_string": None
    }
    
    app.update_state(config, initial_state)
    
    await thread.send(
        f"Match Started! {player1.mention} vs {player2.mention}\n"
        "Please coordinate and play your match. Once finished, report the scores here (e.g., 'I won 2-0'). "
        "The AI Organizer will automatically verify and record the result."
    )
    await ctx.send(f"Match thread created: {thread.mention}")

@bot.command()
async def report(ctx, p1_score: int, p2_score: int):
    """Report match scores in a thread. Usage: !report 2 0"""
    from core.database import get_active_matches, update_active_match, add_bot_feed
    from core.startgg_client import get_client as get_sgg

    if not isinstance(ctx.channel, discord.Thread):
        await ctx.send("This command must be used inside a match thread.")
        return

    thread_id = str(ctx.channel.id)
    all_matches = await get_active_matches()
    match = next((m for m in all_matches if m.get("discord_thread_id") == thread_id), None)
    if not match:
        await ctx.send("No active match found for this thread.")
        return

    set_id = match["set_id"]
    if p1_score == p2_score:
        await ctx.send("Scores cannot be tied. Please report again.")
        return

    winner_key = "p1" if p1_score > p2_score else "p2"
    loser_key = "p2" if winner_key == "p1" else "p1"
    winner_id = match.get(f"{winner_key}_entrant_id")
    if not winner_id:
        await ctx.send("Winner entrant ID not found. Admin must report via the hub.")
        return

    await update_active_match(set_id, p1_score=p1_score, p2_score=p2_score)

    sgg = get_sgg()
    try:
        await sgg.report_set_score_normal(set_id, winner_id, match['p1_entrant_id'], match['p2_entrant_id'], p1_score, p2_score)
    except Exception:
        try:
            await sgg.report_set_winner_only(set_id, winner_id)
        except Exception as e:
            await ctx.send(f"Failed to report to Start.gg: {e}")
            return

    await update_active_match(set_id, status="complete")
    await add_bot_feed(f"📝 Match {set_id} reported via Discord: {p1_score}-{p2_score}", "info")
    await ctx.send(f"✅ Score reported to Start.gg: {p1_score}-{p2_score}")
    await ctx.channel.edit(archived=True, locked=True)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Check if it's a DM
    if isinstance(message.channel, discord.DMChannel):
        await registration_manager.handle_dm(message)
        return

    # Check if it's a Thread
    if isinstance(message.channel, discord.Thread):
        config = {"configurable": {"thread_id": str(message.channel.id)}}
        state_snapshot = app.get_state(config)
        
        if state_snapshot.values:
            current_status = state_snapshot.values.get("match_status")
            
            if current_status not in ["completed", "conflict", "dq"]:
                new_state = await process_message(
                    thread_id=message.channel.id,
                    author_id=message.author.id,
                    author_name=message.author.name,
                    message_content=message.content
                )
                
                if new_state:
                    status = new_state.get("match_status")
                    if status == "completed":
                        winner_id = new_state.get("winner_id")
                        score = new_state.get("score_string")
                        await message.channel.send(
                            f"✅ **Match Completed!**\n"
                            f"Winner: <@{winner_id}>\n"
                            f"Score: {score}\n\n"
                            "Locking this thread."
                        )
                        await message.channel.edit(archived=True, locked=True)
                        
                        # Save to DB and report to Start.gg
                        from core.database import save_match_result, update_active_match
                        from core.startgg_client import get_client
                        sgg = get_client()
                        
                        # We need the set_id from the graph state
                        set_id = new_state.get("set_id")
                        if set_id:
                            await save_match_result(
                                set_id=str(set_id),
                                winner_id=str(winner_id),
                                score=score,
                                status="completed"
                            )
                            await update_active_match(str(set_id), status="completed")
                            
                            # Report to Start.gg (optional, maybe based on a setting)
                            try:
                                # We need to translate winner_discord_id to start.gg entrant_id
                                # For now, we'll assume the graph has the entrant_id if we passed it in
                                # But the current schema uses winner_discord_id.
                                # TODO: Implement ID mapping for reporting
                                pass
                            except Exception as e:
                                print(f"Start.gg reporting failed: {e}")

                        # Push to Hub bot-feed
                        try:
                            async with httpx.AsyncClient() as hc:
                                await hc.post(f"{API_BASE_URL}/api/bot-feed", json={
                                    "message": f"Match #{message.channel.id} auto-completed. Winner: <@{winner_id}>, Score: {score}",
                                    "level": "info"
                                })
                        except Exception:
                            pass
                    elif status == "conflict":
                        await message.channel.send(
                            f"⚠️ **Conflict Detected!**\n"
                            "The reported scores do not match or a dispute was found. An Admin has been pinged."
                        )
                        # Push conflict to DB
                        from core.database import add_conflict, update_active_match
                        set_id = new_state.get("set_id")
                        if set_id:
                            # We don't have claims here yet, so we'll just mark it
                            await add_conflict(str(set_id), "AI detected conflict", "AI detected conflict")
                            await update_active_match(str(set_id), status="conflict")

                        # Push conflict to Hub
                        try:
                            async with httpx.AsyncClient() as hc:
                                await hc.post(f"{API_BASE_URL}/api/bot-feed", json={
                                    "message": f"⚠ Conflict in match #{message.channel.id}",
                                    "level": "warn"
                                })
                        except Exception:
                            pass

    await bot.process_commands(message)

# ── Hub Agent Tools & Polling ──────────────────────────────────────────────

@tool
async def get_active_matches_tool():
    """Returns a list of all active or called matches from the database."""
    from core.database import get_active_matches
    matches = await get_active_matches()
    return str(matches)

@tool
async def get_players_tool():
    """Returns a list of all registered players and their Discord IDs."""
    from core.database import aiosqlite, DB_PATH
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT discord_id, startgg_id, gamer_tag, cfn_id FROM players") as c:
            rows = await c.fetchall()
            return str([dict(zip([col[0] for col in c.description], row)) for row in rows])

@tool
async def create_discord_thread_tool(p1_discord_id: str, p2_discord_id: str, match_title: str):
    """Creates a Discord match thread for the two players and starts the match referee."""
    guild = bot.guilds[0]
    channel = discord.utils.get(guild.text_channels, name="tournament") or guild.text_channels[0]
    
    p1 = guild.get_member(int(p1_discord_id))
    p2 = guild.get_member(int(p2_discord_id))
    
    if not p1 or not p2: 
        return f"Failed to find players. P1 exists: {bool(p1)}, P2 exists: {bool(p2)}"
    
    thread = await channel.create_thread(
        name=match_title,
        type=discord.ChannelType.public_thread,
        invitable=False
    )
    await thread.add_user(p1)
    await thread.add_user(p2)
    
    config = {"configurable": {"thread_id": str(thread.id)}}
    initial_state = {
        "set_id": thread.id, 
        "thread_id": thread.id,
        "player1_discord": p1.id,
        "player2_discord": p2.id,
        "player1_ready": False,
        "player2_ready": False,
        "chat_history": [],
        "match_status": "playing",
        "winner_id": None,
        "score_string": None
    }
    app.update_state(config, initial_state)
    
    await thread.send(
        f"Match Started! {p1.mention} vs {p2.mention}\n"
        "Please coordinate and play your match. Once finished, report the scores here (e.g., 'I won 2-1')."
    )
    return f"Successfully created thread {thread.id}."

hub_tools = [get_active_matches_tool, get_players_tool, create_discord_thread_tool]
hub_agent = build_hub_agent(hub_tools)

MATCH_CALL_CHANNEL_ID = os.getenv("MATCH_CALL_CHANNEL_ID", "")

# ── Helper: extract clean text from LangChain response ─────────────────
def extract_text_from_response(content) -> str:
    """
    LangChain models sometimes return content as a list of dicts:
      [{'type': 'text', 'text': 'Success', 'extras': {...}}]
    This extracts only the plain text string.
    """
    if isinstance(content, list):
        # Take the first text block
        for block in content:
            if isinstance(block, dict) and block.get("text"):
                return str(block["text"])
            if isinstance(block, str):
                return block
        # Fallback: stringify the whole thing
        return str(content)
    return str(content)

# ── msg command: send match call to public channel ─────────────────────
async def handle_msg_command(cmd_text: str) -> str:
    """
    Parses 'msg Player1 vs Player2' and sends an Arabic call
    to the configured public Discord channel.
    """
    import re
    # Strip the 'msg' prefix
    body = cmd_text[3:].strip()
    # Split on ' vs ' (case-insensitive)
    parts = re.split(r'\s+vs\s+', body, flags=re.IGNORECASE)
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        return "❌ Invalid format. Use: msg Player1 vs Player2"

    p1 = parts[0].strip()
    p2 = parts[1].strip()

    if not MATCH_CALL_CHANNEL_ID:
        return "❌ MATCH_CALL_CHANNEL_ID not configured in .env"

    channel = bot.get_channel(int(MATCH_CALL_CHANNEL_ID))
    if not channel:
        return f"❌ Could not find Discord channel with ID {MATCH_CALL_CHANNEL_ID}"

    # Send Arabic match call
    call_msg = f"📢 يرجى من اللاعبين **{p1}** و **{p2}** تأكيد الحضور للمباراة الخاصة بكم الآن."
    await channel.send(call_msg)

    return f"✅ Message sent to the public channel for {p1} and {p2}."


@tasks.loop(seconds=3.0)
async def poll_hub_commands():
    from core.database import get_pending_hub_commands, update_hub_command_status, add_bot_feed
    from langchain_core.messages import HumanMessage
    
    cmds = await get_pending_hub_commands()
    for cmd in cmds:
        cmd_id = cmd['id']
        cmd_text = cmd['command_text']
        
        await update_hub_command_status(cmd_id, 'processing')
        
        try:
            # Check for built-in commands first
            if cmd_text.strip().lower().startswith("msg "):
                result_text = await handle_msg_command(cmd_text.strip())
                await add_bot_feed(f"🤖 {result_text}", "success")
                await update_hub_command_status(cmd_id, 'done')
                continue

            if cmd_text.strip().lower().startswith("announce "):
                msg_to_send = cmd_text[9:].strip()
                if MATCH_CALL_CHANNEL_ID:
                    channel = bot.get_channel(int(MATCH_CALL_CHANNEL_ID))
                    if channel:
                        await channel.send(msg_to_send)
                        await add_bot_feed(f"📢 Announced to Discord: {msg_to_send}", "success")
                        await update_hub_command_status(cmd_id, 'done')
                        continue
                await add_bot_feed("❌ Failed to announce: MATCH_CALL_CHANNEL_ID not set or channel not found", "error")
                await update_hub_command_status(cmd_id, 'failed')
                continue

            if cmd_text.strip().lower().startswith("call_match "):
                set_id = cmd_text.split(" ")[1].strip()
                from core.database import get_active_match, get_tournament
                match = await get_active_match(set_id)
                if match:
                    t = await get_tournament(match['tournament_slug'])
                    from bot.match_threads import create_match_thread
                    await create_match_thread(bot, t, match)
                    await add_bot_feed(f"🤖 Created match thread for {match.get('p1_name')} vs {match.get('p2_name')}", "success")
                else:
                    await add_bot_feed(f"❌ call_match failed: Match {set_id} not found", "error")
                await update_hub_command_status(cmd_id, 'done')
                continue

            # Run the agent for all other commands
            from core.database import get_setting
            custom_prompt = await get_setting("bot_system_prompt")
            
            config = {"configurable": {"thread_id": f"hub_{cmd_id}"}}
            # If custom prompt exists, we inject it as a HumanMessage before the command to guide the agent
            # or we could recreate the agent. For now, let's just pass the message.
            messages = [HumanMessage(content=cmd_text)]
            if custom_prompt:
                messages.insert(0, HumanMessage(content=f"INSTRUCTION: {custom_prompt}"))
            
            response = await hub_agent.ainvoke({"messages": messages}, config)
            
            # Extract clean text from the response (fixes raw JSON bug)
            raw_content = response["messages"][-1].content
            ai_msg = extract_text_from_response(raw_content)
            
            await add_bot_feed(f"🤖 Hub Agent: {ai_msg}", "success")
            await update_hub_command_status(cmd_id, 'done')
        except Exception as e:
            print(f"Hub Agent error: {e}")
            await add_bot_feed(f"❌ Hub Agent Error: {str(e)}", "error")
            await update_hub_command_status(cmd_id, 'failed')

if __name__ == "__main__":
    if TOKEN and TOKEN != "your_discord_bot_token_here":
        bot.run(TOKEN)
    else:
        print("Warning: DISCORD_BOT_TOKEN not found or is default. Please update .env")

