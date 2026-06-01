import discord
import os
from backend.core.database import create_or_update_player, get_player
from backend.core.image_utils import validate_avatar_quality, validate_avatar_safety, process_avatar
from backend.bot.messages import get_msg


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
        elif step == "avatar_uploaded":
            # Avatar was attempted but didn't finalize; nudge them to retry.
            await message.channel.send(get_msg("avatar_prompt", lang))
        elif step == "verified":
            # Fully registered (full flow OR bio-code fast path).
            # Reply so verified players who DM the bot aren't met with silence.
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

    async def _handle_avatar_step(self, message, discord_id, lang):
        if not message.attachments:
            await message.channel.send(get_msg("avatar_prompt", lang))
            return

        attachment = message.attachments[0]
        if not any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg']):
            await message.channel.send(get_msg("error_quality", lang))
            return

        await message.channel.send(get_msg("safety_check", lang))

        try:
            image_bytes = await attachment.read()

            # Quality check
            ok_q, msg_q = validate_avatar_quality(image_bytes)
            if not ok_q:
                await message.channel.send(f"❌ {msg_q}")
                return

            # AI Safety check
            ok_s, msg_s = await validate_avatar_safety(image_bytes)
            if not ok_s:
                await message.channel.send(get_msg("error_safety", lang, reason=msg_s))
                return

            # Process and save
            p = await get_player(discord_id)
            filename_id = p.get('startgg_id') or discord_id
            saved_path = process_avatar(image_bytes, filename_id)

            await create_or_update_player(
                discord_id,
                avatar_path=saved_path,
                registration_step="verified",
                is_verified=True,
            )
            await message.channel.send(get_msg("reg_complete", lang))

        except Exception as e:
            print(f"Registration Avatar Error: {e}")
            await message.channel.send(get_msg("error_generic", lang))

registration_manager = RegistrationManager()
