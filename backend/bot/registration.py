import discord
import os
from backend.core.database import create_or_update_player, get_player
from backend.core.startgg_client import get_client
from backend.core.image_utils import validate_avatar_quality, validate_avatar_safety, process_avatar
from backend.bot.messages import get_msg

sgg_client = get_client()

class RegistrationManager:
    async def handle_dm(self, message: discord.Message):
        discord_id = str(message.author.id)
        player = await get_player(discord_id)
        
        if not player:
            # Should not happen if they clicked the button, but handle just in case
            await message.channel.send(get_msg("welcome", "en"))
            return

        step = player.get("registration_step", "startgg_linked")
        lang = player.get("preferred_language", "en")

        if step == "startgg_linked":
            await self._handle_language_step(message, discord_id, lang)
        elif step == "language_set":
            await self._handle_cfn_step(message, discord_id, lang)
        elif step == "cfn_provided":
            await self._handle_avatar_step(message, discord_id, lang)
        elif step == "complete":
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

        await create_or_update_player(discord_id, preferred_language=lang, registration_step="language_set")
        await message.channel.send(get_msg("cfn_prompt", lang))

    async def _handle_cfn_step(self, message, discord_id, lang):
        cfn_id = message.content.strip()
        if not cfn_id or len(cfn_id) < 3:
            await message.channel.send(get_msg("cfn_prompt", lang))
            return

        await create_or_update_player(discord_id, cfn_id=cfn_id, registration_step="cfn_provided")
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
            
            await create_or_update_player(discord_id, avatar_path=saved_path, registration_step="complete", is_verified=True)
            await message.channel.send(get_msg("reg_complete", lang))
            
        except Exception as e:
            print(f"Registration Avatar Error: {e}")
            await message.channel.send(get_msg("error_generic", lang))

registration_manager = RegistrationManager()
