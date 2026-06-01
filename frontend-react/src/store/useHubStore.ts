import { create } from 'zustand';

interface Tournament {
  slug: string;
  name: string;
  game: string;
  raw_data: string;
  auto_dq_enabled?: boolean;
  dq_timer_seconds?: number;
  bot_manage_limit?: string;
  bot_manage_finish?: string;
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
  p1_team?: string;
  p2_team?: string;
  p1_avatar?: string;
  p2_avatar?: string;
  // New lifecycle fields
  is_stream_match?: boolean;
  tournament_slug?: string;
  phase_group?: string;
  p1_cfn?: string;
  p2_cfn?: string;
  p1_ready?: boolean;
  p2_ready?: boolean;
  called_at?: string;
  started_at?: string;
  dq_player?: string;
  lobby_password?: string;
  discord_thread_id?: string;
  auto_dq_disarmed?: boolean;
  p1_discord?: string | null;
  p2_discord?: string | null;
}

interface Station {
  id: string;
  name: string;
  overlays?: { overlay_name: string }[];
}

interface HubState {
  tournaments: Tournament[];
  currentSlug: string | null;
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
  hubPassword: string;
  setTournaments: (tournaments: Tournament[]) => void;
  setCurrentSlug: (slug: string | null) => void;
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
  setHubPassword: (password: string) => void;
  logout: () => void;
}

export const useHubStore = create<HubState>((set) => ({
  tournaments: [],
  currentSlug: localStorage.getItem('hub_current_slug'),
  matches: [],
  stations: [],
  status: { startgg_api: false, websockets: false, discord_bot: false, token_scope: null },
  plannedStreamIds: [],
  hubPassword: localStorage.getItem('hub_password') || '',
  setTournaments: (tournaments) => set({ tournaments }),
  setCurrentSlug: (currentSlug) => {
    if (currentSlug) localStorage.setItem('hub_current_slug', currentSlug);
    else localStorage.removeItem('hub_current_slug');
    set((state) => ({ 
      currentSlug, 
      matches: currentSlug ? state.matches : [] 
    }));
  },
  setMatches: (matches) => set({ matches }),
  setStations: (stations) => set({ stations }),
  setStatus: (status) => set({ status }),
  setPlannedStreamIds: (plannedStreamIds: string[]) => set({ plannedStreamIds }),
  togglePlannedStream: (setId) => set((state) => ({
    plannedStreamIds: state.plannedStreamIds.includes(setId)
      ? state.plannedStreamIds.filter(id => id !== setId)
      : [...state.plannedStreamIds, setId]
  })),
  setHubPassword: (hubPassword) => {
    localStorage.setItem('hub_password', hubPassword);
    set({ hubPassword });
  },
  logout: () => {
    localStorage.removeItem('hub_password');
    set({ hubPassword: '' });
  }
}));
