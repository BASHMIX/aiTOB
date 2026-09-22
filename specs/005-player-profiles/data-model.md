# Data Model: Persistent Player Profiles and Tournament Overrides

## Existing data retained

- `players`: reusable Discord-linked identity and approved avatar.
- `tournament_player_links`: organizer-confirmed entrant-to-player mapping.
- `player_overrides`: legacy entrant-keyed presentation data.
- `media_assets`: avatar ownership and retirement ledger.
- Provider snapshots and `active_matches`: provider membership and live match
  data; neither becomes a profile store.

## Target aggregates

### PlayerProfile

Stable, workspace-owned identity containing approved presentation values:
display name, prefix, country, and avatar reference. Existing player data is
migrated without asset copying.

### PlayerProviderIdentity

Audited association between a PlayerProfile and a provider account identifier.
It can suggest an entrant link but cannot silently create one.

### PlayerGameProfile and PlayerCharacterDefault

Game-specific account data, preferences, and default character choices. A
default is subordinate to an event-specific override.

### TournamentEntrantLink

Organizer-confirmed relationship between one provider entrant in one tournament
and one PlayerProfile, with source, actor, and time.

### TournamentEntrantOverride

Optional presentation values scoped by workspace, provider, tournament,
event/bracket, and entrant. It may contain name, prefix, country, avatar, and
character; absent fields fall through.

### PlayerPresentationV1

Read model, not a source table. Each resolved field includes provenance:
`entrant_override`, `player_profile`, `provider_snapshot`, or `placeholder`.

## Field resolution

For every field independently: entrant/event override → confirmed profile or
game profile → exact provider snapshot → placeholder. The resolver never
searches by name, mutates state, calls a provider, or changes a match/station.

## Migration rules

1. Backfill profiles from workspace-owned players and retain avatar references.
2. Backfill provider identities only from stored verified provider IDs.
3. Convert a legacy override only if its full scope is provable from a retained
   tournament link/snapshot; mark ambiguous rows for review.
4. Validate row counts, asset references, and workspace ownership before new
   writes are enabled.
