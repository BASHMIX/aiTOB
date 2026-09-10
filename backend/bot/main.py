import discord
from discord.ext import commands, tasks
import logging
import os
from dotenv import load_dotenv
import asyncio
from langchain_core.tools import tool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import sys
# Add project root and backend to sys.path
root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(root)
sys.path.append(os.path.join(root, "backend"))
from core.database import init_db, create_or_update_player, get_player
from bot.registration import registration_manager, finalize_verification
from bot.messages import get_msg
from bot.agent.graph import app
from bot.runtime_logging import console_message, ready_message

load_dotenv()

TOKEN = None
ACTIVE_DISCORD_ACCOUNT_ID = None
ACTIVE_DISCORD_WORKSPACE_ID = None
# Credentials are fetched from the encrypted account store at process startup.
API_BASE_URL_ENV = os.getenv("API_BASE_URL", "http://localhost:8000")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

from backend.core.runtime_tasks import RuntimeTasks
_runtime_tasks = RuntimeTasks()
_hub_listener_task = None


class TournamentBot(commands.Bot):
    async def close(self):
        from core.database import set_hub_command_listener
        set_hub_command_listener(None)
        loops = (auto_dispatch_pool_matches, drain_hub_commands, drain_workflow_outbox)
        pending = [loop.get_task() for loop in loops if loop.get_task() is not None]
        for loop in loops:
            loop.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        await _runtime_tasks.close()
        await super().close()


bot = TournamentBot(command_prefix="!", intents=intents)

# Result Claims are not available yet. A Discord message may never be treated as
# an authoritative score, regardless of whether it contains a strict command or
# an LLM can parse it. The organizer's authenticated Hub controls remain the
# only supported result entry path until that durable review workflow exists.
PLAYER_RESULT_ORGANIZER_MESSAGE = (
    "Match results are confirmed by the tournament organizer in aiTOB. "
    "Please contact the organizer with the score; this message does not submit or save a result."
)
AI_RESULT_MUTATION_BLOCKED_MESSAGE = (
    "AI cannot submit or complete match results. Use the authorized organizer controls in aiTOB."
)
AI_DQ_MUTATION_BLOCKED_MESSAGE = (
    "AI cannot disqualify players. Use the authorized organizer DQ control for one player."
)
AI_ANNOUNCEMENT_MUTATION_BLOCKED_MESSAGE = (
    "AI cannot send announcements. Create an organizer-approved announcement proposal instead."
)
AI_REOPEN_MUTATION_BLOCKED_MESSAGE = (
    "AI cannot reopen matches. Use the authorized organizer controls in aiTOB."
)

@bot.event
async def on_ready():
    global _hub_listener_task
    await init_db()
    print(ready_message())

    # Cutover/recovery starts the bot in a connectivity-only mode first.  Do
    # not attach listeners, drain queues, restore Discord views, or sync slash
    # commands until the operator explicitly resumes workers.  Login itself is
    # still allowed so the selected account can be health-checked.
    if os.getenv("AITOB_DISABLE_BACKGROUND_WORKERS", "").strip().lower() in {"1", "true", "yes", "on"}:
        print("[BOT] Background workers paused by AITOB_DISABLE_BACKGROUND_WORKERS")
        return
    
    # Start background WebSocket listener for real-time Hub commands & log streaming
    if _hub_listener_task is None or _hub_listener_task.done():
        _hub_listener_task = _runtime_tasks.start(bot_ws_listener())
    
    if not auto_dispatch_pool_matches.is_running():
        auto_dispatch_pool_matches.start()

    # Event-driven hub-command outbox: register the in-process listener (fires on
    # bot-side enqueues) and start the 60s fallback sweeper. API-side enqueues
    # arrive as {"type":"drain"} nudges over the bot WS (handled below).
    from core.database import set_hub_command_listener
    set_hub_command_listener(_on_hub_command_enqueued)
    if not drain_hub_commands.is_running():
        drain_hub_commands.start()
    # Phase 7A: the durable local-effect dispatcher is deliberately opt-in.
    # With its flag disabled the legacy Start.gg bot path remains untouched.
    from backend.core.provider_feature_flags import get_provider_feature_flags
    if get_provider_feature_flags().challonge_local_workflow_enabled and not drain_workflow_outbox.is_running():
        drain_workflow_outbox.start()
    if get_provider_feature_flags().challonge_local_workflow_enabled:
        from backend.bot.match_threads import restore_ready_check_views
        restored_ready_views = await restore_ready_check_views(
            bot, workspace_id=ACTIVE_DISCORD_WORKSPACE_ID,
        )
        if restored_ready_views:
            await ws_add_bot_feed(f"Restored {restored_ready_views} persisted Challonge Ready view(s)", "info")
    # Drain anything queued before the bot came online.
    _runtime_tasks.start(run_drain())

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


def _map_discord_locale(locale) -> str:
    """Map Discord's native interaction locale to a bot-supported language.

    Discord sends locales like 'en-US', 'en-GB', 'ar', etc. We only support
    Arabic and English, so anything Arabic-ish maps to 'ar' and everything
    else defaults to 'en'. Capturing this from `interaction.locale` replaces
    the language-selection DM that only the OAuth (Path A) flow used to run.
    """
    code = str(locale or "").lower()
    if code.startswith("ar"):
        return "ar"
    return "en"


async def _avatar_display_url(avatar: str | None) -> str | None:
    """Resolve a stored avatar (local path or URL) to a public URL for embeds.

    Locally-saved avatars live under backend/api/static/avatars and are served
    at {API_BASE_URL}/static/avatars/<file>. Already-absolute URLs pass through.
    """
    if not avatar:
        return None
    if avatar.startswith("http://") or avatar.startswith("https://"):
        return avatar
    from core.database import get_connection
    api_base = await get_connection("API_BASE_URL", API_BASE_URL_ENV)
    base = os.path.basename(avatar)
    return f"{api_base.rstrip('/')}/static/avatars/{base}"


async def _finalize_or_request_cfn(
    discord_id: str,
    gamer_tag: str | None,
    lang: str,
    *,
    followup,
    done_msg: str,
    avatar_path: str | None = None,
):
    """Gate point shared by all Path-B avatar finalization callbacks.

    If the player already has a cfn_id (pre-fetched from start.gg at verify-confirm),
    call finalize_verification immediately and send done_msg via the interaction followup.
    If CFN is still missing, park the player in cfn_pending, DM the prompt, and send
    a holding reply via the followup so the interaction doesn't expire silently.
    """
    from core.database import get_player, create_or_update_player, sync_player_cfns_to_matches
    player = await get_player(discord_id)
    cfn_id = (player or {}).get("cfn_id")
    if not cfn_id:
        await create_or_update_player(discord_id, registration_step="cfn_pending")
        try:
            member = await bot.fetch_user(int(discord_id))
            await member.send(get_msg("cfn_post_verify_prompt", lang))
        except Exception:
            pass
        await followup.send(
            "✅ Avatar confirmed! Check your DMs — one last step to complete registration.",
            ephemeral=True,
        )
        return
    await finalize_verification(discord_id, gamer_tag, avatar_path)
    await followup.send(done_msg, ephemeral=True)


class BroadcastAvatarView(discord.ui.View):
    """Returning-player avatar gate shown after a successful bio-code match.

    [Keep Existing Avatar] finalizes verification with the on-file image.
    [Upload New Avatar] parks the player in the `avatar_upload` state so their
    next DM'd photo is validated and saved before verification completes.
    """

    def __init__(self, discord_id: str, gamer_tag: str | None, lang: str = "en"):
        super().__init__(timeout=600)
        self.discord_id = str(discord_id)
        self.gamer_tag = gamer_tag
        self.lang = lang

        keep_btn = discord.ui.Button(
            label=get_msg("avatar_keep_btn", lang) or "Keep Existing Avatar",
            style=discord.ButtonStyle.success,
            custom_id="bcast_keep",
        )
        keep_btn.callback = self._keep
        self.add_item(keep_btn)

        new_btn = discord.ui.Button(
            label=get_msg("avatar_upload_btn", lang) or "Upload New Avatar",
            style=discord.ButtonStyle.primary,
            custom_id="bcast_new",
        )
        new_btn.callback = self._upload_new
        self.add_item(new_btn)

    async def _guard(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.discord_id:
            await interaction.response.send_message(
                get_msg("not_your_buttons", self.lang) or "These buttons aren't for you.",
                ephemeral=True,
            )
            return False
        return True

    async def _disable_all(self, interaction: discord.Interaction):
        for c in self.children:
            c.disabled = True
        try:
            await interaction.response.edit_message(view=self)
        except Exception:
            pass

    async def _keep(self, interaction: discord.Interaction):
        if not await self._guard(interaction):
            return
        await self._disable_all(interaction)
        await _finalize_or_request_cfn(
            self.discord_id, self.gamer_tag, self.lang,
            followup=interaction.followup,
            done_msg=get_msg("avatar_kept_done", self.lang, gamer_tag=self.gamer_tag or "")
                     or f"✅ Verified as **{self.gamer_tag}** with your existing avatar.",
        )

    async def _upload_new(self, interaction: discord.Interaction):
        if not await self._guard(interaction):
            return
        from core.database import create_or_update_player
        await create_or_update_player(self.discord_id, registration_step="avatar_upload")
        await self._disable_all(interaction)
        await interaction.followup.send(
            get_msg("avatar_send_new", self.lang)
            or "📸 Sure — please DM me a new photo and I'll set it as your broadcast avatar.",
            ephemeral=True,
        )


class NewAvatarPromptView(discord.ui.View):
    """Soft-gate prompt for a brand-new bio-verified player.

    The DM-upload path is still the happy route, but [Skip for Now] lets the
    player finalize verification with NO avatar on file so they're immediately
    safe to be auto-dispatched off-stream. They can backfill later via /avatar.
    """

    def __init__(self, discord_id: str, gamer_tag: str | None, lang: str = "en"):
        super().__init__(timeout=600)
        self.discord_id = str(discord_id)
        self.gamer_tag = gamer_tag
        self.lang = lang

        skip_btn = discord.ui.Button(
            label=get_msg("avatar_skip_btn", lang) or "Skip for Now",
            style=discord.ButtonStyle.secondary,
            custom_id="bcast_skip",
        )
        skip_btn.callback = self._skip
        self.add_item(skip_btn)

    async def _skip(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.discord_id:
            await interaction.response.send_message(
                get_msg("not_your_buttons", self.lang) or "These buttons aren't for you.",
                ephemeral=True,
            )
            return
        for c in self.children:
            c.disabled = True
        try:
            await interaction.response.edit_message(view=self)
        except Exception:
            pass
        # Finalize WITHOUT an avatar — role applied, avatar_path left NULL.
        await _finalize_or_request_cfn(
            self.discord_id, self.gamer_tag, self.lang,
            followup=interaction.followup,
            done_msg=(
                get_msg("avatar_skipped", self.lang)
                or "✅ Verification complete! Remember to upload your avatar later using "
                   "the `/avatar` command before the broadcast begins."
            ),
        )


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
        increment_verification_attempts, create_or_update_player,
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

    # Account control proven. Extract gamerTag and link the start.gg identity —
    # but DO NOT finalize verification yet. For broadcast we require a player
    # avatar on file, so we gate `is_verified` behind avatar collection below.
    sgg_user_id = str(user.get("id"))
    player_node = user.get("player") or {}
    gamer_tag = player_node.get("gamerTag")

    # Path B skips the language-selection DM that Path A ran, so derive the
    # player's language from Discord's native interaction locale instead.
    lang_pref = _map_discord_locale(interaction.locale)

    # Capture any existing broadcast avatar BEFORE writing, so we can tell a brand
    # new player (no avatar → must upload) from a returning one (keep / replace).
    existing_player = await get_player(discord_id)
    existing_avatar = (existing_player or {}).get("avatar_path")

    # Attempt to pre-fetch CFN from start.gg so the player never has to type it.
    # connectedAccounts.capcom.value holds the CFN if they linked Capcom on start.gg.
    cfn_from_sgg: str | None = None
    try:
        from core.database import get_all_tournament_slugs
        # Registration is a bot worker operation, not an HTTP request.  If the
        # Discord identity is already owned, keep the CFN lookup inside that
        # durable workspace; never enumerate another tenant's tournaments.
        slugs = await get_all_tournament_slugs((existing_player or {}).get("workspace_id"))
        if slugs:
            cfn_from_sgg = await sgg.fetch_user_cfn(sgg_user_id, slugs)
    except Exception as _cfn_err:
        pass  # Non-fatal: cfn_pending DM flow handles the gap

    # Persist identity + language FIRST — before the avatar_upload state or any DM — so
    # every subsequent prompt (and future match threads) speaks their language.
    player_fields = dict(
        startgg_id=sgg_user_id,
        gamer_tag=gamer_tag,
        preferred_language=lang_pref,
        registration_step="avatar_upload",
    )
    if cfn_from_sgg:
        player_fields["cfn_id"] = cfn_from_sgg
    await create_or_update_player(discord_id=discord_id, **player_fields)
    if cfn_from_sgg:
        from core.database import sync_player_cfns_to_matches
        await sync_player_cfns_to_matches(discord_id, (existing_player or {}).get("workspace_id"))
    await delete_pending_verification(discord_id)
    await add_bot_feed(
        f"🔗 Bio-code matched: Discord <{discord_id}> ↔ start.gg user {sgg_user_id} "
        f"({gamer_tag}, lang={lang_pref}). Awaiting broadcast avatar.",
        "info",
    )

    if existing_avatar:
        # Returning player — confirm or replace their on-file avatar.
        display_url = await _avatar_display_url(existing_avatar)
        embed = discord.Embed(
            title=get_msg("bio_confirmed_title", lang_pref),
            description=get_msg("bio_confirmed_desc", lang_pref, gamer_tag=gamer_tag or ""),
            color=discord.Color.blue(),
        )
        if display_url:
            embed.set_image(url=display_url)
        view = BroadcastAvatarView(discord_id, gamer_tag, lang_pref)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    else:
        # New player — prompt for an avatar, but SOFT-GATE it: a [Skip for Now]
        # button finalizes verification immediately (role applied, avatar NULL) so
        # the auto-dispatcher never DQs an otherwise-ready player. The avatar is a
        # broadcast nicety they can add later via /avatar.
        view = NewAvatarPromptView(discord_id, gamer_tag, lang_pref)
        await interaction.followup.send(
            get_msg("bio_confirmed_new", lang_pref, gamer_tag=gamer_tag or ""),
            view=view,
            ephemeral=True,
        )


@bot.tree.command(name="register", description="Alias for /verify")
@discord.app_commands.describe(profile="Your start.gg profile URL or slug (optional)")
async def register_command(interaction: discord.Interaction, profile: str | None = None):
    await verify_command.callback(interaction, profile)  # type: ignore[attr-defined]


@bot.tree.command(name="avatar", description="Upload or update your broadcast avatar")
async def avatar_command(interaction: discord.Interaction):
    """Re-enter the broadcast-avatar upload state at any time.

    Idempotent: an already-verified player can run this to backfill or replace
    their avatar without affecting their verified status. The next photo they
    DM the bot flows through the existing _handle_broadcast_avatar_step pipeline.
    """
    from core.database import get_player, create_or_update_player
    discord_id = str(interaction.user.id)
    player = await get_player(discord_id)

    # Prefer the player's stored language; otherwise derive (and persist) it.
    lang = (player or {}).get("preferred_language") or _map_discord_locale(interaction.locale)

    # Require a linked start.gg identity — the avatar upload finalizes verification,
    # so we don't want it to verify someone who never proved account control.
    if not player or not player.get("startgg_id"):
        await interaction.response.send_message(
            get_msg("avatar_need_verify", lang)
            or "Please run `/verify` to link your start.gg account first.",
            ephemeral=True,
        )
        return

    fields = {"registration_step": "avatar_upload"}
    if not (player or {}).get("preferred_language"):
        fields["preferred_language"] = lang
    await create_or_update_player(discord_id, **fields)

    await interaction.response.send_message(
        get_msg("avatar_cmd_prompt", lang)
        or "📸 Please **DM me a photo** (min 500x500, square-ish) to set as your broadcast avatar.",
        ephemeral=True,
    )


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
    """Reject implicit name matching; identity links require an explicit proof."""
    await interaction.response.send_message(
        "For safety, aiTOB does not match Discord identities by name. Use "
        "`/verify profile:<your start.gg URL>` or an organizer-confirmed entrant link.",
        ephemeral=True,
    )

@tasks.loop(seconds=10.0)
async def update_heartbeat():
    from core.database import set_setting
    import time
    await set_setting("bot_last_seen", str(time.time()))


@tasks.loop(seconds=20.0)
async def auto_dispatch_pool_matches():
    """Run deterministic policy/service work; no AI, provider, or station calls."""
    from backend.core.auto_dispatcher import AutoDispatcherService
    from backend.core.database import set_setting
    from datetime import UTC, datetime

    # Lets the Hub distinguish a saved ON setting from a running dispatcher.
    await set_setting("auto_dispatcher_last_seen", datetime.now(UTC).isoformat())
    await AutoDispatcherService(workspace_id=ACTIVE_DISCORD_WORKSPACE_ID).run_once()


# ── Hub-command drain (event-driven outbox) ──────────────────────────────
# add_hub_command() writes rows to the hub_commands queue from BOTH the API
# (the "Call Match" button, role grants) and the in-process auto-dispatcher.
# The queue is the durable record; delivery is EVENT-DRIVEN, not polled:
#   • API enqueue → API fires a {"type":"drain"} nudge over the bot WS → run_drain()
#   • Bot enqueue (dispatcher / transition_match) → in-process listener → run_drain()
#   • drain_hub_commands (below) is only a 60s safety-net sweeper.
# Without draining, queued commands (call_match, dm_score_request,
# apply_verified_role) never execute and the bot looks "silent". The _drain_lock
# serializes overlapping triggers and claim-before-run prevents double execution.
_drain_lock = asyncio.Lock()

async def run_drain():
    """Execute every pending hub command once, in order. Safe to call from any
    trigger (WS nudge, in-process listener, fallback sweeper) — the lock serializes
    and 'processing' claims guard against double execution."""
    from core.database import claim_pending_hub_commands, finish_hub_command
    lease_owner = f"discord-bot:{os.getpid()}"
    async with _drain_lock:
        try:
            # The bot process is bound to exactly one Discord integration
            # account at startup. Resolve its workspace once and constrain the
            # queue claim itself; filtering after a global claim is too late
            # because it temporarily leases another tenant's command.
            pending = await claim_pending_hub_commands(
                lease_owner, workspace_id=ACTIVE_DISCORD_WORKSPACE_ID,
            )
        except Exception as e:
            print(f"[BOT] drain fetch failed: {e}")
            return
        for row in pending:
            cmd_id = row.get("id")
            cmd_text = row.get("command_text")
            if not cmd_text:
                await finish_hub_command(cmd_id, lease_owner, "done")
                continue
            try:
                await handle_ws_command(cmd_text, workspace_id=row.get("workspace_id"))
                await finish_hub_command(cmd_id, lease_owner, "done")
            except Exception as e:
                await finish_hub_command(cmd_id, lease_owner, "error", "Command execution failed")
                print(f"[BOT] hub command {cmd_id} failed")


@tasks.loop(seconds=60.0)
async def drain_hub_commands():
    """Fallback sweeper only — catches anything queued while the bot's WS was down
    (e.g. an API enqueue that couldn't be nudged). The primary path is event-driven."""
    await run_drain()


async def _dispatch_workflow_outbox_event(event: dict):
    """Bot-owned external effects. The worker marks completion only after this returns."""
    from backend.core.database import get_active_match, get_tournament

    event_type = event["event_type"]
    # Tournament-wide announcement drafts are intentionally delivered by the
    # durable outbox, never by an Assistant/tool call.  They may not have a
    # concrete match row, so handle them before the match-specific paths.
    if event_type == "discord_announcement":
        payload = event.get("payload") or {}
        tournament = await get_tournament(
            str(payload.get("tournament_slug") or ""), event.get("workspace_id")
        )
        account_id = (tournament or {}).get("discord_account_id")
        if account_id and ACTIVE_DISCORD_ACCOUNT_ID and account_id != ACTIVE_DISCORD_ACCOUNT_ID:
            raise RuntimeError("Workflow event belongs to a different Discord account.")
        if not account_id:
            raise RuntimeError("Tournament has no Discord account destination.")
        from backend.core.integrations import get_destination
        destination = await get_destination(account_id, "match_call_channel")
        if not destination:
            raise RuntimeError("Discord announcement destination is not configured.")
        channel = bot.get_channel(int(destination["external_id"]))
        if not channel:
            raise RuntimeError("Discord announcement channel is unavailable.")
        await channel.send(str(payload.get("text") or ""))
        return

    match = await get_active_match(event["match_id"], event.get("workspace_id"))
    if not match:
        return
    tournament = await get_tournament(
        match.get("tournament_slug") or "", match.get("workspace_id") or event.get("workspace_id")
    )
    account_id = (tournament or {}).get("discord_account_id")
    if account_id and ACTIVE_DISCORD_ACCOUNT_ID and account_id != ACTIVE_DISCORD_ACCOUNT_ID:
        # A separate bot process owns the other Discord account. Do not leak a
        # destination across accounts; the durable outbox will wait safely.
        raise RuntimeError("Workflow event belongs to a different Discord account.")
    if event_type == "discord_call":
        # A pre-existing thread is the durable idempotency proof after a restart.
        if match.get("discord_thread_id"):
            return
        from backend.bot.match_threads import create_match_thread
        await create_match_thread(
            bot,
            await get_tournament(match.get("tournament_slug") or "", match.get("workspace_id")),
            match,
        )
        return
    if event_type == "discord_ready" and match.get("discord_thread_id"):
        thread = bot.get_channel(int(match["discord_thread_id"]))
        if thread:
            player = (event.get("payload") or {}).get("player", "player")
            await thread.send(f"✅ {player.upper()} readiness recorded.")
        return
    if event_type in {"obs_match_started", "obs_station_assigned", "obs_match_complete"}:
        # Overlay state is already durable in SQLite; notify the Hub/OBS bridge
        # only after the outbox item has been claimed by this bot process.
        await ws_add_bot_feed(f"Workflow effect applied: {event_type} for {event['match_id']}", "info")
        return
    if event_type == "discord_match_complete" and match.get("discord_thread_id"):
        thread = bot.get_channel(int(match["discord_thread_id"]))
        if thread:
            await thread.send("✅ Match completion was verified by aiTOB.")


@tasks.loop(seconds=5.0)
async def drain_workflow_outbox():
    """Retry local Discord/OBS effects without polling a tournament provider."""
    from backend.core.workflow_outbox import WorkflowOutboxWorker

    worker = WorkflowOutboxWorker(_dispatch_workflow_outbox_event)
    await worker.run_once()


def _on_hub_command_enqueued():
    """In-process listener: a command was just queued in the BOT process (dispatcher,
    transition_match). Drain immediately; the lock coalesces with any WS-nudged drain."""
    try:
        _runtime_tasks.start(run_drain())
    except RuntimeError:
        pass  # no running loop yet (import time) — the 60s sweeper will catch it


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
        "Please coordinate and play your match. When it ends, contact the tournament organizer "
        "with the result; aiTOB does not accept or submit player-reported scores in Discord yet."
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
    matches = await get_active_matches(workspace_id=ACTIVE_DISCORD_WORKSPACE_ID)
    
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
    match = await get_active_match(set_id, ACTIVE_DISCORD_WORKSPACE_ID)
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
    """Explain that player score commands are disabled until Result Claims exist."""
    await ctx.send(PLAYER_RESULT_ORGANIZER_MESSAGE)


async def send_score_report_dms(bot, match):
    p1_discord = match.get("p1_discord")
    p2_discord = match.get("p2_discord")
    workspace_id = match.get("workspace_id")
    if not p1_discord and match.get("p1_entrant_id"):
        from bot.match_threads import get_discord_id_from_startgg
        p1_discord = await get_discord_id_from_startgg(match.get("p1_entrant_id"), workspace_id)
    if not p2_discord and match.get("p2_entrant_id"):
        from bot.match_threads import get_discord_id_from_startgg
        p2_discord = await get_discord_id_from_startgg(match.get("p2_entrant_id"), workspace_id)
    p1_name = match.get("p1_name", "TBD")
    p2_name = match.get("p2_name", "TBD")
    set_id = match.get("set_id")
    if p1_discord:
        try:
            member = await bot.fetch_user(int(p1_discord))
            embed = discord.Embed(
                title="Match Result Confirmation",
                description=(
                    f"Your match against **{p2_name}** is in progress.\n\n"
                    "When it ends, contact the tournament organizer with the result. "
                    "aiTOB will not accept or submit a result from a player DM yet."
                ),
                color=discord.Color.blue()
            )
            await member.send(embed=embed)
        except Exception as e:
            print(f"Failed to DM P1 ({p1_discord}): {e}")
    if p2_discord:
        try:
            member = await bot.fetch_user(int(p2_discord))
            embed = discord.Embed(
                title="Match Result Confirmation",
                description=(
                    f"Your match against **{p1_name}** is in progress.\n\n"
                    "When it ends, contact the tournament organizer with the result. "
                    "aiTOB will not accept or submit a result from a player DM yet."
                ),
                color=discord.Color.blue()
            )
            await member.send(embed=embed)
        except Exception as e:
            print(f"Failed to DM P2 ({p2_discord}): {e}")


async def _llm_extract_dm_score(message_content: str, match: dict, discord_id: str) -> tuple[int, int] | None:
    """Disabled pending durable Result Claims and organizer review.

    Kept as a compatibility stub so accidental callers cannot re-enable a
    player-to-provider mutation by merely restoring a parsing prompt.
    """
    return None


async def handle_score_report_dm(message: discord.Message):
    """Reject player result input without parsing, storing, or forwarding it."""
    await message.channel.send(PLAYER_RESULT_ORGANIZER_MESSAGE)


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
    for m in await get_active_matches(workspace_id=ACTIVE_DISCORD_WORKSPACE_ID):
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
    """Keep legacy AI-referee output from changing tournament state.

    Before durable Result Claims exist, a model result is neither evidence nor an
    approval. This compatibility boundary intentionally does not read a match,
    create a conflict, send a provider mutation, archive a thread, or write any
    local score/status.
    """
    if new_state.get("match_status") in {"completed", "conflict"}:
        await message.channel.send(PLAYER_RESULT_ORGANIZER_MESSAGE)

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

    # A match thread remains available for player communication and the explicit
    # Ready button, but the legacy AI Referee must not infer or act on a result.
    if isinstance(message.channel, discord.Thread):
        if message.content.strip().lower().startswith("score "):
            await message.channel.send(PLAYER_RESULT_ORGANIZER_MESSAGE)
            return

    await bot.process_commands(message)

# ── Legacy Bot Helpers ────────────────────────────────────────────────────
# Organizer Assistant execution moved to backend.core.ai_service. These legacy
# helpers are not an execution channel for score or DQ mutations.

@tool
async def get_active_matches_tool():
    """Returns active/called matches as JSON. Use the `set_id` field (NOT any
    thread id) when reporting scores, DQ'ing, or calling a match."""
    import json
    from core.database import get_active_matches
    from bot.agent.tool_helpers import project_match_for_agent
    matches = await get_active_matches(workspace_id=ACTIVE_DISCORD_WORKSPACE_ID)
    return json.dumps([project_match_for_agent(m) for m in matches])

@tool
async def get_players_tool():
    """Returns a list of all registered players and their Discord IDs."""
    # This read-only legacy tool is retained for compatibility, but it must go
    # through the repository boundary so PostgreSQL is used at runtime.  The
    # assistant process is bound to one integration workspace; omitting that
    # scope would expose every tenant's player projection to a read-only tool.
    from core.database import get_players_for_workspace
    return str(await get_players_for_workspace(ACTIVE_DISCORD_WORKSPACE_ID))

@tool
async def call_match_tool(set_id: str = "", p1_discord_id: str = "", p2_discord_id: str = ""):
    """Legacy AI entrypoint retained as a hard non-execution boundary."""
    return "AI cannot call matches. Use the authorized organizer Call control in aiTOB."

@tool
async def post_announcement_tool(announcement_text: str):
    """Legacy AI tool: announcements require an organizer-approved proposal."""
    return AI_ANNOUNCEMENT_MUTATION_BLOCKED_MESSAGE

@tool
async def dq_player_tool(set_id: str, player_to_dq: str):
    """Legacy AI tool retained only to return an explicit no-execution result."""
    return AI_DQ_MUTATION_BLOCKED_MESSAGE

@tool
async def force_score_tool(set_id: str, p1_score: int, p2_score: int):
    """Legacy AI tool retained only to return an explicit no-execution result."""
    return AI_RESULT_MUTATION_BLOCKED_MESSAGE

@tool
async def reopen_match_tool(set_id: str):
    """Legacy AI tool: reopening is an organizer-only workflow action."""
    return AI_REOPEN_MUTATION_BLOCKED_MESSAGE

async def _tournament_discord_ids(tournament_slug: str) -> set[str]:
    """Discord IDs currently appearing in a tournament's synced matches.

    Used to scope the avatar reminder to one tournament. We key off the
    sync-engine-resolved p1_discord/p2_discord on active_matches (reliable
    linkage) rather than the entrant/user-id ambiguity in raw_data.
    """
    from core.database import get_active_matches, get_tournament_workspace_id
    workspace_id = await get_tournament_workspace_id(tournament_slug)
    ids: set[str] = set()
    for m in await get_active_matches(tournament_slug, workspace_id=workspace_id):
        for k in ("p1_discord", "p2_discord"):
            v = m.get(k)
            if v:
                ids.add(str(v))
    return ids


@tool
async def audit_registration_tool(tournament_slug: str = None):
    """Chase down verified players who are missing an avatar, a CFN ID, or both.

    Use this when you want to remind players to complete their profile before the
    bracket starts. The tool sends a targeted DM for each missing item — avatar-only
    players get the avatar reminder, CFN-only players get the CFN reminder, and
    players missing both get a combined message. Pass `tournament_slug` to scope the
    audit to players in that tournament's synced matches; omit it to audit all tracked
    tournaments. Returns a human-readable summary of what was sent.
    """
    from core.database import get_verified_players_missing_profile, add_bot_feed

    from core.database import get_tournament_workspace_id
    workspace_id = await get_tournament_workspace_id(tournament_slug) if tournament_slug else None
    players = await get_verified_players_missing_profile(workspace_id)
    if not players:
        return "All verified players have a complete profile (avatar + CFN ID) — nobody to remind."

    scope_label = ""
    if tournament_slug:
        scoped_ids = await _tournament_discord_ids(tournament_slug)
        players = [p for p in players if str(p.get("discord_id")) in scoped_ids]
        scope_label = f" in '{tournament_slug}'"
        if not players:
            return (
                f"No verified players with incomplete profiles are in synced matches{scope_label}. "
                "(Only players already placed in the bracket can be scoped by tournament.)"
            )

    sent_avatar, sent_cfn, sent_both, failed = 0, 0, 0, 0
    for p in players:
        did = p.get("discord_id")
        lang = p.get("preferred_language") or "en"
        if not did:
            continue
        missing_avatar = not (p.get("avatar_path") or "")
        missing_cfn = not (p.get("cfn_id") or "")
        try:
            member = await bot.fetch_user(int(did))
            if missing_avatar and missing_cfn:
                combined = (
                    get_msg("avatar_reminder_dm", lang)
                    + "\n\n"
                    + get_msg("cfn_reminder_dm", lang)
                )
                await member.send(combined)
                sent_both += 1
            elif missing_avatar:
                await member.send(get_msg("avatar_reminder_dm", lang))
                sent_avatar += 1
            else:
                await member.send(get_msg("cfn_reminder_dm", lang))
                sent_cfn += 1
        except Exception:
            failed += 1

    total_sent = sent_avatar + sent_cfn + sent_both
    await add_bot_feed(
        f"📋 Registration audit{scope_label}: {total_sent} DM(s) sent "
        f"({sent_avatar} avatar, {sent_cfn} CFN, {sent_both} both missing). "
        f"{failed} unreachable.",
        "info",
    )
    return (
        f"Audited {len(players)} player(s){scope_label} with incomplete profiles: "
        f"{sent_avatar} need avatar, {sent_cfn} need CFN ID, {sent_both} need both. "
        f"DMs sent to {total_sent}; {failed} could not be reached (DMs likely closed)."
    )

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
    print(console_message(level, message))
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

async def handle_ws_command(cmd_text: str, *, workspace_id: str | None = None):
    """Executes a hub command directly from the WebSocket connection."""
    
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

        if cmd_text.strip().lower().startswith("execute_action_proposal "):
            proposal_id = cmd_text.split(" ", 1)[1].strip()
            from backend.core.action_proposals import execute_approved_proposal
            result = await execute_approved_proposal(proposal_id, workspace_id=workspace_id)
            await ws_add_bot_feed(
                f"Organizer proposal execution: {result.get('execution_status', 'unknown')}",
                "success" if result.get("execution_status") in {"workflow_started", "outbox_queued"} else "warn",
            )
            return

        if cmd_text.strip().lower().startswith("call_match "):
            set_id = cmd_text.split(" ")[1].strip()
            from core.database import get_active_match, get_tournament
            match = await get_active_match(set_id, workspace_id)
            if match:
                t = await get_tournament(match['tournament_slug'], workspace_id)
                from bot.match_threads import create_match_thread
                await create_match_thread(bot, t, match)
                await ws_add_bot_feed(f"🤖 Created match thread for {match.get('p1_name')} vs {match.get('p2_name')}", "success")
            else:
                await ws_add_bot_feed(f"❌ call_match failed: Match {set_id} not found", "error")
            return

        if cmd_text.strip().lower().startswith("dm_score_request "):
            set_id = cmd_text.split(" ")[1].strip()
            from core.database import get_active_match
            match = await get_active_match(set_id, workspace_id)
            if match:
                await send_score_report_dms(bot, match)
            return

        # ── start.gg-mode lifecycle (driven by the reconciliation poll) ──────
        # The API-process sync detects start.gg state changes and enqueues these so the
        # bot can do the Discord-only side-effects (it has no Discord access itself).
        if cmd_text.strip().lower().startswith("startgg_go_live "):
            set_id = cmd_text.split(" ")[1].strip()
            from core.database import get_active_match, get_available_stream_station, update_active_match
            match = await get_active_match(set_id, workspace_id)
            if not match:
                return
            # Only stream matches need a green-room handoff; off-stream start.gg matches
            # coordinate entirely on start.gg (no lobby DM).
            if match.get("is_stream_match"):
                # Bind an idle event-matching stream station if one isn't already bound
                # (the on_stream overlay, realized at the in_progress edge).
                if not match.get("station_id"):
                    station = await get_available_stream_station(match.get("event_id") or "", match.get("workspace_id"))
                    if station:
                        await update_active_match(set_id, station_id=station["id"])
                        match = await get_active_match(set_id, match.get("workspace_id"))
                thread_id = match.get("discord_thread_id")
                thread = bot.get_channel(int(thread_id)) if thread_id else None
                if thread:
                    from bot.match_threads import deliver_stream_credentials
                    await deliver_stream_credentials(
                        bot, thread, set_id, match.get("p1_discord"), match.get("p2_discord"), match.get("workspace_id")
                    )
            await ws_add_bot_feed(
                f"▶️ start.gg check-in complete — {match.get('p1_name')} vs {match.get('p2_name')} is now live.",
                "info",
            )
            return

        if cmd_text.strip().lower().startswith("startgg_finish "):
            # Format: "startgg_finish <set_id> [<thread_id>]". The optional thread id lets
            # us still archive when the row was orphan-swept before this command drained.
            parts = cmd_text.split(" ")
            set_id = parts[1].strip() if len(parts) > 1 else ""
            explicit_thread_id = parts[2].strip() if len(parts) > 2 else ""
            from core.database import get_active_match
            match = await get_active_match(set_id, workspace_id)
            thread_id = explicit_thread_id or ((match or {}).get("discord_thread_id") or "")
            if thread_id:
                try:
                    thread = bot.get_channel(int(thread_id))
                    if thread:
                        if match:
                            await thread.send(
                                f"✅ Match completed on Start.gg — "
                                f"{match.get('p1_name')} vs {match.get('p2_name')}. Archiving."
                            )
                        else:
                            await thread.send("✅ Match completed on Start.gg. Archiving.")
                        await thread.edit(archived=True, locked=True)
                except Exception:
                    pass
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

        await ws_add_bot_feed(
            "Unknown manual bot command. Use the Organizer Assistant for questions or a documented bot command.",
            "warn",
        )
            
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
                _runtime_tasks.start(ping_loop())
                
                while True:
                    data = await ws.recv()
                    msg = json.loads(data)
                    if msg.get("type") == "command":
                        cmd_text = msg.get("command")
                        if cmd_text:
                            # Run immediately inside an isolated task
                            _runtime_tasks.start(handle_ws_command(cmd_text))
                    elif msg.get("type") == "drain":
                        # Event-driven nudge: a command was just queued API-side.
                        _runtime_tasks.start(run_drain())
        except Exception as e:
            bot_ws = None
            print(f"[BOT] WebSocket connection failed: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    async def _load_account_token():
        await init_db()
        from backend.core.integrations import get_discord_credential, list_integration_accounts
        selected = os.getenv("AITOB_DISCORD_ACCOUNT_ID", "").strip()
        # The process selects an account from its own database, regardless of
        # the account owner's label.  A tournament still binds each workflow
        # event to one concrete account, so this does not cross destinations.
        accounts = [account for account in await list_integration_accounts(None) if account["provider_type"] == "discord" and account["status"] == "active"]
        if selected:
            accounts = [account for account in accounts if account["id"] == selected]
        if len(accounts) != 1:
            raise RuntimeError("Select exactly one active Discord integration account for this bot process.")
        token = await get_discord_credential(accounts[0]["id"])
        if not token:
            raise RuntimeError("Selected Discord account has no bot token.")
        from backend.core.integrations import get_integration_workspace_id
        return accounts[0]["id"], token, await get_integration_workspace_id(accounts[0]["id"])

    try:
        from backend.core.storage import require_runtime_database
        require_runtime_database()
        ACTIVE_DISCORD_ACCOUNT_ID, TOKEN, ACTIVE_DISCORD_WORKSPACE_ID = asyncio.run(_load_account_token())
        bot.run(TOKEN)
    except Exception:
        print("Discord bot did not start: its selected integration account is unavailable.")
        sys.exit(1)
