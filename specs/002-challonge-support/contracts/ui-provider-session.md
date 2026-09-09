# UI Contract: Session Platform Selection

## Import form states

1. `choose_provider`: show Start.gg and Challonge cards/tabs with current connection status.
2. `enter_identifier`: show provider-specific label, examples, and validation.
3. `resolving`: disable submission while the server resolves the identifier.
4. `preview`: show provider badge, tournament name, stable ID, community/subdomain, format, state, and group-stage status.
5. `saving`: create or select the persisted tournament.
6. `error`: show actionable authorization, not-found, ambiguity, quota, or format error without clearing the input.

## Session behavior

- `selected_provider` and draft input may be stored in `sessionStorage` only.
- Opening a fresh browser session presents the platform choice again.
- `currentSlug` may continue to remember the active saved tournament, but the saved tournament's server-provided `provider_type` always controls API, sync, and match actions.
- Switching the import selector never reclassifies the current tournament.

## Provider-specific inputs

### Start.gg

- Accept tournament slug or Start.gg tournament URL.
- Preview events, game, and authorization state.

### Challonge

- Accept numeric tournament ID, normal URL, subdomain/community URL, or legacy `subdomain-slug` identifier.
- Show `Use subdomain/community` as an optional control, off by default.
- When the option is off, require only a numeric ID or normal URL and send no empty/fabricated subdomain.
- When the option is on, accept a subdomain field or derive it from a pasted subdomain URL and show the resolved community in preview.
- Reject URLs containing embedded credentials.
- Preview resolved numeric ID and any community/subdomain before save.

| Mode | Required input | Optional input | Upstream scope |
|------|----------------|----------------|----------------|
| Without subdomain (default) | Numeric ID or normal Challonge URL/slug | None | API-key/OAuth owner's tournaments |
| With subdomain | Tournament slug/URL | Subdomain or resolved community | Selected community only |

Both modes must end with the same server-confirmed numeric `provider_tournament_id` representation.

## Accessibility and feedback

- Platform cards are keyboard-selectable radio controls with visible selected/focus states.
- Every provider badge includes text, not color alone.
- Loading, authorization failure, quota/rate-limit failure, not found, private/inaccessible, and ambiguous identifier states have distinct messages.
