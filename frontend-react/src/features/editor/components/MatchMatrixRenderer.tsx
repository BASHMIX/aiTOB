import { useState, useEffect } from 'react';
import type { OverlayElement } from '@/store/useEditorStore';

interface MatchMatrixRendererProps {
  element: OverlayElement;
  activeMatch?: any;
  interactive?: boolean;
  onUpdateHistory?: (newHistory: ('p1' | 'p2' | null)[]) => void;
}

export function MatchMatrixRenderer({
  element,
  activeMatch,
  interactive = false,
  onUpdateHistory,
}: MatchMatrixRendererProps) {
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
  // Determine format & total columns
  const mode = element.formatMode || 'auto';
  let totalGames = 9;

  if (mode === 'ft2') {
    totalGames = 3;
  } else if (mode === 'ft3') {
    totalGames = 5;
  } else if (mode === 'ft5') {
    totalGames = 9;
  } else if (mode === 'ft7') {
    totalGames = 13;
  } else {
    // Auto from activeMatch
    const bestOf = Number(activeMatch?.best_of) || 9;
    totalGames = bestOf > 0 ? bestOf : 9;
  }

  // Determine game results
  const history: ('p1' | 'p2' | null)[] = (() => {
    if (element.gamesHistoryOverride && Array.isArray(element.gamesHistoryOverride)) {
      const arr = [...element.gamesHistoryOverride];
      while (arr.length < totalGames) arr.push(null);
      return arr.slice(0, totalGames);
    }

    if (activeMatch?.games_history && Array.isArray(activeMatch.games_history)) {
      const arr = [...activeMatch.games_history];
      while (arr.length < totalGames) arr.push(null);
      return arr.slice(0, totalGames);
    }

    // Default sample if scores are empty or 0 (giving a live preview like Red Bull)
    const p1Score = Number(activeMatch?.p1_score ?? (element.p1ScoreOverride ?? 2));
    const p2Score = Number(activeMatch?.p2_score ?? (element.p2ScoreOverride ?? 4));

    // If both 0 and no override, show sample for design preview
    if (p1Score === 0 && p2Score === 0 && !interactive) {
      return Array(totalGames).fill(null);
    }

    // Build sample sequence or reconstruct from score counts
    const reconstructed: ('p1' | 'p2' | null)[] = Array(totalGames).fill(null);
    // Sample pattern like the Red Bull reference if 2 vs 4 in FT5:
    if (totalGames === 9 && p1Score === 2 && p2Score === 4) {
      reconstructed[0] = 'p1';
      reconstructed[1] = 'p2';
      reconstructed[2] = 'p2';
      reconstructed[3] = 'p2';
      reconstructed[4] = 'p1';
      reconstructed[5] = 'p2';
      return reconstructed;
    }

    // Generic fill: alternate or sequential
    let p1Assigned = 0;
    let p2Assigned = 0;
    for (let i = 0; i < totalGames; i++) {
      if (p1Assigned < p1Score && (p1Assigned <= p2Assigned || p2Assigned >= p2Score)) {
        reconstructed[i] = 'p1';
        p1Assigned++;
      } else if (p2Assigned < p2Score) {
        reconstructed[i] = 'p2';
        p2Assigned++;
      }
    }
    return reconstructed;
  })();

  // Current game index being played
  const currentGameIndex = history.findIndex((h) => h === null);

  // Styles
  const wonColor = element.wonColor || '#f59e0b'; // Gold / Amber
  const wonBgColor = element.wonBgColor || 'rgba(245, 158, 11, 0.16)';
  const boxBorderColor = element.boxBorderColor || 'rgba(99, 130, 220, 0.4)';
  const boxBgColor = element.boxBgColor || 'rgba(8, 14, 34, 0.82)';
  const markerStyle = element.winMarkerStyle || 'check';
  const highlightColor = element.currentHighlightColor || '#00ffcc';

  const handleBoxClick = (gameIndex: number, player: 'p1' | 'p2') => {
    if (!interactive || !onUpdateHistory) return;
    const next = [...history];
    if (next[gameIndex] === player) {
      next[gameIndex] = null;
    } else {
      next[gameIndex] = player;
    }
    onUpdateHistory(next);
  };

  const renderMarker = (isWon: boolean) => {
    if (!isWon) return null;
    if (markerStyle === 'image') {
      const markerSrc = element.customMarkerUrl || 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40"><path d="M7 21 L16 30 L35 9" fill="none" stroke="%23f59e0b" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/></svg>';
      const w = element.markerWidth || 32;
      const h = element.markerHeight || 32;
      const ox = element.markerOffsetX || 0;
      const oy = element.markerOffsetY || 0;
      return (
        <img
          src={markerSrc}
          alt="Win Marker"
          className="pointer-events-none select-none shrink-0 z-20"
          style={{
            position: 'absolute',
            width: `${w}px`,
            height: `${h}px`,
            maxWidth: 'none',
            maxHeight: 'none',
            objectFit: 'contain',
            transform: `translate(${ox}px, ${oy}px)`,
            filter: `drop-shadow(0 0 6px ${wonColor}99)`,
          }}
        />
      );
    }
    if (markerStyle === 'solid') {
      return (
        <div
          className="w-full h-full rounded-sm"
          style={{
            backgroundColor: wonColor,
            boxShadow: `0 0 10px ${wonColor}`,
          }}
        />
      );
    }
    if (markerStyle === 'dot') {
      return (
        <div
          className="w-2.5 h-2.5 rounded-full shrink-0"
          style={{
            backgroundColor: wonColor,
            boxShadow: `0 0 8px ${wonColor}`,
          }}
        />
      );
    }
    // Compact check icon like the dot (never blows up cell height)
    return (
      <svg
        viewBox="0 0 24 24"
        className="w-3.5 h-3.5 shrink-0"
        style={{
          color: wonColor,
          filter: `drop-shadow(0 0 4px ${wonColor}cc)`,
        }}
        fill="none"
        stroke="currentColor"
        strokeWidth="3.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <polyline points="20 6 9 17 4 12" />
      </svg>
    );
  };

  // Card Game Animation & Slide Synchronization
  const cardAnim = element.matrixCardAnimation || 'deal';
  const slideAnim = element.animation;
  const slideDuration = slideAnim && slideAnim.animationType !== 'none' ? slideAnim.duration || 500 : 0;
  const baseOffsetMs = slideDuration > 0 ? Math.round(slideDuration * 0.45) : 0;

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
      className="w-full h-full flex flex-col justify-center select-none"
      style={{
        fontFamily: element.fontFamily || 'inherit',
      }}
    >
      {/* Keyframes Engine */}
      <style>{`
        @keyframes tcgDeal {
          0% {
            opacity: 0;
            transform: translateY(-24px) scale(0.9) rotate(-2deg);
          }
          60% {
            opacity: 1;
            transform: translateY(2px) scale(1.02) rotate(1deg);
          }
          100% {
            opacity: 1;
            transform: translateY(0) scale(1) rotate(0deg);
          }
        }
        @keyframes tcgSlam {
          0% {
            opacity: 0;
            transform: translateY(-50px) scale(1.35);
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
            transform: translateY(-4px);
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
            box-shadow: 0 0 6px ${wonColor}55;
          }
          50% {
            box-shadow: 0 0 16px ${wonColor};
          }
        }
        .tcg-anim-deal {
          animation: tcgDeal 0.5s cubic-bezier(0.16, 1, 0.3, 1) backwards;
        }
        .tcg-anim-slam {
          animation: tcgSlam 0.5s cubic-bezier(0.2, 0.8, 0.2, 1) backwards;
        }
        .tcg-anim-flip {
          animation: tcgFlip 0.55s cubic-bezier(0.25, 1, 0.5, 1) backwards;
        }
        .tcg-anim-float {
          animation: tcgDeal 0.45s ease-out backwards, tcgFloat 2.8s ease-in-out infinite 0.45s;
        }
        .tcg-anim-hologram {
          animation: tcgDeal 0.45s ease-out backwards;
        }
        .tcg-anim-glow {
          animation: tcgDeal 0.45s ease-out backwards, tcgEnergyPulse 2.2s ease-in-out infinite;
        }
      `}</style>

      {/* Column Numbers Header */}
      <div className="flex w-full justify-between items-center px-1 mb-1">
        {Array.from({ length: totalGames }).map((_, idx) => {
          const isCurrent = idx === currentGameIndex;
          const delayMs = cardAnim !== 'none' ? `${baseOffsetMs + idx * 45}ms` : '0ms';
          return (
            <div
              key={idx}
              className={`flex-1 text-center font-bold tracking-wider transition-colors ${animClass}`}
              style={{
                animationDelay: delayMs,
                fontSize: totalGames > 9 ? '11px' : '13px',
                color: isCurrent ? highlightColor : '#94a3b8',
                textShadow: isCurrent ? `0 0 8px ${highlightColor}` : undefined,
              }}
            >
              {idx + 1}
            </div>
          );
        })}
      </div>

      {/* Row P1 Boxes */}
      <div className="flex w-full gap-1.5 h-[30px] items-center mb-1.5">
        {Array.from({ length: totalGames }).map((_, idx) => {
          const isWon = history[idx] === 'p1';
          const isCurrent = idx === currentGameIndex;
          const delayMs = cardAnim !== 'none' ? `${baseOffsetMs + idx * 45}ms` : '0ms';
          return (
            <div
              key={`p1_${idx}`}
              onClick={() => handleBoxClick(idx, 'p1')}
              className={`flex-1 h-[28px] max-h-[28px] rounded relative overflow-visible flex items-center justify-center transition-all ${animClass} ${
                interactive ? 'cursor-pointer hover:border-amber-400' : ''
              } ${isCurrent && !isWon ? 'ring-1' : ''}`}
              style={{
                animationDelay: delayMs,
                backgroundColor: isWon ? wonBgColor : boxBgColor,
                border: `1.5px solid ${isWon ? wonColor : isCurrent ? highlightColor : boxBorderColor}`,
                boxShadow: isWon ? `0 0 10px ${wonColor}44` : undefined,
              }}
              title={interactive ? `Game ${idx + 1}: Click to toggle P1 win` : undefined}
            >
              {cardAnim === 'hologram' && (
                <div className="pointer-events-none absolute inset-0 rounded overflow-hidden z-10">
                  <div
                    className="absolute inset-x-0 h-6 bg-gradient-to-b from-transparent via-cyan-400/30 to-transparent"
                    style={{
                      animation: 'tcgHologramScan 2.4s linear infinite',
                      animationDelay: `${(idx * 120) % 900}ms`,
                    }}
                  />
                </div>
              )}
              {renderMarker(isWon)}
            </div>
          );
        })}
      </div>

      {/* Row P2 Boxes */}
      <div className="flex w-full gap-1.5 h-[30px] items-center">
        {Array.from({ length: totalGames }).map((_, idx) => {
          const isWon = history[idx] === 'p2';
          const isCurrent = idx === currentGameIndex;
          const delayMs = cardAnim !== 'none' ? `${baseOffsetMs + idx * 45}ms` : '0ms';
          return (
            <div
              key={`p2_${idx}`}
              onClick={() => handleBoxClick(idx, 'p2')}
              className={`flex-1 h-[28px] max-h-[28px] rounded relative overflow-visible flex items-center justify-center transition-all ${animClass} ${
                interactive ? 'cursor-pointer hover:border-amber-400' : ''
              } ${isCurrent && !isWon ? 'ring-1' : ''}`}
              style={{
                animationDelay: delayMs,
                backgroundColor: isWon ? wonBgColor : boxBgColor,
                border: `1.5px solid ${isWon ? wonColor : isCurrent ? highlightColor : boxBorderColor}`,
                boxShadow: isWon ? `0 0 10px ${wonColor}44` : undefined,
              }}
              title={interactive ? `Game ${idx + 1}: Click to toggle P2 win` : undefined}
            >
              {cardAnim === 'hologram' && (
                <div className="pointer-events-none absolute inset-0 rounded overflow-hidden z-10">
                  <div
                    className="absolute inset-x-0 h-6 bg-gradient-to-b from-transparent via-cyan-400/30 to-transparent"
                    style={{
                      animation: 'tcgHologramScan 2.4s linear infinite',
                      animationDelay: `${(idx * 120) % 900}ms`,
                    }}
                  />
                </div>
              )}
              {renderMarker(isWon)}
            </div>
          );
        })}
      </div>
    </div>
  );
}
