import { useMemo, useState, useEffect } from 'react';
import type { OverlayElement } from '@/store/useEditorStore';
import { useHubStore } from '@/store/useHubStore';

export interface VictoryPathRendererProps {
  element: OverlayElement;
  activeMatch?: any;
  customRunData?: any;
}

// Custom hook to fetch both P1 and P2 victory paths concurrently for 0ms zero-latency switching
function useLiveVictoryPathBoth(
  tournamentSlug: string | null | undefined,
  activeMatch: any,
  isTestMode: boolean
) {
  const [paths, setPaths] = useState<{ p1: any | null; p2: any | null }>({ p1: null, p2: null });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isTestMode || !tournamentSlug || !activeMatch) {
      setPaths({ p1: null, p2: null });
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    const fetchPlayerPath = async (playerId?: string, playerName?: string) => {
      if (!playerId && !playerName) return null;
      const params = new URLSearchParams();
      if (playerId) params.set('player_id', String(playerId));
      if (playerName) params.set('player_name', String(playerName));
      if (activeMatch.event_id) params.set('event_id', String(activeMatch.event_id));

      const res = await fetch(
        `/api/tournaments/${encodeURIComponent(tournamentSlug)}/player-victory-path?${params.toString()}`
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    };

    const fetchBoth = async () => {
      try {
        const [p1Data, p2Data] = await Promise.all([
          fetchPlayerPath(activeMatch.p1_eid, activeMatch.p1_name),
          fetchPlayerPath(activeMatch.p2_eid, activeMatch.p2_name),
        ]);
        if (!cancelled) {
          setPaths({ p1: p1Data, p2: p2Data });
          setError(null);
        }
      } catch (e: any) {
        if (!cancelled) setError(e.message || 'Failed to load victory path');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchBoth();
    const interval = setInterval(fetchBoth, 30000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [
    tournamentSlug,
    activeMatch?.tournament_slug,
    activeMatch?.event_id,
    activeMatch?.p1_eid,
    activeMatch?.p1_name,
    activeMatch?.p2_eid,
    activeMatch?.p2_name,
    isTestMode,
  ]);

  return { paths, loading, error };
}

// Built-in generic demo victory path data (Zero copyrighted brand/sponsor references)
const MOCK_DEMO_VICTORY_PATH = {
  player_name: 'DEMO PLAYER',
  rounds: [
    {
      round_label: 'TOP 8',
      sub_label: 'TOP',
      main_number: '8',
      matches: [
        { score: '2-0', opponent_prefix: 'TEAM A', opponent_name: 'PLAYER A' },
      ],
    },
    {
      round_label: 'ROUND 3',
      sub_label: 'ROUND',
      main_number: '3',
      matches: [
        { score: '2-0', opponent_prefix: 'TEAM B', opponent_name: 'PLAYER B' },
      ],
    },
    {
      round_label: 'ROUND 2',
      sub_label: 'ROUND',
      main_number: '2',
      matches: [
        { score: '2-0', opponent_prefix: 'TEAM C', opponent_name: 'PLAYER C' },
        { score: '2-0', opponent_prefix: 'TEAM D', opponent_name: 'PLAYER D' },
      ],
    },
    {
      round_label: 'ROUND 1',
      sub_label: 'ROUND',
      main_number: '1',
      matches: [
        { score: '2-0', opponent_prefix: 'TEAM E', opponent_name: 'PLAYER E' },
        { score: '2-0', opponent_prefix: 'TEAM F', opponent_name: 'PLAYER F' },
        { score: '2-0', opponent_prefix: '', opponent_name: 'PLAYER G' },
      ],
    },
  ],
};

export function VictoryPathRenderer({ element, activeMatch, customRunData }: VictoryPathRendererProps) {
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

  const isTestMode = element.vpTestMode ?? false;
  const targetPlayer = element.vpTargetPlayer || 'p1';
  const customName = element.vpCustomPlayerName || '';
  const footerText = element.vpFooterText || 'VICTORY PATH';

  const hubCurrentSlug = useHubStore((state) => state.currentSlug);
  const tournaments = useHubStore((state) => state.tournaments);
  const activeTournament = tournaments?.[0];
  const tournamentSlug =
    (element as any).bracketTournamentSlug ||
    activeMatch?.tournament_slug ||
    hubCurrentSlug ||
    activeTournament?.slug;

  const isObsMode = typeof window !== 'undefined' && window.location.pathname.includes('/obs');

  const { paths, loading, error } = useLiveVictoryPathBoth(tournamentSlug, activeMatch, isTestMode);

  // Resolve player name and run
  const data = useMemo(() => {
    if (customRunData && !isTestMode) {
      return customRunData;
    }

    if (!isTestMode) {
      if (targetPlayer === 'custom' && customName) {
        return {
          player_name: customName.toUpperCase(),
          prefix: null,
          country: null,
          rounds: [],
        };
      }

      const activeLive = targetPlayer === 'p2' ? paths.p2 : paths.p1;
      const fallbackName = targetPlayer === 'p2' ? activeMatch?.p2_name : activeMatch?.p1_name;
      const rawName = customName || activeLive?.player_name || fallbackName;

      if (rawName && rawName !== 'TBD') {
        return {
          player_name: rawName.toUpperCase(),
          prefix: activeLive?.prefix || (targetPlayer === 'p2' ? activeMatch?.p2_prefix : activeMatch?.p1_prefix) || null,
          country: activeLive?.country || (targetPlayer === 'p2' ? activeMatch?.p2_country : activeMatch?.p1_country) || null,
          rounds: activeLive?.rounds || [],
        };
      }

      return null;
    }

    // Default test mode: generic demo run clearly labeled as preview
    const result = JSON.parse(JSON.stringify(MOCK_DEMO_VICTORY_PATH));
    if (customName) {
      result.player_name = customName.toUpperCase();
    }
    return result;
  }, [customRunData, isTestMode, targetPlayer, customName, paths, activeMatch]);

  if (!isTestMode && !data) {
    if (isObsMode) {
      return <div className="w-full h-full bg-transparent" />;
    }
    return (
      <div className="w-full h-full flex flex-col items-center justify-center p-6 text-center rounded-r-2xl bg-slate-950/90 border-r-2 border-y-2 border-dashed border-blue-500/40 text-white select-none">
        <span className="text-3xl mb-2">🏆</span>
        <h3 className="text-sm font-black tracking-wider uppercase text-sky-300">
          {loading
            ? 'LOADING VICTORY PATH...'
            : error
            ? 'VICTORY PATH ERROR'
            : !activeMatch
            ? 'NO ACTIVE MATCH'
            : 'NO RUN DATA FOUND'}
        </h3>
        <p className="text-[11px] text-slate-300 max-w-[220px] mt-1 leading-snug">
          {loading
            ? `Fetching match history for ${targetPlayer === 'p2' ? 'P2' : 'P1'}...`
            : error
            ? `${error}`
            : !activeMatch
            ? 'Call a match on this station to show player path.'
            : 'No prior won sets recorded for this player in this tournament.'}
        </p>
      </div>
    );
  }

  const playerName = data.player_name || 'PLAYER';
  const rounds = data.rounds || [];

  const cardAnim = element.vpCardAnimation || 'deal';
  const slideAnim = element.animation;
  const slideDuration = slideAnim && slideAnim.animationType !== 'none' ? slideAnim.duration || 500 : 0;
  const baseOffsetMs = slideDuration > 0 ? Math.round(slideDuration * 0.45) : 0;

  const accentColor = element.vpAccentColor || '#3b82f6';
  const cardBgColor = element.vpCardBgColor || 'rgba(15, 23, 42, 0.7)';
  const borderColor = element.vpBorderColor || 'rgba(59, 130, 246, 0.4)';

  let animClass = '';
  if (cardAnim === 'deal') animClass = 'tcg-anim-deal';
  else if (cardAnim === 'slam') animClass = 'tcg-anim-slam';
  else if (cardAnim === 'flip') animClass = 'tcg-anim-flip';
  else if (cardAnim === 'float') animClass = 'tcg-anim-float';
  else if (cardAnim === 'hologram') animClass = 'tcg-anim-hologram';
  else if (cardAnim === 'glow-pulse') animClass = 'tcg-anim-glow';

  return (
    <div
      key={animKey}
      className="w-full h-full relative select-none flex flex-col justify-between overflow-hidden shadow-2xl rounded-r-2xl border-r-2 border-y-2 transition-colors duration-300"
      style={{
        fontFamily: element.fontFamily || undefined,
        background: element.vpBgColor || 'linear-gradient(180deg, #0d34a4 0%, #072173 50%, #04144d 100%)',
        borderColor: borderColor,
        color: element.color || '#fff',
      }}
    >
      {/* Keyframes Engine */}
      <style>{`
        @keyframes tcgDeal {
          0% {
            opacity: 0;
            transform: translateY(-26px) scale(0.9) rotate(-2deg);
          }
          60% {
            opacity: 1;
            transform: translateY(3px) scale(1.02) rotate(1deg);
          }
          100% {
            opacity: 1;
            transform: translateY(0) scale(1) rotate(0deg);
          }
        }
        @keyframes tcgSlam {
          0% {
            opacity: 0;
            transform: translateY(-60px) scale(1.35);
            filter: brightness(2.2);
          }
          65% {
            opacity: 1;
            transform: translateY(0) scale(0.96);
            filter: brightness(1.3);
          }
          82% {
            transform: translateY(-3px) scale(1.02);
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
            transform: perspective(600px) rotateY(90deg) scale(0.85);
          }
          60% {
            opacity: 1;
            transform: perspective(600px) rotateY(-8deg) scale(1.03);
          }
          100% {
            opacity: 1;
            transform: perspective(600px) rotateY(0deg) scale(1);
          }
        }
        @keyframes tcgFloat {
          0%, 100% {
            transform: translateY(0px);
          }
          50% {
            transform: translateY(-5px);
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
            box-shadow: 0 0 8px ${accentColor}44;
          }
          50% {
            box-shadow: 0 0 22px ${accentColor};
          }
        }
        .tcg-anim-deal {
          animation: tcgDeal 0.55s cubic-bezier(0.16, 1, 0.3, 1) backwards;
        }
        .tcg-anim-slam {
          animation: tcgSlam 0.5s cubic-bezier(0.2, 0.8, 0.2, 1) backwards;
        }
        .tcg-anim-flip {
          animation: tcgFlip 0.6s cubic-bezier(0.25, 1, 0.5, 1) backwards;
        }
        .tcg-anim-float {
          animation: tcgDeal 0.5s ease-out backwards, tcgFloat 3s ease-in-out infinite 0.5s;
        }
        .tcg-anim-hologram {
          animation: tcgDeal 0.5s ease-out backwards;
        }
        .tcg-anim-glow {
          animation: tcgDeal 0.5s ease-out backwards, tcgEnergyPulse 2.4s ease-in-out infinite;
        }
      `}</style>

      {/* Background Radial Glow */}
      <div
        className="absolute inset-0 pointer-events-none opacity-40"
        style={{
          background: `radial-gradient(circle at 50% 30%, ${accentColor}40 0%, transparent 70%)`,
        }}
      />

      {/* TOP HEADER: Player Name with Overlapping Diamonds Background */}
      <div
        className="relative z-10 pt-6 pb-5 px-6 flex flex-col items-center justify-center shrink-0 overflow-hidden border-b"
        style={{ borderColor: borderColor }}
      >
        {/* Overlapping Translucent Diamonds Geometry */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-25">
          <div className="w-20 h-20 rotate-45 border-2 border-white/60 bg-white/10 rounded-sm"></div>
          <div className="w-28 h-28 rotate-45 border border-white/40 absolute rounded-sm"></div>
          <div className="w-36 h-36 rotate-45 border border-white/20 absolute rounded-sm"></div>
        </div>

        {/* Player Name */}
        <h1
          className="relative z-10 text-4xl font-black tracking-widest text-white drop-shadow-[0_2px_10px_rgba(0,0,0,0.6)] uppercase"
          style={{ textShadow: `0 0 20px ${accentColor}66` }}
        >
          {playerName}
        </h1>
      </div>

      {/* MAIN BODY: Chevron Timeline on the Left + Match Rows on the Right */}
      {rounds.length === 0 ? (
        <div className="relative z-10 flex-1 flex flex-col items-center justify-center p-6 text-center text-sky-200/80 select-none">
          <span className="text-3xl mb-2 opacity-60">⚔️</span>
          <p className="text-xs font-black uppercase tracking-wider" style={{ color: accentColor }}>
            TOURNAMENT OPENER
          </p>
          <p className="text-[11px] text-slate-300/80 mt-1 max-w-[220px] leading-snug">
            No prior won sets recorded in this tournament yet.
          </p>
        </div>
      ) : (
        <div className="relative z-10 flex-1 flex flex-row min-h-0">
          {/* Left Vertical Arrow / Chevron Tower */}
          <div
            className="w-20 shrink-0 relative flex flex-col items-center border-r bg-black/35"
            style={{ borderColor: borderColor }}
          >
            {/* Top Arrow Tip */}
            <div
              className="w-full h-8 flex items-center justify-center border-b"
              style={{
                clipPath: 'polygon(50% 0%, 100% 100%, 0% 100%)',
                backgroundColor: accentColor,
                borderColor: borderColor,
              }}
            />

            {/* Round Milestones along the Arrow Shaft */}
            <div className="flex-1 w-full flex flex-col justify-between py-2">
              {rounds.map((r: any, idx: number) => {
                const milestoneDelay = cardAnim !== 'none' ? `${baseOffsetMs + idx * 75}ms` : '0ms';
                return (
                  <div
                    key={idx}
                    className={`flex-1 flex flex-col items-center justify-center text-center px-1 ${animClass}`}
                    style={{ animationDelay: milestoneDelay }}
                  >
                    <span
                      className="text-[10px] font-black tracking-widest uppercase leading-none drop-shadow"
                      style={{ color: accentColor }}
                    >
                      {r.sub_label || 'ROUND'}
                    </span>
                    <span className="text-xl font-black text-white leading-tight font-mono tracking-tight mt-0.5">
                      {r.main_number || r.round_label?.replace(/[^0-9]/g, '') || ''}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right Match Entries List */}
          <div className="flex-1 flex flex-col justify-between overflow-hidden p-2 gap-1.5">
            {rounds.map((r: any, roundIdx: number) => (
              <div
                key={roundIdx}
                className="flex-1 flex flex-col justify-center px-2 py-1.5 border-b last:border-b-0"
                style={{ borderColor: `${borderColor}` }}
              >
                <div className="flex flex-col gap-1.5">
                  {r.matches?.map((m: any, matchIdx: number) => {
                    const cardDelay = cardAnim !== 'none' ? `${baseOffsetMs + 80 + (roundIdx * 2 + matchIdx) * 60}ms` : '0ms';
                    return (
                      <div
                        key={matchIdx}
                        className={`flex items-center gap-2 min-w-0 p-1.5 rounded-lg border transition-all ${animClass} relative overflow-hidden`}
                        style={{
                          animationDelay: cardDelay,
                          backgroundColor: cardBgColor,
                          borderColor: borderColor,
                          boxShadow: '0 2px 8px rgba(0,0,0,0.4)',
                        }}
                      >
                        {/* Hologram scanline effect */}
                        {cardAnim === 'hologram' && (
                          <div
                            className="pointer-events-none absolute inset-x-0 h-10 bg-gradient-to-b from-transparent via-cyan-400/25 to-transparent z-10"
                            style={{
                              animation: 'tcgHologramScan 2.6s linear infinite',
                              animationDelay: `${((roundIdx + matchIdx) * 150) % 1000}ms`,
                            }}
                          />
                        )}

                        {/* Score Pill */}
                        <div
                          className="px-2 py-0.5 rounded font-mono font-black text-xs shrink-0 shadow flex items-center justify-center min-w-[34px]"
                          style={{
                            background: `linear-gradient(135deg, ${accentColor}, ${accentColor}dd)`,
                            color: '#ffffff',
                            border: `1px solid ${accentColor}`,
                            boxShadow: `0 0 8px ${accentColor}66`,
                          }}
                        >
                          {m.score}
                        </div>

                        {/* 'vs.' text */}
                        <span className="text-[10px] font-semibold text-white/60 shrink-0 italic">
                          vs.
                        </span>

                        {/* Opponent Prefix & Name */}
                        <div className="truncate flex items-center gap-1.5 min-w-0">
                          {m.opponent_prefix && (
                            <span
                              className="text-[10px] uppercase font-bold shrink-0"
                              style={{ color: accentColor }}
                            >
                              {m.opponent_prefix}
                            </span>
                          )}
                          <span className="text-sm font-black truncate text-white tracking-wide">
                            {m.opponent_name}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* FOOTER BAR: Solid Light High-Contrast Banner with Accent Stripe */}
      <div
        className="relative z-10 shrink-0 bg-[#e2e8f0] py-3 px-4 text-center shadow-lg border-t-2"
        style={{ borderTopColor: accentColor }}
      >
        <span className="text-xl font-black tracking-widest text-slate-950 uppercase font-sans">
          {footerText}
        </span>
      </div>
    </div>
  );
}
