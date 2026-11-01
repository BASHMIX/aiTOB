import { useState, useEffect } from 'react';
import { useHubStore } from '@/store/useHubStore';
import axios from 'axios';
import { removeTournamentFromHub, tournamentRemovalConfirmation } from '@/features/hub/tournamentRemoval';

export function TopNavigation() {
  const {
    tournaments, setTournaments, currentSlug, setCurrentSlug, removePinnedTournament, status, setMatches,
    events, setEvents, currentEventId, setCurrentEventId, selectTournamentEvent, session,
  } = useHubStore();
  const [isRefreshing, setIsRefreshing] = useState(false);
  const currentTournament = tournaments.find((tournament) => tournament.slug === currentSlug);
  const isChallonge = currentTournament?.provider_type === 'challonge';

  // Discover the selected tournament's events. Auto-select when there's exactly
  // one; require an explicit pick when there are several (prevents cross-game
  // contamination). Clears when no tournament is selected.
  useEffect(() => {
    let cancelled = false;
    if (!currentSlug || isChallonge) {
      setEvents([]);
      setCurrentEventId(null);
      return;
    }
    (async () => {
      try {
        const res = await axios.get(`/api/tournaments/${encodeURIComponent(currentSlug)}/events`);
        if (cancelled) return;
        const evs = res?.data?.events || [];
        setEvents(evs);
        if (evs.length === 1) {
          setCurrentEventId(evs[0].id);
        } else if (evs.length === 0) {
          setCurrentEventId(null);
        } else {
          // Prefer the event explicitly selected in the wizard. Keep a still-
          // valid persisted selection for older cards, otherwise force a pick.
          const wizardEvent = currentTournament?.event_id
            ? evs.find((event: any) => String(event.id) === String(currentTournament.event_id))
            : null;
          const currentStoreEvent = useHubStore.getState().currentEventId || currentEventId;
          const stillValid = currentStoreEvent && evs.some((e: any) => String(e.id) === String(currentStoreEvent));
          if (!stillValid) setCurrentEventId(wizardEvent?.id || null);
        }
      } catch (e) {
        console.error('load events', e);
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentSlug, isChallonge, currentTournament?.event_id]);

  const globalRefresh = async () => {
    setIsRefreshing(true);
    try {
      const [tourneysRes, matchesRes] = await Promise.all([
        axios.get('/api/tournaments'),
        axios.get('/api/active-matches')
      ]);
      setTournaments(tourneysRes.data.tournaments || []);
      setMatches(matchesRes.data.matches || []);
    } catch (err) {
      console.error("Manual refresh failed", err);
    } finally {
      setIsRefreshing(false);
    }
  };

  const deleteTournament = async () => {
    if (!currentSlug) return;
    const slug = currentSlug;
    const name = currentTournament?.name || slug;
    if (!window.confirm(tournamentRemovalConfirmation(name))) return;
    try {
      const { tournaments: updatedTournaments, matches: updatedMatches } = await removeTournamentFromHub(slug);
      setTournaments(updatedTournaments);
      setMatches(updatedMatches);
      removePinnedTournament(slug);
      
      // Select the next available or null
      if (updatedTournaments.length > 0) {
        setCurrentSlug(updatedTournaments[0].slug);
      } else {
        setCurrentSlug(null);
      }
    } catch (err) {
      console.error("Failed to delete tournament", err);
      const detail = axios.isAxiosError(err) && err.response?.data?.detail
        ? String(err.response.data.detail)
        : 'Could not remove the tournament.';
      alert(detail);
    }
  };

  const logout = useHubStore(state => state.logout);
  const signOut = async () => {
    try { await axios.post('/api/session/logout'); } catch { /* local clear still protects the UI */ }
    logout();
  };

  return (
    <nav className="bg-cardDark rounded-md p-3 flex flex-wrap items-center justify-between gap-4 text-sm shadow-md border border-white/5">
      <div className="flex items-center gap-4 font-medium text-white flex-wrap">
        <button 
          onClick={signOut}
          className="text-textDim hover:text-accentYellow transition-colors flex items-center gap-1.5 text-xs font-semibold"
        >
          <span>🚪</span> Logout{session?.workspace_name ? ` · ${session.workspace_name}` : ''}
        </button>
        <a
          href="/admin/players"
          className="text-textDim hover:text-accentYellow transition-colors flex items-center gap-1.5 border-l border-white/20 pl-4 text-xs font-semibold"
          data-testid="nav-player-archive"
        >
          <span>👥</span> Player Archive
        </a>
        <a
          href="/admin/results"
          className="text-textDim hover:text-accentYellow transition-colors flex items-center gap-1.5 border-l border-white/20 pl-4 text-xs font-semibold"
          data-testid="nav-results-studio"
        >
          <span>🏆</span> Results Studio
        </a>
        <div className="flex items-center gap-2 border-l border-white/20 pl-4">
          <span className="text-textDim text-xs font-mono uppercase tracking-wider">Tournament:</span>
          <div className="relative inline-flex items-center">
            <select 
              className="bg-black/30 hover:bg-black/50 border border-white/15 focus:border-accentYellow text-white focus:ring-0 text-xs font-bold py-1 pl-2.5 pr-6 rounded-md cursor-pointer transition-colors appearance-none"
              value={currentSlug || ''}
              onChange={(e) => {
                const slug = e.target.value;
                if (slug) {
                  if (selectTournamentEvent) {
                    selectTournamentEvent(slug, null);
                  } else {
                    setCurrentSlug(slug);
                  }
                } else {
                  setCurrentSlug(null);
                }
              }}
            >
              <option className="bg-[#161c28] text-textDim" value="">Select Tournament</option>
              {tournaments.map((t) => (
                <option key={t.slug} className="bg-[#161c28] text-white" value={t.slug}>
                  {t.name}
                </option>
              ))}
            </select>
            <svg className="pointer-events-none absolute right-1.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-textDim" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M19 9l-7 7-7-7" />
            </svg>
          </div>
          {currentSlug && (
            <div className="flex items-center gap-1.5 ml-1">
              <button
                onClick={globalRefresh}
                disabled={isRefreshing}
                className={`p-1 text-textDim hover:text-accentYellow hover:bg-white/5 rounded transition-colors ${isRefreshing ? 'animate-spin' : ''}`}
                title="Refresh All Data"
                aria-label="Refresh All Data"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="w-3.5 h-3.5">
                  <path d="M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" />
                </svg>
              </button>
              <button
                onClick={deleteTournament}
                className="p-1 text-statusRed/70 hover:text-statusRed hover:bg-statusRed/10 rounded transition-colors"
                title="Delete Tournament"
                aria-label="Delete Tournament"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-3.5 h-3.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
          )}
        </div>

        {/* Challonge has one provider bracket, while Start.gg can have many events. */}
        {currentSlug && isChallonge && (
          <div className="flex items-center gap-1.5 border-l border-white/20 pl-4 text-xs">
            <span className="text-textDim font-mono uppercase tracking-wider">Scope:</span>
            <span className="text-white font-bold bg-white/10 px-2 py-0.5 rounded border border-white/10">Bracket</span>
          </div>
        )}
        {currentSlug && !isChallonge && (events?.length ?? 0) > 0 && (
          <div className="flex items-center gap-2 border-l border-white/20 pl-4">
            <span className="text-textDim text-xs font-mono uppercase tracking-wider">Event:</span>
            {events.length === 1 ? (
              <span className="text-white text-xs font-bold bg-white/10 px-2.5 py-1 rounded-md border border-white/10">
                {events[0].name}{events[0].game ? ` · ${events[0].game}` : ''}
              </span>
            ) : (
              <div className="relative inline-flex items-center">
                <select
                  className={`bg-black/30 hover:bg-black/50 border border-white/15 focus:border-accentYellow focus:ring-0 text-xs py-1 pl-2.5 pr-6 rounded-md cursor-pointer transition-colors appearance-none font-bold ${
                    currentEventId ? 'text-white' : 'text-accentYellow animate-pulse'
                  }`}
                  value={currentEventId || ''}
                  onChange={(e) => setCurrentEventId(e.target.value || null)}
                  title="Select an event to view its matches and attendees"
                >
                  <option className="bg-[#161c28] text-textDim" value="">Select Event</option>
                  {events.map((ev) => (
                    <option key={ev.id} className="bg-[#161c28] text-white" value={ev.id}>
                      {ev.name}{ev.game ? ` · ${ev.game}` : ''}
                    </option>
                  ))}
                </select>
                <svg className="pointer-events-none absolute right-1.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-textDim" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M19 9l-7 7-7-7" />
                </svg>
              </div>
            )}
          </div>
        )}

      </div>
      
      <div className="flex items-center gap-4 font-mono text-xs">
        <span className="text-textDim">Status:</span>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${(isChallonge ? currentTournament?.provider_sync_status !== 'error' : status.startgg_api) ? 'bg-statusGreen shadow-[0_0_8px_rgba(34,197,94,0.4)]' : 'bg-statusRed shadow-[0_0_8px_rgba(239,68,68,0.4)]'}`}></span>
          <span>{isChallonge ? 'Challonge' : 'Start.gg'}</span>
        </div>
        <div className="flex items-center gap-2 border-l border-white/20 pl-4">
          <span className={`w-2 h-2 rounded-full ${status.discord_bot ? 'bg-statusGreen shadow-[0_0_8px_rgba(34,197,94,0.4)]' : 'bg-statusRed shadow-[0_0_8px_rgba(239,68,68,0.4)]'}`}></span>
          <span>Bot</span>
        </div>
        <div className="flex items-center gap-2 border-l border-white/20 pl-4">
          <span className={`w-2 h-2 rounded-full ${status.websockets ? 'bg-statusGreen shadow-[0_0_8px_rgba(34,197,94,0.4)]' : 'bg-statusRed shadow-[0_0_8px_rgba(239,68,68,0.4)]'}`}></span>
          <span>WS</span>
        </div>
      </div>
    </nav>
  );
}
