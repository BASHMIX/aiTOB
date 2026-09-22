# Research: Persistent Player Profiles and Tournament Overrides

## Provider entrant is not a player profile

**Decision**: Preserve entrants as tournament snapshots and use a separate,
confirmed local profile for reusable player data.

**Rationale**: A Start.gg entrant ID represents tournament participation, not a
person across future tournaments. The current entrant-keyed override design
cannot supply a reusable archive. Provider snapshots still own membership,
bracket state, and provider-native fields.

**Alternatives considered**: Permanent entrant IDs were rejected because a new
tournament creates a different entrant. Fetching Start.gg/Discord on every
render was rejected because it is slow, unavailable during provider outages,
and can overwrite organizer-approved data.

## Confirmed local profile is presentation authority

**Decision**: Prefer the confirmed local profile for organizer-approved display
fields; keep provider data as fallback.

**Rationale**: Existing player records already hold durable avatar and provider
identity data. The explicit tournament link supplies proof of the mapping.

**Alternatives considered**: Name matching and automatic profile overwrites were
rejected because neither is reliable identity proof.

## Overrides must be tournament scoped

**Decision**: Scope an override by workspace, provider, tournament,
event/bracket, and entrant.

**Rationale**: Characters and broadcast choices can differ by game and event.
This prevents a selection from leaking into another tournament while allowing a
profile default.

**Alternatives considered**: A global character override was rejected because a
player may play multiple games. Copying profile values into each entrant was
rejected because it creates stale duplicate data.

## Add a read-only hook before touching OBS

**Decision**: Deliver a versioned local presentation contract before a graphics
consumer adopts it.

**Rationale**: It creates a safe, testable seam for future OBS/editor features
without changing live station behavior now.

**Alternatives considered**: Altering the existing OBS endpoint now was rejected
because it risks a live regression. Live provider calls per overlay render were
rejected because the hook must be predictable and local.
