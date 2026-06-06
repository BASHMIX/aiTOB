import discord
import asyncio
from backend.core.database import (
    get_player, get_active_match, update_active_match, add_bot_feed,
    get_setting, upsert_active_match,
)
from backend.core.match_state import generate_lobby_password, start_call_timer


# ── Emergency-Fallback Workflow ────────────────────────────────────────
# When at least one side of a match has no linked Discord account, the bot
# cannot drive the full coordination loop. Per the architecture spec:
#   1. The reachable player(s) still get a Ready DM.
#   2. On Ready click, we DM them fallback instructions and stop trying to
#      coordinate via Discord.
#   3. Auto-DQ is DISARMED for that set — letting it fire would silently
#      penalize a player who's actively waiting on start.gg.
#   4. The sync engine picks up the result whenever both players self-report
#      on start.gg's web UI.
FALLBACK_DM_TEXT = (
    "⚠️ **Your opponent has no linked Discord account.**\n\n"
    "We've recorded your readiness, but we can't coordinate the match for you here.\n\n"
    "**Please proceed to your start.gg match dashboard now** to check in and use the site chat. "
    "Once you both finish and self-report on start.gg, the result will sync automatically.\n\n"
    "No DQ will be issued for this match by the bot."
)
FALLBACK_THREAD_TEXT = (
    "⚠️ Partial-reach match — opponent has no linked Discord account. "
    "Auto-DQ is **DISARMED**. Coordinate and report on start.gg directly."
)

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

    is_stream = set_data.get("is_stream_match", False)

    # Prefer the sync-engine-resolved discord IDs (kept in the active_matches row
    # via _resolve_discord in sync_active_matches). Fall back to a fresh lookup
    # for the case where the row was created outside sync — e.g. via the manual
    # "Activate" hub button before the next sync tick.
    p1_discord = set_data.get('p1_discord') or await get_discord_id_from_startgg(set_data.get('p1_id') or set_data.get('p1_entrant_id'))
    p2_discord = set_data.get('p2_discord') or await get_discord_id_from_startgg(set_data.get('p2_id') or set_data.get('p2_entrant_id'))

    # If NEITHER side is reachable on Discord, there's nothing the bot can do.
    # Disarm immediately and surface a thread message so the TO sees the state.
    fully_unreachable = not p1_discord and not p2_discord
    partial = (bool(p1_discord) ^ bool(p2_discord))  # exactly one side has Discord

    await update_active_match(
        set_id,
        discord_thread_id=str(thread.id),
        status="called",
        p1_discord=p1_discord,
        p2_discord=p2_discord,
        auto_dq_disarmed=(1 if (fully_unreachable or partial) else 0),
    )

    # Initialize the AI-referee state for this thread up front, keyed by the
    # Discord thread id but carrying the REAL start.gg set_id + player Discord
    # IDs + names. Every match — stream or not — uses the single check-in gate
    # ('waiting_for_checkin', mirroring the workflows.json `called` state) so the
    # referee does NOT accept results until both players check in. Stream coverage
    # is the `on_stream` overlay of `in_progress` (realized at that transition),
    # never a separate check-in state.
    try:
        from backend.bot.agent.graph import app as _referee_app
        _cfg = {"configurable": {"thread_id": str(thread.id)}}
        _referee_app.update_state(_cfg, {
            "set_id": set_id,
            "thread_id": thread.id,
            "player1_discord": p1_discord,
            "player2_discord": p2_discord,
            "player1_name": p1_name,
            "player2_name": p2_name,
            "player1_ready": False,
            "player2_ready": False,
            "chat_history": [],
            "match_status": "waiting_for_checkin",
            "winner_id": None,
            "score_string": None,
        })
    except Exception as e:
        await add_bot_feed(f"Referee state init failed for {set_id}: {e}", "warn")

    mentions = []
    if p1_discord: mentions.append(f"<@{p1_discord}>")
    if p2_discord: mentions.append(f"<@{p2_discord}>")
    content = " ".join(mentions) if mentions else "Players, your match is ready!"

    if is_stream:
        title = f"📺 Stream Match: {round_name}"
        desc = (
            f"**{p1_name}** vs **{p2_name}**\n\n"
            "🎥 **You've been selected for the Stream Match!**\n"
            "Click **I'm Ready** to check in. The broadcaster's lobby name and "
            "password will be DM'd to you privately **once both players are ready**. "
            "You have 10 minutes."
        )
        embed = discord.Embed(title=title, description=desc, color=discord.Color.purple())
    else:
        desc = f"**{p1_name}** vs **{p2_name}**\n\nClick **I'm Ready** to check in. You have 10 minutes."
        embed = discord.Embed(title=f"Match Ready: {round_name}", description=desc, color=discord.Color.green())

    view = ReadyCheckView(set_id, p1_discord, p2_discord, is_stream, thread, bot)
    await thread.send(content=content, embed=embed, view=view)

    if fully_unreachable:
        await thread.send(
            "⚠️ Neither player has a linked Discord account. **Auto-DQ disarmed** — "
            "this match must be coordinated and reported entirely on start.gg."
        )
        await add_bot_feed(
            f"Match {set_id} ({p1_name} vs {p2_name}) auto-disarmed: no Discord on either side",
            "warn"
        )
    elif partial:
        await thread.send(FALLBACK_THREAD_TEXT)
        await add_bot_feed(
            f"Match {set_id} ({p1_name} vs {p2_name}) auto-disarmed: partial reach",
            "warn"
        )

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
        opponent_discord = self.p2_discord if player_key == "p1" else self.p1_discord

        # Emergency-fallback path: opponent has no Discord. We've already disarmed
        # auto-DQ at thread-creation time. Send the player the start.gg-only
        # instructions and stop the bot's coordination loop for this set.
        if not opponent_discord:
            try:
                await interaction.followup.send(FALLBACK_DM_TEXT, ephemeral=True)
            except Exception:
                # Followup ephemeral can fail in DMs — fall back to a plain message
                try:
                    await interaction.user.send(FALLBACK_DM_TEXT)
                except Exception:
                    pass
            # Don't try to launch the lobby flow — the opponent isn't in this channel.
            self.stop()
            return

        if match and match.get("p1_ready") and match.get("p2_ready"):
            # Both checked in → advance through the state machine (called → in_progress).
            # transition_match stamps started_at, best-effort marks the provider
            # in_progress, queues the score-request DM, and broadcasts to the Hub.
            from backend.core.match_state import transition_match
            await transition_match(self.set_id, "in_progress")

            # Arm the AI referee: flip the thread's graph state to 'playing' so
            # chat results are now accepted (they were gated during check-in).
            try:
                from backend.bot.agent.graph import app as _referee_app
                _cfg = {"configurable": {"thread_id": str(self.thread.id)}}
                _referee_app.update_state(_cfg, {
                    "match_status": "playing",
                    "player1_ready": True,
                    "player2_ready": True,
                })
            except Exception as e:
                await add_bot_feed(f"Referee arm failed for {self.set_id}: {e}", "warn")

            self.stop()

            if self.is_stream:
                # The green-room handler sends its own (private credentials +
                # public confirmation) messages; don't double up here.
                await self._handle_stream_match()
            else:
                lobby = await self._handle_offstream_match()
                if lobby:
                    await self.thread.send(f"🚀 Both players ready! {'Lobby password: **' + lobby + '**' if lobby else ''}")
                else:
                    await self.thread.send("🚀 Both players ready! GLHF!")

    async def _handle_stream_match(self):
        """Green-room handoff: both players have checked in, so it's now safe to
        privately deliver the broadcaster's lobby credentials. Credentials live on
        the assigned stream station (room_name_or_id / room_password) and are sent
        by DM — never posted in the thread — so the lobby stays private."""
        match = await get_active_match(self.set_id)

        # Resolve the assigned stream station and its lobby credentials.
        station = None
        station_id = match.get("station_id")
        if station_id:
            from backend.core.database import get_stations
            station = next((s for s in await get_stations() if s["id"] == station_id), None)

        room = (station or {}).get("room_name_or_id") or ""
        pwd = (station or {}).get("room_password") or ""

        if room or pwd:
            cred_lines = ["🎥 **Stream Match — Broadcaster Lobby**", ""]
            if room:
                cred_lines.append(f"**Lobby Name/ID:** `{room}`")
            if pwd:
                cred_lines.append(f"**Password:** `{pwd}`")
            cred_lines.append("")
            cred_lines.append("Join the broadcaster's lobby above. Please do **not** share these details publicly.")
            cred_text = "\n".join(cred_lines)

            delivered = 0
            for discord_id in (self.p1_discord, self.p2_discord):
                if not discord_id:
                    continue
                try:
                    member = await self.bot.fetch_user(int(discord_id))
                    if member:
                        await member.send(cred_text)
                        delivered += 1
                except Exception:
                    pass

            if delivered:
                await self.thread.send("🔒 Both players ready! Stream lobby details have been **DM'd privately**. Head to the broadcaster's lobby.")
            else:
                # DMs closed on both sides — fall back so the match isn't stuck,
                # but keep creds out of the public thread.
                await self.thread.send(
                    "🔒 Both players ready! I couldn't DM the stream lobby details "
                    "(DMs may be closed). Please contact a TO for the lobby name & password."
                )
        else:
            # No station bound (none was free at the in_progress transition) OR the
            # station has no credentials configured. Per the approved fallback, the
            # match is NOT blocked — DM both players that the TO will share the lobby
            # shortly (they can be placed via the manual override once one frees up).
            fallback_dm = (
                "🎥 **You're on the Stream Match!**\n\n"
                "A broadcast station is being prepared — the TO will share the lobby "
                "name and password with you here shortly. Please stand by and keep this "
                "DM open."
            )
            for discord_id in (self.p1_discord, self.p2_discord):
                if not discord_id:
                    continue
                try:
                    member = await self.bot.fetch_user(int(discord_id))
                    if member:
                        await member.send(fallback_dm)
                except Exception:
                    pass
            await self.thread.send(
                "📺 Both players ready! No broadcast station is free yet — a TO will "
                "assign one and share the lobby shortly."
            )
            await add_bot_feed(
                f"Stream match {self.set_id} ready but station "
                f"'{station_id or 'unassigned'}' has no lobby credentials — TO to place it.",
                "warn"
            )

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
    warning_at = max(0, timeout_seconds - 180)
    await asyncio.sleep(warning_at)

    # Re-fetch each time — the disarm flag can be flipped mid-flight, e.g. by a
    # T.O. manually marking the match safe, or by the partial-reach fallback.
    match = await get_active_match(set_id)
    if match and match.get('status') == 'called' and not match.get('auto_dq_disarmed'):
        await thread.send("⚠️ **Warning**: 3 minutes remaining. If both players are not ready, the match may be DQ'd.")

    await asyncio.sleep(180)
    match = await get_active_match(set_id)
    if not match or match.get('status') != 'called':
        return
    if match.get('auto_dq_disarmed'):
        # Spec section 3: silent surrender to start.gg. No DQ, no thread spam.
        return
    await thread.send("🛑 **Timeout**: 10 minutes elapsed. Auto-DQ triggered.")
    from backend.core.match_state import auto_dq_match
    await auto_dq_match(set_id)
