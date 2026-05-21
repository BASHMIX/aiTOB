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

export type MatchStatus = "waiting" | "live" | "called" | "done" | "dq";

export interface MatchPlayer {
  name: string;
  avatar?: string;
  score?: number | "DQ";
  highlight?: boolean;
  isTBD?: boolean;
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
}

const STATUS_META: Record<
  MatchStatus,
  { label: string; tone: "activate" | "send" | "reset" | "dq" | "neutral" }
> = {
  waiting: { label: "WAITING", tone: "activate" },
  live: { label: "LIVE", tone: "send" },
  called: { label: "CALLED", tone: "reset" },
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

function ScoreCell({ player, onUpdate }: { player: MatchPlayer; onUpdate?: (val: number) => void }) {
  const isDQ = player.score === "DQ";
  const score = typeof player.score === 'number' ? player.score : 0;

  return (
    <div
      className={`flex h-12 min-w-16 items-center justify-center text-base font-semibold border-l border-[var(--border)] text-slate-100
        ${isDQ ? "text-[var(--tone-dq)]" : ""}
        ${player.highlight ? "bg-[var(--tone-send-highlight)] text-[var(--tone-send)]" : ""}
      `}
    >
      {onUpdate && !isDQ && (
        <button 
          onClick={() => onUpdate(Math.max(0, score - 1))}
          className="w-5 h-full flex items-center justify-center hover:bg-white/5 text-xs text-gray-500 transition-colors"
        >-</button>
      )}
      <span className="flex-1 text-center">{player.score !== undefined ? player.score : ""}</span>
      {onUpdate && !isDQ && (
        <button 
          onClick={() => onUpdate(score + 1)}
          className="w-5 h-full flex items-center justify-center hover:bg-white/5 text-xs text-gray-500 transition-colors"
        >+</button>
      )}
    </div>
  );
}

function PlayersBlock({ players, onUpdateScore }: { players: MatchData["players"], onUpdateScore?: (p: number, val: number) => void }) {
  return (
    <div className="flex-1 overflow-hidden flex flex-col justify-center rounded-l-md">
      {players.map((p, i) => (
        <div
          key={i}
          className={`flex items-center justify-between ${i === 0 ? "border-b border-[var(--border)]" : ""}`}
        >
          <div className="flex-1 flex items-center gap-2.5 px-3 py-2.5 text-sm font-medium text-[var(--foreground)]">
            <div className="w-6 h-6 rounded-full bg-[var(--muted)] overflow-hidden border border-[var(--border)] flex-shrink-0">
              {p.avatar ? (
                <img src={p.avatar} alt="" className="w-full h-full object-cover" onError={(e) => (e.currentTarget.style.display = 'none')} />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-[10px] text-[var(--muted-foreground)]">?</div>
              )}
            </div>
            <span className="truncate">{p.name}</span>
          </div>
          <ScoreCell player={p} onUpdate={onUpdateScore ? (v) => onUpdateScore(i, v) : undefined} />
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
        <div className="absolute right-0 top-full mt-1.5 z-50 bg-[var(--card)] border border-[var(--tone-dq-border)] rounded-md shadow-2xl min-w-[140px] text-left p-1 overflow-hidden animate-slideUp">
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
        className={`inline-flex h-8 items-center justify-center gap-1.5 rounded-md border px-3 text-xs font-semibold transition-all
          ${match.stationId
            ? "border-[var(--tone-send-border)] bg-[var(--tone-send-bg)] text-[var(--tone-send)] hover:bg-[var(--tone-send-hover)] hover:scale-[1.02]"
            : "border-[var(--border)] bg-[var(--foreground-5)] text-gray-300 hover:bg-[var(--foreground-10)] hover:text-white hover:scale-[1.02]"
          }`}
      >
        {match.stationId ? curName : "Station"}
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1.5 z-50 bg-[var(--card)] border border-[var(--border)] rounded-md shadow-2xl min-w-[170px] text-left p-1 overflow-hidden animate-slideUp">
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
    <div className={`flex items-stretch rounded-lg border transition-all duration-200
      ${isDropdownOpen 
        ? "z-40 relative shadow-[0_0_20px_rgba(255,200,0,0.15)] border-accentYellow/40 bg-black/40 scale-[1.01]" 
        : "z-10 relative border-white/10"
      }
      ${PANEL_TONE[meta.tone]}
    `}>
      <PlayersBlock 
        players={match.players} 
        onUpdateScore={match.isLocal ? (p, v) => onAction("updateScore", match, { playerIdx: p, value: v }) : undefined} 
      />

      <div className="relative flex w-[260px] flex-col justify-between border-l border-[var(--border-60)] px-3 py-2.5 rounded-r-lg">
        <span
          className={`absolute right-2.5 top-2.5 rounded border px-2 py-0.5 text-[9px] font-black tracking-widest ${TONE_TEXT[meta.tone]} ${TONE_BORDER[meta.tone]}`}
        >
          {meta.label}
        </span>

        <div>
          <div className="flex items-center gap-1.5 text-sm font-semibold text-[var(--foreground)] truncate font-mono">
            <span className="inline-flex h-5 min-w-5 px-1 items-center justify-center rounded bg-white/5 border border-white/10 text-[9px] font-black text-textDim">
              {match.id || "—"}
            </span>
            {displayPool && <span className="text-[#38bdf8] font-bold">{displayPool}</span>}
          </div>
          <div className="text-[11px] font-medium text-[var(--muted-foreground)] truncate pl-1 mt-0.5">{match.round || "Round"}</div>
        </div>

        <div className="mt-2.5 flex items-center gap-2 flex-wrap">
          {match.status === "waiting" && (
            <>
              {!match.isLocal && (
                <>
                  <ActionButton tone="activate" label="Call Match" icon={<IconCall />} onClick={() => onAction("callMatch", match)} />
                  <ActionButton tone="neutral" label="Activate" onClick={() => onAction("activate", match)} />
                </>
              )}
              {match.isLocal && (
                 <ActionButton tone="activate" label="Call Match" icon={<IconCall />} onClick={() => onAction("callMatch", match)} />
              )}
              <button
                type="button"
                onClick={() => onToggleStream(String(match.raw?.set_id || match.raw?.id || match.id || ''), !!match.isStreamMatch)}
                aria-label="Toggle Stream Q"
                title="Toggle stream indicators"
                className={`inline-flex h-8 w-10 items-center justify-center rounded-md border transition-all ${
                  match.isStreamMatch
                    ? "border-[var(--tone-activate-border)] bg-[var(--tone-activate)] text-[var(--background)] hover:bg-[var(--tone-activate-hover)] hover:scale-105"
                    : "border-[var(--tone-activate-border)] text-[var(--tone-activate)] hover:bg-[var(--tone-activate-hover)] hover:scale-105"
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
            <ActionButton tone="send" label="Send" icon={<IconSend />} onClick={() => onAction("sendScore", match)} />
          )}

          {match.isLocal && (match.status === "live" || match.status === "called") && (
            <DQMenu match={match} onAction={onAction} onOpenChange={setDqMenuOpen} />
          )}

          {match.isLocal && (
            <div className="flex gap-1">
              <ActionButton tone="reset" label="Reset" icon={<IconReset />} onClick={() => onAction("resetMatch", match)} />
              <button
                onClick={() => onAction("removeMatch", match)}
                title="Deactivate (Local only)"
                className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-red-900/40 bg-red-900/10 text-red-400 hover:bg-red-900/30 transition-colors"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="w-3.5 h-3.5">
                  <line x1="18" y1="6" x2="6" y2="18"></line>
                  <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
              </button>
            </div>
          )}

          {showTimer && (
            <span
              className={`ml-auto font-mono text-xs font-bold tabular-nums tracking-tight flex items-center gap-1.5 px-2 py-1 rounded bg-black/20 border border-white/5
                ${match.status === "live" ? "text-[var(--tone-send)]" : (isTimerWarning ? "text-[var(--tone-dq)] animate-pulse" : "text-[var(--tone-reset)]")}
              `}
            >
              <span>{match.status === "live" ? "⏱️" : "⏳"}</span>
              <span>{timeDisplay}</span>
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
