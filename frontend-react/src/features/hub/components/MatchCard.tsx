import { useEffect, useState, useRef } from "react";
import { ActionButton } from "./ActionButton";
import { useHubStore } from "@/store/useHubStore";

// SVG Icons
const IconDQ = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="w-3.5 h-3.5">
    <circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/>
  </svg>
);
const IconReset = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="w-3.5 h-3.5">
    <polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 102.13-9.36L1 10"/>
  </svg>
);
const IconSend = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="w-3.5 h-3.5">
    <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
  </svg>
);
const IconPlay = () => (
  <svg viewBox="0 0 24 24" fill="currentColor" stroke="none" className="w-3.5 h-3.5">
    <polygon points="5 3 19 12 5 21 5 3"/>
  </svg>
);
const IconCall = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="w-3.5 h-3.5">
    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
    <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
  </svg>
);
const IconActivate = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="w-3.5 h-3.5">
    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
  </svg>
);
const IconRemove = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="w-3.5 h-3.5">
    <line x1="18" y1="6" x2="6" y2="18"></line>
    <line x1="6" y1="6" x2="18" y2="18"></line>
  </svg>
);
const IconMonitor = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="w-3.5 h-3.5">
    <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
    <line x1="8" y1="21" x2="16" y2="21"/>
    <line x1="12" y1="17" x2="12" y2="21"/>
  </svg>
);

export type MatchStatus = "waiting" | "live" | "called" | "conflict" | "done" | "dq";

export interface MatchPlayer {
  name: string;
  avatar?: string;
  score?: number | "DQ";
  highlight?: boolean;
  isTBD?: boolean;
  // Reachability — true when this entrant has a linked Discord account in our players table.
  // Drives the "📵 unreachable" badge. Only meaningful once the match is local (synced).
  hasDiscord?: boolean;
}

export interface MatchData {
  id: string;
  pool: string;
  round: string;
  status: MatchStatus;
  players: [MatchPlayer, MatchPlayer];
  isLocal: boolean;
  isStreamMatch?: boolean;
  startedAt?: string;
  calledAt?: string;
  raw: any;
  stationId?: string;
  // True when the bot has surrendered auto-DQ for this set (partial / no Discord reach).
  // Surfaces as a small banner so the TO knows the bot won't intervene.
  autoDqDisarmed?: boolean;
}

const STATUS_META: Record<
  MatchStatus,
  { label: string; tone: "activate" | "send" | "reset" | "dq" | "neutral" }
> = {
  waiting: { label: "WAITING", tone: "activate" },
  live: { label: "LIVE", tone: "send" },
  called: { label: "CALLED", tone: "reset" },
  conflict: { label: "CONFLICT", tone: "dq" },
  done: { label: "DONE", tone: "neutral" },
  dq: { label: "DQ", tone: "dq" },
};

const TONE_TEXT: Record<string, string> = {
  activate: "text-[var(--tone-activate)]",
  send: "text-[var(--tone-send)]",
  reset: "text-[var(--tone-reset)]",
  dq: "text-[var(--tone-dq)]",
  neutral: "text-[var(--muted-foreground)]",
};
const TONE_BORDER: Record<string, string> = {
  activate: "border-[var(--tone-activate)]",
  send: "border-[var(--tone-send)]",
  reset: "border-[var(--tone-reset)]",
  dq: "border-[var(--tone-dq)]",
  neutral: "border-[var(--border)]",
};
const PANEL_TONE: Record<string, string> = {
  activate: "border-[var(--tone-activate-border)] bg-[var(--tone-activate-bg)]",
  send: "border-[var(--tone-send-border)] bg-[var(--tone-send-bg)]",
  reset: "border-[var(--tone-reset-border)] bg-[var(--tone-reset-bg)]",
  dq: "border-[var(--tone-dq-border)] bg-[var(--tone-dq-bg)]",
  neutral: "border-[var(--border)] bg-[var(--card)]",
};

function ScoreCell({ player }: { player: MatchPlayer }) {
  const isDQ = player.score === "DQ";

  return (
    <div
      className={`flex h-11 w-12 items-center justify-center text-base font-black border-l border-[var(--border)] text-slate-100 shrink-0
        ${isDQ ? "text-[var(--tone-dq)] animate-pulse" : ""}
        ${player.highlight ? "bg-[var(--tone-send-highlight)] text-[var(--tone-send)]" : ""}
      `}
    >
      <span className="text-center">{player.score !== undefined ? player.score : ""}</span>
    </div>
  );
}

function UnreachableBadge() {
  return (
    <span
      title="No linked Discord account — bot can't reach this player. They must check in & report on start.gg directly."
      className="inline-flex items-center justify-center text-amber-400/90 text-xs leading-none flex-shrink-0 cursor-help select-none"
    >
      📵
    </span>
  );
}

function PlayersBlock({ players }: { players: MatchData["players"] }) {
  return (
    <div className="flex-1 overflow-hidden flex flex-col justify-center rounded-l-md">
      {players.map((p, i) => (
        <div
          key={i}
          className={`flex items-center justify-between ${i === 0 ? "border-b border-[var(--border)]" : ""}`}
        >
          <div className="flex-1 flex items-center gap-2.5 px-3.5 py-2.5 text-sm font-semibold text-[var(--foreground)]">
            <div className="w-6 h-6 rounded-full bg-[var(--muted)] overflow-hidden border border-[var(--border)] flex-shrink-0">
              {p.avatar ? (
                <img src={p.avatar} alt="" className="w-full h-full object-cover" onError={(e) => (e.currentTarget.style.display = 'none')} />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-xs text-[var(--muted-foreground)]">?</div>
              )}
            </div>
            <span className="truncate">{p.name}</span>
            {/* Only show the badge once we're sure: hasDiscord is set on local matches; undefined for unsynced bracket rows. */}
            {p.hasDiscord === false && !p.isTBD && <UnreachableBadge />}
          </div>
          <ScoreCell player={p} />
        </div>
      ))}
    </div>
  );
}

interface MatchCardProps {
  match: MatchData;
  dqTimerSeconds: number;
  autoDqEnabled: boolean;
  onAction: (action: string, row: any, data?: any) => void;
  onToggleStream: (setId: string, currentVal: boolean) => void;
  stations?: { id: string; name: string }[];
}

function DQMenu({ match, onAction, onOpenChange }: { match: MatchData; onAction: MatchCardProps['onAction']; onOpenChange?: (open: boolean) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    onOpenChange?.(open);
  }, [open, onOpenChange]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [ref]);

  return (
    <div className="relative" ref={ref}>
      <ActionButton tone="dq" label="DQ" icon={<IconDQ />} onClick={() => setOpen(!open)} />
      {open && (
        <div className="absolute right-0 top-full mt-1.5 z-[100] bg-[var(--card)] border border-[var(--tone-dq-border)] rounded-md shadow-2xl min-w-[140px] text-left p-1 overflow-hidden animate-slideUp">
          <div className="px-2.5 py-1 text-[9px] text-[var(--tone-dq)] font-bold uppercase tracking-widest border-b border-white/5 mb-1">DQ who?</div>
          <button onClick={() => { setOpen(false); onAction("dq", match, "p1"); }} className="w-full text-left px-3 py-2 text-xs text-white hover:bg-[var(--tone-dq-hover)] rounded transition-colors truncate">{match.players[0].name || 'P1'}</button>
          <button onClick={() => { setOpen(false); onAction("dq", match, "p2"); }} className="w-full text-left px-3 py-2 text-xs text-white hover:bg-[var(--tone-dq-hover)] rounded transition-colors truncate">{match.players[1].name || 'P2'}</button>
          <button onClick={() => { setOpen(false); onAction("dq", match, "both"); }} className="w-full text-left px-3 py-2 text-xs font-bold text-red-500 hover:bg-[var(--tone-dq-hover)] border-t border-white/5 rounded mt-1 italic transition-colors">Both Players</button>
        </div>
      )}
    </div>
  );
}

function StationMenu({ match, stations, onAction, onOpenChange }: { match: MatchData; stations: any[]; onAction: MatchCardProps['onAction']; onOpenChange?: (open: boolean) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    onOpenChange?.(open);
  }, [open, onOpenChange]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [ref]);

  const curName = stations.find((s) => s.id === match.stationId)?.name;

  // Find occupied station IDs by scanning all active matches in the store
  const occupiedStationIds = new Set(
    useHubStore.getState().matches
      .filter((m) => m.set_id !== match.raw?.set_id && (m.status === 'in_progress' || m.status === 'called') && m.station_id)
      .map((m) => m.station_id)
  );

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        title={match.stationId ? `Live on: ${curName}` : "Assign to station"}
        className={`inline-flex h-7 items-center justify-center rounded-md border text-[10px] font-semibold transition-all duration-200 hover:scale-105 active:scale-95 shadow-sm
          ${match.stationId
            ? "border-[var(--tone-send-border)] bg-[var(--tone-send-bg)] text-[var(--tone-send)] hover:bg-[var(--tone-send-hover)] hover:shadow-[0_0_8px_rgba(59,130,246,0.15)] px-1.5 gap-1"
            : "border-[var(--border)] bg-[var(--foreground-5)] text-gray-300 hover:bg-[var(--foreground-10)] hover:text-white w-7"
          }`}
      >
        <IconMonitor />
        {match.stationId && <span className="font-bold font-mono text-[9px]">{curName}</span>}
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1.5 z-[100] bg-[var(--card)] border border-[var(--border)] rounded-md shadow-2xl min-w-[170px] text-left p-1 overflow-hidden animate-slideUp">
          <div className="px-2.5 py-1 text-[9px] text-[var(--muted-foreground)] font-bold uppercase tracking-widest border-b border-white/5 mb-1">Assign Station</div>
          {match.stationId && (
            <button onClick={() => { setOpen(false); onAction("assignStation", match, null); }} className="w-full text-left px-3 py-1.5 text-xs text-gray-400 hover:bg-[var(--foreground-5)] rounded transition-colors">— Unassign</button>
          )}
          {stations.length === 0 && <div className="px-3 py-2 text-[10px] text-gray-600 italic">No stations configured</div>}
          {stations.map((s) => {
            const isOccupied = occupiedStationIds.has(s.id);
            return (
              <button
                key={s.id}
                disabled={isOccupied}
                onClick={() => { setOpen(false); onAction("assignStation", match, s.id); }}
                className={`w-full text-left px-3 py-1.5 text-xs transition-colors rounded flex items-center justify-between
                  ${isOccupied
                    ? "text-red-400/60 bg-red-950/5 cursor-not-allowed border border-red-900/10 mb-0.5"
                    : s.id === match.stationId
                      ? "text-[var(--tone-send)] bg-[var(--tone-send-hover)] font-semibold"
                      : "text-gray-200 hover:bg-[var(--foreground-5)]"
                  }`}
              >
                <span className="truncate pr-1">{s.name}</span>
                {isOccupied && <span className="text-[8px] leading-none text-red-500 font-extrabold px-1 py-0.5 rounded bg-red-500/10 border border-red-500/20 flex-shrink-0">OCCUPIED</span>}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function MatchCard({ match, dqTimerSeconds, autoDqEnabled, onAction, onToggleStream, stations }: MatchCardProps) {
  const meta = STATUS_META[match.status];
  const showTimer = match.status === "live" || match.status === "called";

  const [timeDisplay, setTimeDisplay] = useState("00:00");
  const [isTimerWarning, setIsTimerWarning] = useState(false);
  const [stationMenuOpen, setStationMenuOpen] = useState(false);
  const [dqMenuOpen, setDqMenuOpen] = useState(false);

  const isDropdownOpen = stationMenuOpen || dqMenuOpen;

  // Preview sets are start.gg's unresolved bracket placeholders (IDs like
  // "preview_XXX"). They have no entrants assigned yet and cannot be mutated
  // via the API. We still render the row so the TO can see upcoming bracket
  // structure AND flag it for stream — but we hide every action that would
  // round-trip to start.gg (Call, Activate, Send, DQ, Reset, Remove).
  const rawSetId = String(match.raw?.set_id || match.raw?.id || match.id || "");
  const isPreview = rawSetId.startsWith("preview");

  const displayPool = match.pool 
    ? (match.pool.toLowerCase().includes('pool') ? match.pool : `Pool ${match.pool}`) 
    : "";
  const parseUTCDate = (dateStr: string | undefined | null) => {
    if (!dateStr) return 0;
    let clean = dateStr.trim();
    if (clean.includes(' ') && !clean.includes('T')) {
      clean = clean.replace(' ', 'T');
    }
    const hasZ = clean.endsWith('Z');
    const hasPlus = clean.includes('+');
    const tIdx = clean.indexOf('T');
    const hasMinusOffset = tIdx !== -1 && clean.indexOf('-', tIdx) !== -1;
    
    if (!hasZ && !hasPlus && !hasMinusOffset) {
      clean = `${clean}Z`;
    }
    return new Date(clean).getTime();
  };

  // Timer logic
  useEffect(() => {
    if (!showTimer) return;
    
    const updateTimer = () => {
      const now = Date.now();
      
      if (match.status === "live" && match.startedAt) {
        // Count up
        const started = parseUTCDate(match.startedAt);
        const diff = Math.max(0, Math.floor((now - started) / 1000));
        const m = Math.floor(diff / 60).toString().padStart(2, '0');
        const s = (diff % 60).toString().padStart(2, '0');
        setTimeDisplay(`${m}:${s}`);
        setIsTimerWarning(false);
      } 
      else if (match.status === "called" && match.calledAt) {
        // Count down
        const called = parseUTCDate(match.calledAt);
        const diff = Math.floor((now - called) / 1000);
        const remaining = Math.max(0, dqTimerSeconds - diff);
        const m = Math.floor(remaining / 60).toString().padStart(2, '0');
        const s = (remaining % 60).toString().padStart(2, '0');
        setTimeDisplay(`${m}:${s}`);
        
        setIsTimerWarning(remaining <= 60 && remaining > 0);
        
        if (remaining === 0 && autoDqEnabled) {
          setTimeDisplay("00:00");
          setIsTimerWarning(true);
        }
      }
    };

    updateTimer();
    const iv = setInterval(updateTimer, 1000);
    return () => clearInterval(iv);
  }, [match.status, match.startedAt, match.calledAt, dqTimerSeconds, autoDqEnabled, showTimer]);

  return (
    <div className={`flex flex-col rounded-lg border transition-all duration-200
      ${isDropdownOpen 
        ? "z-50 relative shadow-[0_0_20px_rgba(255,200,0,0.15)] border-accentYellow/40 bg-black/40 scale-[1.01] overflow-visible" 
        : "z-10 relative border-white/10 overflow-hidden"
      }
      ${PANEL_TONE[meta.tone]}
    `}>
      {/* Top Section: Players, Scores, and Match Metadata */}
      <div className="flex items-stretch w-full">
        <PlayersBlock 
          players={match.players} 
        />
        
        {/* Match Metadata Column */}
        <div className="w-[125px] border-l border-white/5 flex flex-col justify-center px-3 py-1 bg-black/20 gap-1 select-none shrink-0 font-mono text-xs leading-tight">
          {/* Match ID and Status Pill */}
          <div className="flex items-center justify-between gap-1">
            <span className="font-extrabold text-[11px] text-textDim truncate font-mono">
              #{match.id || "—"}
            </span>
            <span className={`rounded border px-1.5 py-[2px] text-[10px] font-black tracking-wider leading-none ${TONE_TEXT[meta.tone]} ${TONE_BORDER[meta.tone]}`}>
              {meta.label}
            </span>
          </div>

          {/* Pool */}
          {displayPool ? (
            <span className="text-[#38bdf8] font-bold truncate text-xs" title={displayPool}>
              {displayPool}
            </span>
          ) : (
            <span className="text-textDim/40 italic text-[11px]">No Pool</span>
          )}

          {/* Stage / Round */}
          <span className="text-textDim truncate font-semibold text-xs" title={match.round}>
            {match.round || "Round"}
          </span>
        </div>
      </div>

      {/* Bottom Section (Row 3): Timer & Action Buttons Toolbar */}
      <div className="flex items-center justify-between border-t border-white/5 bg-black/20 px-2.5 py-1.5 gap-2 text-xs">
        {/* Left Side: Timer & Auto-DQ Manual Warning */}
        <div className="flex items-center gap-1.5 flex-wrap min-w-0">
          {/* Unreachable / Auto-DQ Banner */}
          {match.autoDqDisarmed && match.isLocal && match.status !== "done" && match.status !== "dq" && (
            <span
              title="Auto-DQ disarmed — partial-reach match. Bot won't intervene; coordinate on start.gg."
              className="rounded border border-amber-500/40 bg-amber-500/10 text-amber-300 px-1.5 py-0.5 text-[8px] font-bold tracking-wider cursor-help select-none shrink-0"
            >
              ⚠ MANUAL
            </span>
          )}

          {/* Timer */}
          {showTimer && (
            <span
              className={`h-7 px-2 font-mono text-xs font-extrabold tabular-nums tracking-wide flex items-center justify-center gap-1.5 rounded bg-black/40 border border-white/10 shrink-0 shadow-inner
                ${match.status === "live" ? "text-[var(--tone-send)]" : (isTimerWarning ? "text-[var(--tone-dq)] animate-pulse" : "text-[var(--tone-reset)]")}
              `}
            >
              <span>{match.status === "live" ? "⏱️" : "⏳"}</span>
              <span>{timeDisplay}</span>
            </span>
          )}
        </div>

        {/* Right Side: Action Buttons (Icon Only) */}
        <div className="flex items-center gap-1 shrink-0">
          {isPreview ? (
            <>
              <span
                title="This bracket position hasn't resolved yet. Actions unlock once start.gg fills in both entrants."
                className="text-[9px] font-mono uppercase tracking-widest text-textDim italic select-none mr-1"
              >
                Awaiting bracket
              </span>
              <button
                type="button"
                onClick={() => onToggleStream(rawSetId, !!match.isStreamMatch)}
                aria-label="Plan for stream"
                title="Plan this future match for stream coverage"
                className={`inline-flex h-7 w-7 items-center justify-center rounded-md border transition-all duration-200 hover:scale-105 active:scale-95 ${
                  match.isStreamMatch
                    ? "border-[var(--tone-activate-border)] bg-[var(--tone-activate)] text-[var(--background)] hover:bg-[var(--tone-activate-hover)]"
                    : "border-[var(--tone-activate-border)] text-[var(--tone-activate)] hover:bg-[var(--tone-activate-hover)]/10"
                }`}
              >
                <IconPlay />
              </button>
            </>
          ) : (
            <>
              {match.status === "waiting" && (
                <>
                  {!match.isLocal && (
                    <>
                      <ActionButton tone="activate" label="Call Match" icon={<IconCall />} onClick={() => onAction("callMatch", match)} />
                      <ActionButton tone="neutral" label="Activate Match" icon={<IconActivate />} onClick={() => onAction("activate", match)} />
                    </>
                  )}
                  {match.isLocal && (
                    <ActionButton tone="activate" label="Call Match" icon={<IconCall />} onClick={() => onAction("callMatch", match)} />
                  )}
                  <button
                    type="button"
                    onClick={() => onToggleStream(rawSetId, !!match.isStreamMatch)}
                    aria-label="Toggle Stream Q"
                    title="Plan this match for stream coverage"
                    className={`inline-flex h-7 w-7 items-center justify-center rounded-md border transition-all duration-200 hover:scale-105 active:scale-95 ${
                      match.isStreamMatch
                        ? "border-[var(--tone-activate-border)] bg-[var(--tone-activate)] text-[var(--background)] hover:bg-[var(--tone-activate-hover)]"
                        : "border-[var(--tone-activate-border)] text-[var(--tone-activate)] hover:bg-[var(--tone-activate-hover)]/10"
                    }`}
                  >
                    <IconPlay />
                  </button>
                </>
              )}

              {match.isLocal && match.status !== "done" && match.status !== "dq" && (
                <StationMenu match={match} stations={stations || []} onAction={onAction} onOpenChange={setStationMenuOpen} />
              )}

              {match.isLocal && match.status === "live" && (
                <ActionButton tone="send" label="Send Score" icon={<IconSend />} onClick={() => onAction("sendScore", match)} />
              )}

              {match.isLocal && (match.status === "live" || match.status === "called" || match.status === "conflict") && (
                <DQMenu match={match} onAction={onAction} onOpenChange={setDqMenuOpen} />
              )}

              {match.isLocal && (
                <>
                  <ActionButton tone="reset" label="Reset Match" icon={<IconReset />} onClick={() => onAction("resetMatch", match)} />
                  <ActionButton tone="dq" label="Remove Match" icon={<IconRemove />} onClick={() => onAction("removeMatch", match)} />
                </>
              )}

              {/* Force to In-Progress button for called matches */}
              {match.isLocal && match.status === "called" && (
                <ActionButton tone="send" label="Force to In-Progress" icon={<IconPlay />} onClick={() => onAction("forceToInProgress", match)} />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
