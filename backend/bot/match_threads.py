import discord
import asyncio
from datetime import UTC, datetime, timedelta
from backend.core.database import (
    get_player, get_active_match, update_active_match, add_bot_feed,
    get_setting, upsert_active_match, get_active_matches,
)
from backend.core.match_state import generate_lobby_password, start_call_timer


# ── Emergency-Fallback Workflow ────────────────────────────────────────
# When at least one side of a match has no linked Discord account, the bot
# cannot drive the full coordination loop. Per the architecture spec:
#   1. The reachable player(s) still get a Ready DM.
#   2. On Ready click, we DM them fallback instructions and stop trying to
#      coordinate via Discord.
#   3. A verified Ready protects the reachable player at Start.gg. If the
#      opponent remains absent through the mirrored provider deadline, the
#      documented single-player DQ path advances the attendee.
FALLBACK_DM_TEXT = (
    "⚠️ **Your opponent has no linked Discord account.**\n\n"
    "We've recorded your readiness, but we can't coordinate the match for you here.\n\n"
    "**Please proceed to your start.gg match dashboard now** to check in and use the site chat. "
    "Once you both finish and self-report on start.gg, the result will sync automatically.\n\n"
    "Your verified Ready protects you from the native no-show timer."
)
FALLBACK_THREAD_TEXT = (
    "⚠️ Partial-reach match — opponent has no linked Discord account. "
    "The linked player's verified Ready is protected on Start.gg. Coordinate and report there if the opponent appears."
)

async def create_match_thread(bot, tournament, set_data):
    # The platform bot resolves every outbound effect from the durable
    # workspace/tournament binding. It never falls back to a global channel.
    workspace_id = str(set_data.get("workspace_id") or "")
    tournament_id = str(set_data.get("tournament_slug") or (tournament or {}).get("slug") or "")
    try:
        from backend.core.bot_routing import resolve_discord_route
        route = await resolve_discord_route(
            workspace_id, tournament_id, destination_kind="match"
        )
    except Exception as exc:
        await add_bot_feed(
            f"Match thread failed: Discord route unavailable ({type(exc).__name__}).",
            "error", workspace_id=workspace_id or None,
        )
        return
    channel_id = route.channel_id

    channel = bot.get_channel(int(channel_id))
    if not channel:
        await add_bot_feed(
            f"Match thread failed: Channel {channel_id} not found.", "error",
            workspace_id=workspace_id,
        )
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
    # A Challonge entrant ID is not a Start.gg ID. Never infer a Discord mention
    # from a display name or query the Start.gg identity table for it; an explicit
    # persisted link/organizer override is the only permitted recipient source.
    if (tournament or {}).get("provider_type") == "challonge":
        p1_discord = set_data.get('p1_discord')
        p2_discord = set_data.get('p2_discord')
    else:
        workspace_id = set_data.get("workspace_id")
        # Entrant-scoped organizer links are the authoritative recipient
        # source.  The older player.startgg_id lookup remains a compatibility
        # fallback for migrated rows, but must never override an explicit
        # verified link or infer a mention from a display name.
        from backend.core.identity_links import resolve_verified_discord_recipient
        p1_entrant = set_data.get('p1_id') or set_data.get('p1_entrant_id')
        p2_entrant = set_data.get('p2_id') or set_data.get('p2_entrant_id')
        p1_discord = set_data.get('p1_discord') or await resolve_verified_discord_recipient(
            "startgg", set_data.get("tournament_slug") or "", str(p1_entrant or ""), workspace_id
        ) or await get_discord_id_from_startgg(p1_entrant, workspace_id)
        p2_discord = set_data.get('p2_discord') or await resolve_verified_discord_recipient(
            "startgg", set_data.get("tournament_slug") or "", str(p2_entrant or ""), workspace_id
        ) or await get_discord_id_from_startgg(p2_entrant, workspace_id)

    # ── Dual-mode check-in: 'startgg' hands check-in + DQ to start.gg ──────
    # The bot still opens the thread and pings players, but with a "go to start.gg"
    # embed (no I'm-Ready buttons, no auto-DQ timer). markSetCalled fires start.gg's
    # native check-in wave; the reconciliation poll mirrors the resulting state.
    check_in_source = (tournament or {}).get("check_in_source") or "discord"
    if check_in_source == "startgg":
        await _create_startgg_checkin_thread(
            bot, thread, set_id, p1_name, p2_name, round_name,
            p1_discord, p2_discord, is_stream, set_data,
        )
        return

    # If NEITHER side is reachable on Discord, there's nothing the bot can do.
    # Disarm immediately and surface a thread message so the TO sees the state.
    fully_unreachable = not p1_discord and not p2_discord
    partial = (bool(p1_discord) ^ bool(p2_discord))  # exactly one side has Discord

    # Challonge DQ is intentionally unavailable until a provider contract has
    # been proven end-to-end. Its attendance timer may warn, but it must never
    # invoke the legacy auto-DQ path just because both Discord users are known.
    from backend.core.provider_feature_flags import get_provider_feature_flags
    # Challonge's 0/-1 convention is an explicit organizer choice, never an
    # attendance-timer decision.  Manual DQ may be enabled separately, but
    # Auto-DQ remains disarmed for every Challonge match.
    challonge_dq_disarmed = (tournament or {}).get("provider_type") == "challonge"
    await update_active_match(
        set_id,
        workspace_id=set_data.get("workspace_id"),
        discord_thread_id=str(thread.id),
        status="called",
        hub_status="called",
        hub_status_origin="local_workflow",
        p1_discord=p1_discord,
        p2_discord=p2_discord,
        auto_dq_disarmed=(1 if (fully_unreachable or partial or challonge_dq_disarmed) else 0),
    )

    # Discord is the attendance UI, but Start.gg still owns the native no-show
    # path when nobody attends. Calling the remote set here starts that timer;
    # the first verified Discord attendee will protect the set by moving only
    # the provider axis to IN_PROGRESS.
    if (tournament or {}).get("provider_type", "startgg") == "startgg":
        try:
            from backend.core.providers.registry import get_provider_for_tournament
            provider = await get_provider_for_tournament(
                set_data.get("tournament_slug") or "", set_data.get("workspace_id")
            )
            from backend.core.provider_commands import DurableProviderMutationService
            called = await DurableProviderMutationService(
                workspace_id=str(set_data.get("workspace_id") or "")
            ).dispatch(
                match_id=set_id, action="mark_called", payload={"set_id": set_id},
                operation=lambda: provider.mark_called(set_id),
                precondition_revision=set_data.get("provider_revision"),
            )
            if called.success:
                called_at = datetime.now(UTC)
                timeout_seconds = int(
                    (tournament or {}).get("provider_dq_timer_seconds")
                    or (tournament or {}).get("dq_timer_seconds")
                    or 600
                )
                await update_active_match(
                    set_id, workspace_id=set_data.get("workspace_id"),
                    called_at=called_at.isoformat(),
                    attendance_deadline=(called_at + timedelta(seconds=timeout_seconds)).isoformat(),
                    provider_state_raw="6", provider_state_normalized="called",
                    sync_status="synced", sync_reason="Start.gg native DQ timer started",
                )
            else:
                await add_bot_feed(
                    f"Start.gg call failed for {set_id}: {called.error_message or 'provider rejected markSetCalled'}",
                    "warn", workspace_id=set_data.get("workspace_id"),
                )
        except Exception as exc:
            await add_bot_feed(
                f"Start.gg call unavailable for {set_id}: {str(exc)[:240]}",
                "warn", workspace_id=set_data.get("workspace_id"),
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

    timeout_seconds = int(
        (tournament or {}).get("provider_dq_timer_seconds")
        or (tournament or {}).get("dq_timer_seconds")
        or 600
    )
    timeout_label = (
        f"{timeout_seconds // 60} minute(s)"
        if timeout_seconds % 60 == 0
        else f"{timeout_seconds} seconds"
    )
    if is_stream:
        title = f"📺 Stream Match: {round_name}"
        desc = (
            f"**{p1_name}** vs **{p2_name}**\n\n"
            "🎥 **You've been selected for the Stream Match!**\n"
            "Click **I'm Ready** to check in. The broadcaster's lobby name and "
            "password will be DM'd to you privately **once both players are ready**. "
            f"You have {timeout_label}."
        )
        embed = discord.Embed(title=title, description=desc, color=discord.Color.purple())
    else:
        desc = f"**{p1_name}** vs **{p2_name}**\n\nClick **I'm Ready** to check in. You have {timeout_label}."
        embed = discord.Embed(title=f"Match Ready: {round_name}", description=desc, color=discord.Color.green())

    view = ReadyCheckView(set_id, p1_discord, p2_discord, is_stream, thread, bot, workspace_id=set_data.get("workspace_id"))
    call_message = await thread.send(content=content, embed=embed, view=view)
    # The thread id is the durable idempotency proof. Persisting the call
    # message as well gives the Hub an auditable delivery record without
    # relying on an inferred "called" state.
    await update_active_match(
        set_id,
        workspace_id=set_data.get("workspace_id"),
        call_message_id=str(call_message.id),
        thread_id=str(thread.id),
    )

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
    t = await get_tournament(set_data.get('tournament_slug', ''), set_data.get('workspace_id'))
    timeout = (
        (t.get('provider_dq_timer_seconds') or t.get('dq_timer_seconds') or 600)
        if t else 600
    )
    asyncio.create_task(run_ready_check_timeout(bot, thread, set_id, timeout, set_data.get("workspace_id")))

async def _create_startgg_checkin_thread(
    bot, thread, set_id, p1_name, p2_name, round_name,
    p1_discord, p2_discord, is_stream, set_data,
):
    """'startgg' check_in_source: post a buttonless 'check in on start.gg' thread and
    fire markSetCalled so start.gg owns the check-in wave + DQ.

    No ReadyCheckView, no auto-DQ timer, no Discord referee — the reconciliation poll
    (sync_active_matches) mirrors start.gg's state changes into our local match and
    drives the in_progress / complete side-effects via hub commands.
    """
    # auto_dq_disarmed=1: the bot issues no DQ in this mode (start.gg owns the timer).
    await update_active_match(
        set_id,
        workspace_id=set_data.get("workspace_id"),
        discord_thread_id=str(thread.id),
        status="called",
        p1_discord=p1_discord,
        p2_discord=p2_discord,
        auto_dq_disarmed=1,
    )

    mentions = []
    if p1_discord:
        mentions.append(f"<@{p1_discord}>")
    if p2_discord:
        mentions.append(f"<@{p2_discord}>")
    content = " ".join(mentions) if mentions else "Players, your match is ready!"

    title = f"{'📺 Stream Match' if is_stream else 'Match Ready'}: {round_name}"
    desc = (
        f"**{p1_name}** vs **{p2_name}**\n\n"
        "✅ **Your match is ready!** Please proceed **immediately to Start.gg** to check in.\n"
        "⏱️ The **Start.gg-managed check-in timer has started there** — use the deadline "
        "shown by Start.gg and check in there to avoid being DQ'd.\n\n"
    )
    if is_stream:
        desc += "🎥 You're on the **Stream Match** — once you both check in on Start.gg, the broadcaster's lobby details will be DM'd to you here."
    else:
        desc += "Coordinate and report your result on Start.gg. The hub will sync the result automatically."
    embed = discord.Embed(title=title, description=desc, color=discord.Color.blurple())
    await thread.send(content=content, embed=embed)

    # Fire start.gg's native check-in wave. Best-effort: surface failures to the TO
    # (e.g. set not yet in a callable state) without breaking the thread.
    try:
        from backend.core.providers.registry import get_provider_for_tournament
        provider = await get_provider_for_tournament(set_data.get("tournament_slug") or "", set_data.get("workspace_id"))
        from backend.core.provider_commands import DurableProviderMutationService
        result = await DurableProviderMutationService(
            workspace_id=str(set_data.get("workspace_id") or "")
        ).dispatch(
            match_id=set_id, action="mark_called", payload={"set_id": set_id},
            operation=lambda: provider.mark_called(set_id),
            precondition_revision=set_data.get("provider_revision"),
        )
        if result.success:
            await add_bot_feed(
                f"📣 Called on start.gg: {p1_name} vs {p2_name} — start.gg check-in started.", "info"
            )
        else:
            await add_bot_feed(
                f"⚠️ markSetCalled failed for {set_id} ({p1_name} vs {p2_name}): "
                f"{result.error_message}. Players were pinged but start.gg check-in may not have started.",
                "warn",
            )
            await thread.send(
                "⚠️ I couldn't start check-in on Start.gg automatically — a TO may need to call this set manually."
            )
    except Exception as e:
        await add_bot_feed(f"⚠️ markSetCalled error for {set_id}: {e}", "warn")

    from backend.api.ws_manager import manager as hub_mgr
    try:
        await hub_mgr.broadcast({"type": "match_update", "_workspace_id": set_data.get("workspace_id")})
    except Exception:
        pass


async def get_discord_id_from_startgg(sgg_id: str, workspace_id: str | None = None) -> str | None:
    if not sgg_id:
        return None
    from backend.core.database import get_discord_id_by_startgg
    return await get_discord_id_by_startgg(sgg_id, workspace_id)

class ReadyCheckView(discord.ui.View):
    def __init__(self, set_id, p1_discord, p2_discord, is_stream, thread, bot, *, workspace_id=None):
        # Persistent component registration is restored at bot startup from the
        # durable call/thread/message IDs.  A view timeout made a valid player
        # click fail after a restart even though the Hub still said `called`.
        super().__init__(timeout=None)
        self.set_id = set_id
        self.ready_players = set()
        self.p1_discord = p1_discord
        self.p2_discord = p2_discord
        self.is_stream = is_stream
        self.thread = thread
        self.bot = bot
        self.workspace_id = workspace_id
        self.ready_button.custom_id = f"aitob:ready:{set_id}"

    async def on_timeout(self):
        match = await (get_active_match(self.set_id, self.workspace_id)
                       if self.workspace_id is not None else get_active_match(self.set_id))
        if match and match.get("status") == "called":
            await self.thread.send("⏰ Ready check expired. Use the hub to manage this match.")

    @discord.ui.button(label="I'm Ready", style=discord.ButtonStyle.success)
    async def ready_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        if user_id not in {str(self.p1_discord or ""), str(self.p2_discord or "")}:
            await interaction.response.send_message("This Ready button is only for the two assigned players.", ephemeral=True)
            return
        # Acknowledge before PostgreSQL/outbox work. Discord expires an interaction
        # after roughly three seconds, and an expired acknowledgement used to
        # show “This interaction failed” even when the Ready state committed.
        await interaction.response.defer(ephemeral=True, thinking=False)
        self.ready_players.add(user_id)
        player_key = "p1" if user_id == str(self.p1_discord) else "p2"
        match = await (get_active_match(self.set_id, self.workspace_id)
                       if self.workspace_id is not None else get_active_match(self.set_id))
        if not match:
            await interaction.response.send_message("This match is no longer available.", ephemeral=True)
            return
        is_challonge_local = (
            match.get("tournament_slug", "").startswith("challonge:")
            and (await _challonge_local_workflow_enabled())
        )
        if is_challonge_local:
            from backend.core.match_commands import MatchCommandService
            try:
                service = (MatchCommandService(workspace_id=self.workspace_id)
                           if self.workspace_id is not None else MatchCommandService())
                await service.mark_ready(self.set_id, player_key)
            except ValueError as exc:
                await interaction.followup.send(str(exc), ephemeral=True)
                return
        else:
            from backend.core.match_attendance import AttendanceCommandError, AttendanceCommandService
            try:
                service = AttendanceCommandService(workspace_id=self.workspace_id)
                await service.set_attendance(
                    self.set_id, player=player_key, state="present", source="discord"
                )
            except AttendanceCommandError as exc:
                await interaction.followup.send(
                    f"⚠️ حضورك سُجّل، لكن Start.gg لم يؤكد حماية المباراة: {exc}",
                    ephemeral=True,
                )
                return
        await interaction.followup.send(f"✅ {interaction.user.display_name} is ready!", ephemeral=True)

        match = await (get_active_match(self.set_id, self.workspace_id)
                       if self.workspace_id is not None else get_active_match(self.set_id))
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
            if is_challonge_local:
                from backend.core.match_commands import MatchCommandService
                service = (MatchCommandService(workspace_id=self.workspace_id)
                           if self.workspace_id is not None else MatchCommandService())
                await service.start(self.set_id)
            elif match.get("status") != "in_progress":
                from backend.core.match_state import transition_match
                await transition_match(
                    self.set_id, "in_progress", workspace_id=self.workspace_id,
                    skip_provider=bool(match.get("attendance_protected_at")),
                )

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
        """Green-room handoff (thin wrapper). Both players have checked in, so deliver
        the broadcaster's lobby credentials privately. The implementation lives in the
        module-level deliver_stream_credentials so the start.gg-mode sync path can reuse it."""
        await deliver_stream_credentials(self.bot, self.thread, self.set_id, self.p1_discord, self.p2_discord, self.workspace_id)

    async def _handle_offstream_match(self):
        password = generate_lobby_password()
        await update_active_match(
            self.set_id, workspace_id=self.workspace_id, lobby_password=password,
        )
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


async def _challonge_local_workflow_enabled() -> bool:
    from backend.core.provider_feature_flags import get_provider_feature_flags
    return get_provider_feature_flags().challonge_local_workflow_enabled


async def restore_ready_check_views(bot, workspace_id: str | None = None) -> int:
    """Re-register durable Challonge Ready buttons after a bot process restart.

    This reads PostgreSQL only. It neither sends a Discord message nor performs a
    provider request, and is intentionally limited to stored called matches.
    """
    restored = 0
    # Runtime callers always supply one managed workspace. The no-argument path
    # remains only for focused compatibility tests.
    matches = (await get_active_matches(workspace_id=workspace_id)
               if workspace_id is not None else await get_active_matches())
    for match in matches:
        if (
            match.get("provider_type") != "challonge"
            or match.get("status") != "called"
            or not match.get("call_message_id")
            or not match.get("discord_thread_id")
            or not match.get("p1_discord")
            or not match.get("p2_discord")
        ):
            continue
        try:
            thread = bot.get_channel(int(match["discord_thread_id"]))
            if thread is None:
                thread = await bot.fetch_channel(int(match["discord_thread_id"]))
            view = ReadyCheckView(
                str(match["set_id"]), str(match["p1_discord"]), str(match["p2_discord"]),
                bool(match.get("is_stream_match")), thread, bot,
                workspace_id=match.get("workspace_id"),
            )
            bot.add_view(view, message_id=int(match["call_message_id"]))
            restored += 1
        except (ValueError, TypeError, discord.DiscordException):
            # A deleted thread/message is not a reason to block the remaining
            # recovery work.  It stays visible in the Hub for organizer review.
            continue
    return restored

async def deliver_stream_credentials(bot, thread, set_id, p1_discord, p2_discord, workspace_id: str | None = None):
    """Privately DM the assigned stream station's broadcaster-lobby credentials to both
    players, posting only a non-sensitive confirmation in the thread.

    Shared by the Discord ready-check flow (ReadyCheckView._handle_stream_match) and the
    start.gg-mode sync path (startgg_go_live drain handler). Credentials live on the
    assigned stream station (room_name_or_id / room_password); they are never posted
    publicly. Best-effort throughout — DMs may be closed."""
    match = await get_active_match(set_id, workspace_id)
    if not match:
        return

    station = None
    station_id = match.get("station_id")
    if station_id:
        from backend.core.database import get_stations
        station = next((s for s in await get_stations(match.get("workspace_id")) if s["id"] == station_id), None)

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
        for discord_id in (p1_discord, p2_discord):
            if not discord_id:
                continue
            try:
                member = await bot.fetch_user(int(discord_id))
                if member:
                    await member.send(cred_text)
                    delivered += 1
            except Exception:
                pass

        if delivered:
            await thread.send("🔒 Both players ready! Stream lobby details have been **DM'd privately**. Head to the broadcaster's lobby.")
        else:
            await thread.send(
                "🔒 Both players ready! I couldn't DM the stream lobby details "
                "(DMs may be closed). Please contact a TO for the lobby name & password."
            )
    else:
        fallback_dm = (
            "🎥 **You're on the Stream Match!**\n\n"
            "A broadcast station is being prepared — the TO will share the lobby "
            "name and password with you here shortly. Please stand by and keep this "
            "DM open."
        )
        for discord_id in (p1_discord, p2_discord):
            if not discord_id:
                continue
            try:
                member = await bot.fetch_user(int(discord_id))
                if member:
                    await member.send(fallback_dm)
            except Exception:
                pass
        await thread.send(
            "📺 Both players ready! No broadcast station is free yet — a TO will "
            "assign one and share the lobby shortly."
        )
        await add_bot_feed(
            f"Stream match {set_id} ready but station "
            f"'{station_id or 'unassigned'}' has no lobby credentials — TO to place it.",
            "warn"
        )

    from backend.api.ws_manager import manager as hub_mgr
    try:
        await hub_mgr.broadcast({"type": "match_update", "_workspace_id": match.get("workspace_id")})
    except Exception:
        pass


async def run_ready_check_timeout(bot, thread, set_id, timeout_seconds: int = 600, workspace_id: str | None = None):
    warning_lead = min(180, max(10, timeout_seconds // 3))
    warning_at = max(0, timeout_seconds - warning_lead)
    await asyncio.sleep(warning_at)

    # Re-fetch each time — the disarm flag can be flipped mid-flight, e.g. by a
    # T.O. manually marking the match safe, or by the partial-reach fallback.
    match = await get_active_match(set_id, workspace_id)
    workspace_id = match.get("workspace_id") if match else None
    if match and match.get('status') == 'called':
        remaining_label = (
            f"{warning_lead // 60} minute(s)"
            if warning_lead >= 60 and warning_lead % 60 == 0
            else f"{warning_lead} seconds"
        )
        await thread.send(
            f"⚠️ **Reminder**: {remaining_label} remain in the attendance window."
        )

    await asyncio.sleep(warning_lead)
    match = await get_active_match(set_id, workspace_id)
    if not match or match.get('status') != 'called':
        return
    from backend.core.database import get_tournament
    try:
        tournament = await get_tournament(match.get("tournament_slug") or "", workspace_id)
    except Exception:
        tournament = None
    if tournament and tournament.get("provider_type") == "startgg":
        from backend.core.match_attendance import AttendanceCommandError, AttendanceCommandService
        try:
            outcome = await AttendanceCommandService(workspace_id=workspace_id).resolve_deadline(set_id)
        except AttendanceCommandError as exc:
            await thread.send(f"⚠️ **Attendance deadline needs review:** {exc}")
            await add_bot_feed(
                f"Attendance deadline for {set_id} needs review: {exc}", "warn",
                workspace_id=workspace_id,
            )
            return
        if outcome["outcome"] == "single_attendee_dq_verified":
            await thread.send("⏰ **Attendance window expired.** Start.gg verified the absent player's DQ and advanced the attending player.")
            return
        if outcome["outcome"] == "provider_double_dq":
            await thread.send("⏰ **Attendance window expired with no attendees.** Waiting for Start.gg's native Double-DQ, then aiTOB will read the result back.")
            reconciled = await AttendanceCommandService(
                workspace_id=workspace_id
            ).reconcile_provider_completion(set_id)
            if reconciled["outcome"] in {"provider_double_dq_reconciled", "already_reconciled"}:
                await thread.send("✅ **Start.gg result reconciled.** The provider closed the match after the attendance deadline.")
            else:
                await thread.send("⚠️ **Start.gg has not closed the match yet.** aiTOB retried the read and flagged it for organizer review; no winner was fabricated.")
            return
        if outcome["outcome"] in {"both_present", "not_called", "provider_already_complete"}:
            return

    await thread.send(
        "⏰ **Attendance window expired.** An organizer must review this provider's match outcome."
    )
    try:
        await add_bot_feed(
            f"Attendance expired for {set_id}; organizer review required (automatic DQ disabled).",
            "warn",
            workspace_id=workspace_id,
        )
    except Exception:
        # A Discord timeout must not fail just because the optional feed store
        # is unavailable during startup or an isolated unit test.
        pass
