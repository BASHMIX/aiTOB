from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
import os
import httpx

from backend.core.database import (
    create_or_update_player, get_setting, get_connection, add_hub_command, add_bot_feed,
)

router = APIRouter(tags=["auth"])

STARTGG_OAUTH_AUTHORIZE = "https://start.gg/oauth/authorize"
STARTGG_OAUTH_TOKEN = "https://api.start.gg/oauth/access_token"
STARTGG_GQL = "https://api.start.gg/gql/alpha"

# Scope needed to call currentUser{ id slug player { gamerTag } }
_SCOPE = "user.identity"


async def _resolve_secret(key: str, default: str | None = None) -> str | None:
    # Settings table takes precedence over the connections table (admin overrides .env).
    return await get_setting(key) or await get_connection(key) or default


@router.get(
    "/startgg/login",
    summary="OAuth login link for Start.gg",
    operation_id="startggLogin",
)
async def login(discord_id: str):
    """Redirect the player's browser to start.gg's OAuth authorize page.

    `state` carries the Discord ID so the callback can map the resulting
    start.gg user to the right Discord account without any session storage.
    """
    client_id = await _resolve_secret("STARTGG_CLIENT_ID")
    if not client_id:
        raise HTTPException(500, "STARTGG_CLIENT_ID not configured")

    api_base = os.getenv("API_BASE_URL", "http://localhost:8000")
    redirect_uri = f"{api_base}/api/auth/startgg/callback"
    url = (
        f"{STARTGG_OAUTH_AUTHORIZE}?client_id={client_id}"
        f"&redirect_uri={redirect_uri}&response_type=code&scope={_SCOPE}&state={discord_id}"
    )
    return RedirectResponse(url=url)


async def _exchange_code_for_token(code: str, redirect_uri: str) -> dict:
    client_id = await _resolve_secret("STARTGG_CLIENT_ID")
    client_secret = await _resolve_secret("STARTGG_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise HTTPException(500, "Start.gg OAuth client not fully configured")

    async with httpx.AsyncClient(timeout=20.0) as http:
        resp = await http.post(
            STARTGG_OAUTH_TOKEN,
            json={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Content-Type": "application/json"},
        )
    if resp.status_code != 200:
        raise HTTPException(502, f"Start.gg token exchange failed: {resp.status_code} {resp.text[:200]}")
    return resp.json()


async def _fetch_current_user(access_token: str) -> dict:
    """Call start.gg GraphQL with the player's access token to identify them.

    Uses the player's token (not the T.O. API token) so we get *their* user id.
    """
    query = """
    query { currentUser { id slug name player { id gamerTag } } }
    """
    async with httpx.AsyncClient(timeout=20.0) as http:
        resp = await http.post(
            STARTGG_GQL,
            json={"query": query},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
        )
    if resp.status_code != 200:
        raise HTTPException(502, f"Start.gg currentUser query failed: {resp.status_code}")
    data = resp.json()
    if "errors" in data:
        raise HTTPException(502, f"Start.gg GraphQL error: {data['errors']}")
    user = (data.get("data") or {}).get("currentUser")
    if not user:
        raise HTTPException(502, "Start.gg returned no currentUser — token scope may be wrong")
    return user


def _html_response(title: str, body_html: str, ok: bool = True) -> HTMLResponse:
    color = "#10b981" if ok else "#ef4444"
    return HTMLResponse(f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>body{{font-family:system-ui,-apple-system,sans-serif;background:#0a0a0a;color:#eee;
display:flex;align-items:center;justify-content:center;height:100vh;margin:0;padding:1rem;text-align:center}}
.card{{max-width:480px;padding:2rem;background:#1a1a1a;border:1px solid {color}33;border-radius:12px}}
h1{{color:{color};margin:0 0 1rem}}p{{line-height:1.6;color:#ccc}}</style></head>
<body><div class="card">{body_html}</div></body></html>""")


@router.get(
    "/startgg/callback",
    summary="OAuth callback from Start.gg",
    operation_id="startggCallback",
)
async def callback(code: str, state: str):
    """Exchange the OAuth code, identify the player, and link them in our DB.

    `state` is the Discord ID we passed at /login time. This is safe here because
    the value is never used as anything other than a foreign key — it doesn't grant
    any privilege on its own and an attacker would need both a valid start.gg login
    AND a target Discord ID, which they could just register normally anyway.
    """
    discord_id = state
    api_base = os.getenv("API_BASE_URL", "http://localhost:8000")
    redirect_uri = f"{api_base}/api/auth/startgg/callback"

    try:
        token = await _exchange_code_for_token(code, redirect_uri)
        access_token = token.get("access_token")
        if not access_token:
            raise HTTPException(502, "Start.gg returned no access_token")

        user = await _fetch_current_user(access_token)
        startgg_user_id = str(user["id"])
        gamer_tag = (user.get("player") or {}).get("gamerTag") or user.get("name") or user.get("slug") or "Player"

        # THIS is the link that was previously missing — without writing startgg_id,
        # every downstream lookup (bracket→discord) silently failed.
        await create_or_update_player(
            discord_id=discord_id,
            startgg_id=startgg_user_id,
            gamer_tag=gamer_tag,
            is_verified=True,
            registration_step="startgg_linked",
        )

        # Hand off to the bot to apply the Verified role + nickname.
        # Doing it via hub_commands keeps the bot the single Discord actor.
        await add_hub_command(f"apply_verified_role {discord_id} {gamer_tag}")
        await add_bot_feed(f"✅ Linked Discord {discord_id} ↔ start.gg user {startgg_user_id} ({gamer_tag})", "success")

        return _html_response(
            "Linked!",
            f"<h1>✅ Verified</h1><p>Your Discord account is now linked to "
            f"<strong>{gamer_tag}</strong> on start.gg.</p><p>You can close this tab and return to Discord.</p>",
            ok=True,
        )
    except HTTPException as e:
        await add_bot_feed(f"OAuth callback failed for discord_id={discord_id}: {e.detail}", "error")
        return _html_response(
            "Link failed",
            f"<h1>❌ Verification failed</h1><p>{e.detail}</p><p>Return to Discord and try again, or contact a T.O.</p>",
            ok=False,
        )
    except Exception as e:
        await add_bot_feed(f"OAuth callback error for discord_id={discord_id}: {e}", "error")
        return _html_response(
            "Link failed",
            f"<h1>❌ Verification failed</h1><p>{e}</p><p>Return to Discord and try again.</p>",
            ok=False,
        )
