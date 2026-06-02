import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv
import asyncio
from langchain_core.tools import tool

import sys
# Add project root and backend to sys.path
root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(root)
sys.path.append(os.path.join(root, "backend"))
from core.database import init_db, create_or_update_player, get_player
from bot.registration import registration_manager
from bot.messages import get_msg
from bot.agent.graph import app, process_message
from bot.agent.hub_agent import build_hub_agent, build_hub_agent_async

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
    global hub_agent
    await init_db()
    print(f"\u2705 Bot is online and connected to Discord as {bot.user}")
    
    # Start background WebSocket listener for real-time Hub commands & log streaming
    asyncio.create_task(bot_ws_listener())
    
    # If hub_agent wasn't built at import time (no env key), build it now from DB
    if hub_agent is None:
        try:
            hub_agent = await build_hub_agent_async(hub_tools)
            print("[BOT] Hub agent initialized from DB API key")
        except Exception as e:
            print(f"[BOT] Warning: Hub agent could not be initialized: {e}")
            
    if not auto_dispatch_pool_matches.is_running():
        auto_dispatch_pool_matches.start()

    # Sync the slash command tree. Per-guild sync propagates instantly;
    # global sync can take up to an hour. We sync to every guild the bot is
    # in for snappy UX during testing AND globally so newly-joined guilds work.
    try:
        for guild in bot.guilds:
            await bot.tree.sync(guild=guild)
        await bot.tree.sync()
        await ws_add_bot_feed(f"Slash commands synced to {len(bot.guilds)} guild(s)", "info")
    except Exception as e:
        print(f"[BOT] Slash-command sync failed: {e}")

    print('------')


# ── Slash Commands: Bio-Code Verification ──────────────────────────────
# Used when start.gg OAuth isn't available. The player edits their start.gg
# bio to include a temporary code; the bot reads the bio via the public API
# and confirms account control. Same downstream effect as OAuth — writes
# players.startgg_id and triggers role/nick assignment.
#
# Anti-abuse:
#   • Codes expire after 5 minutes
#   • Max 5 confirm attempts per pending entry (after that, restart with /verify)
#   • Code is 8 chars from a 32-char alphabet → collision probability negligible

import re as _re
import secrets as _secrets

# Parse a start.gg profile slug from common input shapes:
#   "abc123"                                 → "abc123"
#   "user/abc123"                            → "abc123"
#   "https://start.gg/user/abc123"           → "abc123"
#   "https://www.start.gg/user/abc123/info"  → "abc123"
_SGG_SLUG_RE = _re.compile(r"(?:start\.gg/)?(?:user/)?([A-Za-z0-9_-]+)(?:/.*)?$")

def _parse_sgg_slug(raw: str) -> str | None:
    if not raw:
        return None
    raw = raw.strip().rstrip("/")
    if "/" in raw:
        # Take the segment right after "user/" if present
        m = _re.search(r"user/([A-Za-z0-9_-]+)", raw)
        if m:
            return m.group(1)
    m = _SGG_SLUG_RE.search(raw)
    return m.group(1) if m else None


def _generate_verify_code() -> str:
    # 8 chars, upper-only, no ambiguous 0/O/1/I/L
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(_secrets.choice(alphabet) for _ in range(8))


async def _start_bio_verification(interaction: discord.Interaction, slug: str):
    """Issue a fresh code for this Discord user + slug, DM-style ephemeral reply."""
    from core.database import create_pending_verification

    discord_id = str(interaction.user.id)
    code = _generate_verify_code()
    await create_pending_verification(discord_id, slug, code, ttl_seconds=300)

    embed = discord.Embed(
        title="🔗 One more step — prove account control",
        description=(
            f"To link **start.gg/user/{slug}** to your Discord account, add this "
            f"code to your start.gg **bio**:\n\n"
            f"```\n{code}\n```\n"
            f"1. Open https://start.gg/admin/profile\n"
            f"2. Paste the code anywhere in your **Bio** field, click **Save**.\n"
            f"3. Come back and run `/verify-confirm`.\n\n"
            f"_You have **5 minutes**. After confirming, you can remove the code._"
        ),
        color=discord.Color.blue(),
    )
    # Use followup if response already deferred, otherwise direct response
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="verify", description="Link your Discord account to your start.gg profile")
@discord.app_commands.describe(profile="Your start.gg profile URL or slug (optional — bot will try to find you)")
async def verify_command(interaction: discord.Interaction, profile: str | None = None):
    from core.database import get_player
    discord_id = str(interaction.user.id)

    # Idempotency — already verified?
    player = await get_player(discord_id)
    if player and player.get("is_verified") and player.get("startgg_id"):
        tag = player.get("gamer_tag") or "your start.gg account"
        await interaction.response.send_message(
            f"✅ You're already verified as **{tag}**.\n"
            "If you need to re-link a different start.gg account, contact a T.O.",
            ephemeral=True,
        )
        return

    if profile:
        # Player provided their slug — straight to bio-code flow.
        slug = _parse_sgg_slug(profile)
        if not slug:
            await interaction.response.send_message(
                "❌ I couldn't read that as a start.gg profile. Try a URL like "
                "`https://start.gg/user/abc123` or just the slug `abc123`.",
                ephemeral=True,
            )
            return
        await _start_bio_verification(interaction, slug)
        return

    # No profile provided — let LLM disambiguation handle it (Gap B).
    # Falls back to "please provide a URL" if the helper can't find candidates.
    await _verify_with_disambiguation(interaction)


@bot.tree.command(name="verify-confirm", description="Finish linking after adding the code to your start.gg bio")
async def verify_confirm_command(interaction: discord.Interaction):
    from core.database import (
        get_pending_verification, delete_pending_verification,
        increment_verification_attempts, create_or_update_player, add_hub_command,
        add_bot_feed, get_player,
    )

    discord_id = str(interaction.user.id)

    # Cheap idempotency guard.
    existing = await get_player(discord_id)
    if existing and existing.get("is_verified") and existing.get("startgg_id"):
        await interaction.response.send_message(
            f"✅ Already verified as **{existing.get('gamer_tag') or 'your start.gg account'}**.",
            ephemeral=True,
        )
        return

    pending = await get_pending_verification(discord_id)
    if not pending:
        await interaction.response.send_message(
            "❌ No active verification request found, or it expired. Run `/verify` to start over.",
            ephemeral=True,
        )
        return

    attempts = await increment_verification_attempts(discord_id)
    if attempts > 5:
        await delete_pending_verification(discord_id)
        await interaction.response.send_message(
            "❌ Too many attempts. Please run `/verify` again to get a fresh code.",
            ephemeral=True,
        )
        return

    # Defer because the API fetch can take a second or two.
    await interaction.response.defer(ephemeral=True, thinking=True)

    slug = pending["startgg_slug"]
    code = pending["code"]

    from core.providers.startgg.client import get_client
    sgg = get_client()
    user = await sgg.fetch_user_by_slug(slug)
    if not user:
        await interaction.followup.send(
            f"❌ Couldn't fetch `start.gg/user/{slug}` — is the slug correct?",
            ephemeral=True,
        )
        return

    bio = user.get("bio") or ""
    if code not in bio:
        remaining = max(0, 5 - attempts)
        await interaction.followup.send(
            f"❌ The code `{code}` wasn't found in your start.gg bio. "
            f"Make sure you saved the bio, then try `/verify-confirm` again. "
            f"({remaining} attempts left.)",
            ephemeral=True,
        )
        return

    # Verified. Extract gamerTag + avatar and write the player row.
    sgg_user_id = str(user.get("id"))
    player_node = user.get("player") or {}
    gamer_tag = player_node.get("gamerTag")
    images = user.get("images") or []
    avatar = next((i.get("url") for i in images if i.get("type") == "profile"), None) or (
        images[0].get("url") if images else None
    )

    await create_or_update_player(
        discord_id=discord_id,
        startgg_id=sgg_user_id,
        gamer_tag=gamer_tag,
        avatar_path=avatar,
        is_verified=True,
        registration_step="verified",
    )
    await delete_pending_verification(discord_id)
    # Hand off role/nick assignment to the existing hub-command worker.
    await add_hub_command(f"apply_verified_role {discord_id}")
    await add_bot_feed(
        f"✅ Bio-code verified: Discord <{discord_id}> ↔ start.gg user {sgg_user_id} ({gamer_tag})",
        "success",
    )

    await interaction.followup.send(
        f"✅ Verified as **{gamer_tag}**! You can now remove the code from your bio.",
        ephemeral=True,
    )


@bot.tree.command(name="register", description="Alias for /verify")
@discord.app_commands.describe(profile="Your start.gg profile URL or slug (optional)")
async def register_command(interaction: discord.Interaction, profile: str | None = None):
    await verify_command.callback(interaction, profile)  # type: ignore[attr-defined]


# ── Gap B: LLM-driven entrant disambiguation ───────────────────────────
# When /verify is called without a profile URL, pull the entrant list from
# every tracked tournament, ask Gemini to rank candidates by likelihood of
# being this Discord user, and present a buttoned picker. Click → bio-code
# flow against the picked entrant's user slug.
#
# The LLM is ONLY ranking/suggesting — security is still bio-code. Worst
# case the LLM proposes the wrong person, the player clicks "None of these,"
# they fall back to pasting their profile URL. No new attack surface.

_VERIFY_DISAMBIG_TIMEOUT = 120  # seconds the picker stays interactive


def _collect_candidate_entrants() -> list[dict]:
    """Flatten entrants across all tracked tournaments. Each candidate has:
        slug      — start.gg user slug (None if no linked user)
        user_id   — start.gg user.id (None if no linked user)
        gamerTag  — display name
        prefix    — team/sponsor tag
        country   — best-effort flag emoji input ("US", "AE", etc.)
        tournament— tournament name (for context)
    Returns at most ~30 to keep the LLM prompt bounded.
    """
    import asyncio as _aio
    import json as _json
    from core.database import get_tournaments

    async def _gather():
        tournaments = await get_tournaments()
        candidates: list[dict] = []
        for t in tournaments:
            raw = t.get("raw_data")
            if not raw:
                continue
            try:
                parsed = _json.loads(raw)
            except Exception:
                continue
            for ev in (parsed.get("events") or []):
                for ent in ((ev.get("entrants") or {}).get("nodes") or []):
                    participants = ent.get("participants") or []
                    if not participants:
                        continue
                    user = (participants[0] or {}).get("user") or {}
                    candidates.append({
                        "slug": user.get("slug"),
                        "user_id": user.get("id"),
                        "gamerTag": ent.get("name") or "",
                        "prefix": (user.get("player") or {}).get("prefix"),
                        "tournament": t.get("name"),
                    })
        # Drop entries with no slug (can't bio-verify against them).
        candidates = [c for c in candidates if c.get("slug")]
        # Dedupe by slug.
        seen = set()
        unique = []
        for c in candidates:
            if c["slug"] in seen:
                continue
            seen.add(c["slug"])
            unique.append(c)
        return unique[:50]  # hard cap on prompt size

    return _aio.get_event_loop().run_until_complete(_gather()) if False else None  # see below


async def _collect_candidate_entrants_async() -> list[dict]:
    """Async version (the sync wrapper above is unused; kept for clarity)."""
    import json as _json
    from core.database import get_tournaments

    tournaments = await get_tournaments()
    candidates: list[dict] = []
    for t in tournaments:
        raw = t.get("raw_data")
        if not raw:
            continue
        try:
            parsed = _json.loads(raw)
        except Exception:
            continue
        for ev in (parsed.get("events") or []):
            for ent in ((ev.get("entrants") or {}).get("nodes") or []):
                participants = ent.get("participants") or []
                if not participants:
                    continue
                user = (participants[0] or {}).get("user") or {}
                candidates.append({
                    "slug": user.get("slug"),
                    "user_id": user.get("id"),
                    "gamerTag": ent.get("name") or "",
                    "prefix": (user.get("player") or {}).get("prefix"),
                    "tournament": t.get("name"),
                })
    candidates = [c for c in candidates if c.get("slug")]
    seen, unique = set(), []
    for c in candidates:
        if c["slug"] in seen:
            continue
        seen.add(c["slug"])
        unique.append(c)
    return unique[:50]


class _VerifyPickerView(discord.ui.View):
    """Buttoned picker showing top-3 LLM-ranked candidates + a 'None of these' fallback."""

    def __init__(self, top: list[dict], invoking_user_id: int):
        super().__init__(timeout=_VERIFY_DISAMBIG_TIMEOUT)
        self.invoking_user_id = invoking_user_id

        for idx, cand in enumerate(top[:3]):
            label = cand["gamerTag"]
            if cand.get("prefix"):
                label = f"{cand['prefix']} | {label}"
            label = label[:80]  # Discord button label cap
            btn = discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.primary,
                custom_id=f"verify_pick_{idx}",
            )

            # Closure capture — bind cand by default arg.
            async def _cb(interaction: discord.Interaction, _slug=cand["slug"]):
                if interaction.user.id != self.invoking_user_id:
                    await interaction.response.send_message(
                        "Only the person who ran /verify can use these buttons.",
                        ephemeral=True,
                    )
                    return
                # Disable all buttons after a pick.
                for c in self.children:
                    c.disabled = True
                await interaction.message.edit(view=self)
                await _start_bio_verification(interaction, _slug)
            btn.callback = _cb
            self.add_item(btn)

        none_btn = discord.ui.Button(
            label="None of these",
            style=discord.ButtonStyle.secondary,
            custom_id="verify_pick_none",
        )

        async def _none_cb(interaction: discord.Interaction):
            if interaction.user.id != self.invoking_user_id:
                await interaction.response.send_message(
                    "Only the person who ran /verify can use these buttons.",
                    ephemeral=True,
                )
                return
            for c in self.children:
                c.disabled = True
            await interaction.message.edit(view=self)
            await interaction.response.send_message(
                "No problem. Run `/verify profile:<your-start.gg-url>` to link manually.",
                ephemeral=True,
            )
        none_btn.callback = _none_cb
        self.add_item(none_btn)


async def _llm_rank_entrants(discord_user: discord.User | discord.Member,
                              candidates: list[dict]) -> list[dict]:
    """Ask Gemini to rank candidates by likelihood of being this Discord user.

    Returns up to 3 candidates ordered most→least likely. Falls back to
    case-insensitive substring matching if the LLM call fails — still gives
    the player something useful to click.
    """
    nick = getattr(discord_user, "nick", None) or discord_user.display_name
    handle = discord_user.name

    # Cheap deterministic fallback (used when LLM unavailable OR as tiebreaker).
    def _heuristic_rank() -> list[dict]:
        nick_l = (nick or "").lower()
        handle_l = (handle or "").lower()
        def score(c):
            tag = (c.get("gamerTag") or "").lower()
            if not tag:
                return 0
            s = 0
            if tag == nick_l or tag == handle_l: s += 100
            if tag in nick_l or tag in handle_l: s += 30
            if nick_l and nick_l in tag: s += 20
            if handle_l and handle_l in tag: s += 20
            return s
        ranked = sorted(candidates, key=score, reverse=True)
        return [c for c in ranked if score(c) > 0][:3]

    try:
        from bot.agent.graph import _get_llm
        from pydantic import BaseModel, Field as _Field
        from typing import List as _List

        class _RankItem(BaseModel):
            slug: str = _Field(description="The candidate's start.gg slug")
            confidence: float = _Field(description="0.0–1.0; >0.7 means strong match")
            reasoning: str = _Field(description="One short sentence")

        class _RankResult(BaseModel):
            top: _List[_RankItem] = _Field(description="Up to 3 most likely, best first")

        llm, _ = await _get_llm()
        ranker = llm.with_structured_output(_RankResult)

        # Compact prompt — bound at ~50 candidates so it stays cheap.
        roster = "\n".join(
            f"- slug={c['slug']!r}, gamerTag={c['gamerTag']!r}, prefix={c.get('prefix')!r}"
            for c in candidates
        )
        prompt = (
            "Match this Discord user to a tournament entrant by name similarity, "
            "team prefix overlap, and obvious aliases. Return UP TO 3 candidates "
            "ordered most→least likely. If nothing's likely, return an empty list.\n\n"
            f"Discord username: {handle}\n"
            f"Discord display name: {discord_user.display_name}\n"
            f"Discord nickname (server): {nick or '(none)'}\n\n"
            f"Candidates:\n{roster}"
        )
        result = ranker.invoke(prompt)

        # Translate slugs back to full candidate dicts in the LLM's order.
        by_slug = {c["slug"]: c for c in candidates}
        ranked = [by_slug[r.slug] for r in result.top if r.slug in by_slug]
        if ranked:
            return ranked[:3]
    except Exception as e:
        print(f"[BOT] LLM disambiguation failed, falling back to heuristic: {e}")

    return _heuristic_rank()


async def _verify_with_disambiguation(interaction: discord.Interaction):
    """No-arg /verify path: LLM picks top-3 likely entrants, presents buttons."""
    candidates = await _collect_candidate_entrants_async()
    if not candidates:
        await interaction.response.send_message(
            "I don't see any tournaments with entrants tracked yet. Please run "
            "`/verify profile:<your start.gg URL>` to link manually.",
            ephemeral=True,
        )
        return

    # Defer — the LLM call can take a couple seconds.
    await interaction.response.defer(ephemeral=True, thinking=True)
    top = await _llm_rank_entrants(interaction.user, candidates)

    if not top:
        await interaction.followup.send(
            "I couldn't find a likely match for your Discord identity in the entrant list. "
            "Run `/verify profile:<your start.gg URL>` to link manually.",
            ephemeral=True,
        )
        return

    embed = discord.Embed(
        title="🔗 Is this you?",
        description=(
            "I found these likely matches in the tournament entrant list. Click "
            "the right one to start verification, or **None of these** to enter "
            "your start.gg URL manually."
        ),
        color=discord.Color.blue(),
    )
    for cand in top:
        prefix_disp = f"{cand['prefix']} | " if cand.get("prefix") else ""
        embed.add_field(
            name=f"{prefix_disp}{cand['gamerTag']}",
            value=f"start.gg/user/{cand['slug']} — *{cand.get('tournament') or 'tournament'}*",
            inline=False,
        )

    view = _VerifyPickerView(top, interaction.user.id)
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)

@tasks.loop(seconds=10.0)
async def update_heartbeat():
    from core.database import set_setting
    import time
    await set_setting("bot_last_seen", str(time.time()))


# ── Auto-Dispatcher ─────────────────────────────────────────────────────
# Pops the next bot-managed, fully-resolved match off the queue and queues a
# `call_match` hub command for it. Same code path as the manual "Call Match"
# button — only difference is who pressed it. Designed so the TO can flip
# the master switch off and resume manual control at any time.
#
# Safety rails:
#   • Master switch in global_settings.auto_dispatch_master_switch ("on"/"off")
#   • Per-tournament arming via tournaments.auto_dispatch_enabled
#   • Concurrency cap per tournament (auto_dispatch_concurrency)
#   • Hands back to TO when remaining matches ≤ stop_at threshold (Top 8)
#   • Skips planned-stream sets (those wait for a free stream station)
#   • Skips matches with TBD entrants (upstream bracket unresolved)
#   • Every dispatch and every gate logs to bot_feed so the TO can audit

_DISPATCH_LAST_TICK: dict[str, float] = {}  # per-tournament cooldown
_DISPATCH_COOLDOWN_SECONDS = 30.0           # minimum gap between dispatches per tournament

@tasks.loop(seconds=20.0)
async def auto_dispatch_pool_matches():
    import time
    from core.database import (
        get_setting, get_dispatch_eligible_tournaments,
        count_active_dispatched, count_remaining_event_matches,
        get_dispatch_candidates, add_hub_command, add_bot_feed,
    )

    # Master kill switch — overrides every per-tournament setting.
    master = (await get_setting("auto_dispatch_master_switch", "off") or "off").lower()
    if master != "on":
        return

    tournaments = await get_dispatch_eligible_tournaments()
    now = time.time()

    for t in tournaments:
        slug = t["slug"]
        concurrency = max(1, int(t.get("auto_dispatch_concurrency") or 1))
        stop_at = max(0, int(t.get("auto_dispatch_stop_at") or 8))

        # Cooldown — prevents back-to-back dispatches from one tick if the loop
        # interval is reduced. The 30s gap also gives players time to react.
        last = _DISPATCH_LAST_TICK.get(slug, 0.0)
        if now - last < _DISPATCH_COOLDOWN_SECONDS:
            continue

        # Top-N changeover: when fewer than (stop_at) uncompleted matches remain,
        # we treat the bracket as "in TO territory" and stop calling.
        remaining = await count_remaining_event_matches(slug)
        if remaining <= stop_at:
            # One-shot signal so the operator sees it once, not every tick.
            key = f"_dispatcher_stop_signaled_{slug}"
            if not await get_setting(key):
                from core.database import set_setting as _set
                await _set(key, "1")
                await add_bot_feed(
                    f"🤖 Auto-dispatcher stopped for {t['name']}: {remaining} matches remain "
                    f"(threshold ≤ {stop_at}). TO takes over from here.",
                    "info"
                )
            continue

        # Compute open slots.
        in_flight = await count_active_dispatched(slug)
        slots = concurrency - in_flight
        if slots <= 0:
            continue

        candidates = await get_dispatch_candidates(slug, limit=slots)
        if not candidates:
            continue

        for m in candidates:
            set_id = m["set_id"]
            await add_hub_command(f"call_match {set_id}")
            await add_bot_feed(
                f"🤖 Auto-dispatched: {m.get('p1_name')} vs {m.get('p2_name')} "
                f"({m.get('round_name') or m.get('phase_group') or 'pool'})",
                "info"
            )

        _DISPATCH_LAST_TICK[slug] = now

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
        login_url = f"{api_base}/api/auth/startgg/login?discord_id={discord_id}"

        
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

@bot.group(name="workflow", invoke_without_command=True)
async def workflow_group(ctx):
    """View match and tournament workflow information."""
    await ctx.send(
        "ℹ️ **Workflow Command Usage**:\n"
        "• `!workflow rules` - Show state machine rules & registration flow steps.\n"
        "• `!workflow status` - Show active matches and their current workflow states.\n"
        "• `!workflow validate <set_id>` - Check allowed next transitions for a match."
    )

@workflow_group.command(name="rules")
async def workflow_rules(ctx):
    """Show the configured workflow rules from workflows.json."""
    import json
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(current_dir)
        json_path = os.path.join(root_dir, "docs", "workflows.json")
        
        if not os.path.exists(json_path):
            await ctx.send("❌ `docs/workflows.json` not found.")
            return
            
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        embed = discord.Embed(
            title="🎯 FNC Workflow Configuration Rules",
            color=discord.Color.blue(),
            description="Driven by dynamic `docs/workflows.json` configuration."
        )
        
        # Match States
        match_wf = data.get("match_workflow", {}).get("states", {})
        match_desc = []
        for state, config in match_wf.items():
            if config.get("overlay"):
                match_desc.append(
                    f"• **`{state}`** *(overlay)*: {config.get('description')}\n"
                    f"  ↳ Derived from `{config.get('derived_from')}` when {config.get('condition')}"
                )
                continue
            allowed = ", ".join([f"`{s}`" for s in config.get("allowed_next", [])])
            match_desc.append(f"• **`{state}`**: {config.get('description')}\n  ↳ Transitions to: {allowed or '*None*'}")
            
        embed.add_field(
            name="⚔️ Match State Transitions",
            value="\n".join(match_desc),
            inline=False
        )
        
        # Registration Steps
        reg_wf = data.get("registration_workflow", {}).get("steps", {})
        sorted_steps = sorted(reg_wf.items(), key=lambda x: x[1].get("index", 0))
        reg_desc = []
        for step, config in sorted_steps:
            reg_desc.append(f"{config.get('index')}. **`{step}`**: {config.get('description')}")
            
        embed.add_field(
            name="👤 Registration Progression Flow",
            value="\n".join(reg_desc),
            inline=False
        )
        
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ Failed to load or display rules: {e}")

@workflow_group.command(name="status")
async def workflow_status(ctx):
    """Show current states of all active matches."""
    from core.database import get_active_matches
    matches = await get_active_matches()
    
    if not matches:
        await ctx.send("ℹ️ No active matches in the system right now.")
        return
        
    embed = discord.Embed(
        title="📊 Active Match Workflow Status",
        color=discord.Color.purple()
    )
    
    # Group by state
    from collections import defaultdict
    by_state = defaultdict(list)
    for m in matches:
        by_state[m.get("status", "not_started")].append(m)
        
    for state, state_matches in by_state.items():
        match_list = []
        for m in state_matches:
            match_list.append(f"• Set `{m.get('set_id')}`: {m.get('p1_name')} vs {m.get('p2_name')} (Station: `{m.get('station_id') or 'None'}`)")
        
        embed.add_field(
            name=f"State: `{state}` ({len(state_matches)})",
            value="\n".join(match_list) if match_list else "*None*",
            inline=False
        )
        
    await ctx.send(embed=embed)

@workflow_group.command(name="validate")
async def workflow_validate(ctx, set_id: str):
    """Validate transition pathways for a match."""
    from core.database import get_active_match
    match = await get_active_match(set_id)
    if not match:
        await ctx.send(f"❌ Match with set ID `{set_id}` not found.")
        return
        
    from backend.core.match_state import VALID_TRANSITIONS
    current_status = match.get("status", "not_started")
    allowed = VALID_TRANSITIONS.get(current_status, [])
    allowed_str = ", ".join([f"`{s}`" for s in allowed])
    
    embed = discord.Embed(
        title=f"🔍 Match Transition Validation: Set {set_id}",
        color=discord.Color.green()
    )
    embed.add_field(name="Match", value=f"{match.get('p1_name')} vs {match.get('p2_name')}", inline=False)
    embed.add_field(name="Current Workflow State", value=f"`{current_status}`", inline=True)
    embed.add_field(name="Allowed Next Transitions", value=allowed_str or "*None*", inline=True)
    
    # Check start.gg status if synchronizing
    sgg_url = f"https://start.gg/admin/set/{set_id}"
    embed.description = f"[Manage set on Start.gg]({sgg_url})"
    
    await ctx.send(embed=embed)

@bot.command()
async def report(ctx, p1_score: int, p2_score: int):
    """Report match scores in a thread. Usage: !report 2 0"""
    from core.database import get_active_matches, update_active_match, add_bot_feed

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

    from core.providers.registry import get_provider_for_tournament
    from core.score_reporting import report_score_to_provider

    provider = await get_provider_for_tournament(match.get('tournament_slug') or '')
    result = await report_score_to_provider(
        set_id=set_id,
        winner_id=winner_id,
        p1_id=match['p1_entrant_id'],
        p2_id=match['p2_entrant_id'],
        p1_score=p1_score,
        p2_score=p2_score,
        provider=provider
    )
    if not result.success:
        await ctx.send(f"Failed to report scores: {result.error_message}")
        return

    await update_active_match(set_id, status="complete")
    await add_bot_feed(f"📝 Match {set_id} reported via Discord: {p1_score}-{p2_score}", "info")
    await ctx.send(f"✅ Score reported to provider: {p1_score}-{p2_score}")
    await ctx.channel.edit(archived=True, locked=True)


async def send_score_report_dms(bot, match):
    p1_discord = match.get("p1_discord")
    p2_discord = match.get("p2_discord")
    if not p1_discord and match.get("p1_entrant_id"):
        from bot.match_threads import get_discord_id_from_startgg
        p1_discord = await get_discord_id_from_startgg(match.get("p1_entrant_id"))
    if not p2_discord and match.get("p2_entrant_id"):
        from bot.match_threads import get_discord_id_from_startgg
        p2_discord = await get_discord_id_from_startgg(match.get("p2_entrant_id"))
    p1_name = match.get("p1_name", "TBD")
    p2_name = match.get("p2_name", "TBD")
    set_id = match.get("set_id")
    if p1_discord:
        try:
            member = await bot.fetch_user(int(p1_discord))
            embed = discord.Embed(
                title="Report Your Match Score",
                description=f"Your match against **{p2_name}** is in progress!\n\nOnce completed, please reply to this DM with:\n`score <your_score> <opponent_score>`\n(e.g., `score 2 1` if you won 2-1).",
                color=discord.Color.blue()
            )
            await member.send(embed=embed)
        except Exception as e:
            print(f"Failed to DM P1 ({p1_discord}): {e}")
    if p2_discord:
        try:
            member = await bot.fetch_user(int(p2_discord))
            embed = discord.Embed(
                title="Report Your Match Score",
                description=f"Your match against **{p1_name}** is in progress!\n\nOnce completed, please reply to this DM with:\n`score <your_score> <opponent_score>`\n(e.g., `score 2 1` if you won 2-1).",
                color=discord.Color.blue()
            )
            await member.send(embed=embed)
        except Exception as e:
            print(f"Failed to DM P2 ({p2_discord}): {e}")


async def _llm_extract_dm_score(message_content: str, match: dict, discord_id: str) -> tuple[int, int] | None:
    """Fallback NL parser: hand the DM to the existing structured-output LLM.

    Returns (score1, score2) from the reporting player's perspective, i.e.
    score1 = how many games the SENDER won, score2 = opponent. Returns None
    if the LLM can't parse a clear result.

    Same Gemini extractor that handles thread chat — we just give it a tiny
    one-message "history" with whose-is-who context so it can infer winner.
    """
    try:
        from bot.agent.graph import _get_llm
        _, extractor = await _get_llm()
    except Exception as e:
        print(f"[BOT] LLM unavailable for DM score parsing: {e}")
        return None

    is_p1 = (str(match.get("p1_discord")) == discord_id)
    sender_name = match["p1_name"] if is_p1 else match["p2_name"]
    opponent_name = match["p2_name"] if is_p1 else match["p1_name"]

    prompt = (
        "Extract the match result from a single DM the reporting player just sent.\n\n"
        f"Sender: {sender_name} (Discord ID: {discord_id})\n"
        f"Opponent: {opponent_name}\n"
        f"Message: \"{message_content}\"\n\n"
        "Determine who won and the series score (e.g. 2-1, 3-0). "
        "If the message clearly reports a result, set winner_discord_id to "
        f"{discord_id} if the SENDER won, or to anything else (or null) if the opponent won.\n"
        "Set conflict_detected=false unless the sender clearly disputes a prior result. "
        "If the message is not a score report at all, leave winner_discord_id and score empty."
    )
    try:
        result = extractor.invoke(prompt)
    except Exception as e:
        print(f"[BOT] LLM DM-extraction failed: {e}")
        return None

    if not result or not result.score or "-" not in result.score:
        return None

    try:
        a, b = [int(x.strip()) for x in result.score.split("-", 1)]
    except Exception:
        return None
    if a == b or max(a, b) > 9:
        return None  # ties / nonsense

    sender_won = (str(result.winner_discord_id) == discord_id)
    # `score` is conventionally "winner-loser" — flip to sender-perspective.
    if sender_won:
        return (max(a, b), min(a, b))
    else:
        return (min(a, b), max(a, b))


async def handle_score_report_dm(message: discord.Message):
    discord_id = str(message.author.id)
    content = message.content.strip()
    import re
    from core.database import get_player_in_progress_match, update_active_match, get_tournament, add_bot_feed

    match = await get_player_in_progress_match(discord_id)
    if not match:
        await message.channel.send("❌ No active, in-progress match found for you in this tournament.")
        return

    # Strict regex path — fast & deterministic. Try first.
    match_obj = re.search(r'^score\s+(\d+)\s+(\d+)', content, re.IGNORECASE)
    if match_obj:
        score1 = int(match_obj.group(1))
        score2 = int(match_obj.group(2))
    else:
        # Gap A: fall back to LLM extractor for natural language ("i won 2-1", "lost 0-2", etc).
        extracted = await _llm_extract_dm_score(content, match, discord_id)
        if not extracted:
            await message.channel.send(
                "❌ I couldn't read that as a score. Try either:\n"
                "• `score 2 1` (your score first, opponent second), or\n"
                "• plain English like `i won 2-1` / `lost 0-2`."
            )
            return
        score1, score2 = extracted
        await add_bot_feed(
            f"🤖 LLM parsed DM score for {match.get('set_id')}: '{content}' → {score1}-{score2}",
            "info",
        )

    set_id = match["set_id"]
    is_p1 = (str(match.get("p1_discord")) == discord_id)
    p1_score = score1 if is_p1 else score2
    p2_score = score2 if is_p1 else score1
    if p1_score == p2_score:
        await message.channel.send("❌ Scores cannot be tied. Please report again.")
        return
    t = await get_tournament(match["tournament_slug"])
    bot_manage_finish = t.get("bot_manage_finish", "off") if t else "off"
    is_stream = match.get("is_stream_match", False)
    if bot_manage_finish in ["on", "auto"] and not is_stream:
        from core.providers.registry import get_provider_for_tournament
        from core.score_reporting import report_score_to_provider
        
        provider = await get_provider_for_tournament(match.get('tournament_slug') or '')
        winner_key = "p1" if p1_score > p2_score else "p2"
        winner_id = match.get(f"{winner_key}_entrant_id")
        
        result = await report_score_to_provider(
            set_id=set_id,
            winner_id=winner_id,
            p1_id=match['p1_entrant_id'],
            p2_id=match['p2_entrant_id'],
            p1_score=p1_score,
            p2_score=p2_score,
            provider=provider
        )
        if result.success:
            await update_active_match(set_id, status="complete", p1_score=p1_score, p2_score=p2_score)
            await add_bot_feed(f"🤖 Bot auto-finished match {set_id} ({match['p1_name']} {p1_score} - {p2_score} {match['p2_name']}) via player DM", "success")
            await message.channel.send(f"✅ Match score reported and completed: {p1_score} - {p2_score}. Thanks!")
            thread_id = match.get("discord_thread_id")
            if thread_id:
                try:
                    thread = bot.get_channel(int(thread_id))
                    if thread:
                        await thread.send(f"✅ Match completed via DM report! Score: {match['p1_name']} **{p1_score}** - **{p2_score}** {match['p2_name']}")
                        await thread.edit(archived=True, locked=True)
                except Exception:
                    pass
        else:
            await add_bot_feed(f"❌ Bot failed to auto-report match {set_id} via DM: {result.error_message}", "error")
            await message.channel.send(f"⚠️ Failed to report score to provider: {result.error_message}. Scores saved in hub; admin will verify.")
    else:
        await update_active_match(set_id, p1_score=p1_score, p2_score=p2_score)
        await add_bot_feed(f"📝 Score reported via DM for match {set_id}: {p1_score} - {p2_score} (Awaiting admin submit)", "info")
        await message.channel.send(f"✅ Scores saved: {p1_score} - {p2_score}. Awaiting admin submit or stream broadcast.")
        thread_id = match.get("discord_thread_id")
        if thread_id:
            try:
                thread = bot.get_channel(int(thread_id))
                if thread:
                    await thread.send(f"📝 Scores reported via DM: {match['p1_name']} **{p1_score}** - **{p2_score}** {match['p2_name']}. Awaiting admin verification.")
            except Exception:
                pass


async def handle_conflict_statement_dm(message) -> bool:
    """Capture a player's conflict statement DM; summarize once both have replied.

    Returns True if the DM was consumed (i.e. this player is in a conflicted match),
    so the caller skips the registration handler.
    """
    from core.database import (
        get_active_matches, get_conflict_by_set_id, update_conflict_claim,
        update_conflict_summary, add_bot_feed,
    )
    author_id = str(message.author.id)

    # Find a conflicted match this player belongs to.
    match, slot = None, None
    for m in await get_active_matches():
        if m.get("status") != "conflict":
            continue
        if str(m.get("p1_discord")) == author_id:
            match, slot = m, "p1"
            break
        if str(m.get("p2_discord")) == author_id:
            match, slot = m, "p2"
            break
    if not match:
        return False

    set_id = str(match.get("set_id"))
    conflict = await get_conflict_by_set_id(set_id)
    if not conflict:
        return False

    await update_conflict_claim(conflict["id"], slot, message.content.strip())
    await message.channel.send(
        "✅ Got it — your statement was sent to the tournament organizer. Thanks!"
    )

    # Re-fetch: once BOTH sides have spoken (and we haven't summarized yet), ask the LLM.
    conflict = await get_conflict_by_set_id(set_id)
    p1_claim = (conflict.get("p1_claim") or "").strip()
    p2_claim = (conflict.get("p2_claim") or "").strip()
    if p1_claim and p2_claim and not (conflict.get("ai_summary") or "").strip():
        summary = None
        try:
            from bot.agent.conflict_investigator import summarize_conflict
            summary = await summarize_conflict(
                match.get("p1_name") or "P1", p1_claim,
                match.get("p2_name") or "P2", p2_claim,
            )
        except Exception:
            summary = None
        if summary:
            await update_conflict_summary(conflict["id"], summary)
            await add_bot_feed(f"🕵️ AI conflict summary (set {set_id}): {summary}", "warn")
            try:
                from backend.api.ws_manager import manager as hub_mgr
                await hub_mgr.broadcast({"type": "match_update"})
            except Exception:
                pass
    return True



async def handle_match_state_update(message: discord.Message, new_state: dict, bot_instance: commands.Bot):
    """
    Process the new state of a match thread after a message is handled.
    Updates the match status (completed, conflict) based on the LLM evaluation.
    """
    status = new_state.get("match_status")
    reasoning = new_state.get("reasoning") or "(no reasoning provided)"

    if status == "completed":
        winner_id = new_state.get("winner_id")
        score = new_state.get("score_string")

        # ── LLM winner_id sanity check (cleanup #3) ──
        from core.database import (
            save_match_result, update_active_match, get_active_match,
            add_conflict, add_bot_feed,
        )
        set_id = new_state.get("set_id")
        match_details = await get_active_match(str(set_id)) if set_id else None
        valid_players = {
            str(match_details.get("p1_discord")) if match_details else None,
            str(match_details.get("p2_discord")) if match_details else None,
        }
        valid_players.discard(None)
        valid_players.discard("None")

        if not match_details or str(winner_id) not in valid_players:
            # Demote — do NOT touch start.gg with a bogus winner.
            await add_bot_feed(
                f"🚫 AI Referee rejected (set {set_id}): proposed winner "
                f"<{winner_id}> isn't a player in this match. Reasoning: {reasoning}",
                "warn",
            )
            if set_id:
                await add_conflict(
                    str(set_id),
                    "AI returned invalid winner_id",
                    f"LLM said winner=<{winner_id}>; players are {valid_players}",
                )
                await update_active_match(str(set_id), status="conflict")
            await message.channel.send(
                "⚠️ I parsed a result but the winner didn't match either player. "
                "Flagging for admin review."
            )
            return

        await message.channel.send(
            f"✅ **Match Completed!**\n"
            f"Winner: <@{winner_id}>\n"
            f"Score: {score}\n\n"
            "Locking this thread."
        )
        await message.channel.edit(archived=True, locked=True)

        p1_name = match_details.get("p1_name", "")
        p2_name = match_details.get("p2_name", "")
        tournament_slug = match_details.get("tournament_slug", "")
        stream_slot = match_details.get("station_id")
        round_name = match_details.get("round_name", "")

        p1_score = "0"
        p2_score = "0"
        if score and "-" in score:
            parts = score.split("-")
            if len(parts) == 2:
                p1_score, p2_score = parts[0].strip(), parts[1].strip()

        await save_match_result(
            set_id=str(set_id),
            tournament_slug=tournament_slug,
            stream_slot=stream_slot or "",
            p1_name=p1_name,
            p2_name=p2_name,
            winner=str(winner_id),
            p1_score=p1_score,
            p2_score=p2_score,
            round_name=round_name,
        )
        await update_active_match(str(set_id), status="complete")

        await add_bot_feed(
            f"🤖 AI Referee → completed (set {set_id}, {p1_score}-{p2_score}, "
            f"winner <@{winner_id}>). Reasoning: {reasoning}",
            "info",
        )
    elif status == "conflict":
        await message.channel.send(
            "⚠️ **Conflict Detected!**\n"
            "The reported scores do not match or a dispute was found. An Admin has been pinged."
        )
        from core.database import add_conflict, update_active_match, add_bot_feed, get_active_match
        set_id = new_state.get("set_id")
        if set_id:
            await add_conflict(str(set_id), "", "")
            await update_active_match(str(set_id), status="conflict")

            cmatch = await get_active_match(str(set_id))
            if cmatch:
                investigate_msg = (
                    "⚠️ **Score conflict on your match.**\n"
                    "Please reply to **this DM** with a brief explanation of what happened "
                    "(and a **screenshot of the final results screen** if you have one). "
                    "Your statement goes to the tournament organizer to settle the result."
                )
                for did in (cmatch.get("p1_discord"), cmatch.get("p2_discord")):
                    if did:
                        try:
                            player_user = await bot_instance.fetch_user(int(did))
                            if player_user:
                                await player_user.send(investigate_msg)
                        except Exception:
                            pass
                await message.channel.send(
                    "⚠️ Conflict flagged. I've DMed both players for their statements — "
                    "the TO will resolve this from the dashboard."
                )

        await add_bot_feed(
            f"⚠️ AI Referee → conflict (set {set_id}). Reasoning: {reasoning}",
            "warn",
        )

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Check if it's a DM
    if isinstance(message.channel, discord.DMChannel):
        if message.content.strip().lower().startswith("score "):
            await handle_score_report_dm(message)
            return
        # If this player is in a match flagged 'conflict', treat the DM as their
        # investigation statement rather than a registration message.
        if await handle_conflict_statement_dm(message):
            return
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
                    await handle_match_state_update(message, new_state, bot)

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

@tool
async def post_announcement_tool(announcement_text: str):
    """Announces a message to the public tournament channel on Discord. Use this to notify players about rounds, schedules, or updates."""
    from core.database import get_setting, get_connection
    channel_id = await get_connection("MATCH_CALL_CHANNEL_ID") or await get_setting("MATCH_CALL_CHANNEL_ID") or MATCH_CALL_CHANNEL_ID
    if not channel_id:
        return "Failed: MATCH_CALL_CHANNEL_ID is not configured in settings."
    channel = bot.get_channel(int(channel_id))
    if not channel:
        return f"Failed: Could not find channel with ID {channel_id}."
    await channel.send(announcement_text)
    return f"Announced successfully: '{announcement_text}'"

@tool
async def dq_player_tool(set_id: str, player_to_dq: str):
    """Disqualifies a player in an active match. player_to_dq can be 'p1', 'p2', or 'both'."""
    from core.database import get_active_match, update_active_match, add_bot_feed
    from core.startgg_client import get_client
    
    match = await get_active_match(set_id)
    if not match:
        return f"Failed: Active match with set ID {set_id} not found."
        
    p_to_dq = player_to_dq.lower().strip()
    if p_to_dq not in ["p1", "p2", "both"]:
        return "Failed: player_to_dq must be 'p1', 'p2', or 'both'."
        
    p1_entrant = match.get("p1_entrant_id")
    p2_entrant = match.get("p2_entrant_id")
    
    if p_to_dq == "both":
        sgg = get_client()
        res1 = await sgg.mark_set_dq(set_id, p1_entrant) if p1_entrant else False
        res2 = await sgg.mark_set_dq(set_id, p2_entrant) if p2_entrant else False
        if res1 and res2:
            await update_active_match(set_id, status="complete", p1_score=-1, p2_score=-1)
            await add_bot_feed(f"🤖 Agent DQ'd both players in match {set_id}", "success")
            return f"Successfully DQ'd both players in match {set_id}."
        return "Failed to disqualify both players on Start.gg."
    else:
        dq_entrant = p1_entrant if p_to_dq == "p1" else p2_entrant
        if not dq_entrant:
            return f"Failed: Entrant ID not found for {p_to_dq}."
        sgg = get_client()
        ok = await sgg.mark_set_dq(set_id, dq_entrant)
        if ok:
            winner_key = "p2" if p_to_dq == "p1" else "p1"
            p1_score = -1 if p_to_dq == "p1" else 0
            p2_score = -1 if p_to_dq == "p2" else 0
            await update_active_match(set_id, status="complete", p1_score=p1_score, p2_score=p2_score)
            await add_bot_feed(f"🤖 Agent DQ'd {p_to_dq} in match {set_id}", "success")
            return f"Successfully DQ'd player {p_to_dq} in match {set_id}."
        return "Failed to disqualify player on Start.gg."

@tool
async def force_score_tool(set_id: str, p1_score: int, p2_score: int):
    """Forces a specific score result for a match and reports it to Start.gg. Example: set_id='1234', p1_score=2, p2_score=0."""
    from core.database import get_active_match, update_active_match, add_bot_feed
    from core.providers.registry import get_provider_for_tournament
    from core.score_reporting import report_score_to_provider
    
    match = await get_active_match(set_id)
    if not match:
        return f"Failed: Match with set ID {set_id} not found."
        
    if p1_score == p2_score:
        return "Failed: Scores cannot be tied."
        
    winner_key = "p1" if p1_score > p2_score else "p2"
    winner_id = match.get(f"{winner_key}_entrant_id")
    if not winner_id:
        return "Failed: Winner entrant ID not found."
        
    provider = await get_provider_for_tournament(match.get('tournament_slug') or '')
    result = await report_score_to_provider(
        set_id=set_id,
        winner_id=winner_id,
        p1_id=match['p1_entrant_id'],
        p2_id=match['p2_entrant_id'],
        p1_score=p1_score,
        p2_score=p2_score,
        provider=provider
    )
    if not result.success:
        return f"Failed to report score to provider: {result.error_message}"
        
    await update_active_match(set_id, status="complete", p1_score=p1_score, p2_score=p2_score)
    await add_bot_feed(f"🤖 Agent forced score on match {set_id}: {p1_score}-{p2_score}", "success")
    return f"Successfully forced score {p1_score}-{p2_score} and completed match {set_id}."

@tool
async def reopen_match_tool(set_id: str):
    """Reopens or resets a match on Start.gg and resets its local database status back to 'called' / 'in_progress' so it can be re-played or re-reported."""
    from core.database import get_active_match, update_active_match, add_bot_feed
    from backend.core.startgg_client import get_client
    
    match = await get_active_match(set_id)
    if not match:
        return f"Failed: Active match with set ID {set_id} not found."
        
    sgg = get_client()
    ok = await sgg.reset_set(set_id)
    if ok:
        await update_active_match(set_id, status="in_progress", p1_score=0, p2_score=0)
        await add_bot_feed(f"🤖 Agent reopened match {set_id}", "success")
        return f"Successfully reopened match {set_id}."
    return "Failed to reset set on Start.gg."

hub_tools = [
    get_active_matches_tool,
    get_players_tool,
    create_discord_thread_tool,
    post_announcement_tool,
    dq_player_tool,
    force_score_tool,
    reopen_match_tool
]
hub_agent = build_hub_agent(hub_tools)  # fast-path: uses env key if present

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

    from core.database import get_setting, get_connection
    channel_id = await get_connection("MATCH_CALL_CHANNEL_ID") or await get_setting("MATCH_CALL_CHANNEL_ID") or MATCH_CALL_CHANNEL_ID
    if not channel_id:
        return "❌ MATCH_CALL_CHANNEL_ID not configured in .env or DB"

    channel = bot.get_channel(int(channel_id))
    if not channel:
        return f"❌ Could not find Discord channel with ID {channel_id}"

    # Send Arabic match call
    call_msg = f"📢 يرجى من اللاعبين **{p1}** و **{p2}** تأكيد الحضور للمباراة الخاصة بكم الآن."
    await channel.send(call_msg)

    return f"✅ Message sent to the public channel for {p1} and {p2}."


bot_ws: any = None  # Global bot websocket reference

async def ws_add_bot_feed(message: str, level: str = "info"):
    """Logs a message over the WebSocket connection to the API, falling back to local DB if disconnected."""
    global bot_ws
    print(f"[{level.upper()}] {message}")
    if bot_ws:
        try:
            import json
            await bot_ws.send(json.dumps({
                "type": "log",
                "message": message,
                "level": level
            }))
            return
        except Exception as e:
            # Clear reference on error to trigger fallback
            bot_ws = None
            print(f"[BOT] Failed to stream log over WS: {e}")
            
    # Fallback: Write directly to SQLite database
    try:
        from core.database import add_bot_feed as db_add_bot_feed
        await db_add_bot_feed(message, level)
    except Exception as e:
        print(f"[BOT] DB fallback logging failed: {e}")

async def handle_ws_command(cmd_text: str):
    """Executes a hub command directly from the WebSocket connection."""
    from langchain_core.messages import HumanMessage
    import time
    
    try:
        # Check for built-in commands first
        if cmd_text.strip().lower().startswith("msg "):
            result_text = await handle_msg_command(cmd_text.strip())
            await ws_add_bot_feed(f"🤖 {result_text}", "success")
            return

        if cmd_text.strip().lower().startswith("announce "):
            msg_to_send = cmd_text[9:].strip()
            from core.database import get_setting, get_connection
            channel_id = await get_connection("MATCH_CALL_CHANNEL_ID") or await get_setting("MATCH_CALL_CHANNEL_ID") or MATCH_CALL_CHANNEL_ID
            if channel_id:
                channel = bot.get_channel(int(channel_id))
                if channel:
                    await channel.send(msg_to_send)
                    await ws_add_bot_feed(f"📢 Announced to Discord: {msg_to_send}", "success")
                    return
            await ws_add_bot_feed("❌ Failed to announce: MATCH_CALL_CHANNEL_ID not set or channel not found", "error")
            return

        if cmd_text.strip().lower().startswith("call_match "):
            set_id = cmd_text.split(" ")[1].strip()
            from core.database import get_active_match, get_tournament
            match = await get_active_match(set_id)
            if match:
                t = await get_tournament(match['tournament_slug'])
                from bot.match_threads import create_match_thread
                await create_match_thread(bot, t, match)
                await ws_add_bot_feed(f"🤖 Created match thread for {match.get('p1_name')} vs {match.get('p2_name')}", "success")
            else:
                await ws_add_bot_feed(f"❌ call_match failed: Match {set_id} not found", "error")
            return

        if cmd_text.strip().lower().startswith("dm_score_request "):
            set_id = cmd_text.split(" ")[1].strip()
            from core.database import get_active_match
            match = await get_active_match(set_id)
            if match:
                await send_score_report_dms(bot, match)
            return

        if cmd_text.strip().lower().startswith("apply_verified_role "):
            parts = cmd_text.split(" ", 2)
            if len(parts) < 2:
                return
            discord_id = parts[1].strip()
            gamer_tag = parts[2].strip() if len(parts) > 2 else None
            applied_in = 0
            for guild in bot.guilds:
                try:
                    member = guild.get_member(int(discord_id))
                    if not member:
                        try:
                            member = await guild.fetch_member(int(discord_id))
                        except Exception:
                            continue
                    role = discord.utils.get(guild.roles, name="Verified Player")
                    if not role:
                        try:
                            role = await guild.create_role(name="Verified Player", reason="FNC Hub verified")
                        except discord.Forbidden:
                            role = None
                    if role and role not in member.roles:
                        try:
                            await member.add_roles(role, reason="start.gg OAuth verified")
                        except discord.Forbidden:
                            pass
                    if gamer_tag and member.nick != gamer_tag:
                        try:
                            await member.edit(nick=gamer_tag[:32], reason="start.gg gamerTag sync")
                        except discord.Forbidden:
                            pass
                    applied_in += 1
                except Exception as e:
                    print(f"apply_verified_role guild {guild.id} failed: {e}")
            await ws_add_bot_feed(
                f"🎟️ Applied Verified role to {discord_id} in {applied_in} guild(s)",
                "success" if applied_in else "warn"
            )
            return

        # General Hub Agent NLP fallback
        if hub_agent:
            await ws_add_bot_feed(f"🧠 Hub Agent processing: '{cmd_text}'", "info")
            
            from core.database import get_setting as db_get_setting
            custom_prompt = await db_get_setting("bot_system_prompt")
            messages = [HumanMessage(content=cmd_text)]
            if custom_prompt:
                messages.insert(0, HumanMessage(content=f"INSTRUCTION: {custom_prompt}"))
                
            config = {"configurable": {"thread_id": f"hub_ws_{int(time.time())}"}}
            response = await hub_agent.ainvoke({"messages": messages}, config)
            raw_content = response["messages"][-1].content
            ai_msg = extract_text_from_response(raw_content)
            
            # Send final response over the WS as an agent_response type!
            if bot_ws:
                try:
                    import json
                    await bot_ws.send(json.dumps({
                        "type": "agent_response",
                        "response": ai_msg,
                        "command": cmd_text
                    }))
                except Exception as e:
                    print(f"Error sending agent_response: {e}")
                    
            await ws_add_bot_feed(f"🤖 Hub Agent: {ai_msg}", "success")
        else:
            await ws_add_bot_feed("❌ Command ignored: Hub Agent not initialized", "error")
            
    except Exception as e:
        print(f"WS Command execution error: {e}")
        await ws_add_bot_feed(f"❌ Error executing command '{cmd_text}': {e}", "error")

async def bot_ws_listener():
    """Maintains a persistent, stateful WebSocket connection to the Hub API."""
    global bot_ws
    import websockets
    import json
    ws_url = f"{API_BASE_URL_ENV.replace('http://', 'ws://').replace('https://', 'wss://')}/ws/bot"
    
    while True:
        try:
            async with websockets.connect(ws_url) as ws:
                bot_ws = ws
                await ws_add_bot_feed("🤖 Discord Bot is online and connected to Hub API!", "success")
                
                # Start a simple ping task to keep connection alive
                async def ping_loop():
                    while True:
                        try:
                            await ws.send(json.dumps({"type": "ping"}))
                            await asyncio.sleep(15)
                        except Exception:
                            break
                asyncio.create_task(ping_loop())
                
                while True:
                    data = await ws.recv()
                    msg = json.loads(data)
                    if msg.get("type") == "command":
                        cmd_text = msg.get("command")
                        if cmd_text:
                            # Run immediately inside an isolated task
                            asyncio.create_task(handle_ws_command(cmd_text))
        except Exception as e:
            bot_ws = None
            print(f"[BOT] WebSocket connection failed: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    if TOKEN and TOKEN != "your_discord_bot_token_here":
        bot.run(TOKEN)
    else:
        print("Warning: DISCORD_BOT_TOKEN not found or is default. Please update .env")

