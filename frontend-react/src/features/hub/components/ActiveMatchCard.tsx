import { useState, useRef, useEffect } from 'react';
import { useHubStore } from '@/store/useHubStore';
import axios from 'axios';
import { DQPlayerMenu } from './DQPlayerMenu';
import { tournamentAccent, withAccentAlpha } from './tournamentAccent';
import { usePermission } from '@/hooks/usePermission';

// ── Icons ──────────────────────────────────────────────────────────────
const IconBot = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
    <rect x="3" y="11" width="18" height="10" rx="2"/>
    <path d="M12 11V7"/><circle cx="12" cy="5" r="2"/>
    <path d="M7 15h.01M17 15h.01M8 19h8"/>
  </svg>
);
const IconSwap = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="w-5 h-5">
    <path d="M7 16V4m0 0L3 8m4-4l4 4"/><path d="M17 8v12m0 0l4-4m-4 4l-4-4"/>
  </svg>
);
const IconSend = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
    <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
  </svg>
);
const IconDQ = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
    <circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/>
  </svg>
);

export function ActiveMatchCard({ match }: { match: any }) {
  const canOperate = usePermission('match.operate');
  const canManageStations = usePermission('station.manage');
  const canReportResult = usePermission('result.report');
  const canManualDq = usePermission('dq.manual');
  const { stations, matches, setMatches, tournaments, currentSlug } = useHubStore();
  const [dqOpen, setDqOpen] = useState(false);
  const [sending, setSending] = useState(false);
  const [stationOpen, setStationOpen] = useState(false);
  const [notice, setNotice] = useState<{ text: string; ok: boolean } | null>(null);
  const stationRef = useRef<HTMLDivElement>(null);
  const [ftOpen, setFtOpen] = useState(false);
  const ftRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (ftRef.current && !ftRef.current.contains(event.target as Node)) {
        setFtOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [ftRef]);

  const updateBestOf = async (newBestOf: number) => {
    setFtOpen(false);
    setMatches(matches.map(m => m.set_id === match.set_id ? { ...m, best_of: newBestOf } : m));
    try {
      await axios.patch(`/api/active-matches/${match.set_id}`, { best_of: newBestOf });
    } catch (e) {
      console.error('Failed to update match format', e);
    }
  };

  const getFormatLabel = (bestOf?: number) => {
    if (bestOf === 5) return 'FT3';
    if (bestOf === 7) return 'FT4';
    if (bestOf === 9) return 'FT5';
    if (bestOf === 13) return 'FT7';
    return 'FT2';
  };

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (stationRef.current && !stationRef.current.contains(event.target as Node)) {
        setStationOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [stationRef]);

  const broadcastState = match.broadcast_state || (match.station_id && match.status === 'in_progress' ? 'live' : 'off_air');
  const isLive = broadcastState === 'live';
  const isSwapped = !!match.swapped;
  const trackedMatch = matches.find((item) => item.set_id === match.set_id);
  // The On-Stream card receives a compact match snapshot. Read the mutable
  // value from Hub state so its colour changes as soon as the PATCH succeeds.
  const botEnabled = (trackedMatch?.bot_enabled ?? match.bot_enabled) !== false;
  const tournament = tournaments.find((item) => item.slug === match.tournament_slug || item.slug === currentSlug);
  const providerType = match.provider_type || tournament?.provider_type || 'startgg';
  const providerLabel = providerType === 'challonge' ? 'Challonge' : 'Start.gg';
  const accent = tournamentAccent(tournament);
  // The On-Stream endpoint is intentionally compact.  Reuse the authoritative
  // action projection already loaded for the same match in Match Dashboard so
  // a provider-backed score/DQ action does not disappear from this card.
  const dashboardMatch = matches.find((item) => item.set_id === match.set_id);
  const actionEnabled = (action: string) => {
    const projected = match.actions?.[action] ?? dashboardMatch?.actions?.[action];
    return projected ? projected.enabled : providerType !== 'challonge';
  };
  const canSendScore = canReportResult && actionEnabled('report_score');
  const canDq = canManualDq && actionEnabled('dq');

  // ── Close / remove from active tracking ────────────────────────────
  const closeMatch = async () => {
    try {
      await axios.delete(`/api/active-matches/${match.set_id}`);
      setMatches(matches.filter(m => m.set_id !== match.set_id));
    } catch (e) {
      console.error('Failed to close match', e);
    }
  };

  const updateTimerRef = useRef<number | null>(null);

  // ── Optimistic score update — instant UI ───────────────────────────
  const changeScore = (player: 'p1' | 'p2', delta: number) => {
    const key = `${player}_score` as const;
    const currentMatches = useHubStore.getState().matches;
    const currentMatch = currentMatches.find(m => m.set_id === match.set_id);
    const oldVal = Number(currentMatch ? currentMatch[key] : match[key]) || 0;
    const newVal = Math.max(0, oldVal + delta);
    
    setMatches(currentMatches.map(m =>
      m.set_id === match.set_id ? { ...m, [key]: newVal } : m
    ));

    if (updateTimerRef.current) {
      window.clearTimeout(updateTimerRef.current);
    }

    updateTimerRef.current = window.setTimeout(() => {
      const latestMatch = useHubStore.getState().matches.find(m => m.set_id === match.set_id);
      if (latestMatch) {
        axios.patch(`/api/active-matches/${match.set_id}`, { [key]: latestMatch[key] }).catch(() => {
          setMatches(useHubStore.getState().matches.map(m =>
            m.set_id === match.set_id ? { ...m, [key]: oldVal } : m
          ));
        });
      }
    }, 400);
  };

  // ── Station assign ─────────────────────────────────────────────────
  const assignStation = async (stationId: string) => {
    await axios.patch(`/api/active-matches/${match.set_id}`, {
      station_id: stationId || null,
      status: stationId ? 'in_progress' : 'called'
    });
    setMatches(matches.map(m =>
      m.set_id === match.set_id ? { ...m, station_id: stationId || undefined } : m
    ));
  };

  const enqueueStation = async (stationId: string, stationName: string) => {
    try {
      await axios.post(`/api/stations/${stationId}/queue`, { set_id: match.set_id });
      setNotice({ text: `Queued on ${stationName} ✓`, ok: true });
      const fresh = await axios.get('/api/active-matches');
      setMatches(fresh.data.matches || []);
    } catch (error: any) {
      setNotice({ text: error.response?.data?.detail || 'Could not add to queue.', ok: false });
    }
  };

  // ── Swap ───────────────────────────────────────────────────────────
  const toggleSwap = async () => {
    const newSwap = !isSwapped;
    setMatches(matches.map(m =>
      m.set_id === match.set_id ? { ...m, swapped: newSwap } : m
    ));
    await axios.patch(`/api/active-matches/${match.set_id}`, { swapped: newSwap });
  };

  // ── Bot toggle ─────────────────────────────────────────────────────
  const toggleBot = async () => {
    const newBot = !botEnabled;
    setMatches(matches.map(m =>
      m.set_id === match.set_id ? { ...m, bot_enabled: newBot } : m
    ));
    try {
      await axios.patch(`/api/active-matches/${match.set_id}`, { bot_enabled: newBot });
    } catch (error: any) {
      setMatches(matches.map(m =>
        m.set_id === match.set_id ? { ...m, bot_enabled: botEnabled } : m
      ));
      setNotice({ text: error.response?.data?.detail || 'Could not update Bot for this match.', ok: false });
    }
  };

  // ── DQ ─────────────────────────────────────────────────────────────
  const dqPlayer = async (player: 'p1' | 'p2') => {
    setDqOpen(false);
    try {
      const response = providerType === 'challonge'
        ? await axios.post(`/api/active-matches/${match.set_id}/dq`, { player })
        : await axios.post(`/api/active-matches/${match.set_id}/attendance`, { player, state: 'withdrawn' });
      const fresh = await axios.get('/api/active-matches');
      setMatches(fresh.data.matches || []);
      setNotice({ text: response.data.message || (providerType === 'challonge' ? 'DQ submitted for provider verification.' : 'Player marked withdrawn.'), ok: true });
    } catch (error: any) {
      setNotice({ text: error.response?.data?.detail || 'Could not submit DQ.', ok: false });
    }
  };

  // ── Send score ─────────────────────────────────────────────────────
  const sendScore = async () => {
    setSending(true);
    try {
      const res = await axios.post(`/api/active-matches/${match.set_id}/send`);
      if (!res.data.error && providerType !== 'challonge') {
        const currentMatches = useHubStore.getState().matches;
        setMatches(currentMatches.map(m =>
          m.set_id === match.set_id ? { ...m, status: 'complete' as const } : m
        ));
      }
      if (providerType === 'challonge') {
        const fresh = await axios.get('/api/active-matches');
        setMatches(fresh.data.matches || []);
      }
      setNotice({ text: res.data.message || 'Result submitted.', ok: true });
    } catch (error: any) {
      setNotice({ text: error.response?.data?.detail || 'Could not submit the result.', ok: false });
    } finally {
      setSending(false);
    }
  };

  // Display order respects swap
  const p1 = isSwapped
    ? { name: match.p2_name, score: match.p2_score, team: match.p2_team, cfn: match.p2_cfn, avatar: match.p2_avatar, attendance: match.p2_attendance_state, key: 'p2' as const }
    : { name: match.p1_name, score: match.p1_score, team: match.p1_team, cfn: match.p1_cfn, avatar: match.p1_avatar, attendance: match.p1_attendance_state, key: 'p1' as const };
  const p2 = isSwapped
    ? { name: match.p1_name, score: match.p1_score, team: match.p1_team, cfn: match.p1_cfn, avatar: match.p1_avatar, attendance: match.p1_attendance_state, key: 'p1' as const }
    : { name: match.p2_name, score: match.p2_score, team: match.p2_team, cfn: match.p2_cfn, avatar: match.p2_avatar, attendance: match.p2_attendance_state, key: 'p2' as const };

  // ── Timer Logic ──
  const curTourney = tournaments.find(t => t.name === currentSlug || t.slug === currentSlug);
  const actualTourney = tournaments.find(t => t.slug === currentSlug) || curTourney;
  const dqTimerSeconds = providerType === 'startgg'
    ? (actualTourney?.provider_dq_timer_seconds ?? actualTourney?.dq_timer_seconds ?? 600)
    : (actualTourney?.dq_timer_seconds ?? 600);

  const showTimer = match.status === "in_progress" || match.status === "called";
  const [timeDisplay, setTimeDisplay] = useState("00:00");
  const [isTimerWarning, setIsTimerWarning] = useState(false);

  // Helper to parse dates in UTC safely to avoid local timezone offset shifts
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

  useEffect(() => {
    if (!showTimer) return;
    
    const updateTimer = () => {
      const now = Date.now();
      
      if (match.status === "in_progress" && match.started_at) {
        const started = parseUTCDate(match.started_at);
        const diff = Math.max(0, Math.floor((now - started) / 1000));
        const m = Math.floor(diff / 60).toString().padStart(2, '0');
        const s = (diff % 60).toString().padStart(2, '0');
        setTimeDisplay(`${m}:${s}`);
        setIsTimerWarning(false);
      } 
      else if (match.status === "called" && providerType === 'startgg') {
        const deadline = parseUTCDate(match.attendance_deadline);
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
      else if (match.status === "called" && match.called_at) {
        const called = parseUTCDate(match.called_at);
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
  }, [match.status, match.started_at, match.called_at, match.attendance_deadline, providerType, dqTimerSeconds, showTimer]);

  return (
    <div id={`active-match-${match.set_id}`} style={{ borderColor: withAccentAlpha(accent, 0.5) }} className={`bg-cardDark border rounded-lg flex flex-col shadow-md transition-all relative ${dqOpen || stationOpen ? 'z-30' : 'z-10'}`}>

      {/* ── Header ── */}
      <div className="flex items-center justify-between px-3 py-2 bg-appDark border-b border-white/10 rounded-t-lg">
        <div className="min-w-0">
          <span style={{ color: accent }} className="block truncate font-bold text-sm">Match#: {match.match_number || match.set_id}</span>
          <span className="block truncate text-[9px] font-semibold uppercase tracking-wide text-textDim">
            {tournament?.name || match.tournament_slug || 'Tournament'} · {providerLabel}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span style={isLive ? { backgroundColor: accent } : undefined} className={`w-2 h-2 rounded-full ${isLive ? 'animate-pulse' : 'bg-gray-600'}`} />
          <span style={isLive ? { color: accent } : undefined} className={`text-[10px] font-bold ${isLive ? '' : 'text-textDim'}`}>
            {isLive ? 'LIVE ON' : 'NOT LIVE'}
          </span>
          {/* Custom Station Dropdown */}
          {canManageStations && <div className="relative" ref={stationRef}>
            <button
              onClick={() => setStationOpen(!stationOpen)}
              className={`ml-1 px-2 py-0.5 rounded border text-[10px] font-bold transition-all flex items-center gap-1
                ${match.station_id
                  ? 'border-statusGreen/30 bg-statusGreen/10 text-statusGreen hover:bg-statusGreen/20'
                  : 'border-white/20 bg-appDark text-textLight hover:border-white/40'
                }`}
            >
              <span>{match.station_id ? stations.find(s => s.id === match.station_id)?.name || 'Station' : '— station —'}</span>
              <span className="text-[8px] opacity-75">▼</span>
            </button>
            {stationOpen && (
              <div className="absolute right-0 top-full mt-1.5 z-50 bg-cardDark border border-white/10 rounded-md shadow-2xl min-w-[160px] text-left p-1 overflow-hidden animate-slideUp">
                <div className="px-2 py-1 text-[8px] text-textDim font-bold uppercase tracking-widest border-b border-white/5 mb-1">Assign Station</div>
                {match.station_id && (
                  <button
                    onClick={() => { setStationOpen(false); assignStation(''); }}
                    className="w-full text-left px-2.5 py-1 text-[10px] text-gray-400 hover:bg-white/5 rounded transition-colors"
                  >
                    — Unassign
                  </button>
                )}
                {stations.length === 0 && <div className="px-2.5 py-1.5 text-[10px] text-textDim italic">No stations</div>}
                {stations.map(s => {
                  const isOccupied = matches.some(m => m.set_id !== match.set_id && m.station_id === s.id && (m.status === 'in_progress' || m.status === 'called'));
                  return (
                    <button
                      key={s.id}
                      onClick={() => {
                        setStationOpen(false);
                        if (isOccupied) {
                          enqueueStation(s.id, s.name);
                        } else {
                          assignStation(s.id);
                        }
                      }}
                      title={isOccupied ? `Station occupied — click to add to ${s.name} queue` : undefined}
                      className={`w-full text-left px-2.5 py-1.5 text-[10px] transition-colors rounded flex items-center justify-between mb-0.5
                        ${isOccupied
                          ? "text-yellow-300 hover:bg-yellow-500/15 border border-yellow-500/25 cursor-pointer"
                          : s.id === match.station_id
                            ? "text-statusGreen bg-statusGreen/10 font-bold"
                            : "text-gray-200 hover:bg-white/5"
                        }`}
                    >
                      <span className="truncate pr-1">{s.name}</span>
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
          </div>}
          {/* × Close button */}
          {canOperate && <button
            onClick={closeMatch}
            className="ml-1 w-5 h-5 flex items-center justify-center rounded text-textDim hover:text-red-400 hover:bg-red-900/20 transition-colors"
            title="Remove from On-Stream panel"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="w-3.5 h-3.5">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>}
        </div>
      </div>

      {/* ── Round / Timer ── */}
      <div className="px-3 py-1 text-[10px] text-textDim border-b border-white/5 flex items-center justify-between bg-black/10">
        <div className="truncate pr-2">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span>Round: <span className="text-textLight font-semibold">{match.round_name || '—'}</span></span>
            <div className="relative inline-block" ref={ftRef}>
              <button
                type="button"
                disabled={!canOperate}
                onClick={() => setFtOpen(!ftOpen)}
                className="rounded border border-amber-400/30 bg-amber-400/10 px-1.5 py-0.5 text-[9px] font-bold text-amber-300 hover:bg-amber-400/20 transition-all flex items-center gap-0.5 leading-none cursor-pointer"
                title="Match format (First to N). Click to change."
              >
                <span>{getFormatLabel(match.best_of)}</span>
                {canOperate && <span className="text-[7px] opacity-70">▼</span>}
              </button>
              {ftOpen && (
                <div className="absolute left-0 top-full mt-1 z-50 bg-cardDark border border-white/10 rounded-md shadow-2xl py-1 min-w-[85px] text-left animate-slideUp">
                  {[
                    { label: 'FT2 (Bo3)', bestOf: 3 },
                    { label: 'FT3 (Bo5)', bestOf: 5 },
                    { label: 'FT5 (Bo9)', bestOf: 9 },
                    { label: 'FT7 (Bo13)', bestOf: 13 },
                  ].map((opt) => (
                    <button
                      key={opt.bestOf}
                      onClick={() => updateBestOf(opt.bestOf)}
                      className={`w-full text-left px-2.5 py-1 text-[10px] hover:bg-white/10 transition-colors ${
                        (match.best_of ?? 3) === opt.bestOf ? 'text-accentYellow font-bold' : 'text-gray-200'
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
          {match.is_stream_match && (
            <span className="ml-2 text-blue-400 inline-flex items-center gap-0.5 font-bold">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-3 h-3">
                <rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/>
              </svg>
              {broadcastState === 'live' ? 'LIVE' : broadcastState === 'ready' ? 'STREAM READY' : 'STREAM QUEUED'}
            </span>
          )}
        </div>
        {showTimer && (
          <span title={match.status === 'called' && providerType === 'startgg' ? 'Start.gg owns the check-in deadline and bracket outcome.' : undefined} className={`font-mono text-[10px] font-bold tabular-nums flex items-center gap-1 ${
            match.status === "in_progress" 
              ? "text-statusGreen bg-green-500/10 border border-green-500/20 px-1.5 py-0.5 rounded-sm" 
              : (isTimerWarning ? "text-red-400 bg-red-500/10 border border-red-500/20 px-1.5 py-0.5 rounded-sm animate-pulse" : "text-yellow-400 bg-yellow-500/10 border border-yellow-500/20 px-1.5 py-0.5 rounded-sm")
          }`}>
            <span>{match.status === "in_progress" ? "⏱️" : "⏳"}</span>
            <span>{timeDisplay}</span>
          </span>
        )}
      </div>

      {/* ── Players ── */}
      <div className="flex flex-col gap-0.5 p-2">
        {[
          { label: 'P1', player: p1, accentClass: 'bg-accentYellow' },
          { label: 'P2', player: p2, accentClass: 'bg-orange-600' },
        ].map(({ label, player, accentClass }) => (
          <div key={label} className="flex items-center gap-2 bg-appDark rounded px-2 py-1.5 border border-white/5">
            <span className={`${accentClass} text-black text-[10px] font-black px-1.5 py-0.5 rounded flex-shrink-0`}>{label}</span>
            <div className="w-8 h-8 rounded-full bg-white/10 overflow-hidden flex-shrink-0 border border-white/10">
              {player.avatar ? (
                <img src={player.avatar} alt={label} className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full bg-white/5 flex items-center justify-center text-textDim text-[9px]">{label}</div>
              )}
            </div>
            <div className="flex flex-col flex-1 min-w-0">
              <span className="text-sm font-bold text-white leading-tight truncate">{player.name || '—'}</span>
              {player.attendance === 'withdrawn' && <span className="text-[9px] font-black uppercase tracking-wide text-red-400">Withdrawn</span>}
              {player.attendance === 'present' && <span className="text-[9px] font-black uppercase tracking-wide text-statusGreen">Present</span>}
              <span className="text-[9px] text-textDim truncate">
                {player.cfn ? `CFN: ${player.cfn}` : player.team ? `[${player.team}]` : ''}
              </span>
            </div>
            <div className="flex items-center ml-auto bg-white rounded overflow-hidden shadow-inner">
              <div className="text-black font-black text-xl w-11 text-center py-0.5 select-none">
                {player.score ?? 0}
              </div>
              {canOperate && <div className="flex flex-col border-l border-gray-300 bg-gray-100">
                <button onClick={() => changeScore(player.key, 1)}
                  className="text-gray-600 hover:text-black hover:bg-gray-300 transition-colors px-2 py-0.5 text-[10px] leading-none border-b border-gray-300">▲</button>
                <button onClick={() => changeScore(player.key, -1)}
                  className="text-gray-600 hover:text-black hover:bg-gray-300 transition-colors px-2 py-0.5 text-[10px] leading-none">▼</button>
              </div>}
            </div>
          </div>
        ))}
      </div>

      {/* ── Action Bar ── */}
      {notice && <p role="status" className={`mx-2 mt-2 rounded border px-2 py-1 text-[10px] ${notice.ok ? 'border-statusGreen/30 bg-statusGreen/10 text-statusGreen' : 'border-statusRed/30 bg-statusRed/10 text-statusRed'}`}>{notice.text}</p>}
      <div className="flex items-center border-t border-white/10 bg-appDark rounded-b-lg overflow-visible">
        {/* DQ / Force */}
        {canDq && <div className="flex-1">
          <DQPlayerMenu
            players={[{ name: match.p1_name }, { name: match.p2_name }]}
            onSelect={dqPlayer}
            onOpenChange={setDqOpen}
            menuPositionClassName="left-0 bottom-full mb-1.5"
            renderTrigger={({ toggle }) => (
              <button onClick={toggle}
                className="w-full flex flex-col items-center gap-0.5 py-2 px-1 text-red-400 hover:bg-red-900/20 transition-colors"
                title="DQ a player">
                <IconDQ /><span className="text-[9px] font-bold">DQ</span>
              </button>
            )}
          />
        </div>}
        {canDq && <div className="w-px h-8 bg-white/10" />}
        {/* Bot toggle */}
        {canOperate && <button onClick={toggleBot}
            title={botEnabled ? 'Disable Bot for this match' : 'Enable Bot for this match'}
            aria-pressed={botEnabled}
            className={`flex-1 flex flex-col items-center gap-0.5 py-2 px-1 transition-colors
            ${botEnabled ? 'text-accentYellow hover:bg-yellow-900/20' : 'text-gray-600 hover:bg-white/5'}`}>
          <IconBot /><span className="text-[9px] font-bold">Bot</span>
        </button>}
        {canOperate && <div className="w-px h-8 bg-white/10" />}
        {/* Swap */}
        {canOperate && <button onClick={toggleSwap}
          title="Swap player display positions in OBS overlay"
          className={`flex-1 flex flex-col items-center gap-0.5 py-2 px-1 transition-colors
            ${isSwapped ? 'text-blue-300 bg-blue-900/20' : 'text-textDim hover:bg-white/5'}`}>
          <IconSwap /><span className="text-[9px] font-bold">Swap</span>
        </button>}
        {canSendScore && <div className="w-px h-8 bg-white/10" />}
        {/* Send */}
        {canSendScore && <button onClick={sendScore} disabled={sending}
          title={providerType === 'challonge' ? 'Submit result for provider verification' : 'Report score to Start.gg and close match'}
          className="flex-1 flex flex-col items-center gap-0.5 py-2 px-1 text-statusGreen hover:bg-green-900/20 transition-colors disabled:opacity-40">
          <IconSend /><span className="text-[9px] font-bold">{sending ? '...' : 'Send'}</span>
        </button>}
      </div>
    </div>
  );
}
