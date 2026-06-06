import discord
import os
from backend.core.database import (
    create_or_update_player, get_player, add_hub_command, add_bot_feed,
    sync_player_cfns_to_matches,
)
from backend.core.image_utils import validate_avatar_quality, validate_avatar_safety
from backend.core.image_store import store_avatar
from backend.bot.messages import get_msg


async def finalize_verification(
    discord_id: str,
    gamer_tag: str | None = None,
    avatar_path: str | None = None,
):
    """Single source of truth for completing a player's verification.

    Flips ``is_verified`` on, marks the registration step ``verified``, and hands
    role/nick assignment to the bot's hub-command worker. Both the bio-code DM
    avatar handler and the returning-player "Keep Existing Avatar" button funnel
    through here so the finalize semantics never drift between the two paths.
    """
    fields = {"is_verified": True, "registration_step": "verified"}
    if avatar_path:
        fields["avatar_path"] = avatar_path
    await create_or_update_player(discord_id, **fields)
    cmd = f"apply_verified_role {discord_id}"
    if gamer_tag:
        cmd += f" {gamer_tag}"
    await add_hub_command(cmd)
    await add_bot_feed(
        f"✅ Verified (broadcast-ready): <{discord_id}> ({gamer_tag or '—'})",
        "success",
    )


class RegistrationManager:
    """DM-driven registration state machine.

    Step names are the canonical strings defined in docs/workflows.json's
    registration_workflow.steps. Any change here must be mirrored there.
    Tolerates legacy step names from earlier deployments so existing rows
    don't get stuck mid-flow after the rename.
    """

    # Legacy → canonical mapping. Lets old DBs upgrade in place.
    _LEGACY_STEP_ALIASES = {
        "language_set":  "language_selected",
        "cfn_provided":  "cfn_entered",
        "complete":      "verified",
        # cfn_pending is a Path-B only state added in the CFN fallback commit.
        # No legacy alias needed — it's new — but listed here for documentation.
    }

    def _normalize_step(self, step: str | None) -> str:
        if not step:
            return "startgg_linked"
        return self._LEGACY_STEP_ALIASES.get(step, step)

    async def handle_dm(self, message: discord.Message):
        discord_id = str(message.author.id)
        player = await get_player(discord_id)

        if not player:
            # Should not happen if they clicked the button, but handle just in case
            await message.channel.send(get_msg("welcome", "en"))
            return

        step = self._normalize_step(player.get("registration_step"))
        lang = player.get("preferred_language", "en")

        if step == "startgg_linked":
            await self._handle_language_step(message, discord_id, lang)
        elif step == "language_selected":
            await self._handle_cfn_step(message, discord_id, lang)
        elif step == "cfn_entered":
            await self._handle_avatar_step(message, discord_id, lang)
        elif step == "avatar_upload":
            # Bio-code (Path B) broadcast-avatar collection. No language/CFN was
            # gathered on this path, so we fall back to the stored language.
            await self._handle_broadcast_avatar_step(message, discord_id, lang)
        elif step == "cfn_pending":
            # Path B post-avatar: CFN was not found on start.gg, player is DMing it now.
            await self._handle_cfn_pending_step(message, discord_id, lang)
        elif step == "avatar_uploaded":
            # Avatar was attempted but didn't finalize; nudge them to retry.
            await message.channel.send(get_msg("avatar_prompt", lang))
        elif step == "verified":
            # Fully registered (full flow OR bio-code fast path).
            # If they DM an IMAGE, treat it as a broadcast-avatar update rather
            # than swallowing it behind the generic "update your profile?" reply.
            if message.attachments:
                await self._handle_broadcast_avatar_step(message, discord_id, lang)
            else:
                await message.channel.send(get_msg("profile_update", lang))

    async def _handle_language_step(self, message, discord_id, current_lang):
        text = message.content.strip().lower()
        if text in ("1", "ar", "arabic", "العربية"):
            lang = "ar"
        elif text in ("2", "en", "english", "إنجليزي"):
            lang = "en"
        else:
            await message.channel.send(get_msg("lang_prompt", current_lang))
            return

        await create_or_update_player(
            discord_id,
            preferred_language=lang,
            registration_step="language_selected",
        )
        await message.channel.send(get_msg("cfn_prompt", lang))

    async def _handle_cfn_step(self, message, discord_id, lang):
        cfn_id = message.content.strip()
        if not cfn_id or len(cfn_id) < 3:
            await message.channel.send(get_msg("cfn_prompt", lang))
            return

        await create_or_update_player(
            discord_id,
            cfn_id=cfn_id,
            registration_step="cfn_entered",
        )
        await message.channel.send(get_msg("avatar_prompt", lang))

    async def _process_and_save_avatar(self, message, discord_id, lang) -> str | None:
        """Validate (quality + safety) and persist a DM'd avatar attachment.

        Shared by the full-flow (Path A) avatar step and the bio-code (Path B)
        broadcast-avatar step. Sends the appropriate error message to the player
        and returns ``None`` on any failure; returns the saved local path on success.
        """
        if not message.attachments:
            await message.channel.send(get_msg("avatar_prompt", lang))
            return None

        attachment = message.attachments[0]
        if not any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg']):
            await message.channel.send(get_msg("error_quality", lang))
            return None

        await message.channel.send(get_msg("safety_check", lang))

        try:
            image_bytes = await attachment.read()

            # Quality check
            ok_q, msg_q = validate_avatar_quality(image_bytes)
            if not ok_q:
                await message.channel.send(f"❌ {msg_q}")
                return None

            # AI Safety check
            ok_s, msg_s = await validate_avatar_safety(image_bytes)
            if not ok_s:
                await message.channel.send(get_msg("error_safety", lang, reason=msg_s))
                return None

            # Process + store (Cloudinary when configured, local fallback otherwise).
            p = await get_player(discord_id)
            filename_id = (p or {}).get('startgg_id') or discord_id
            return await store_avatar(image_bytes, filename_id)

        except Exception as e:
            print(f"Registration Avatar Error: {e}")
            await message.channel.send(get_msg("error_generic", lang))
            return None

    async def _handle_avatar_step(self, message, discord_id, lang):
        saved_path = await self._process_and_save_avatar(message, discord_id, lang)
        if not saved_path:
            return
        await create_or_update_player(
            discord_id,
            avatar_path=saved_path,
            registration_step="verified",
            is_verified=True,
        )
        await message.channel.send(get_msg("reg_complete", lang))

    async def _handle_cfn_pending_step(self, message, discord_id, lang):
        """Path B post-avatar: player is DMing their CFN ID to complete registration.

        Reached when start.gg had no linked Capcom account and the avatar step
        already completed. Any text reply ≥ 3 chars is accepted as the CFN ID.
        """
        cfn_id = message.content.strip()
        if not cfn_id or len(cfn_id) < 3:
            await message.channel.send(get_msg("cfn_post_verify_prompt", lang))
            return
        await create_or_update_player(discord_id, cfn_id=cfn_id)
        await sync_player_cfns_to_matches(discord_id)
        player = await get_player(discord_id)
        gamer_tag = (player or {}).get("gamer_tag")
        await finalize_verification(discord_id, gamer_tag, avatar_path=None)
        await message.channel.send(get_msg("reg_complete", lang))

    async def _handle_broadcast_avatar_step(self, message, discord_id, lang):
        """Bio-code (Path B): collect the broadcast avatar, then finalize or request CFN.

        Reached when a new (or replacing) bio-verified player DMs their photo.
        If CFN was pre-populated from start.gg at verify-confirm, we finalize immediately.
        If CFN is still missing, we park the player in cfn_pending and prompt them to DM it.
        """
        saved_path = await self._process_and_save_avatar(message, discord_id, lang)
        if not saved_path:
            return
        player = await get_player(discord_id)
        gamer_tag = (player or {}).get("gamer_tag")
        cfn_id = (player or {}).get("cfn_id")
        if not cfn_id:
            # CFN was not on start.gg — park in cfn_pending, avatar is already saved.
            await create_or_update_player(discord_id, avatar_path=saved_path, registration_step="cfn_pending")
            await message.channel.send(get_msg("cfn_post_verify_prompt", lang))
            return
        await finalize_verification(discord_id, gamer_tag, saved_path)
        await message.channel.send(get_msg("reg_complete", lang))

registration_manager = RegistrationManager()
