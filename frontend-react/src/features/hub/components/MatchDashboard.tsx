import { useEffect, useState, useCallback, useMemo } from 'react';
import { useHubStore } from '@/store/useHubStore';
import { useHubSocket } from '@/hooks/useHubSocket';
import axios from 'axios';
import { MatchesList } from './MatchesList';
import { MatchSettingsModal } from './MatchSettingsModal';
import type { MatchData, MatchStatus } from './MatchCard';

// ── Helpers ────────────────────────────────────────────────────────────
const safe = (val: unknown): string => (val != null ? String(val) : '');
const shortId = (val: unknown) => safe(val).substring(0, 8) || '—';
const isTBD = (name: string) => !name || name === 'TBD' || name === 'Unknown';

function mapStartggState(state: unknown): MatchStatus {
  switch (Number(state)) {
    case 1: case 4: return 'waiting'; // 4 is Reset
    case 2: return 'live';
    case 3: return 'done';
    case 6: return 'dq';
    default: return 'called';
  }
}

function mapLocalState(status: string): MatchStatus {
  switch (status) {
    case 'not_started': return 'waiting';
    case 'in_progress': return 'live';
    case 'called': return 'called';
    case 'complete': return 'done';
    case 'dq': return 'dq';
    default: return 'waiting';
  }
}

// ── TBD Sort: non-TBD first, TBD last ──────────────────────────────────
function sortTBDLast(rows: MatchData[]): MatchData[] {
  return [...rows].sort((a, b) => {
    const aHasTBD = a.players[0].isTBD || a.players[1].isTBD;
    const bHasTBD = b.players[0].isTBD || b.players[1].isTBD;
    if (aHasTBD === bHasTBD) return 0;
    return aHasTBD ? 1 : -1;
  });
}

// ── Main Component ─────────────────────────────────────────────────────
export function MatchDashboard() {
  const { matches, currentSlug, tournaments, stations, setMatches, plannedStreamIds, togglePlannedStream } = useHubStore();
  const [sets, setSets] = useState<any[]>([]);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);
  
  const [settingsModalOpen, setSettingsModalOpen] = useState(false);

  // ── Filter state ──
  const [hideTBD, setHideTBD] = useState(false);
  const [selectedPhaseGroup, setSelectedPhaseGroup] = useState<string>('__all__');

  const showToast = (msg: string, ok = true) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3000);
  };

  const reload = useCallback(async () => {
    try {
      const res = await axios.get('/api/active-matches');
      setMatches(res.data.matches ?? []);
    } catch (e) { console.error('reload matches', e); }
  }, [setMatches]);

  const loadSets = useCallback(async () => {
    if (!currentSlug) { setSets([]); return; }
    try {
      const res = await axios.get(`/api/tournaments/${currentSlug}/sets`);
      setSets(res.data.sets ?? []);
    } catch (e) { console.error('load sets', e); }
  }, [currentSlug]);

  // ── WebSocket Integration ──
  useHubSocket(useCallback((evt) => {
    if (evt.type === 'match_update') {
      loadSets();
      reload();
    }
  }, [loadSets, reload]));

  useEffect(() => {
    loadSets();
    reload();
  }, [loadSets, reload]);

  // ── Collect unique phaseGroups from sets ──
  const phaseGroups = useMemo(() => {
    const pgSet = new Set<string>();
    (sets ?? []).forEach(s => {
      if (s?.phaseGroup) pgSet.add(s.phaseGroup);
    });
    return Array.from(pgSet).sort();
  }, [sets]);

  // ── Build mapped matches ─────────────────────────────────────
  const mappedMatches: MatchData[] = [];

  // Local matches first
  (matches ?? []).forEach(m => {
    if (!m || !m.set_id) return;
    
    // Skip if wrong tournament
    if (currentSlug && m.tournament_slug && m.tournament_slug !== currentSlug) return;

    mappedMatches.push({
      id: safe(m.match_number) || shortId(m.set_id),
      pool: safe(m.phase_group),
      round: safe(m.round_name),
      status: mapLocalState(m.status),
      isLocal: true,
      isStreamMatch: plannedStreamIds.includes(m.set_id) || !!m.is_stream_match,
      startedAt: m.started_at,
      calledAt: m.called_at,
      players: [
        { name: safe(m.p1_name) || 'Unknown', score: m.p1_score != null ? Number(m.p1_score) : undefined, isTBD: isTBD(safe(m.p1_name)) },
        { name: safe(m.p2_name) || 'Unknown', score: m.p2_score != null ? Number(m.p2_score) : undefined, isTBD: isTBD(safe(m.p2_name)) }
      ],
      raw: m,
      stationId: m.station_id,
    });
  });

  // Start.gg sets (not already local)
  (sets ?? []).forEach(s => {
    if (!s || !s.id) return;
    const sid = safe(s.id);
    if (matches?.some(m => safe(m?.set_id) === sid)) return;
    
    const mapped = mapStartggState(s.state);
    
    // For Start.gg data, the score string is like "Player A 2 - Player B 1" or we can just parse it if needed.
    // For simplicity, we just use 0 if not complete.
    
    mappedMatches.push({
      id: s.identifier || shortId(s.id),
      pool: safe(s.phaseGroup),
      round: safe(s.round),
      status: mapped,
      isLocal: false,
      isStreamMatch: plannedStreamIds.includes(s.id),
      players: [
        { name: safe(s.p1) || 'TBD', score: undefined, isTBD: isTBD(safe(s.p1)) },
        { name: safe(s.p2) || 'TBD', score: undefined, isTBD: isTBD(safe(s.p2)) }
      ],
      raw: s,
    });
  });

  // ── Apply filters + sorting to each group ──
  let filtered = mappedMatches;
  if (hideTBD) {
    filtered = filtered.filter(r => !r.players[0].isTBD && !r.players[1].isTBD);
  }
  if (selectedPhaseGroup !== '__all__') {
    filtered = filtered.filter(r => (r.pool || '') === selectedPhaseGroup);
  }
  filtered = sortTBDLast(filtered);

  // ── Action handlers ────────────────────────────────────────────────
  const handleAction = async (action: string, row: any, data?: any) => {
    try {
      if (action === 'activate') {
        await axios.post('/api/active-matches', {
          set_id: row.id, p1_name: row.p1, p2_name: row.p2,
          p1_entrant_id: row.p1_eid || '', p2_entrant_id: row.p2_eid || '',
          round_name: row.round || '', tournament_slug: currentSlug || '',
          match_number: row.identifier,
          status: 'called', p1_score: 0, p2_score: 0,
          phase_group: row.phaseGroup || '',
        });
        showToast(`Activated: ${row.p1} vs ${row.p2}`);
        reload();
      } 
      else if (action === 'sendScore') {
        const res = await axios.post(`/api/active-matches/${row.set_id}/send`);
        if (res.data.error) showToast(res.data.message, false);
        else { showToast('Score reported to Start.gg ✓'); reload(); }
      } 
      else if (action === 'resetMatch') {
        if (!confirm(`Reset match on Start.gg and locally?`)) return;
        const res = await axios.post(`/api/active-matches/${row.set_id}/reset`);
        showToast(res.data.message || 'Reset OK');
        reload();
        loadSets();
      } 
      else if (action === 'dq') {
        // data contains 'p1', 'p2', or 'both'
        await axios.post(`/api/active-matches/${row.set_id}/dq`, { player: data });
        reload();
      } 
      else if (action === 'assignStation') {
        await axios.patch(`/api/active-matches/${row.set_id}`, {
          station_id: data,
          status: data ? 'in_progress' : 'called'
        });
        reload();
      }
    } catch {
      showToast(`${action} failed`, false);
    }
  };

  const handleToggleStream = async (setId: string, currentVal: boolean) => {
    togglePlannedStream(setId);
  };

  // Get Settings for Current Tournament
  const curTourney = tournaments.find(t => t.name === currentSlug || t.slug === currentSlug); // Check slug first usually
  // Fallback to searching by slug or name since sometimes name is the identifier in URL
  const actualTourney = tournaments.find(t => t.slug === currentSlug) || curTourney;
  
  const autoDqEnabled = actualTourney?.auto_dq_enabled ?? true;
  const dqTimerSeconds = actualTourney?.dq_timer_seconds ?? 600;

  if (!currentSlug) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-center border-2 border-dashed border-white/5 rounded-xl bg-white/[0.01]">
        <div className="w-16 h-16 rounded-full bg-accentYellow/5 flex items-center justify-center text-accentYellow/30 text-3xl mb-4">
          🏆
        </div>
        <h3 className="text-white font-bold text-lg">No Tournament Selected</h3>
        <p className="text-textDim text-sm max-w-xs mt-1 italic">
          Please select a tournament from the dropdown menu above to manage its matches.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 relative">
      {/* Toast */}
      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-2.5 rounded-lg shadow-2xl text-sm font-bold border
          ${toast.ok ? 'bg-green-950 border-green-600/50 text-green-200' : 'bg-red-950 border-red-600/50 text-red-200'}`}>
          {toast.msg}
        </div>
      )}

      {/* ── Controls / Filters Row ── */}
      <div className="flex flex-wrap items-center gap-3 text-xs bg-[var(--card)] rounded-lg px-3 py-2 border border-[var(--border)]">
        {/* Hide TBD */}
        <label className="flex items-center gap-1.5 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={hideTBD}
            onChange={e => setHideTBD(e.target.checked)}
            className="w-3.5 h-3.5 rounded border-[var(--border)] bg-transparent accent-[var(--primary)]"
          />
          <span className="text-[var(--muted-foreground)]">Hide TBD</span>
        </label>

        <div className="w-px h-5 bg-[var(--border)]" />

        {/* PhaseGroup Filter */}
        <div className="flex items-center gap-1.5">
          <span className="text-[var(--muted-foreground)]">Pool:</span>
          <select
            value={selectedPhaseGroup}
            onChange={e => setSelectedPhaseGroup(e.target.value)}
            className="bg-transparent border border-[var(--border)] rounded px-2 py-0.5 text-xs text-[var(--foreground)] focus:outline-none focus:border-[var(--primary)]"
          >
            <option value="__all__" className="text-black">All Pools</option>
            {phaseGroups.map(pg => (
              <option key={pg} value={pg} className="text-black">{pg}</option>
            ))}
          </select>
        </div>

        {/* Match Settings (Gear Icon) */}
        <button 
          onClick={() => setSettingsModalOpen(true)}
          title="Match Settings"
          className="ml-auto flex items-center justify-center p-1.5 rounded-md hover:bg-[var(--foreground)]/10 text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
            <circle cx="12" cy="12" r="3"></circle>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
          </svg>
        </button>
      </div>

      <MatchesList 
        matches={filtered}
        dqTimerSeconds={dqTimerSeconds}
        autoDqEnabled={autoDqEnabled}
        onAction={handleAction}
        onToggleStream={handleToggleStream}
        stations={stations ?? []}
      />

      {settingsModalOpen && (
        <MatchSettingsModal
          currentSlug={currentSlug}
          initialAutoDqEnabled={autoDqEnabled}
          initialDqTimerSeconds={dqTimerSeconds}
          onClose={() => setSettingsModalOpen(false)}
          onSave={() => {
            // Can reload tournaments from API if needed, 
            // but for now relying on backend to update. 
            // Let's trigger a full refresh to be safe or update local store.
            axios.get('/api/tournaments').then(r => useHubStore.getState().setTournaments(r.data.tournaments || []));
          }}
        />
      )}
    </div>
  );
}
