import { useEffect, useState, useRef } from "react";
import { ActionButton } from "./ActionButton";
import { DQPlayerMenu } from "./DQPlayerMenu";
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
  attendanceState?: 'pending' | 'present' | 'withdrawn';
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
  providerType?: 'startgg' | 'challonge';
  // Owning start.gg event — drives the per-card Event badge so multi-game
  // tournaments are visually distinguishable at a glance.
  eventId?: string;
  eventName?: string;
  // True when the bot has surrendered auto-DQ for this set (partial / no Discord reach).
  // Surfaces as a small banner so the TO knows the bot won't intervene.
  autoDqDisarmed?: boolean;
  stateAxes?: { provider?: { raw?: string | null; normalized?: string | null }; hub_status?: string | null; sync_status?: string | null } | null;
  discordWorkflow?: { call_sent?: boolean; called_at?: string | null; thread_id?: string | null; player1_ready_at?: string | null; player2_ready_at?: string | null; attendance_deadline?: string | null } | null;
  eligibility?: { two_sided?: boolean; actionable?: boolean; reason?: string | null };
  providerActions?: Record<string, { kind: 'local' | 'remote' | 'unavailable'; enabled: boolean; label?: string; reason?: string }> | null;
}

// Stable, distinct badge color per event (hash → palette index) so the same
// event always reads the same color across cards.
const EVENT_BADGE_COLORS = [
  "bg-purple-500/15 text-purple-300 border-purple-500/30",
  "bg-sky-500/15 text-sky-300 border-sky-500/30",
  "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  "bg-amber-500/15 text-amber-300 border-amber-500/30",
  "bg-pink-500/15 text-pink-300 border-pink-500/30",
  "bg-cyan-500/15 text-cyan-300 border-cyan-500/30",
];
function eventBadgeColor(key: string): string {
  let h = 0;
  for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) >>> 0;
  return EVENT_BADGE_COLORS[h % EVENT_BADGE_COLORS.length];
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
      title="No linked Discord account — the bot cannot reach this player. Coordinate their check-in through the tournament provider or the Hub."
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
            {p.attendanceState === 'withdrawn' && (
              <span className="rounded border border-red-500/40 bg-red-500/10 px-1 py-0.5 text-[8px] font-black uppercase tracking-wide text-red-300">
                Withdrawn
              </span>
            )}
            {p.attendanceState === 'present' && (
              <span className="rounded border border-emerald-500/40 bg-emerald-500/10 px-1 py-0.5 text-[8px] font-black uppercase tracking-wide text-emerald-300">
                Present
              </span>
            )}
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
  stations?: { id: string; name: string; is_stream_station?: boolean }[];
  // Stream preflight failed — no local stream station maps to a live start.gg
  // stream. Warn-but-allow: we badge the button, we do NOT disable it (local
  // overlays/routing/green-room still work; only the public 📺 won't render).
  streamUnlinked?: boolean;
}

// Compact amber chip shown beside the "For Stream" button when the start.gg
// stream isn't linked. Tooltip carries the full explanation.
function StreamUnlinkedBadge() {
  return (
    <span
      title="No Hub stream station is linked to a live start.gg stream. You can still flag this match — local overlays, station routing and lobby DMs work — but the public 📺 won't appear on the start.gg bracket until a stream is linked in start.gg admin."
      className="inline-flex items-center gap-0.5 rounded border border-amber-500/40 bg-amber-500/10 px-1 py-0.5 text-[8px] font-bold uppercase tracking-wider text-amber-300/90 leading-none cursor-help select-none shrink-0"
    >
      ⚠ 📺
    </span>
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
            const isStream = !!s.is_stream_station;
            return (
              <button
                key={s.id}
                onClick={() => {
                  setOpen(false);
                  if (isOccupied) {
                    onAction("enqueueStation", match, s.id);
                  } else {
                    onAction("assignStation", match, s.id);
                  }
                }}
                title={isOccupied ? `Station occupied — click to add to ${s.name} queue` : (isStream ? "Stream station — assigning flags this match for stream" : undefined)}
                className={`w-full text-left px-3 py-1.5 text-xs transition-colors rounded flex items-center justify-between
                  ${isOccupied
                    ? "text-yellow-300 hover:bg-yellow-500/15 border border-yellow-500/25 mb-0.5 cursor-pointer"
                    : s.id === match.stationId
                      ? "text-[var(--tone-send)] bg-[var(--tone-send-hover)] font-semibold"
                      : "text-gray-200 hover:bg-[var(--foreground-5)]"
                  }`}
              >
                <span className="truncate pr-1 flex items-center gap-1">
                  {isStream && <span className="flex-shrink-0" title="Stream station">📺</span>}
                  <span className="truncate">{s.name}</span>
                </span>
                {isOccupied && (
                  <span className="text-[8px] leading-none text-yellow-400 font-bold px-1.5 py-0.5 rounded bg-yellow-400/10 border border-yellow-400/30 flex-shrink-0">
                    + Add to Queue
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function MatchCard({ match, dqTimerSeconds, autoDqEnabled, onAction, onToggleStream, stations, streamUnlinked }: MatchCardProps) {
  const meta = STATUS_META[match.status];
  const showTimer = match.status === "live" || match.status === "called";
  // Legacy Start.gg rows do not carry an action projection. New provider rows
  // must opt in explicitly, so an unavailable Challonge operation never leaks
  // through the old fallback controls.
  const actionEnabled = (action: string) => {
    const projected = match.providerActions?.[action];
    return projected ? projected.enabled : match.providerType !== 'challonge';
  };

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
      else if (match.status === "called" && match.providerType === 'startgg') {
        const deadline = parseUTCDate(match.discordWorkflow?.attendance_deadline);
        if (!deadline) {
          setTimeDisplay("Start.gg");
          setIsTimerWarning(false);
          return;
        }
        const remaining = Math.max(0, Math.floor((deadline - now) / 1000));
        const m = Math.floor(remaining / 60).toString().padStart(2, '0');
        const s = (remaining % 60).toString().padStart(2, '0');
        setTimeDisplay(`${m}:${s}`);
        setIsTimerWarning(remaining <= 60 && remaining > 0);
      }
      else if (match.status === "called" && match.calledAt) {
        const called = parseUTCDate(match.calledAt);
        const diff = Math.floor((now - called) / 1000);
        const remaining = Math.max(0, dqTimerSeconds - diff);
        const m = Math.floor(remaining / 60).toString().padStart(2, '0');
        const s = (remaining % 60).toString().padStart(2, '0');
        setTimeDisplay(`${m}:${s}`);
        setIsTimerWarning(remaining <= 60 && remaining > 0);
      }
    };

    updateTimer();
    const iv = setInterval(updateTimer, 1000);
    return () => clearInterval(iv);
  }, [match.status, match.startedAt, match.calledAt, match.providerType, match.discordWorkflow?.attendance_deadline, dqTimerSeconds, autoDqEnabled, showTimer]);

  return (
    <div
      draggable={!isDropdownOpen}
      onDragStart={(e) => {
        const setId = String(match.raw?.set_id || match.raw?.id || match.id || "");
        e.dataTransfer.setData("text/plain", setId);
        e.dataTransfer.setData("application/json", JSON.stringify({
          setId,
          round: match.round,
          p1: match.players[0]?.name,
          p2: match.players[1]?.name,
          raw: match.raw,
          isLocal: match.isLocal,
        }));
        e.dataTransfer.effectAllowed = "copyMove";
      }}
      title="Drag and drop onto a station card to assign or queue"
      className={`flex flex-col rounded-lg border transition-all duration-200 cursor-grab active:cursor-grabbing
      ${isDropdownOpen 
        ? "z-50 relative shadow-[0_0_20px_rgba(255,200,0,0.15)] border-accentYellow/40 bg-black/40 scale-[1.01] overflow-visible" 
        : "z-10 relative border-white/10 hover:border-white/30 overflow-hidden"
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

          {/* Event badge — distinct color per game so SF6 vs Tekken etc. read instantly */}
          {match.eventName && (
            <span
              title={`Event: ${match.eventName}`}
              className={`self-start max-w-full truncate rounded border px-1.5 py-[1px] text-[9px] font-black uppercase tracking-wider leading-none ${eventBadgeColor(match.eventId || match.eventName)}`}
            >
              {match.eventName}
            </span>
          )}

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
          {match.stateAxes && (
            <div className="flex flex-wrap gap-1 pt-0.5 text-[8px] font-sans">
              <span className="rounded border border-sky-500/30 px-1 text-sky-200" title={match.stateAxes.provider?.raw || undefined}>P: {match.stateAxes.provider?.normalized || 'unknown'}</span>
              {match.stateAxes.hub_status && <span className="rounded border border-amber-500/30 px-1 text-amber-200">H: {match.stateAxes.hub_status}</span>}
              {match.stateAxes.sync_status && <span className="rounded border border-violet-500/30 px-1 text-violet-200">S: {match.stateAxes.sync_status}</span>}
            </div>
          )}
        </div>
      </div>

      {/* Bottom Section (Row 3): Timer & Action Buttons Toolbar */}
      <div className="flex items-center justify-between border-t border-white/5 bg-black/20 px-2.5 py-1.5 gap-2 text-xs">
        {/* Left Side: Timer & Auto-DQ Manual Warning */}
        <div className="flex items-center gap-1.5 flex-wrap min-w-0">
          {match.discordWorkflow && (match.discordWorkflow.call_sent || match.discordWorkflow.thread_id || match.discordWorkflow.player1_ready_at || match.discordWorkflow.player2_ready_at) && (
            <span title={`Call: ${match.discordWorkflow.call_sent ? 'sent' : 'not recorded'} · Thread: ${match.discordWorkflow.thread_id || 'not recorded'} · Ready: ${match.discordWorkflow.player1_ready_at ? 'P1' : '—'} / ${match.discordWorkflow.player2_ready_at ? 'P2' : '—'}`} className="rounded border border-indigo-500/30 bg-indigo-500/10 px-1.5 py-0.5 text-[8px] font-bold text-indigo-200">
              Discord: {match.discordWorkflow.call_sent ? 'call recorded' : 'workflow recorded'}
            </span>
          )}
          {match.providerActions?.report_score?.kind === 'unavailable' && (
            <span title={match.providerActions.report_score.reason} className="rounded border border-slate-500/40 bg-slate-500/10 px-1.5 py-0.5 text-[8px] font-bold text-slate-200">
              Result: unavailable
            </span>
          )}
          {/* Unreachable / Auto-DQ Banner */}
          {match.autoDqDisarmed && match.isLocal && match.status !== "done" && match.status !== "dq" && (
            <span
              title="Auto-DQ disarmed — partial-reach match. Bot will not intervene; coordinate this match manually."
              className="rounded border border-amber-500/40 bg-amber-500/10 text-amber-300 px-1.5 py-0.5 text-[8px] font-bold tracking-wider cursor-help select-none shrink-0"
            >
              ⚠ MANUAL
            </span>
          )}

          {/* Timer */}
          {showTimer && (
            <span
              title={match.status === 'called' && match.providerType === 'startgg' ? 'Start.gg owns the check-in deadline and bracket outcome.' : undefined}
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
              {streamUnlinked && !match.isStreamMatch && <StreamUnlinkedBadge />}
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
                  {streamUnlinked && !match.isStreamMatch && <StreamUnlinkedBadge />}
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

              {match.isLocal && match.status === "live" && actionEnabled('report_score') && (
                <ActionButton tone="send" label="Send Score" icon={<IconSend />} onClick={() => onAction("sendScore", match)} />
              )}

              {match.isLocal && (match.status === "waiting" || match.status === "called" || match.status === "live") && actionEnabled('dq') && (
                <DQPlayerMenu
                  players={match.players}
                  onSelect={(player) => onAction("dq", match, player)}
                  onOpenChange={setDqMenuOpen}
                  renderTrigger={({ toggle }) => <ActionButton tone="dq" label="DQ" icon={<IconDQ />} onClick={toggle} />}
                />
              )}

              {match.isLocal && (
                <>
                  {actionEnabled('reset') && <ActionButton tone="reset" label="Reset Match" icon={<IconReset />} onClick={() => onAction("resetMatch", match)} />}
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
