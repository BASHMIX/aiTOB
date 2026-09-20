import { create } from 'zustand';

interface Tournament {
  slug: string;
  name: string;
  game: string;
  raw_data: string;
  event_id?: string | null;
  auto_dq_enabled?: boolean;
  dq_timer_seconds?: number;
  bot_manage_limit?: string;
  bot_manage_finish?: string;
  provider_type?: 'startgg' | 'challonge';
  provider_tournament_id?: string;
  provider_sync_status?: 'ready' | 'error';
  provider_sync_error?: string | null;
  provider_last_synced_at?: string | null;
  accent_color?: string | null;
  challonge_sync_mode?: 'economy' | 'live';
  economy_sync_on_stale_open?: number | boolean;
}

export interface ProviderActionProjection {
  action: string;
  availability: 'remote' | 'local' | 'unavailable';
  reason?: string | null;
}

export interface ProviderCapabilityProfile {
  provider_type: 'startgg' | 'challonge';
  display_name: string;
  provider_tournament_id?: string | null;
  provider_subdomain?: string | null;
  contract_version: 'legacy' | 'v2';
  actions: ProviderActionProjection[];
  supports_incremental_sync?: boolean | null;
  supports_targeted_match_fetch?: boolean | null;
  supports_remote_revision?: boolean | null;
  supports_idempotency?: boolean | null;
}

interface Match {
  set_id: string;
  p1_name: string;
  p2_name: string;
  p1_score: number;
  p2_score: number;
  status: 'not_started' | 'in_progress' | 'called' | 'conflict' | 'complete' | 'dq';
  round_name: string;
  station_id?: string;
  match_number?: string;
  swapped?: boolean;
  bot_enabled?: boolean;
  p1_entrant_id?: string;
  p2_entrant_id?: string;
  is_external?: boolean;
  p1_prefix?: string;
  p2_prefix?: string;
  /** Deprecated aliases retained while old saved overlays are migrated. */
  p1_team?: string;
  p2_team?: string;
  p1_avatar?: string;
  p2_avatar?: string;
  // New lifecycle fields
  is_stream_match?: boolean;
  tournament_slug?: string;
  event_id?: string;
  event_name?: string;
  phase_group?: string;
  p1_cfn?: string;
  p2_cfn?: string;
  p1_country?: string;
  p2_country?: string;
  p1_ready?: boolean;
  p2_ready?: boolean;
  called_at?: string;
  started_at?: string;
  dq_player?: string;
  lobby_password?: string;
  discord_thread_id?: string;
  provider_set_id?: string;
  provider_type?: 'startgg' | 'challonge';
  provider_state?: string;
  hub_status?: 'not_started' | 'available' | 'called' | 'ready' | 'in_progress' | 'complete' | null;
  result_kind?: 'score' | 'dq' | null;
  auto_dq_disarmed?: boolean;
  p1_discord?: string | null;
  p2_discord?: string | null;
  // Additive read-only provider projection. These fields are absent for the
  // legacy Start.gg response, so existing cards retain their previous UI.
  state_axes?: {
    provider?: { raw?: string | null; normalized?: string | null };
    hub_status?: string | null;
    sync_status?: string | null;
  } | null;
  discord?: {
    call_sent?: boolean;
    call_message_id?: string | null;
    thread_id?: string | null;
    called_at?: string | null;
    player1_ready_at?: string | null;
    player2_ready_at?: string | null;
    attendance_deadline?: string | null;
  } | null;
  eligibility?: {
    two_sided?: boolean;
    actionable?: boolean;
    reason?: string | null;
  } | null;
  actions?: Record<string, { kind: 'local' | 'remote' | 'unavailable'; enabled: boolean; label?: string; reason?: string }> | null;
}

interface Station {
  id: string;
  name: string;
  is_stream_station?: boolean;
  event_id?: string;
  preview_match_id?: string | null;
  preview_match_json?: string | null;
  overlays?: { overlay_name: string }[];
}

interface EventOpt {
  id: string;
  name: string;
  game?: string;
}

// Result of GET /api/tournaments/{slug}/verify-stream — the live preflight that
// checks whether local stream stations resolve to a stream that still exists on
// start.gg. `ok` is informational (warn-but-allow): it drives a warning badge,
// it does NOT disable streaming, since local overlays/routing work regardless.
export interface StreamGate {
  ok: boolean;
  reason: 'ok' | 'no_stream_stations' | 'no_startgg_streams' | 'unlinked';
  warning: string | null;
  startgg_streams: { id: string; name: string; source?: string; game?: string }[];
  stations: {
    id: string;
    name: string;
    startgg_stream_id: string | null;
    status: 'linked' | 'stale' | 'unmapped';
    matched_stream: { id: string; name: string } | null;
    suggested_stream_id: string | null;
  }[];
}

interface HubState {
  tournaments: Tournament[];
  currentSlug: string | null;
  pinnedTournamentSlugs: string[];
  events: EventOpt[];
  currentEventId: string | null;
  matches: Match[];
  stations: Station[];
  status: {
    startgg_api: boolean;
    websockets: boolean;
    discord_bot: boolean;
    token_scope?: { valid: boolean; has_write_scope: boolean; error: string | null; user_name?: string } | null;
    auto_dispatcher?: boolean;
  };
  plannedStreamIds: string[];
  streamGate: StreamGate | null;
  providerProfile: ProviderCapabilityProfile | null;
  session: { user_id: string; email: string; display_name: string; workspace_id: string; workspace_name: string; workspace_slug: string; role: string } | null;
  setTournaments: (tournaments: Tournament[]) => void;
  setCurrentSlug: (slug: string | null) => void;
  removePinnedTournament: (slug: string) => void;
  setEvents: (events: EventOpt[]) => void;
  setCurrentEventId: (id: string | null) => void;
  setMatches: (matches: Match[]) => void;
  setStations: (stations: Station[]) => void;
  setStatus: (status: {
    startgg_api: boolean;
    websockets: boolean;
    discord_bot: boolean;
    token_scope?: { valid: boolean; has_write_scope: boolean; error: string | null; user_name?: string } | null;
    auto_dispatcher?: boolean;
  }) => void;
  togglePlannedStream: (setId: string) => void;
  setPlannedStreamIds: (ids: string[]) => void;
  setStreamGate: (gate: StreamGate | null) => void;
  setProviderProfile: (profile: ProviderCapabilityProfile | null) => void;
  setSession: (session: HubState['session']) => void;
  logout: () => void;
}

export const useHubStore = create<HubState>((set) => ({
  tournaments: [],
  currentSlug: localStorage.getItem('hub_current_slug'),
  pinnedTournamentSlugs: (() => {
    try {
      const stored = JSON.parse(localStorage.getItem('hub_pinned_tournaments') || '[]');
      return Array.isArray(stored) ? stored.filter((value): value is string => typeof value === 'string') : [];
    } catch {
      return [];
    }
  })(),
  events: [],
  currentEventId: localStorage.getItem('hub_current_event'),
  matches: [],
  stations: [],
  status: { startgg_api: false, websockets: false, discord_bot: false, token_scope: null },
  plannedStreamIds: [],
  streamGate: null,
  providerProfile: null,
  session: null,
  setTournaments: (tournaments) => set({ tournaments }),
  setCurrentSlug: (currentSlug) => {
    if (currentSlug) localStorage.setItem('hub_current_slug', currentSlug);
    else localStorage.removeItem('hub_current_slug');
    set((state) => {
      // Switching tournaments invalidates the selected event (a different game).
      const slugChanged = currentSlug !== state.currentSlug;
      if (slugChanged) localStorage.removeItem('hub_current_event');
      const pinnedTournamentSlugs = currentSlug && !state.pinnedTournamentSlugs.includes(currentSlug)
        ? [...state.pinnedTournamentSlugs, currentSlug]
        : state.pinnedTournamentSlugs;
      if (pinnedTournamentSlugs !== state.pinnedTournamentSlugs) {
        localStorage.setItem('hub_pinned_tournaments', JSON.stringify(pinnedTournamentSlugs));
      }
      return {
        currentSlug,
        pinnedTournamentSlugs,
        matches: currentSlug ? state.matches : [],
        events: slugChanged ? [] : state.events,
        currentEventId: slugChanged ? null : state.currentEventId,
      };
    });
  },
  removePinnedTournament: (slug) => set((state) => {
    const pinnedTournamentSlugs = state.pinnedTournamentSlugs.filter((value) => value !== slug);
    localStorage.setItem('hub_pinned_tournaments', JSON.stringify(pinnedTournamentSlugs));
    return { pinnedTournamentSlugs };
  }),
  setEvents: (events) => set({ events }),
  setCurrentEventId: (currentEventId) => {
    if (currentEventId) localStorage.setItem('hub_current_event', currentEventId);
    else localStorage.removeItem('hub_current_event');
    set({ currentEventId });
  },
  setMatches: (matches) => set({ matches }),
  setStations: (stations) => set({ stations }),
  setStatus: (status) => set({ status }),
  setPlannedStreamIds: (plannedStreamIds: string[]) => set({ plannedStreamIds }),
  setStreamGate: (streamGate) => set({ streamGate }),
  setProviderProfile: (providerProfile) => set({ providerProfile }),
  togglePlannedStream: (setId) => set((state) => ({
    plannedStreamIds: state.plannedStreamIds.includes(setId)
      ? state.plannedStreamIds.filter(id => id !== setId)
      : [...state.plannedStreamIds, setId]
  })),
  setSession: (session) => set({ session }),
  logout: () => {
    set({ session: null });
  }
}));
