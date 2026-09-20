"""
All Start.gg GraphQL query and mutation strings.
Extracted from startgg_client.py for maintainability.
"""

TOURNAMENT_INFO = """
query TournamentInfo($slug: String!) {
  tournament(slug: $slug) {
    id
    name
    slug
    startAt
    state
    timezone
    images { url type }
    participants(query: {page: 1, perPage: 500}) {
      nodes {
        id
        prefix
        gamerTag
        user { id location { country countryId } }
        player { prefix gamerTag }
      }
    }
    streams {
      id
      streamName
      streamSource
      streamGame
    }
    events {
      id
      name
      slug
      state
      videogame { name }
      entrants(query: {page: 1, perPage: 250}) {
        nodes {
          id
          name
          participants {
            gamerTag
            prefix
            connectedAccounts
            player { prefix gamerTag }
            user {
              id
              location { country countryId }
              images { url type }
            }
          }
        }
      }
    }
  }
}
"""

# Event resolution is intentionally separate from tournament resolution.  A
# direct Event slug must retain its complete ``tournament/.../event/...`` scope
# and must never be approximated by selecting the first tournament event.
EVENT_INFO = """
query EventInfo($slug: String!) {
  event(slug: $slug) {
    id
    name
    slug
    state
    videogame { name }
    tournament { id name slug state timezone startAt images { url type } }
  }
}
"""

# Start.gg maintains the canonical character/stage catalog per videogame.
# Unlike entrant names, these IDs/names are provider-owned and should never be
# copied into a static aiTOB list.
EVENT_GAME_METADATA = """
query EventGameMetadata($eventId: ID!) {
  event(id: $eventId) {
    id
    name
    videogame {
      id
      name
      displayName
      characters {
        id
        name
        images { id url type width height ratio }
      }
      stages { id name }
    }
  }
}
"""

# Retained legacy-client queries. They remain distinct from the adapter queries
# above because their selected fields are part of old API behavior.
LEGACY_TOURNAMENT_INFO = """
query TournamentInfo($slug: String!) {
  tournament(slug: $slug) {
    id
    name
    events {
      id
      name
      videogame { name }
      entrants(query: {page: 1, perPage: 250}) {
        nodes {
          id
          name
          participants { user { images { url type } } }
        }
      }
    }
  }
}
"""

LEGACY_TOURNAMENT_SETS = """
query TournamentSets($slug: String!) {
  tournament(slug: $slug) {
    events {
      sets(page: 1, perPage: 500) {
        nodes {
          id
          state
          winnerId
          completedAt
          fullRoundText
          identifier
          phaseGroup { displayIdentifier }
          slots {
            entrant {
              id
              name
              participants { user { images { url type } } }
            }
          }
        }
      }
    }
  }
}
"""

LEGACY_REPORT_SET_SCORE = """
mutation ReportBracketSet($setId: ID!, $winnerId: ID!, $gameData: [BracketSetGameDataInput]) {
  reportBracketSet(setId: $setId, winnerId: $winnerId, gameData: $gameData) { id state }
}
"""

# Standalone stream-only query — cheaper to call on refresh than full TOURNAMENT_INFO.
TOURNAMENT_STREAMS = """
query TournamentStreams($slug: String!) {
  tournament(slug: $slug) {
    id
    streams {
      id
      streamName
      streamSource
      streamGame
    }
  }
}
"""

# Push a set onto the public stream queue (renders in start.gg's "On Stream" panel).
# Requires the calling token to be a T.O. on the event AND the stream to exist
# in tournament admin → Manage → Streams. Set must be in state >= READY (4).
ASSIGN_STREAM = """
mutation AssignStream($setId: ID!, $streamId: ID!) {
  assignStream(setId: $setId, streamId: $streamId) {
    id
    state
    stream { id streamName }
  }
}
"""

# NOTE: start.gg exposes no `removeStream` mutation — only `assignStream`. There
# is no API to pull a set off the public stream queue, so client.remove_stream is
# a local-only no-op (see its docstring). The query is intentionally not defined.

# Fetch a start.gg user by URL slug. Used by bio-code verification — we read
# the user's bio to check for a temporary verification code the player added
# to prove account control without OAuth.
USER_BY_SLUG = """
query UserBySlug($slug: String!) {
  user(slug: $slug) {
    id
    bio
    name
    player {
      id
      gamerTag
      prefix
    }
    images {
      url
      type
    }
  }
}
"""

# Cheap activity probe: tournament + event + phase state in one round-trip.
# ActivityState semantics: 1=CREATED (not started), 2=ACTIVE (running),
# 3=COMPLETED (finished). Used by fetch_sets to abort early when the
# tournament isn't running, and to scope the subsequent sets query to
# ACTIVE phases only.
TOURNAMENT_STATE = """
query TournamentState($slug: String!) {
  tournament(slug: $slug) {
    id
    state
    events {
      id
      state
      phases {
        id
        state
      }
    }
  }
}
"""

# Paginated sets query, scoped by phaseIds at the API level (SetFilters.phaseIds).
# Callers should pass the ACTIVE phase ID list from TOURNAMENT_STATE — start.gg
# does the filtering server-side; we never receive sets from completed or
# not-yet-started phases.
TOURNAMENT_SETS = """
query TournamentSets($slug: String!, $page: Int!, $perPage: Int!, $phaseIds: [ID!]) {
  tournament(slug: $slug) {
    events {
      id
      name
      sets(page: $page, perPage: $perPage, filters: { phaseIds: $phaseIds }) {
        pageInfo { totalPages }
        nodes {
          id
          state
          fullRoundText
          identifier
          phaseGroup { displayIdentifier }
          slots {
            entrant {
              id
              name
              participants {
                gamerTag
                prefix
                connectedAccounts
                player { prefix gamerTag }
                user {
                  id
                  location { country countryId }
                  images { url type }
                }
              }
            }
          }
        }
      }
    }
  }
}
"""

SET_ENTRANT_ORDER = """
query SetEntrants($id: ID!) {
  set(id: $id) {
    slots { entrant { id } }
  }
}
"""

SET_STATE = """
query SetState($id: ID!) {
  set(id: $id) { state }
}
"""

REPORT_BRACKET_SET = """
mutation ReportBracketSet($setId: ID!, $winnerId: ID!, $gameData: [BracketSetGameDataInput!]) {
  reportBracketSet(setId: $setId, winnerId: $winnerId, gameData: $gameData) {
    id
    state
    winnerId
    completedAt
  }
}
"""

REPORT_WINNER_ONLY = """
mutation SimpleReport($setId: ID!, $winnerId: ID!) {
  reportBracketSet(setId: $setId, winnerId: $winnerId) { id state }
}
"""

# DQ MUST use isDQ:true so start.gg flags the loser's record correctly.
# Pass the winner's entrantId — start.gg auto-marks the opposing slot DQ.
MARK_SET_DQ = """
mutation MarkSetDQ($setId: ID!, $winnerId: ID!) {
  reportBracketSet(setId: $setId, winnerId: $winnerId, isDQ: true) {
    id
    state
    winnerId
  }
}
"""

MARK_IN_PROGRESS = """
mutation MarkInProgress($setId: ID!) {
  markSetInProgress(setId: $setId) { id state }
}
"""

# Call a set on start.gg (state -> CALLED). Spike-verified: this triggers start.gg's
# NATIVE check-in wave — the player-facing check-in timer + push notifications — when
# the event has check-in enabled. Used by 'startgg' check_in_source mode so start.gg
# (not the bot) owns check-in and DQ.
MARK_SET_CALLED = """
mutation MarkSetCalled($setId: ID!) {
  markSetCalled(setId: $setId) { id state }
}
"""

RESET_SET = """
mutation ResetSet($setId: ID!) {
  resetSet(setId: $setId) { id state }
}
"""

# Start.gg does not expose a documented tournament-level resetBracket mutation.
# This token-authenticated operation resets root sets and their dependent sets;
# it clears match results but does not claim to transition the event/phase back
# to the provider UI's CREATED state.
RESET_SET_WITH_DEPENDENCIES = """
mutation ResetSetWithDependencies($setId: ID!, $resetDependentSets: Boolean!) {
  resetSet(setId: $setId, resetDependentSets: $resetDependentSets) {
    id
    state
    resetAffectedData {
      affectedSetCount
      affectedPhaseGroupCount
      affectedSets { id state }
    }
  }
}
"""

# Resolve the phase groups belonging to the selected event.  Tournament setup
# stores the event scope, while Start.gg's bracket reset is scoped to its phase
# groups, so the adapter resolves this relationship at mutation time.
EVENT_PHASE_GROUPS = """
query EventPhaseGroups($eventId: ID!) {
  event(id: $eventId) {
    id
    phases {
      id
      name
      phaseGroups(query: { page: 1, perPage: 100 }) {
        pageInfo { total }
        nodes { id displayIdentifier }
      }
    }
  }
}
"""

PHASE_GROUP_RESET_SETS = """
query PhaseGroupResetSets($phaseGroupId: ID!, $page: Int!, $perPage: Int!) {
  phaseGroup(id: $phaseGroupId) {
    id
    displayIdentifier
    sets(page: $page, perPage: $perPage, sortType: STANDARD) {
      pageInfo { total }
      nodes {
        id
        state
        round
        fullRoundText
        identifier
        entrant1Source { type typeId }
        entrant2Source { type typeId }
      }
    }
  }
}
"""

# Fetch every entrant's connectedAccounts for a tournament so we can look up a
# user's linked Capcom Fighter Network ID without requiring a separate entrant query.
# connectedAccounts is a JSON blob; the Capcom CFN lives at connectedAccounts.capcom.value.
ENTRANT_CONNECTED_ACCOUNTS = """
query EntrantConnectedAccounts($slug: String!) {
  tournament(slug: $slug) {
    events {
      entrants(query: {page: 1, perPage: 500}) {
        nodes {
          participants {
            user { id location { country countryId } }
            connectedAccounts
          }
        }
      }
    }
  }
}
"""

CURRENT_USER = """
query {
  currentUser { id name }
}
"""

PROBE_WRITE_SCOPE = """
mutation ProbeWriteScope {
  markSetInProgress(setId: "9999999999") { id }
}
"""
