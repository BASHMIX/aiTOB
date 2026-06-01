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

// Start.gg ActivityState → local MatchStatus
// 1 = CREATED   (ready to run, not yet called) → waiting
// 2 = ACTIVE    (in progress)                  → live
// 3 = COMPLETED (done)                         → done
// 4 = READY     (reset / ready again)          → waiting
// 5 = INVALID   (bye / void)                   → done (filtered out visually)
// 6 = CALLED    (players summoned to station)  → called
// 7 = QUEUED    (queued, not yet called)        → waiting
function mapStartggState(state: unknown): MatchStatus {
  switch (Number(state)) {
    case 1: return 'waiting';  // CREATED
    case 2: return 'live';     // ACTIVE
    case 3: return 'done';     // COMPLETED
    case 4: return 'waiting';  // READY (reset)
    case 5: return 'done';     // INVALID (bye) — rendered as done, filtered in UI
    case 6: return 'called';   // CALLED
    case 7: return 'waiting';  // QUEUED
    default: return 'waiting';
  }
}

function mapLocalState(status: string): MatchStatus {
  switch (status) {
    case 'not_started': return 'waiting';
    case 'in_progress': return 'live';
    case 'called': return 'called';
    case 'conflict': return 'conflict';
    case 'complete':
    case 'done': return 'done';
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
  const { matches, currentSlug, tournaments, stations, setMatches, plannedStreamIds, setPlannedStreamIds } = useHubStore();
  const [sets, setSets] = useState<any[]>([]);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

  const [settingsModalOpen, setSettingsModalOpen] = useState(false);

  // ── Filter state ──
  const [hideTBD, setHideTBD] = useState(true);
  const [selectedPhaseGroup, setSelectedPhaseGroup] = useState<string>('__all__');

  const showToast = (msg: unknown, ok = true) => {
    const text = typeof msg === 'string' ? msg : JSON.stringify(msg);
    setToast({ msg: text, ok });
    setTimeout(() => setToast(null), 3000);
  };

  const reload = useCallback(async () => {
    if (!currentSlug) { setMatches([]); return; }
    try {
      const res = await axios.get('/api/active-matches');
      setMatches(res.data.matches ?? []);
    } catch (err: any) {
      console.error('Action failed:', err);
      const msg = err.response?.data?.detail || err.response?.data?.message || err.message || 'Action failed';
      showToast(msg, false);
    }
  }, [setMatches, currentSlug]);

  const loadSets = useCallback(async () => {
    if (!currentSlug) { setSets([]); return; }
    try {
      const res = await axios.get(`/api/tournaments/${currentSlug}/sets`);
      setSets(res.data.sets ?? []);
    } catch (e) { console.error('load sets', e); }
  }, [currentSlug]);

  const loadPlanned = useCallback(async () => {
    if (!currentSlug) { setPlannedStreamIds([]); return; }
    try {
      const res = await axios.get('/api/planned-streams', { params: { tournament_slug: currentSlug } });
      setPlannedStreamIds((res.data.planned || []).map((p: any) => String(p.set_id)));
    } catch (e) {
      console.error('load planned streams', e);
    }
  }, [currentSlug, setPlannedStreamIds]);

  // ── WebSocket Integration ──
  useHubSocket(useCallback((evt) => {
    if (evt.type === 'match_update') {
      loadSets();
      reload();
      loadPlanned();
    }
  }, [loadSets, reload, loadPlanned]));

  useEffect(() => {
    loadSets();
    reload();
    loadPlanned();
  }, [loadSets, reload, loadPlanned]);

  // ── Collect unique phaseGroups from sets ──
  const phaseGroups = useMemo(() => {
    const pgSet = new Set<string>();
    (sets ?? []).forEach(s => {
      const pg = s?.phaseGroup?.displayIdentifier;
      if (pg) pgSet.add(String(pg));
    });
    return Array.from(pgSet).sort();
  }, [sets]);

  // ── Build mapped matches ─────────────────────────────────────
  // Memoized so it rebuilds only when its inputs change; Start.gg sets are
  // de-duplicated against local matches via an O(1) Set lookup.
  const mappedMatches: MatchData[] = useMemo(() => {
    const result: MatchData[] = [];
    const localMatchIds = new Set((matches ?? []).map(m => safe(m?.set_id)));

  // Local matches first
  (matches ?? []).forEach(m => {
    if (!m || !m.set_id) return;

    // Skip if wrong tournament
    if (currentSlug && m.tournament_slug && m.tournament_slug !== currentSlug) return;

    result.push({
      id: safe(m.match_number) || shortId(m.set_id),
      pool: safe(m.phase_group),
      round: safe(m.round_name),
      status: mapLocalState(m.status),
      isLocal: true,
      isStreamMatch: plannedStreamIds.includes(m.set_id) || !!m.is_stream_match,
      startedAt: m.started_at,
      calledAt: m.called_at,
      autoDqDisarmed: !!m.auto_dq_disarmed,
      players: [
        {
          name: safe(m.p1_name) || 'Unknown',
          avatar: m.p1_avatar,
          score: m.p1_score != null ? Number(m.p1_score) : undefined,
          isTBD: isTBD(safe(m.p1_name)),
          hasDiscord: !!m.p1_discord,
        },
        {
          name: safe(m.p2_name) || 'Unknown',
          avatar: m.p2_avatar,
          score: m.p2_score != null ? Number(m.p2_score) : undefined,
          isTBD: isTBD(safe(m.p2_name)),
          hasDiscord: !!m.p2_discord,
        }
      ],
      raw: m,
      stationId: m.station_id,
    });
  });

  // Start.gg sets (not already local)
  (sets ?? []).forEach(s => {
    if (!s || !s.id) return;
    const sid = safe(s.id);
    if (localMatchIds.has(sid)) return;

    const mapped = mapStartggState(s.state);

    result.push({
      id: s.identifier || shortId(s.id),
      pool: safe(s.phaseGroup?.displayIdentifier),
      round: safe(s.fullRoundText || s.round),
      status: mapped,
      isLocal: false,
      isStreamMatch: plannedStreamIds.includes(s.id),
      players: [
        { name: safe(s.p1) || 'TBD', avatar: s.p1_avatar, score: undefined, isTBD: isTBD(safe(s.p1)) },
        { name: safe(s.p2) || 'TBD', avatar: s.p2_avatar, score: undefined, isTBD: isTBD(safe(s.p2)) }
      ],
      raw: s,
    });
  });

    return result;
  }, [matches, sets, currentSlug, plannedStreamIds]);

  // ── Action handlers ────────────────────────────────────────────────
  const handleAction = async (action: string, row: any, data?: any) => {
    try {
      // Resolve the actual set_id — for local matches use raw.set_id, for Start.gg-only use raw.id
      const setId: string = String(row.raw?.set_id || row.raw?.id || row.set_id || row.id || '');

      if (action === 'activate') {
        if (!setId) { showToast('Cannot activate: missing set ID', false); return; }
        await axios.post('/api/active-matches', {
          set_id: setId, p1_name: row.players[0].name, p2_name: row.players[1].name,
          p1_entrant_id: row.raw?.p1_eid || '', p2_entrant_id: row.raw?.p2_eid || '',
          p1_avatar: row.players[0].avatar || '', p2_avatar: row.players[1].avatar || '',
          round_name: row.round || '', tournament_slug: currentSlug || '',
          match_number: row.id,
          status: 'not_started', p1_score: 0, p2_score: 0,
          phase_group: row.pool || '',
        });
        showToast(`Activated: ${row.players[0].name} vs ${row.players[1].name}`);
        reload();
      }
      else if (action === 'updateScore') {
        const { playerIdx, value } = data;
        const key = playerIdx === 0 ? 'p1_score' : 'p2_score';
        await axios.patch(`/api/active-matches/${setId}`, { [key]: value });
        reload();
      }
      else if (action === 'sendScore') {
        const res = await axios.post(`/api/active-matches/${setId}/send`);
        if (res.data.error) showToast(res.data.message, false);
        else { showToast('Score reported to Start.gg ✓'); reload(); }
      }
      else if (action === 'callMatch') {
        if (!setId) { showToast('Cannot call match: missing set ID', false); return; }
        if (!row.isLocal) {
          // If not activated yet, activate it first
          await axios.post('/api/active-matches', {
            set_id: setId, p1_name: row.players[0].name, p2_name: row.players[1].name,
            p1_entrant_id: row.raw?.p1_eid || '', p2_entrant_id: row.raw?.p2_eid || '',
            p1_avatar: row.players[0].avatar || '', p2_avatar: row.players[1].avatar || '',
            round_name: row.round || '', tournament_slug: currentSlug || '',
            match_number: row.id,
            status: 'not_started', p1_score: 0, p2_score: 0,
            phase_group: row.pool || '',
          });
        }
        await axios.post(`/api/active-matches/${setId}/call`);
        showToast('Players called via Discord');
        reload();
      }
      else if (action === 'forceToInProgress') {
        if (!setId) { showToast('Cannot force: missing set ID', false); return; }
        const res = await axios.post(`/api/active-matches/${setId}/force-in-progress`);
        showToast(res.data.message || 'Forced to in-progress ✓');
        reload();
      }
      else if (action === 'resetMatch') {
        if (!confirm(`Reset match on Start.gg and locally?`)) return;
        const res = await axios.post(`/api/active-matches/${setId}/reset`);
        showToast(res.data.message || 'Reset OK');
        reload();
        loadSets();
      }
      else if (action === 'removeMatch') {
        if (!setId) { showToast('Cannot remove: missing set ID', false); return; }
        await axios.delete(`/api/active-matches/${setId}`);
        showToast('Match removed from active status');
        reload();
      }
      else if (action === 'dq') {
        if (!setId) { showToast('Cannot DQ: missing set ID', false); return; }
        // data contains 'p1', 'p2', or 'both'
        await axios.post(`/api/active-matches/${setId}/dq`, { player: data });
        reload();
      }
      else if (action === 'assignStation') {
        // Assigning a station to a called match elevates it to in_progress
        // server-side (stamps started_at + notifies the provider).
        await axios.patch(`/api/active-matches/${setId}`, { station_id: data });
        reload();
      }
    } catch (err: any) {
      if (err.response?.status === 401) {
        showToast('Session expired. Please login again.', false);
        useHubStore.getState().logout();
        window.location.href = '/login';
      }       else {
        const raw = err.response?.data?.detail || err.response?.data?.message || err.message || `${action} failed`;
        const msg = typeof raw === 'string' ? raw : typeof raw === 'object' && raw !== null ? JSON.stringify(raw) : String(raw);
        showToast(msg, false);
      }
    }
  };

  const handleToggleStream = async (setId: string, currentVal: boolean) => {
    const actualSetId = String(setId || '');
    if (!actualSetId) return;

    // Optimistic local update so the star flips instantly.
    const wasPlanned = plannedStreamIds.includes(actualSetId);
    setPlannedStreamIds(
      wasPlanned
        ? plannedStreamIds.filter(id => id !== actualSetId)
        : [...plannedStreamIds, actualSetId]
    );

    try {
      // Is this set already tracked as an active match? If so, also flip is_stream_match.
      const isLocal = matches?.some(m => String(m?.set_id) === actualSetId);

      if (wasPlanned) {
        // Unplan: remove the wishlist entry. Do NOT auto-toggle-stream-off on an
        // already-active match — the operator may still want it on stream for now.
        await axios.delete(`/api/planned-streams/${actualSetId}`);
        if (isLocal && currentVal) {
          await axios.post(`/api/active-matches/${actualSetId}/toggle-stream`, { is_stream_match: false });
        }
      } else {
        // Plan it. Backend also auto-promotes if it's already in active_matches.
        await axios.post('/api/planned-streams', {
          set_id: actualSetId,
          tournament_slug: currentSlug || '',
        });
        if (isLocal && !currentVal) {
          // Tag the live row too for immediate effect (stream queue assignment etc.).
          await axios.post(`/api/active-matches/${actualSetId}/toggle-stream`, { is_stream_match: true });
        }
      }
      reload();
    } catch (e) {
      console.error('Failed to persist planned-stream toggle', e);
      // Revert optimistic update on failure.
      setPlannedStreamIds(plannedStreamIds);
      showToast('Failed to update stream plan', false);
    }
  };

  // Get Settings for Current Tournament
  const curTourney = tournaments.find(t => t.name === currentSlug || t.slug === currentSlug); // Check slug first usually
  // Fallback to searching by slug or name since sometimes name is the identifier in URL
  const actualTourney = tournaments.find(t => t.slug === currentSlug) || curTourney;

  const autoDqEnabled = actualTourney?.auto_dq_enabled ?? true;
  const dqTimerSeconds = actualTourney?.dq_timer_seconds ?? 600;

  // ── Main Render ───────────────────────────────────────────────────────
  const filtered = hideTBD ? mappedMatches.filter(m => m.players.every(p => !p.isTBD)) : mappedMatches;
  const finalFiltered = selectedPhaseGroup !== '__all__' ? filtered.filter(r => (r.pool || '') === selectedPhaseGroup) : filtered;
  const sorted = sortTBDLast(finalFiltered);

  return (
    <div className="flex flex-col gap-4 relative p-1 flex-1 h-full overflow-hidden">
      {/* Toast */}
      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-2.5 rounded-lg shadow-2xl text-sm font-bold border
          ${toast.ok ? 'bg-green-950 border-green-600/50 text-green-200' : 'bg-red-950 border-red-600/50 text-red-200'}`}>
          {toast.msg}
        </div>
      )}

      {/* ── Controls / Filters Row ── */}
      <div className="flex flex-wrap items-center gap-3 text-xs bg-cardDark rounded-lg px-3 py-2 border border-white/10 shadow-sm">
        {/* Hide TBD */}
        <label className="flex items-center gap-1.5 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={hideTBD}
            onChange={e => setHideTBD(e.target.checked)}
            className="w-4 h-4 rounded border-white/20 bg-transparent accent-accentYellow"
          />
          <span className="text-textLight">Hide TBD</span>
        </label>

        <div className="w-px h-5 bg-white/10" />

        {/* PhaseGroup Filter */}
        <div className="flex items-center gap-2">
          <span className="text-textDim">Pool:</span>
          <select
            value={selectedPhaseGroup}
            onChange={e => setSelectedPhaseGroup(e.target.value)}
            className="bg-transparent border border-white/10 rounded px-2 py-1 text-xs text-textLight focus:outline-none focus:border-accentYellow/50"
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
          className="ml-auto flex items-center justify-center p-1.5 rounded-md hover:bg-white/10 text-textDim hover:text-white transition-colors"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
            <circle cx="12" cy="12" r="3"></circle>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
          </svg>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar pr-1">
        <MatchesList
          matches={sorted}
          dqTimerSeconds={dqTimerSeconds}
          autoDqEnabled={autoDqEnabled}
          onAction={handleAction}
          onToggleStream={handleToggleStream}
          stations={stations ?? []}
        />
      </div>

      {settingsModalOpen && (
        <MatchSettingsModal
          currentSlug={currentSlug || ''}
          initialAutoDqEnabled={autoDqEnabled}
          initialDqTimerSeconds={dqTimerSeconds}
          initialBotManageLimit={actualTourney?.bot_manage_limit}
          initialBotManageFinish={actualTourney?.bot_manage_finish}
          initialAutoDispatchEnabled={!!(actualTourney as any)?.auto_dispatch_enabled}
          initialAutoDispatchConcurrency={Number((actualTourney as any)?.auto_dispatch_concurrency ?? 1)}
          initialAutoDispatchStopAt={Number((actualTourney as any)?.auto_dispatch_stop_at ?? 8)}
          initialIgnoreActivityGuard={!!(actualTourney as any)?.ignore_activity_guard}
          phaseGroups={phaseGroups}
          onClose={() => setSettingsModalOpen(false)}
          onSave={() => {
            axios.get('/api/tournaments').then(r => useHubStore.getState().setTournaments(r.data.tournaments || []));
          }}
        />
      )}
    </div>
  );
}
