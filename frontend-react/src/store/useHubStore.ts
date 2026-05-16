import { create } from 'zustand';

interface Tournament {
  slug: string;
  name: string;
  game: string;
  raw_data: string;
  auto_dq_enabled?: boolean;
  dq_timer_seconds?: number;
}

interface Match {
  set_id: string;
  p1_name: string;
  p2_name: string;
  p1_score: number;
  p2_score: number;
  status: 'not_started' | 'in_progress' | 'called' | 'complete' | 'dq';
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
  status: { startgg_api: boolean; websockets: boolean; discord_bot: boolean };
  plannedStreamIds: string[];
  setTournaments: (tournaments: Tournament[]) => void;
  setCurrentSlug: (slug: string | null) => void;
  setMatches: (matches: Match[]) => void;
  setStations: (stations: Station[]) => void;
  setStatus: (status: { startgg_api: boolean; websockets: boolean; discord_bot: boolean }) => void;
  togglePlannedStream: (setId: string) => void;
}

export const useHubStore = create<HubState>((set) => ({
  tournaments: [],
  currentSlug: null,
  matches: [],
  stations: [],
  status: { startgg_api: false, websockets: false, discord_bot: false },
  plannedStreamIds: [],
  setTournaments: (tournaments) => set({ tournaments }),
  setCurrentSlug: (currentSlug) => set({ currentSlug }),
  setMatches: (matches) => set({ matches }),
  setStations: (stations) => set({ stations }),
  setStatus: (status) => set({ status }),
  togglePlannedStream: (setId) => set((state) => ({
    plannedStreamIds: state.plannedStreamIds.includes(setId)
      ? state.plannedStreamIds.filter(id => id !== setId)
      : [...state.plannedStreamIds, setId]
  })),
}));
