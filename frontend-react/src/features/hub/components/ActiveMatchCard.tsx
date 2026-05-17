import { useState, useRef } from 'react';
import { useHubStore } from '@/store/useHubStore';
import axios from 'axios';

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
  const { stations, matches, setMatches } = useHubStore();
  const [dqOpen, setDqOpen] = useState(false);
  const [sending, setSending] = useState(false);

  const isLive = !!match.station_id;
  const isSwapped = !!match.swapped;
  const botEnabled = match.bot_enabled !== false;

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
    await axios.patch(`/api/active-matches/${match.set_id}`, { bot_enabled: newBot });
  };

  // ── DQ ─────────────────────────────────────────────────────────────
  const dqPlayer = async (player: 'p1' | 'p2') => {
    setDqOpen(false);
    await axios.post(`/api/active-matches/${match.set_id}/dq`, { player });
    setMatches(matches.map(m =>
      m.set_id === match.set_id ? { ...m, status: 'dq' as const } : m
    ));
  };

  // ── Send score ─────────────────────────────────────────────────────
  const sendScore = async () => {
    setSending(true);
    try {
      const res = await axios.post(`/api/active-matches/${match.set_id}/send`);
      if (!res.data.error) {
        const currentMatches = useHubStore.getState().matches;
        setMatches(currentMatches.map(m =>
          m.set_id === match.set_id ? { ...m, status: 'complete' as const } : m
        ));
      }
    } finally {
      setSending(false);
    }
  };

  // Display order respects swap
  const p1 = isSwapped
    ? { name: match.p2_name, score: match.p2_score, team: match.p2_team, cfn: match.p2_cfn, avatar: match.p2_avatar, key: 'p2' as const }
    : { name: match.p1_name, score: match.p1_score, team: match.p1_team, cfn: match.p1_cfn, avatar: match.p1_avatar, key: 'p1' as const };
  const p2 = isSwapped
    ? { name: match.p1_name, score: match.p1_score, team: match.p1_team, cfn: match.p1_cfn, avatar: match.p1_avatar, key: 'p1' as const }
    : { name: match.p2_name, score: match.p2_score, team: match.p2_team, cfn: match.p2_cfn, avatar: match.p2_avatar, key: 'p2' as const };

  return (
    <div className="bg-cardDark border border-white/10 rounded-lg overflow-hidden flex flex-col shadow-md">

      {/* ── Header ── */}
      <div className="flex items-center justify-between px-3 py-2 bg-appDark border-b border-white/10">
        <div className="flex items-center gap-2">
          <span className="font-bold text-white text-sm">Match#: {match.match_number || match.set_id}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${isLive ? 'bg-statusGreen animate-pulse' : 'bg-gray-600'}`} />
          <span className={`text-[10px] font-bold ${isLive ? 'text-statusGreen' : 'text-textDim'}`}>
            {isLive ? 'LIVE ON' : 'NOT LIVE'}
          </span>
          {/* Station dropdown */}
          <select
            className="ml-1 bg-appDark border border-white/20 rounded px-1.5 py-0.5 text-[10px] text-textLight focus:outline-none focus:border-accentYellow/50"
            value={match.station_id || ''}
            onChange={e => assignStation(e.target.value)}
          >
            <option value="">— station —</option>
            {stations.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          {/* × Close button */}
          <button
            onClick={closeMatch}
            className="ml-1 w-5 h-5 flex items-center justify-center rounded text-textDim hover:text-red-400 hover:bg-red-900/20 transition-colors"
            title="Remove from Active Match Status"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="w-3.5 h-3.5">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
      </div>

      {/* ── Round ── */}
      <div className="px-3 py-1 text-[10px] text-textDim border-b border-white/5">
        Round: <span className="text-textLight">{match.round_name || '—'}</span>
        {match.is_stream_match && (
          <span className="ml-2 text-blue-400 inline-flex items-center gap-0.5">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-3 h-3">
              <rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/>
            </svg>
            STREAM
          </span>
        )}
      </div>

      {/* ── Players ── */}
      <div className="flex flex-col gap-0.5 p-2">
        {[
          { label: 'P1', player: p1, accentClass: 'bg-accentYellow' },
          { label: 'P2', player: p2, accentClass: 'bg-orange-600' },
        ].map(({ label, player, accentClass }) => (
          <div key={label} className="flex items-center gap-2 bg-appDark rounded px-2 py-1.5">
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
              <span className="text-[9px] text-textDim truncate">
                {player.cfn ? `CFN: ${player.cfn}` : player.team ? `[${player.team}]` : ''}
              </span>
            </div>
            <div className="flex items-center ml-auto bg-white rounded overflow-hidden shadow-inner">
              <div className="text-black font-black text-xl w-11 text-center py-0.5 select-none">
                {player.score ?? 0}
              </div>
              <div className="flex flex-col border-l border-gray-300 bg-gray-100">
                <button onClick={() => changeScore(player.key, 1)}
                  className="text-gray-600 hover:text-black hover:bg-gray-300 transition-colors px-2 py-0.5 text-[10px] leading-none border-b border-gray-300">▲</button>
                <button onClick={() => changeScore(player.key, -1)}
                  className="text-gray-600 hover:text-black hover:bg-gray-300 transition-colors px-2 py-0.5 text-[10px] leading-none">▼</button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* ── Action Bar ── */}
      <div className="flex items-center border-t border-white/10 bg-appDark">
        {/* DQ / Force */}
        <div className="relative flex-1">
          <button onClick={() => setDqOpen(o => !o)}
            className="w-full flex flex-col items-center gap-0.5 py-2 px-1 text-red-400 hover:bg-red-900/20 transition-colors"
            title="Force DQ a player">
            <IconDQ /><span className="text-[9px] font-bold">Force</span>
          </button>
          {dqOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setDqOpen(false)} />
              <div className="absolute left-0 bottom-full mb-1 z-50 bg-cardDark border border-red-500/40 rounded shadow-2xl min-w-[130px]">
                <div className="px-2 py-1 text-[9px] text-red-400 font-bold border-b border-white/10 uppercase">DQ Who?</div>
                <button onClick={() => dqPlayer('p1')} className="w-full text-left px-3 py-2 text-xs text-red-300 hover:bg-red-900/30 truncate">{match.p1_name}</button>
                <button onClick={() => dqPlayer('p2')} className="w-full text-left px-3 py-2 text-xs text-red-300 hover:bg-red-900/30 truncate">{match.p2_name}</button>
              </div>
            </>
          )}
        </div>
        <div className="w-px h-8 bg-white/10" />
        {/* Bot toggle */}
        <button onClick={toggleBot}
          title={botEnabled ? 'Disable Bot for this match' : 'Enable Bot for this match'}
          className={`flex-1 flex flex-col items-center gap-0.5 py-2 px-1 transition-colors
            ${botEnabled ? 'text-accentYellow hover:bg-yellow-900/20' : 'text-gray-600 hover:bg-white/5'}`}>
          <IconBot /><span className="text-[9px] font-bold">Bot</span>
        </button>
        <div className="w-px h-8 bg-white/10" />
        {/* Swap */}
        <button onClick={toggleSwap}
          title="Swap player display positions in OBS overlay"
          className={`flex-1 flex flex-col items-center gap-0.5 py-2 px-1 transition-colors
            ${isSwapped ? 'text-blue-300 bg-blue-900/20' : 'text-textDim hover:bg-white/5'}`}>
          <IconSwap /><span className="text-[9px] font-bold">Swap</span>
        </button>
        <div className="w-px h-8 bg-white/10" />
        {/* Send */}
        <button onClick={sendScore} disabled={sending}
          title="Report score to Start.gg and close match"
          className="flex-1 flex flex-col items-center gap-0.5 py-2 px-1 text-statusGreen hover:bg-green-900/20 transition-colors disabled:opacity-40">
          <IconSend /><span className="text-[9px] font-bold">{sending ? '...' : 'Send'}</span>
        </button>
      </div>
    </div>
  );
}
