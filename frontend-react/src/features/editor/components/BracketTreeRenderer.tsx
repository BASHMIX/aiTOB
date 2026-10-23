import { useMemo, useState, useEffect } from 'react';
import type { OverlayElement } from '@/store/useEditorStore';
import { useHubStore } from '@/store/useHubStore';
import { countryCode } from '@/utils/country';

export interface BracketTreeRendererProps {
  element: OverlayElement;
  bracketData?: any;
  activeMatch?: any;
  interactive?: boolean;
}

// Custom hook to poll live Top 8 bracket data from the tournament provider
function useLiveBracketData(
  tournamentSlug: string | null | undefined,
  eventId: string | null | undefined,
  isTestMode: boolean
) {
  const [liveData, setLiveData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isTestMode || !tournamentSlug) {
      setLiveData(null);
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    const fetchBracket = async () => {
      try {
        const params = new URLSearchParams();
        if (eventId) params.set('event_id', eventId);
        const q = params.toString() ? `?${params.toString()}` : '';
        const res = await fetch(`/api/tournaments/${encodeURIComponent(tournamentSlug)}/bracket-tree${q}`);
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        const data = await res.json();
        if (!cancelled) {
          setLiveData(data);
          setError(null);
        }
      } catch (err: any) {
        if (!cancelled) {
          setError(err.message || 'Failed to fetch bracket data');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    fetchBracket();
    const interval = setInterval(fetchBracket, 30000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [tournamentSlug, eventId, isTestMode]);

  return { liveData, loading, error };
}

// Built-in generic tournament test data (Zero copyrighted brand/sponsor references)
const MOCK_CHAMPIONSHIP_TOP8_DATA = {
  tournament_slug: 'championship-2026',
  tournament_name: 'CHAMPIONSHIP FINALS',
  game_name: 'TOURNAMENT BRACKET',
  has_reset: false,
  reset_active: false,
  matches: {
    winners_semis: [
      {
        id: 'mock-wsf-1',
        round_name: 'Winners Semifinal 1',
        identifier: 'WSF1',
        state: 'complete',
        p1: { id: 'm1', name: 'PLAYER 1', prefix: 'TEAM A', country: 'US', score: 3, is_winner: true, avatar_url: '' },
        p2: { id: 'm2', name: 'PLAYER 2', prefix: 'TEAM B', country: 'JO', score: 1, is_winner: false, avatar_url: '' },
      },
      {
        id: 'mock-wsf-2',
        round_name: 'Winners Semifinal 2',
        identifier: 'WSF2',
        state: 'complete',
        p1: { id: 'm3', name: 'PLAYER 3', prefix: 'TEAM C', country: 'JP', score: 3, is_winner: true, avatar_url: '' },
        p2: { id: 'm4', name: 'PLAYER 4', prefix: 'TEAM D', country: 'FR', score: 0, is_winner: false, avatar_url: '' },
      },
    ],
    winners_finals: {
      id: 'mock-wf',
      round_name: 'Winners Finals',
      identifier: 'WF',
      state: 'complete',
      p1: { id: 'm1', name: 'PLAYER 1', prefix: 'TEAM A', country: 'US', score: 2, is_winner: false, avatar_url: '' },
      p2: { id: 'm3', name: 'PLAYER 3', prefix: 'TEAM C', country: 'JP', score: 3, is_winner: true, avatar_url: '' },
    },
    losers_round1: [
      {
        id: 'mock-lr1-1',
        round_name: 'Losers Round 1 · Match 1',
        identifier: 'LR1-1',
        state: 'complete',
        p1: { id: 'm5', name: 'PLAYER 5', prefix: 'TEAM E', country: 'SA', score: 3, is_winner: true, avatar_url: '' },
        p2: { id: 'm6', name: 'PLAYER 6', prefix: 'TEAM F', country: 'UK', score: 2, is_winner: false, avatar_url: '' },
      },
      {
        id: 'mock-lr1-2',
        round_name: 'Losers Round 1 · Match 2',
        identifier: 'LR1-2',
        state: 'complete',
        p1: { id: 'm7', name: 'PLAYER 7', prefix: 'TEAM G', country: 'KR', score: 3, is_winner: true, avatar_url: '' },
        p2: { id: 'm8', name: 'PLAYER 8', prefix: 'TEAM H', country: 'DE', score: 1, is_winner: false, avatar_url: '' },
      },
    ],
    losers_quarters: [
      {
        id: 'mock-lqf-1',
        round_name: 'Losers Quarterfinal 1',
        identifier: 'LQF1',
        state: 'complete',
        p1: { id: 'm4', name: 'PLAYER 4', prefix: 'TEAM D', country: 'FR', score: 3, is_winner: true, avatar_url: '' },
        p2: { id: 'm5', name: 'PLAYER 5', prefix: 'TEAM E', country: 'SA', score: 1, is_winner: false, avatar_url: '' },
      },
      {
        id: 'mock-lqf-2',
        round_name: 'Losers Quarterfinal 2',
        identifier: 'LQF2',
        state: 'complete',
        p1: { id: 'm2', name: 'PLAYER 2', prefix: 'TEAM B', country: 'JO', score: 3, is_winner: true, avatar_url: '' },
        p2: { id: 'm7', name: 'PLAYER 7', prefix: 'TEAM G', country: 'KR', score: 0, is_winner: false, avatar_url: '' },
      },
    ],
    losers_semis: {
      id: 'mock-lsf',
      round_name: 'Losers Semifinals',
      identifier: 'LSF',
      state: 'complete',
      p1: { id: 'm4', name: 'PLAYER 4', prefix: 'TEAM D', country: 'FR', score: 2, is_winner: false, avatar_url: '' },
      p2: { id: 'm2', name: 'PLAYER 2', prefix: 'TEAM B', country: 'JO', score: 3, is_winner: true, avatar_url: '' },
    },
    losers_finals: {
      id: 'mock-lf',
      round_name: 'Losers Finals',
      identifier: 'LF',
      state: 'complete',
      p1: { id: 'm1', name: 'PLAYER 1', prefix: 'TEAM A', country: 'US', score: 3, is_winner: true, avatar_url: '' },
      p2: { id: 'm2', name: 'PLAYER 2', prefix: 'TEAM B', country: 'JO', score: 1, is_winner: false, avatar_url: '' },
    },
    grand_finals: {
      id: 'mock-gf',
      round_name: 'Grand Finals',
      identifier: 'GF',
      state: 'complete',
      p1: { id: 'm3', name: 'PLAYER 3', prefix: 'TEAM C', country: 'JP', score: 3, is_winner: true, avatar_url: '', bracket_origin: 'winners' },
      p2: { id: 'm1', name: 'PLAYER 1', prefix: 'TEAM A', country: 'US', score: 2, is_winner: false, avatar_url: '', bracket_origin: 'losers' },
    },
    grand_finals_reset: {
      id: 'mock-gf-reset',
      round_name: 'Grand Finals Reset',
      identifier: 'GF-R',
      state: 'complete',
      p1: { id: 'm3', name: 'PLAYER 3', prefix: 'TEAM C', country: 'JP', score: 3, is_winner: true, avatar_url: '', bracket_origin: 'winners' },
      p2: { id: 'm1', name: 'PLAYER 1', prefix: 'TEAM A', country: 'US', score: 1, is_winner: false, avatar_url: '', bracket_origin: 'losers' },
    },
  },
};

export function BracketTreeRenderer({ element, bracketData, activeMatch }: BracketTreeRendererProps) {
  const [animKey, setAnimKey] = useState(0);

  // Synchronize with Slide preview & element preview events
  useEffect(() => {
    const handleReplay = (e: Event) => {
      const isGlobal = e.type === 'play-slide-preview';
      const customEvent = e as CustomEvent;
      if (isGlobal || customEvent.detail?.id === element.id) {
        setAnimKey((prev) => prev + 1);
      }
    };

    window.addEventListener('play-slide-preview', handleReplay);
    window.addEventListener('play-element-preview', handleReplay);
    return () => {
      window.removeEventListener('play-slide-preview', handleReplay);
      window.removeEventListener('play-element-preview', handleReplay);
    };
  }, [element.id]);

  const slideAnim = element.animation;
  const slideDuration = slideAnim && slideAnim.animationType !== 'none' ? slideAnim.duration || 500 : 0;
  const baseOffsetMs = slideDuration > 0 ? Math.round(slideDuration * 0.45) : 0;

  const hubTournaments = useHubStore((s) => s.tournaments);
  const currentSlug = useHubStore((s) => s.currentSlug);
  const activeTournament = hubTournaments.find((t) => t.slug === currentSlug) || hubTournaments[0] || null;

  const isObsMode = typeof window !== 'undefined' && window.location.pathname.includes('/obs');
  const isTestMode = element.bracketTestMode ?? false;
  const layout = element.bracketLayoutVariant || 'top8-double-elim';
  const showBackground = element.bracketShowBackground ?? true;
  const showSponsors = element.bracketShowSponsors ?? true;
  const simulateReset = element.bracketSimulateReset ?? false;
  const roundFormat = element.bracketRoundBestOf || 'BO5';

  const tournamentSlug = activeTournament?.slug || activeMatch?.tournament_slug || currentSlug || undefined;
  const eventId = activeTournament?.event_id || activeMatch?.event_id || undefined;

  const { liveData, loading, error } = useLiveBracketData(tournamentSlug, eventId, isTestMode);

  // Dynamic titles
  const gameTitle = useMemo(() => {
    if (element.bracketGameName && element.bracketGameName.trim()) {
      return element.bracketGameName.trim().toUpperCase();
    }
    if (liveData?.game_name && liveData.game_name.trim()) {
      return liveData.game_name.trim().toUpperCase();
    }
    if (activeMatch?.game_name && activeMatch.game_name.trim()) {
      return activeMatch.game_name.trim().toUpperCase();
    }
    if (activeTournament?.game && activeTournament.game.trim()) {
      return activeTournament.game.trim().toUpperCase();
    }
    return '';
  }, [element.bracketGameName, liveData?.game_name, activeMatch?.game_name, activeTournament?.game]);

  const tournamentTitle = useMemo(() => {
    if (element.bracketTournamentName && element.bracketTournamentName.trim()) {
      return element.bracketTournamentName.trim().toUpperCase();
    }
    if (liveData?.tournament_name && liveData.tournament_name.trim()) {
      return liveData.tournament_name.trim().toUpperCase();
    }
    if (activeMatch?.tournament_name && activeMatch.tournament_name.trim()) {
      return activeMatch.tournament_name.trim().toUpperCase();
    }
    if (activeTournament?.name && activeTournament.name.trim()) {
      return activeTournament.name.trim().toUpperCase();
    }
    return '';
  }, [element.bracketTournamentName, liveData?.tournament_name, activeMatch?.tournament_name, activeTournament?.name]);

  // Unified Theme System
  const theme = useMemo(() => {
    const preset = element.bracketThemePreset || 'crimson';
    const defaults: Record<string, {
      accent: string;
      bg: string;
      cardBg: string;
      cardBorder: string;
      connector: string;
      header: string;
      scoreText: string;
      winnerGlow: string;
    }> = {
      crimson: {
        accent: '#ef4444',
        bg: 'linear-gradient(180deg, #09090b 0%, #18181b 50%, #09090b 100%)',
        cardBg: '#18181b',
        cardBorder: 'rgba(239, 68, 68, 0.4)',
        connector: '#ef4444',
        header: 'linear-gradient(90deg, #7f1d1d, #991b1b, #7f1d1d)',
        scoreText: '#ef4444',
        winnerGlow: 'rgba(239, 68, 68, 0.4)',
      },
      'royal-blue': {
        accent: '#3b82f6',
        bg: 'radial-gradient(circle at 50% 30%, #0d2878 0%, #081a52 50%, #040c29 100%)',
        cardBg: '#0f172a',
        cardBorder: 'rgba(59, 130, 246, 0.4)',
        connector: '#60a5fa',
        header: 'linear-gradient(90deg, #1e3a8a, #2563eb, #1e3a8a)',
        scoreText: '#fbbf24',
        winnerGlow: 'rgba(59, 130, 246, 0.4)',
      },
      'cyber-gold': {
        accent: '#f59e0b',
        bg: 'linear-gradient(180deg, #0a0a0c 0%, #17140e 50%, #0a0a0c 100%)',
        cardBg: '#18140e',
        cardBorder: 'rgba(245, 158, 11, 0.4)',
        connector: '#f59e0b',
        header: 'linear-gradient(90deg, #78350f, #b45309, #78350f)',
        scoreText: '#fcd34d',
        winnerGlow: 'rgba(245, 158, 11, 0.4)',
      },
      emerald: {
        accent: '#10b981',
        bg: 'linear-gradient(180deg, #022c22 0%, #064e3b 50%, #022c22 100%)',
        cardBg: '#061e18',
        cardBorder: 'rgba(16, 185, 129, 0.4)',
        connector: '#34d399',
        header: 'linear-gradient(90deg, #064e3b, #059669, #064e3b)',
        scoreText: '#6ee7b7',
        winnerGlow: 'rgba(16, 185, 129, 0.4)',
      },
      monochrome: {
        accent: '#ffffff',
        bg: 'linear-gradient(180deg, #09090b 0%, #121214 50%, #09090b 100%)',
        cardBg: '#121214',
        cardBorder: 'rgba(255, 255, 255, 0.25)',
        connector: '#a1a1aa',
        header: 'linear-gradient(90deg, #18181b, #27272a, #18181b)',
        scoreText: '#ffffff',
        winnerGlow: 'rgba(255, 255, 255, 0.3)',
      },
    };

    const sel = defaults[preset] || defaults.crimson;

    return {
      accent: element.bracketAccentColor || sel.accent,
      bg: sel.bg,
      cardBg: element.bracketCardBgColor || sel.cardBg,
      cardBorder: element.bracketCardBorderColor || sel.cardBorder,
      connector: element.bracketConnectorColor || sel.connector,
      header: sel.header,
      scoreText: sel.scoreText,
      winnerGlow: sel.winnerGlow,
    };
  }, [
    element.bracketThemePreset,
    element.bracketAccentColor,
    element.bracketCardBgColor,
    element.bracketCardBorderColor,
    element.bracketConnectorColor,
  ]);

  // Resolve active dataset
  const resolvedData = useMemo(() => {
    if (bracketData && !isTestMode) {
      return bracketData;
    }
    if (!isTestMode && liveData) {
      return liveData;
    }
    if (!isTestMode) {
      return null;
    }

    const mock = JSON.parse(JSON.stringify(MOCK_CHAMPIONSHIP_TOP8_DATA));
    mock.game_name = gameTitle;
    mock.tournament_name = tournamentTitle;

    if (!simulateReset) {
      mock.has_reset = false;
      mock.reset_active = false;
      mock.matches.grand_finals_reset = null;
    } else {
      mock.has_reset = true;
      mock.reset_active = true;
    }
    return mock;
  }, [bracketData, isTestMode, liveData, simulateReset, gameTitle, tournamentTitle]);

  const matches = resolvedData?.matches || {};

  // Grand Finals origin badge
  const renderOriginBadge = (origin?: 'winners' | 'losers') => {
    if (!origin) return null;
    const isW = origin === 'winners';
    return (
      <span
        className={`px-1.5 py-0.5 rounded text-[10px] font-black tracking-wider uppercase inline-flex items-center justify-center mr-1.5 shadow-sm ${
          isW
            ? 'bg-emerald-500/30 text-emerald-300 border border-emerald-400/70'
            : 'bg-amber-500/30 text-amber-300 border border-amber-400/70'
        }`}
      >
        {isW ? '[W]' : '[L]'}
      </span>
    );
  };

  // Entrant Row in Match Card (Clean layout, safe country code display, zero text collision)
  const renderEntrantRow = (entrant: any, isWinner: boolean) => {
    const isTbd = !entrant || entrant.name === 'TBD';
    const code = countryCode(entrant?.country) || (entrant?.country ? String(entrant.country).trim().slice(0, 3).toUpperCase() : null);
    const countryDisplay = isTbd ? '--' : (code || '--');
    const showAvatar = element.bracketShowAvatars ?? true;

    return (
      <div className="flex items-center w-full h-[32px] shadow-sm select-none">
        {/* Country Code Pill */}
        <div className="w-9 h-full bg-[#cbd5e1] text-[#0f172a] font-black text-[11px] flex items-center justify-center rounded-l shrink-0 border-r border-[#94a3b8]/50 shadow-inner">
          {countryDisplay}
        </div>

        {/* Player Name Container */}
        <div
          className={`h-full flex-1 px-2.5 flex items-center justify-between min-w-0 transition-colors ${
            isWinner
              ? 'bg-white/15 shadow-sm'
              : 'bg-black/40'
          }`}
          style={{
            borderLeft: isWinner ? `3px solid ${theme.accent}` : 'none',
          }}
        >
          <div className="flex items-center gap-1.5 min-w-0 truncate">
            {renderOriginBadge(entrant?.bracket_origin)}
            {showAvatar && entrant?.avatar_url && (
              <img
                src={entrant.avatar_url}
                alt=""
                className="w-4 h-4 rounded-full object-cover shrink-0 border border-white/50 shadow-sm"
                onError={(e) => { (e.target as HTMLElement).style.display = 'none'; }}
              />
            )}
            {entrant?.prefix && (
              <span className="text-[10px] font-bold text-white/70 uppercase tracking-wider mr-1 opacity-85 shrink-0">
                {entrant.prefix}
              </span>
            )}
            <span
              className={`text-xs font-black uppercase tracking-wider truncate ${
                isTbd ? 'text-white/40 italic' : isWinner ? 'text-white' : 'text-white/90'
              }`}
            >
              {entrant?.name || 'TBD'}
            </span>
          </div>
        </div>

        {/* Score Box */}
        <div
          className="w-9 h-full flex items-center justify-center rounded-r text-xs font-mono font-black shrink-0 border-l border-white/10 bg-black/60 shadow-inner"
          style={{
            color: isWinner ? theme.scoreText : '#ffffff',
          }}
        >
          {entrant?.score ?? 0}
        </div>
      </div>
    );
  };

  // Match Card Component with solid background & z-10 to prevent line collisions
  const renderMatchCard = (match: any, _label: string, isFinals = false) => {
    if (!match) {
      return (
        <div
          className="relative z-10 w-full rounded-lg overflow-hidden border p-0.5 flex flex-col gap-0.5 opacity-60 shadow-md"
          style={{ backgroundColor: theme.cardBg, borderColor: theme.cardBorder }}
        >
          {renderEntrantRow({ name: 'TBD', score: 0 }, false)}
          {renderEntrantRow({ name: 'TBD', score: 0 }, false)}
        </div>
      );
    }

    const isComplete = match.state === 'complete';
    const p1Winner = isComplete && match.p1?.is_winner;
    const p2Winner = isComplete && match.p2?.is_winner;

    return (
      <div
        className={`relative z-10 w-full rounded-lg overflow-hidden border p-0.5 flex flex-col gap-0.5 transition-all shadow-md ${
          isFinals ? 'ring-1' : ''
        }`}
        style={{
          backgroundColor: theme.cardBg,
          borderColor: isFinals ? theme.accent : theme.cardBorder,
          boxShadow: isFinals ? `0 0 12px ${theme.winnerGlow}` : undefined,
        }}
      >
        {renderEntrantRow(match.p1, p1Winner)}
        {renderEntrantRow(match.p2, p2Winner)}
      </div>
    );
  };

  // Grand Finals Slot (Shows Set 2 ONLY when reset is active)
  const renderGrandFinalsSlot = () => {
    const gf = matches.grand_finals;
    const gfReset = matches.grand_finals_reset;
    const hasReset = (Boolean(resolvedData?.reset_active) || Boolean(simulateReset)) && Boolean(gfReset);

    return (
      <div className="w-full flex flex-col gap-2">
        {/* Set 1 */}
        <div className="w-full">
          {renderMatchCard(gf, 'GRAND FINALS', true)}
        </div>

        {/* Set 2 (Grand Finals Reset - STRICTLY hidden if reset not triggered) */}
        {hasReset && (
          <div className="w-full pt-1.5 border-t border-amber-500/40 animate-in fade-in duration-300">
            <div className="flex items-center justify-center mb-1">
              <span className="px-2 py-0.5 rounded text-[9px] font-black tracking-widest uppercase bg-gradient-to-r from-amber-500 to-rose-500 text-slate-950 shadow-md animate-pulse">
                ⚡ RESET (SET 2)
              </span>
            </div>
            {renderMatchCard(gfReset, 'GRAND FINALS RESET', true)}
          </div>
        )}
      </div>
    );
  };

  // Loading / Error Handling
  if (!isTestMode && !resolvedData) {
    if (isObsMode) {
      return <div className="w-full h-full bg-transparent" />;
    }
    return (
      <div className="w-full h-full flex flex-col items-center justify-center p-6 text-center rounded-2xl bg-slate-950/90 border-2 border-dashed border-white/20 text-white select-none">
        <span className="text-3xl mb-2">⚡</span>
        <h3 className="text-lg font-black tracking-wider uppercase text-white">
          {loading ? 'SYNCING BRACKET...' : error ? 'BRACKET SYNC ERROR' : 'NO TOURNAMENT CONNECTED'}
        </h3>
        <p className="text-xs text-white/70 max-w-md mt-1">
          {loading
            ? 'Fetching live Top 8 bracket structure from provider...'
            : error
            ? `${error}. Ensure tournament exists and is reachable.`
            : 'No active tournament found. Connect a tournament in Hub, or enable Test Mode to preview.'}
        </p>
      </div>
    );
  }

  // ===========================================================================
  // LAYOUT 1: TOP 8 DOUBLE ELIMINATION (4-Column Tree)
  // ===========================================================================
  if (layout === 'top8-double-elim') {
    return (
      <div
        key={animKey}
        className="w-full h-full relative select-none flex flex-col justify-between overflow-hidden p-6 rounded-2xl"
        style={{
          fontFamily: element.fontFamily || undefined,
          color: element.color || '#fff',
          background: showBackground ? theme.bg : 'transparent',
          border: showBackground ? `2px solid ${theme.cardBorder}` : 'none',
          boxShadow: showBackground ? '0 0 50px rgba(0, 0, 0, 0.8)' : 'none',
        }}
      >
        {/* Top Header Bar */}
        <div
          className="relative w-full h-12 rounded-lg border flex items-center justify-between px-5 z-10 shrink-0 overflow-hidden shadow-lg"
          style={{
            background: theme.header,
            borderColor: theme.cardBorder,
          }}
        >
          {/* Main Tournament / Game Header Title */}
          <div className="flex items-center gap-2.5">
            <span className="w-2.5 h-2.5 bg-white rotate-45 shrink-0 shadow-sm" />
            <h1 className="text-lg md:text-xl font-black italic tracking-wider text-white uppercase drop-shadow-md">
              {gameTitle ? `${gameTitle}: ` : ''}TOP 8 BRACKET
            </h1>
          </div>

          {/* Right Legend */}
          <div className="flex items-center gap-3 text-xs font-bold text-white/90">
            <span className="flex items-center gap-1.5">
              <span className="px-1.5 py-0.5 rounded text-[10px] font-black bg-emerald-500/30 text-emerald-300 border border-emerald-400/60">
                [W]
              </span>
              <span>Winners</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="px-1.5 py-0.5 rounded text-[10px] font-black bg-amber-500/30 text-amber-300 border border-amber-400/60">
                [L]
              </span>
              <span>Losers</span>
            </span>
          </div>
        </div>

        {/* Main Bracket Arena (4 Columns with Orthogonal Connectors) */}
        <div className="relative flex-1 w-full my-3 z-10 min-h-0 flex flex-col justify-between">
          {/* UPPER SECTION: WINNERS BRACKET */}
          <div className="w-full grid grid-cols-4 gap-8 items-start h-[46%]">
            {/* Col 1: Winners Semifinals */}
            <div className="flex flex-col gap-2 h-full justify-start">
              <div
                className="font-black text-[11px] py-1 px-3 rounded uppercase tracking-wider text-center shadow border"
                style={{ backgroundColor: theme.cardBg, borderColor: theme.cardBorder, color: '#fff' }}
              >
                WINNERS SEMIS ({roundFormat})
              </div>
              <div className="flex flex-col justify-around flex-1 gap-2">
                {renderMatchCard(matches.winners_semis?.[0], 'WSF 1')}
                {renderMatchCard(matches.winners_semis?.[1], 'WSF 2')}
              </div>
            </div>

            {/* Col 2: Winners Finals */}
            <div className="flex flex-col gap-2 h-full justify-start">
              <div
                className="font-black text-[11px] py-1 px-3 rounded uppercase tracking-wider text-center shadow border"
                style={{ backgroundColor: theme.cardBg, borderColor: theme.cardBorder, color: '#fff' }}
              >
                WINNERS FINALS ({roundFormat})
              </div>
              <div className="flex flex-col justify-center flex-1">
                {renderMatchCard(matches.winners_finals, 'WINNERS FINALS', true)}
              </div>
            </div>

            {/* Col 3: Spacer */}
            <div className="flex flex-col gap-2 h-full opacity-0 pointer-events-none">
              <div className="py-1 px-3 text-xs font-black">SPACER</div>
            </div>

            {/* Col 4: Grand Finals */}
            <div className="flex flex-col gap-2 h-full justify-start">
              <div
                className="font-black text-[11px] py-1 px-3 rounded uppercase tracking-wider text-center shadow border"
                style={{ backgroundColor: theme.cardBg, borderColor: theme.cardBorder, color: '#fff' }}
              >
                GRAND FINALS ({roundFormat})
              </div>
              <div className="flex flex-col justify-center flex-1">
                {renderGrandFinalsSlot()}
              </div>
            </div>
          </div>

          {/* LOWER SECTION: LOSERS BRACKET */}
          <div className="w-full grid grid-cols-4 gap-8 items-start h-[52%]">
            {/* Col 1: Losers Round 1 */}
            <div className="flex flex-col gap-2 h-full justify-start">
              <div
                className="font-black text-[11px] py-1 px-3 rounded uppercase tracking-wider text-center shadow border"
                style={{ backgroundColor: theme.cardBg, borderColor: theme.cardBorder, color: '#fff' }}
              >
                LOSERS ROUND 1 ({roundFormat})
              </div>
              <div className="flex flex-col justify-around flex-1 gap-2">
                {renderMatchCard(matches.losers_round1?.[0], 'LR1 - 1')}
                {renderMatchCard(matches.losers_round1?.[1], 'LR1 - 2')}
              </div>
            </div>

            {/* Col 2: Losers Quarters */}
            <div className="flex flex-col gap-2 h-full justify-start">
              <div
                className="font-black text-[11px] py-1 px-3 rounded uppercase tracking-wider text-center shadow border"
                style={{ backgroundColor: theme.cardBg, borderColor: theme.cardBorder, color: '#fff' }}
              >
                LOSERS QUARTERS ({roundFormat})
              </div>
              <div className="flex flex-col justify-around flex-1 gap-2">
                {renderMatchCard(matches.losers_quarters?.[0], 'LQF 1')}
                {renderMatchCard(matches.losers_quarters?.[1], 'LQF 2')}
              </div>
            </div>

            {/* Col 3: Losers Semis */}
            <div className="flex flex-col gap-2 h-full justify-start">
              <div
                className="font-black text-[11px] py-1 px-3 rounded uppercase tracking-wider text-center shadow border"
                style={{ backgroundColor: theme.cardBg, borderColor: theme.cardBorder, color: '#fff' }}
              >
                LOSERS SEMIS ({roundFormat})
              </div>
              <div className="flex flex-col justify-center flex-1">
                {renderMatchCard(matches.losers_semis, 'LOSERS SEMIS')}
              </div>
            </div>

            {/* Col 4: Losers Finals */}
            <div className="flex flex-col gap-2 h-full justify-start">
              <div
                className="font-black text-[11px] py-1 px-3 rounded uppercase tracking-wider text-center shadow border"
                style={{ backgroundColor: theme.cardBg, borderColor: theme.cardBorder, color: '#fff' }}
              >
                LOSERS FINALS ({roundFormat})
              </div>
              <div className="flex flex-col justify-center flex-1">
                {renderMatchCard(matches.losers_finals, 'LOSERS FINALS', true)}
              </div>
            </div>
          </div>

          {/* SVG Connector Lines (Subtle z-0 underneath solid match cards) */}
          <svg className="absolute inset-0 w-full h-full pointer-events-none z-0">
            {/* WSF 1 & 2 -> WF */}
            <line x1="22.5%" y1="13.5%" x2="24%" y2="13.5%" stroke={theme.connector} strokeWidth="2.5" strokeLinecap="round" />
            <line x1="22.5%" y1="36.5%" x2="24%" y2="36.5%" stroke={theme.connector} strokeWidth="2.5" strokeLinecap="round" />
            <line x1="24%" y1="13.5%" x2="24%" y2="36.5%" stroke={theme.connector} strokeWidth="2.5" strokeLinecap="round" />
            <line x1="24%" y1="25%" x2="25.5%" y2="25%" stroke={theme.connector} strokeWidth="2.5" strokeLinecap="round" />

            {/* WF -> GF */}
            <line x1="48%" y1="25%" x2="75.5%" y2="25%" stroke={theme.connector} strokeWidth="2.5" strokeLinecap="round" />

            {/* LR1 -> LQF */}
            <line x1="22.5%" y1="65.5%" x2="25.5%" y2="65.5%" stroke={theme.connector} strokeWidth="2.5" strokeLinecap="round" />
            <line x1="22.5%" y1="88.5%" x2="25.5%" y2="88.5%" stroke={theme.connector} strokeWidth="2.5" strokeLinecap="round" />

            {/* LQF -> LSF */}
            <line x1="48%" y1="65.5%" x2="49.5%" y2="65.5%" stroke={theme.connector} strokeWidth="2.5" strokeLinecap="round" />
            <line x1="48%" y1="88.5%" x2="49.5%" y2="88.5%" stroke={theme.connector} strokeWidth="2.5" strokeLinecap="round" />
            <line x1="49.5%" y1="65.5%" x2="49.5%" y2="88.5%" stroke={theme.connector} strokeWidth="2.5" strokeLinecap="round" />
            <line x1="49.5%" y1="77%" x2="51%" y2="77%" stroke={theme.connector} strokeWidth="2.5" strokeLinecap="round" />

            {/* LSF -> LF */}
            <line x1="73.5%" y1="77%" x2="75.5%" y2="77%" stroke={theme.connector} strokeWidth="2.5" strokeLinecap="round" />

            {/* LF -> GF Ascent */}
            <line x1="98.5%" y1="77%" x2="99.2%" y2="77%" stroke={theme.connector} strokeWidth="2.5" strokeLinecap="round" />
            <line x1="99.2%" y1="77%" x2="99.2%" y2="25%" stroke={theme.connector} strokeWidth="2.5" strokeLinecap="round" />
            <line x1="99.2%" y1="25%" x2="98.5%" y2="25%" stroke={theme.connector} strokeWidth="2.5" strokeLinecap="round" />
          </svg>
        </div>

        {/* Bottom Broadcast Footer (Broadcast-safe, no copyrighted third-party sponsor logos) */}
        {showSponsors && (
          <div
            className="relative w-full h-12 rounded-lg border px-5 py-2 flex items-center justify-between shadow-lg z-10 shrink-0"
            style={{ backgroundColor: theme.cardBg, borderColor: theme.cardBorder }}
          >
            <div className="flex items-center gap-3">
              <span className="text-xl">🏆</span>
              <div className="flex flex-col">
                <span className="text-xs font-black uppercase tracking-wider text-white">
                  {tournamentTitle || 'TOURNAMENT BROADCAST'}
                </span>
                <span className="text-[9px] font-bold uppercase tracking-wider opacity-60">
                  OFFICIAL TOURNAMENT BROADCAST
                </span>
              </div>
            </div>

            <div className="text-xs font-black uppercase tracking-wider" style={{ color: theme.accent }}>
              {element.bracketSponsorText || 'POWERED BY AITOB BROADCAST ENGINE'}
            </div>
          </div>
        )}
      </div>
    );
  }

  // ===========================================================================
  // LAYOUT 2: TOP 4 SHOWCASE (Bellator MMA 5-Column Progressive Architecture)
  // ===========================================================================
  const wsf1 = matches.winners_semis?.[0];
  const wsf2 = matches.winners_semis?.[1];
  const wf = matches.winners_finals;

  const lr1_1 = matches.losers_round1?.[0];
  const lr1_2 = matches.losers_round1?.[1];
  const lqf1 = matches.losers_quarters?.[0];
  const lqf2 = matches.losers_quarters?.[1];
  const lsf = matches.losers_semis;
  const lf = matches.losers_finals;

  const gf = matches.grand_finals;
  const gfReset = matches.grand_finals_reset;
  const isReset = (Boolean(resolvedData?.reset_active) || Boolean(simulateReset)) && Boolean(gfReset);
  const activeGF = isReset ? gfReset : gf;

  // Resolve active Losers Feeder matches for Far Right (Col 5)
  // In Top 8: LR1 or LQF. In Top 4: LSF.
  const hasRealLr1 = Boolean(lr1_1?.p1 && lr1_1.p1.name !== 'TBD');
  const hasRealLqf = Boolean(lqf1?.p1 && lqf1.p1.name !== 'TBD');

  const farRightMatch1 = hasRealLr1
    ? lr1_1
    : hasRealLqf
    ? lqf1
    : lsf;

  const farRightMatch2 = hasRealLr1
    ? lr1_2
    : hasRealLqf
    ? lqf2
    : null;

  // Determine World Champion
  const isGfComplete = activeGF?.state === 'complete';
  const champion = isGfComplete
    ? activeGF?.p1?.is_winner
      ? activeGF.p1
      : activeGF?.p2?.is_winner
      ? activeGF.p2
      : null
    : null;

  // Single Fighter Portrait Card in authentic Bellator MMA Grand Prix style (Strict 4:5 Portrait)
  const renderGrandPrixFighterCard = (
    entrant: any,
    isWinner: boolean,
    origin?: 'winners' | 'losers',
    isLarge = false,
    lineageLabel?: string,
    cardIndex = 0
  ) => {
    const isTbd = !entrant || entrant.name === 'TBD';
    const code = countryCode(entrant?.country) || (entrant?.country ? String(entrant.country).trim().slice(0, 3).toUpperCase() : null);
    const cardAnim = element.bracketCardAnimation || 'deal';

    // Smart Prefix & Name Extraction (e.g. "FGC FNCESPORTS" => prefix: "FGC", name: "FNCESPORTS")
    let displayPrefix = entrant?.prefix;
    let displayName = entrant?.name || '';
    if (!displayPrefix && displayName.includes(' ')) {
      const parts = displayName.split(' ');
      if (parts[0].length <= 5 && parts.length > 1) {
        displayPrefix = parts[0];
        displayName = parts.slice(1).join(' ');
      }
    }

    let animClass = '';
    if (cardAnim === 'deal') animClass = 'tcg-anim-deal';
    else if (cardAnim === 'slam') animClass = 'tcg-anim-slam';
    else if (cardAnim === 'flip') animClass = 'tcg-anim-flip';
    else if (cardAnim === 'float') animClass = 'tcg-anim-float';
    else if (cardAnim === 'hologram') animClass = 'tcg-anim-hologram';
    else if (cardAnim === 'glow-pulse') animClass = 'tcg-anim-glow';

    const delayMs = cardAnim !== 'none' ? `${baseOffsetMs + Math.min(cardIndex * 65, 800)}ms` : '0ms';

    return (
      <div
        className={`relative rounded-xl overflow-hidden border transition-all duration-300 flex flex-col justify-between shadow-2xl shrink-0 group hover:scale-105 hover:-translate-y-1.5 hover:z-30 cursor-pointer ${animClass} ${
          isLarge
            ? 'w-32 md:w-36 lg:w-40 aspect-[4/5]'
            : 'w-24 md:w-28 lg:w-32 aspect-[4/5]'
        }`}
        style={{
          animationDelay: delayMs,
          backgroundColor: '#121214',
          borderColor: isWinner ? theme.accent : 'rgba(255, 255, 255, 0.16)',
          boxShadow: isWinner ? `0 0 18px ${theme.winnerGlow}` : '0 4px 14px rgba(0,0,0,0.6)',
        }}
      >
        {/* Hologram Scanline Effect */}
        {cardAnim === 'hologram' && (
          <div
            className="pointer-events-none absolute inset-x-0 h-16 bg-gradient-to-b from-transparent via-cyan-400/25 to-transparent z-20"
            style={{
              animation: 'tcgHologramScan 2.6s linear infinite',
              animationDelay: `${(cardIndex * 150) % 1000}ms`,
            }}
          />
        )}

        {/* Foil Shimmer Sheen Layer */}
        {cardAnim !== 'none' && (
          <div
            className="pointer-events-none absolute -inset-full w-[300%] h-[300%] bg-gradient-to-r from-transparent via-white/10 to-transparent z-20"
            style={{
              animation: 'tcgFoilShimmer 4s ease-in-out infinite',
              animationDelay: `${1.5 + cardIndex * 0.2}s`,
            }}
          />
        )}

        {/* Top Badges (Country + Origin + Prominent Score Pill) */}
        <div className="absolute top-1.5 left-1.5 right-1.5 flex items-center justify-between z-10 pointer-events-none">
          <div className="flex items-center gap-1">
            {code && (
              <span className="px-1.5 py-0.5 rounded text-[9px] font-black uppercase bg-black/85 text-white border border-white/20 shadow">
                {code}
              </span>
            )}
            {renderOriginBadge(origin || entrant?.bracket_origin)}
          </div>

          {/* Prominent Glowing Score Badge */}
          <span
            className="px-1.5 py-0.5 rounded font-mono font-black text-[11px] md:text-xs bg-black/90 border shadow-lg"
            style={{
              color: isWinner ? theme.accent : theme.scoreText || '#ffffff',
              borderColor: isWinner ? theme.accent : 'rgba(255, 255, 255, 0.25)',
              boxShadow: isWinner ? `0 0 10px ${theme.winnerGlow}` : undefined,
            }}
          >
            {entrant?.score ?? 0}
          </span>
        </div>

        {/* Fighter Photo / Avatar (Fills portrait box cleanly with head & shoulders) */}
        <div className="relative flex-1 w-full flex items-center justify-center overflow-hidden bg-gradient-to-b from-white/10 to-transparent min-h-0">
          {entrant?.avatar_url ? (
            <img
              src={entrant.avatar_url}
              alt={displayName}
              className="w-full h-full object-cover object-top group-hover:scale-105 transition-transform duration-500"
              onError={(e) => { (e.target as HTMLElement).style.display = 'none'; }}
            />
          ) : (
            <div className="flex flex-col items-center justify-center text-white/40">
              <span className={`${isLarge ? 'text-2xl' : 'text-lg'} font-black`}>
                {!isTbd && displayName ? displayName.slice(0, 2).toUpperCase() : '??'}
              </span>
            </div>
          )}

          {/* Feeder / Lineage Origin Badge */}
          {lineageLabel && (
            <div className="absolute bottom-1 left-1 px-1 py-0.2 rounded bg-black/85 text-[7px] font-mono uppercase text-white/80 border border-white/15 shadow">
              {lineageLabel}
            </div>
          )}
        </div>

        {/* Solid Bottom Accent Bar with Fighter Name (Bellator Red / Accent Banner) */}
        <div
          className="w-full py-1.5 px-1 flex items-center justify-center text-center shrink-0 shadow-md transition-colors min-h-[26px]"
          style={{
            backgroundColor: isWinner ? theme.accent : '#1c1c1f',
            color: isWinner ? '#000000' : '#ffffff',
          }}
        >
          {isTbd ? (
            <span className="text-xs md:text-[13px] font-black uppercase tracking-wider">TBD</span>
          ) : (
            <div className="flex items-center justify-center gap-1 w-full overflow-hidden px-0.5">
              {displayPrefix && (
                <span
                  className={`text-[8px] md:text-[9px] font-bold uppercase truncate max-w-[40%] shrink-0 ${
                    isWinner ? 'text-black/80' : 'text-white/60'
                  }`}
                >
                  {displayPrefix}
                </span>
              )}
              <span
                className={`font-black uppercase tracking-wider truncate ${
                  displayName.length > 11 ? 'text-[9px] md:text-[10px]' : 'text-xs md:text-[11px]'
                }`}
              >
                {displayName}
              </span>
            </div>
          )}
        </div>
      </div>
    );
  };

  // Complete Match Unit Block with Vertical Bracket Spine (Bellator MMA Reference)
  const renderMmaMatchBlock = (
    matchNode: any,
    roundTitle: string,
    side: 'left' | 'right',
    bestOf = roundFormat,
    startCardIndex = 0
  ) => {
    const isMatchActive = matchNode?.state === 'active';
    const isP1Winner = matchNode?.state === 'complete' && Boolean(matchNode?.p1?.is_winner);
    const isP2Winner = matchNode?.state === 'complete' && Boolean(matchNode?.p2?.is_winner);

    if (side === 'left') {
      return (
        <div className="flex items-center gap-1.5 shrink-0">
          {/* Stacked Fighter Cards (2 fighters) */}
          <div className="flex flex-col gap-2 shrink-0">
            {renderGrandPrixFighterCard(matchNode?.p1, isP1Winner, undefined, false, undefined, startCardIndex)}
            {renderGrandPrixFighterCard(matchNode?.p2, isP2Winner, undefined, false, undefined, startCardIndex + 1)}
          </div>

          {/* Right-Side Bracket Spine with Vertical Badge & Outbound Connector */}
          <div className="flex items-center self-stretch py-2 shrink-0">
            <div
              className="relative flex items-center justify-center h-full border-r-2 border-t-2 border-b-2 rounded-r-md px-1"
              style={{ borderColor: theme.connector }}
            >
              <div
                className="px-0.5 py-2 rounded bg-black/95 border text-[10px] md:text-[11px] font-black uppercase tracking-widest whitespace-nowrap select-none shadow-md"
                style={{
                  writingMode: 'vertical-lr',
                  transform: 'rotate(180deg)',
                  borderColor: isMatchActive ? theme.accent : 'rgba(255, 255, 255, 0.2)',
                  color: isMatchActive ? theme.accent : '#ffffff',
                }}
              >
                {roundTitle} {bestOf ? `• ${bestOf}` : ''}
              </div>
            </div>
            {/* Outbound Connector Line */}
            <div className="w-2.5 md:w-3.5 h-0.5" style={{ backgroundColor: theme.connector }} />
          </div>
        </div>
      );
    }

    // Mirrored for Right Side
    return (
      <div className="flex items-center gap-1.5 shrink-0">
        {/* Inbound Connector Line & Left-Side Bracket Spine */}
        <div className="flex items-center self-stretch py-2 shrink-0">
          <div className="w-2.5 md:w-3.5 h-0.5" style={{ backgroundColor: theme.connector }} />
          <div
            className="relative flex items-center justify-center h-full border-l-2 border-t-2 border-b-2 rounded-l-md px-1"
            style={{ borderColor: theme.connector }}
          >
            <div
              className="px-0.5 py-2 rounded bg-black/95 border text-[10px] md:text-[11px] font-black uppercase tracking-widest whitespace-nowrap select-none shadow-md"
              style={{
                writingMode: 'vertical-lr',
                borderColor: isMatchActive ? theme.accent : 'rgba(255, 255, 255, 0.2)',
                color: isMatchActive ? theme.accent : '#ffffff',
              }}
            >
              {roundTitle} {bestOf ? `• ${bestOf}` : ''}
            </div>
          </div>
        </div>

        {/* Stacked Fighter Cards (2 fighters) */}
        <div className="flex flex-col gap-2 shrink-0">
          {renderGrandPrixFighterCard(matchNode?.p1, isP1Winner, undefined, false, undefined, startCardIndex)}
          {renderGrandPrixFighterCard(matchNode?.p2, isP2Winner, undefined, false, undefined, startCardIndex + 1)}
        </div>
      </div>
    );
  };

  return (
    <div
      key={animKey}
      className="w-full h-full relative select-none flex flex-col justify-between overflow-hidden p-4 md:p-6 rounded-2xl"
      style={{
        fontFamily: element.fontFamily || undefined,
        color: element.color || '#fff',
        background: showBackground ? theme.bg : 'transparent',
        border: showBackground ? `2px solid ${theme.cardBorder}` : 'none',
        boxShadow: showBackground ? '0 0 50px rgba(0, 0, 0, 0.9)' : 'none',
      }}
    >
      {/* Dynamic Keyframes & Card Game Animation Engine */}
      <style>{`
        @keyframes tcgDeal {
          0% {
            opacity: 0;
            transform: translateY(-30px) scale(0.88) rotate(-3deg);
          }
          60% {
            opacity: 1;
            transform: translateY(4px) scale(1.02) rotate(1deg);
          }
          100% {
            opacity: 1;
            transform: translateY(0) scale(1) rotate(0deg);
          }
        }

        @keyframes tcgSlam {
          0% {
            opacity: 0;
            transform: translateY(-80px) scale(1.4);
            filter: brightness(2.2);
          }
          65% {
            opacity: 1;
            transform: translateY(0) scale(0.96);
            filter: brightness(1.3);
          }
          82% {
            transform: translateY(-4px) scale(1.02);
          }
          100% {
            opacity: 1;
            transform: translateY(0) scale(1);
            filter: brightness(1);
          }
        }

        @keyframes tcgFlip {
          0% {
            opacity: 0;
            transform: perspective(700px) rotateY(90deg) scale(0.85);
          }
          60% {
            opacity: 1;
            transform: perspective(700px) rotateY(-8deg) scale(1.03);
          }
          100% {
            opacity: 1;
            transform: perspective(700px) rotateY(0deg) scale(1);
          }
        }

        @keyframes tcgFloat {
          0%, 100% {
            transform: translateY(0px) rotate(0deg);
          }
          50% {
            transform: translateY(-5px) rotate(0.6deg);
          }
        }

        @keyframes tcgHologramScan {
          0% {
            top: -120%;
            opacity: 0;
          }
          20% {
            opacity: 0.9;
          }
          80% {
            opacity: 0.9;
          }
          100% {
            top: 220%;
            opacity: 0;
          }
        }

        @keyframes tcgEnergyPulse {
          0%, 100% {
            box-shadow: 0 0 10px rgba(239, 68, 68, 0.35);
          }
          50% {
            box-shadow: 0 0 24px rgba(239, 68, 68, 0.85);
          }
        }

        @keyframes tcgFoilShimmer {
          0% {
            transform: translateX(-180%) rotate(25deg);
          }
          30%, 100% {
            transform: translateX(280%) rotate(25deg);
          }
        }

        .tcg-anim-deal {
          animation: tcgDeal 0.6s cubic-bezier(0.16, 1, 0.3, 1) backwards;
        }
        .tcg-anim-slam {
          animation: tcgSlam 0.55s cubic-bezier(0.2, 0.8, 0.2, 1) backwards;
        }
        .tcg-anim-flip {
          animation: tcgFlip 0.65s cubic-bezier(0.25, 1, 0.5, 1) backwards;
        }
        .tcg-anim-float {
          animation: tcgDeal 0.5s ease-out backwards, tcgFloat 3.2s ease-in-out infinite 0.5s;
        }
        .tcg-anim-hologram {
          animation: tcgDeal 0.5s ease-out backwards;
        }
        .tcg-anim-glow {
          animation: tcgDeal 0.5s ease-out backwards, tcgEnergyPulse 2.4s ease-in-out infinite;
        }
      `}</style>

      {/* Top Header */}
      <div className="relative z-10 flex items-center justify-between pb-2 border-b border-white/10 shrink-0">
        <div className="flex items-center gap-3">
          <span
            className="px-3 py-1 rounded text-white font-black text-xs uppercase tracking-wider shadow"
            style={{ backgroundColor: theme.accent, color: '#000' }}
          >
            DYNAMIC TOP 8
          </span>
          <span className="text-sm md:text-base font-black tracking-widest uppercase text-white">
            {gameTitle ? `${gameTitle} · ` : ''}{tournamentTitle || 'WORLD GRAND PRIX'}
          </span>
        </div>
        {isReset && (
          <span className="px-3 py-1 rounded-full bg-gradient-to-r from-amber-500 to-rose-500 text-slate-950 text-xs font-black tracking-widest uppercase shadow-lg animate-pulse">
            ⚡ GRAND FINALS RESET ACTIVE (SET 2)
          </span>
        )}
      </div>

      {/* Symmetrical 5-Column Progressive Grand Prix Arena with Explicit Bracket Bridges */}
      <div className="relative z-10 flex-1 flex items-stretch justify-center w-full h-full min-h-0 py-2 px-1 gap-1 md:gap-2.5 lg:gap-4 overflow-hidden">
        {/* ================================================================= */}
        {/* COL 1: FAR LEFT - WINNERS SEMIFINALS (4 FIGHTERS / 2 MATCHES)     */}
        {/* ================================================================= */}
        <div className="flex flex-col items-center h-full shrink-0">
          {/* Unified Stage Header Badge */}
          <div
            className="px-3 py-1 rounded-md text-center font-black text-[10px] md:text-[11px] uppercase tracking-wider border shadow-md shrink-0 mb-3 whitespace-nowrap"
            style={{
              backgroundColor: '#18181b',
              borderColor: 'rgba(255, 255, 255, 0.18)',
              color: '#ffffff',
            }}
          >
            WINNERS SEMIS
          </div>

          {/* Match Blocks */}
          <div className="flex-1 flex flex-col justify-around items-center w-full min-h-0 my-auto py-1">
            {renderMmaMatchBlock(wsf1, 'SEMI 1', 'left', roundFormat, 0)}
            {renderMmaMatchBlock(wsf2, 'SEMI 2', 'left', roundFormat, 2)}
          </div>
        </div>

        {/* ================================================================= */}
        {/* BRIDGE 1-TO-2: BRACKET FORK FROM WSF 1 & 2 INTO WINNERS FINALS     */}
        {/* ================================================================= */}
        <div className="flex flex-col items-center h-full shrink-0 w-8 md:w-10">
          <div className="h-[28px] shrink-0 mb-3" />
          <div className="flex-1 w-full my-auto py-1 flex items-center justify-center">
            <svg className="w-full h-full pointer-events-none" viewBox="0 0 40 100" preserveAspectRatio="none">
              <path
                d="M 0,25 H 22 V 75 H 0"
                fill="none"
                stroke={theme.connector}
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{ vectorEffect: 'non-scaling-stroke', filter: `drop-shadow(0 0 4px ${theme.winnerGlow})` }}
              />
              <path
                d="M 22,50 H 35"
                fill="none"
                stroke={theme.connector}
                strokeWidth="2.5"
                strokeLinecap="round"
                style={{ vectorEffect: 'non-scaling-stroke', filter: `drop-shadow(0 0 4px ${theme.winnerGlow})` }}
              />
              <polygon points="34,46 40,50 34,54" fill={theme.accent} />
            </svg>
          </div>
        </div>

        {/* ================================================================= */}
        {/* COL 2: LEFT INNER - WINNERS FINALS (2 FIGHTERS / 1 MATCH)         */}
        {/* ================================================================= */}
        <div className="flex flex-col items-center h-full shrink-0">
          {/* Unified Stage Header Badge */}
          <div
            className="px-3 py-1 rounded-md text-center font-black text-[10px] md:text-[11px] uppercase tracking-wider border shadow-md shrink-0 mb-3 whitespace-nowrap"
            style={{
              backgroundColor: '#18181b',
              borderColor: 'rgba(255, 255, 255, 0.18)',
              color: '#ffffff',
            }}
          >
            WINNERS FINALS
          </div>

          {/* Match Block */}
          <div className="flex-1 flex flex-col justify-center items-center w-full min-h-0 my-auto">
            {renderMmaMatchBlock(wf, 'WINNERS FINAL', 'left', roundFormat, 4)}
          </div>
        </div>

        {/* ================================================================= */}
        {/* BRIDGE 2-TO-3: DIRECT ARROW LINE INTO GRAND FINALS (WINNERS SIDE)  */}
        {/* ================================================================= */}
        <div className="flex flex-col items-center h-full shrink-0 w-8 md:w-10">
          <div className="h-[28px] shrink-0 mb-3" />
          <div className="flex-1 flex items-center justify-center w-full">
            <div className="w-full h-0.5" style={{ backgroundColor: theme.connector, boxShadow: `0 0 8px ${theme.winnerGlow}` }} />
            <span className="text-xs font-black -ml-1" style={{ color: theme.accent }}>►</span>
          </div>
        </div>

        {/* ================================================================= */}
        {/* COL 3: CENTER - GRAND FINALS FACE-OFF & WORLD CHAMPION PODIUM     */}
        {/* ================================================================= */}
        <div className="flex flex-col items-center h-full shrink-0 max-w-sm md:max-w-md px-1">
          {/* Unified Stage Header Badge */}
          <div
            className="px-3.5 py-1 rounded-md text-center font-black text-[10px] md:text-[11px] uppercase tracking-widest border shadow-lg shrink-0 mb-3 flex items-center gap-1.5 whitespace-nowrap"
            style={{
              backgroundColor: theme.accent,
              borderColor: theme.accent,
              color: '#000000',
            }}
          >
            <span>👑</span>
            <span>{isReset ? 'GRAND FINALS (SET 2)' : 'GRAND FINALS'}</span>
          </div>

          {/* Hero Faceoff Arena */}
          <div className="flex-1 flex flex-col justify-center items-center w-full min-h-0 gap-2">
            {/* Grand Finals Faceoff Hero Cards */}
            <div className="flex items-center justify-center gap-2">
              {/* Finalist 1 (Winners Bracket Champion) */}
              {renderGrandPrixFighterCard(
                activeGF?.p1,
                isGfComplete && Boolean(activeGF.p1?.is_winner),
                'winners',
                true,
                'WINNERS SIDE',
                6
              )}

              {/* Center VS Element */}
              <div className="flex flex-col items-center justify-center text-center px-1">
                <span
                  className="text-2xl md:text-3xl font-black italic tracking-tighter drop-shadow"
                  style={{ color: theme.accent }}
                >
                  VS
                </span>
                <span className="text-[9px] font-black uppercase tracking-widest text-white/60 mt-0.5">
                  {roundFormat}
                </span>
              </div>

              {/* Finalist 2 (Losers Bracket Champion) */}
              {renderGrandPrixFighterCard(
                activeGF?.p2,
                isGfComplete && Boolean(activeGF.p2?.is_winner),
                'losers',
                true,
                'LOSERS SIDE',
                7
              )}
            </div>

            {/* Grand Finals Reset: Historic Set 1 Collapsed Bar */}
            {isReset && (
              <div className="w-full max-w-xs py-1 px-2.5 rounded-lg bg-black/85 border border-amber-500/50 flex items-center justify-between text-[11px] font-mono shadow-md">
                <div className="flex items-center gap-1.5">
                  <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-500 text-slate-950 font-black">
                    SET 1
                  </span>
                  <span className="text-white font-bold">
                    {gf?.p1?.name || 'P1'} ({gf?.p1?.score ?? 0}) - ({gf?.p2?.score ?? 0}) {gf?.p2?.name || 'P2'}
                  </span>
                </div>
                <span className="text-[9px] text-amber-400 font-bold uppercase tracking-wider">
                  RESET TRIGGERED
                </span>
              </div>
            )}

            {/* WORLD CHAMPION PODIUM CARD (Bellator Style Center Box) */}
            <div className="flex flex-col items-center mt-1 w-44 md:w-52 shrink-0">
              <div
                className={`relative w-full rounded-xl overflow-hidden border shadow-2xl flex flex-col items-center justify-between transition-all group hover:scale-105 cursor-pointer ${
                  element.bracketCardAnimation === 'deal'
                    ? 'tcg-anim-deal'
                    : element.bracketCardAnimation === 'slam'
                    ? 'tcg-anim-slam'
                    : element.bracketCardAnimation === 'flip'
                    ? 'tcg-anim-flip'
                    : element.bracketCardAnimation === 'float'
                    ? 'tcg-anim-float'
                    : element.bracketCardAnimation === 'glow-pulse'
                    ? 'tcg-anim-glow'
                    : ''
                }`}
                style={{
                  animationDelay: '600ms',
                  backgroundColor: '#121214',
                  borderColor: champion ? '#f59e0b' : 'rgba(255, 255, 255, 0.2)',
                  boxShadow: champion ? '0 0 25px rgba(245, 158, 11, 0.4)' : undefined,
                  height: '95px',
                }}
              >
                <div className="flex-1 flex flex-col items-center justify-center p-1.5 text-center">
                  <span className="text-xl mb-0.5">{champion ? '👑' : '🏆'}</span>
                  <span className="text-xs font-black uppercase tracking-wider text-white truncate max-w-[170px]">
                    {champion ? `${champion.prefix ? `${champion.prefix} ` : ''}${champion.name}` : 'TBD'}
                  </span>
                  {champion?.country && (
                    <span className="text-[9px] font-mono text-white/60 uppercase">
                      {countryCode(champion.country) || champion.country}
                    </span>
                  )}
                </div>
                <div
                  className="w-full py-1 text-center font-black text-[10px] uppercase tracking-widest text-slate-950 shadow"
                  style={{ backgroundColor: champion ? '#f59e0b' : '#cbd5e1' }}
                >
                  WORLD CHAMPION
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ================================================================= */}
        {/* BRIDGE 3-TO-4: DIRECT ARROW LINE INTO GRAND FINALS (LOSERS SIDE)   */}
        {/* ================================================================= */}
        <div className="flex flex-col items-center h-full shrink-0 w-8 md:w-10">
          <div className="h-[28px] shrink-0 mb-3" />
          <div className="flex-1 flex items-center justify-center w-full">
            <span className="text-xs font-black -mr-1" style={{ color: theme.accent }}>◄</span>
            <div className="w-full h-0.5" style={{ backgroundColor: theme.connector, boxShadow: `0 0 8px ${theme.winnerGlow}` }} />
          </div>
        </div>

        {/* ================================================================= */}
        {/* COL 4: RIGHT INNER - LOSERS FINALS (2 FIGHTERS / 1 MATCH)         */}
        {/* ================================================================= */}
        <div className="flex flex-col items-center h-full shrink-0">
          {/* Unified Stage Header Badge */}
          <div
            className="px-3 py-1 rounded-md text-center font-black text-[10px] md:text-[11px] uppercase tracking-wider border shadow-md shrink-0 mb-3 whitespace-nowrap"
            style={{
              backgroundColor: '#18181b',
              borderColor: 'rgba(255, 255, 255, 0.18)',
              color: '#ffffff',
            }}
          >
            LOSERS FINALS
          </div>

          {/* Match Block */}
          <div className="flex-1 flex flex-col justify-center items-center w-full min-h-0 my-auto">
            {renderMmaMatchBlock(lf, 'LOSERS FINAL', 'right', roundFormat, 8)}
          </div>
        </div>

        {/* ================================================================= */}
        {/* BRIDGE 4-TO-5: BRACKET FORK/LINE FROM LOSERS FEEDER INTO LF        */}
        {/* ================================================================= */}
        <div className="flex flex-col items-center h-full shrink-0 w-8 md:w-10">
          <div className="h-[28px] shrink-0 mb-3" />
          <div className="flex-1 w-full my-auto py-1 flex items-center justify-center">
            {farRightMatch2 ? (
              <svg className="w-full h-full pointer-events-none" viewBox="0 0 40 100" preserveAspectRatio="none">
                <path
                  d="M 40,25 H 18 V 75 H 40"
                  fill="none"
                  stroke={theme.connector}
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{ vectorEffect: 'non-scaling-stroke', filter: `drop-shadow(0 0 4px ${theme.winnerGlow})` }}
                />
                <path
                  d="M 18,50 H 5"
                  fill="none"
                  stroke={theme.connector}
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  style={{ vectorEffect: 'non-scaling-stroke', filter: `drop-shadow(0 0 4px ${theme.winnerGlow})` }}
                />
                <polygon points="6,46 0,50 6,54" fill={theme.accent} />
              </svg>
            ) : (
              <div className="flex items-center justify-center w-full">
                <span className="text-xs font-black -mr-1" style={{ color: theme.accent }}>◄</span>
                <div className="w-full h-0.5" style={{ backgroundColor: theme.connector, boxShadow: `0 0 8px ${theme.winnerGlow}` }} />
              </div>
            )}
          </div>
        </div>

        {/* ================================================================= */}
        {/* COL 5: FAR RIGHT - LOSERS BRACKET FEEDER (LSF OR LR1/LQF)         */}
        {/* ================================================================= */}
        <div className="flex flex-col items-center h-full shrink-0">
          {/* Unified Stage Header Badge */}
          <div
            className="px-3 py-1 rounded-md text-center font-black text-[10px] md:text-[11px] uppercase tracking-wider border shadow-md shrink-0 mb-3 whitespace-nowrap"
            style={{
              backgroundColor: '#18181b',
              borderColor: 'rgba(255, 255, 255, 0.18)',
              color: '#ffffff',
            }}
          >
            {hasRealLr1 ? 'LOSERS ROUND 1' : hasRealLqf ? 'LOSERS QUARTERS' : 'LOSERS SEMIS'}
          </div>

          {/* Match Content Area */}
          <div
            className={`flex-1 flex flex-col ${
              farRightMatch2 ? 'justify-around' : 'justify-center'
            } items-center w-full min-h-0 my-auto py-1`}
          >
            {renderMmaMatchBlock(
              farRightMatch1,
              hasRealLr1 ? 'LOSERS R1' : hasRealLqf ? 'LOSERS QF 1' : 'LOSERS SEMI',
              'right',
              roundFormat,
              10
            )}
            {farRightMatch2 &&
              renderMmaMatchBlock(
                farRightMatch2,
                hasRealLr1 ? 'LOSERS R1 • M2' : 'LOSERS QF 2',
                'right',
                roundFormat,
                12
              )}
          </div>
        </div>
      </div>

      {/* Bottom Sponsor / Broadcast Bar */}
      {showSponsors && (
        <div className="relative z-10 pt-2 border-t border-white/10 flex items-center justify-between shrink-0">
          <div className="text-xs font-mono text-white/50 uppercase tracking-widest">
            DYNAMIC TOP 8 ENGINE
          </div>
          <div className="text-xs font-black uppercase tracking-wider" style={{ color: theme.accent }}>
            {element.bracketSponsorText || 'POWERED BY AITOB BROADCAST ENGINE'}
          </div>
        </div>
      )}
    </div>
  );
}
