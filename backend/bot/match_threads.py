import discord
import asyncio
from backend.core.database import get_player, get_active_match, update_active_match, add_bot_feed, get_setting, upsert_active_match
from backend.core.match_state import generate_lobby_password, start_call_timer

async def create_match_thread(bot, tournament, set_data):
    channel_id = await get_setting("match_threads_channel_id")
    if not channel_id:
        for guild in bot.guilds:
            channel = discord.utils.get(guild.text_channels, name="active-matches")
            if channel:
                channel_id = channel.id
                break

    if not channel_id:
        await add_bot_feed("Match thread failed: No 'active-matches' channel found.", "error")
        return

    channel = bot.get_channel(int(channel_id))
    if not channel:
        await add_bot_feed(f"Match thread failed: Channel {channel_id} not found.", "error")
        return

    p1_name = set_data.get('p1_name', 'TBD')
    p2_name = set_data.get('p2_name', 'TBD')
    round_name = set_data.get('round_name', 'Unknown Round')
    set_id = str(set_data.get('set_id') or set_data.get('id'))

    thread_name = f"{round_name}: {p1_name} vs {p2_name}"
    thread = await channel.create_thread(name=thread_name, type=discord.ChannelType.public_thread)

    await update_active_match(set_id, discord_thread_id=str(thread.id), status="called")

    is_stream = set_data.get("is_stream_match", False)
    p1_discord = await get_discord_id_from_startgg(set_data.get('p1_id') or set_data.get('p1_entrant_id'))
    p2_discord = await get_discord_id_from_startgg(set_data.get('p2_id') or set_data.get('p2_entrant_id'))

    mentions = []
    if p1_discord: mentions.append(f"<@{p1_discord}>")
    if p2_discord: mentions.append(f"<@{p2_discord}>")
    content = " ".join(mentions) if mentions else "Players, your match is ready!"

    embed = discord.Embed(
        title=f"Match Ready: {round_name}",
        description=f"**{p1_name}** vs **{p2_name}**\n\nClick **I'm Ready** to check in. You have 10 minutes.",
        color=discord.Color.green()
    )

    view = ReadyCheckView(set_id, p1_discord, p2_discord, is_stream, thread, bot)
    await thread.send(content=content, embed=embed, view=view)

    from backend.core.database import get_tournament
    t = await get_tournament(set_data.get('tournament_slug', ''))
    timeout = (t.get('dq_timer_seconds') or 600) if t else 600
    asyncio.create_task(run_ready_check_timeout(bot, thread, set_id, timeout))

async def get_discord_id_from_startgg(sgg_id: str) -> str | None:
    if not sgg_id:
        return None
    from backend.core.database import aiosqlite, DB_PATH
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT discord_id FROM players WHERE startgg_id = ?", (sgg_id,)) as c:
            row = await c.fetchone()
            return str(row[0]) if row else None

class ReadyCheckView(discord.ui.View):
    def __init__(self, set_id, p1_discord, p2_discord, is_stream, thread, bot):
        super().__init__(timeout=600)
        self.set_id = set_id
        self.ready_players = set()
        self.p1_discord = p1_discord
        self.p2_discord = p2_discord
        self.is_stream = is_stream
        self.thread = thread
        self.bot = bot

    async def on_timeout(self):
        match = await get_active_match(self.set_id)
        if match and match.get("status") == "called":
            await self.thread.send("⏰ Ready check expired. Use the hub to manage this match.")

    @discord.ui.button(label="I'm Ready", style=discord.ButtonStyle.success)
    async def ready_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        self.ready_players.add(user_id)
        player_key = "p1" if user_id == str(self.p1_discord) else "p2"
        await update_active_match(self.set_id, **{f"{player_key}_ready": True})
        await interaction.response.send_message(f"✅ {interaction.user.display_name} is ready!", ephemeral=False)

        match = await get_active_match(self.set_id)
        if match and match.get("p1_ready") and match.get("p2_ready"):
            await update_active_match(self.set_id, started_at=discord.utils.utcnow().isoformat())
            self.stop()

            if self.is_stream:
                lobby = await self._handle_stream_match()
            else:
                lobby = await self._handle_offstream_match()

            if lobby:
                await self.thread.send(f"🚀 Both players ready! {'Lobby password: **' + lobby + '**' if lobby else ''}")
            else:
                await self.thread.send("🚀 Both players ready! GLHF!")

    async def _handle_stream_match(self):
        match = await get_active_match(self.set_id)
        p1_cfn = match.get("p1_cfn") or ""
        p2_cfn = match.get("p2_cfn") or ""
        if not p1_cfn:
            await self.thread.send(f"<@{self.p1_discord}> Please provide your CFN ID for the stream overlay.")
        if not p2_cfn:
            await self.thread.send(f"<@{self.p2_discord}> Please provide your CFN ID for the stream overlay.")
        from backend.api.ws_manager import manager as hub_mgr
        try:
            await hub_mgr.broadcast({"type": "match_update"})
        except Exception:
            pass
        return None

    async def _handle_offstream_match(self):
        password = generate_lobby_password()
        await update_active_match(self.set_id, lobby_password=password)
        host_discord = self.p1_discord
        opp_discord = self.p2_discord
        try:
            host_member = await self.bot.fetch_user(int(host_discord))
            opp_member = await self.bot.fetch_user(int(opp_discord))
            if host_member:
                await host_member.send(f"🔑 Create a lobby with password **{password}**, invite your opponent, play, then report scores with `!report <your_score> <opponent_score>` in {self.thread.mention}")
            if opp_member:
                await opp_member.send(f"🔑 Join the lobby with password **{password}**, play, then report scores with `!report <your_score> <opponent_score>` in {self.thread.mention}")
        except Exception:
            pass
        return password

async def run_ready_check_timeout(bot, thread, set_id, timeout_seconds: int = 600):
    warning_at = timeout_seconds - 180
    await asyncio.sleep(warning_at)
    match = await get_active_match(set_id)
    if match and match.get('status') == 'called':
        await thread.send("⚠️ **Warning**: 3 minutes remaining. If both players are not ready, the match may be DQ'd.")
    await asyncio.sleep(180)
    match = await get_active_match(set_id)
    if match and match.get('status') == 'called':
        await thread.send("🛑 **Timeout**: 10 minutes elapsed. Auto-DQ triggered.")
        from backend.core.match_state import auto_dq_match
        await auto_dq_match(set_id)
