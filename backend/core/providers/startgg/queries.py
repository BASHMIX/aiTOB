"""
All Start.gg GraphQL query and mutation strings.
Extracted from startgg_client.py for maintainability.
"""

TOURNAMENT_INFO = """
query TournamentInfo($slug: String!) {
  tournament(slug: $slug) {
    id
    name
    streams {
      id
      streamName
      streamSource
      streamGame
    }
    events {
      id
      name
      videogame { name }
      entrants(query: {page: 1, perPage: 250}) {
        nodes {
          id
          name
          participants {
            user {
              images { url type }
            }
          }
        }
      }
    }
  }
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

REMOVE_STREAM = """
mutation RemoveStream($setId: ID!) {
  removeStream(setId: $setId) {
    id
    state
  }
}
"""

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
                user {
                  id
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
  reportBracketSet(setId: $setId, winnerId: $winnerId) { id state winnerId }
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

RESET_SET = """
mutation ResetSet($setId: ID!) {
  resetSet(setId: $setId) { id state }
}
"""
