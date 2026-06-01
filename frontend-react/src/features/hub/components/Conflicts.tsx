import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useHubSocket } from '@/hooks/useHubSocket';

interface Conflict {
  id: number;
  set_id: string;
  p1_claim?: string;
  p2_claim?: string;
  ai_summary?: string | null;
  p1_name?: string;
  p2_name?: string;
  p1_entrant_id?: string;
  p2_entrant_id?: string;
}

export function Conflicts() {
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [busyId, setBusyId] = useState<number | null>(null);

  const loadConflicts = useCallback(async () => {
    const res = await axios.get('/api/conflicts');
    setConflicts(res.data.conflicts || []);
  }, []);

  useEffect(() => {
    loadConflicts();
  }, [loadConflicts]);

  // Refresh when the AI investigation posts a summary (or any match update).
  useHubSocket(useCallback((evt: { type: string }) => {
    if (evt.type === 'match_update') loadConflicts();
  }, [loadConflicts]));

  // TO picks the winner → backend assigns a default 2-0, completes the set,
  // and reports the official result to start.gg.
  const chooseWinner = async (cf: Conflict, winnerId: string, winnerName: string) => {
    setBusyId(cf.id);
    try {
      await axios.post(`/api/conflicts/${cf.id}/resolve`, {
        winner_id: winnerId,
        resolution: `TO awarded the set to ${winnerName}`,
      });
      await loadConflicts();
    } catch (err: any) {
      alert(err.response?.data?.detail || err.message || 'Resolve failed');
    } finally {
      setBusyId(null);
    }
  };

  // Annotation-only: clears the alert without reporting a result.
  const dismiss = async (id: number) => {
    setBusyId(id);
    try {
      await axios.post(`/api/conflicts/${id}/resolve`, { resolution: 'dismissed' });
      await loadConflicts();
    } catch (err: any) {
      alert(err.response?.data?.detail || err.message || 'Dismiss failed');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="bg-cardDark rounded-lg shadow-md flex-1 flex flex-col border border-white/5">
      <div className="p-4 border-b border-white/10">
        <h2 className="text-accentYellow font-bold text-lg tracking-wide uppercase text-center">Conflicts & Alerts</h2>
      </div>
      <div className="p-4 flex-1 overflow-y-auto flex flex-col gap-4 text-sm">
        {conflicts.length === 0 ? (
          <div className="text-center p-5 text-textDim text-sm">No conflicts</div>
        ) : (
          conflicts.map((cf) => {
            const busy = busyId === cf.id;
            const p1Name = cf.p1_name || 'Player 1';
            const p2Name = cf.p2_name || 'Player 2';
            return (
              <div key={cf.id} className="bg-appDark border border-red-500/30 rounded p-3 text-white">
                <div className="font-bold text-red-400 mb-2">Match #{cf.set_id} — Conflict!</div>

                {/* AI investigation summary (or a waiting state) */}
                {cf.ai_summary ? (
                  <div className="mb-3 rounded border border-accentYellow/30 bg-accentYellow/5 p-2.5">
                    <div className="text-[10px] uppercase tracking-widest text-accentYellow/80 font-bold mb-1">🕵️ AI Summary</div>
                    <div className="text-xs text-textLight leading-relaxed">{cf.ai_summary}</div>
                  </div>
                ) : (
                  <div className="mb-3 text-xs text-textDim italic">
                    Awaiting player statements via Discord…
                    {(cf.p1_claim || cf.p2_claim) && (
                      <div className="mt-1 font-mono not-italic text-textLight/80">
                        {cf.p1_claim && <div>• {p1Name}: {cf.p1_claim}</div>}
                        {cf.p2_claim && <div>• {p2Name}: {cf.p2_claim}</div>}
                      </div>
                    )}
                  </div>
                )}

                {/* TO decision: pick the winner (backend reports a default 2-0). */}
                <div className="text-[10px] uppercase tracking-widest text-textDim font-bold mb-1.5">Choose Winner:</div>
                <div className="flex gap-2 mb-2">
                  <button
                    onClick={() => chooseWinner(cf, cf.p1_entrant_id || '', p1Name)}
                    disabled={busy || !cf.p1_entrant_id}
                    title={cf.p1_entrant_id ? `Award the set to ${p1Name}` : 'No start.gg entrant for this player'}
                    className="flex-1 bg-white/5 hover:bg-green-600/30 hover:border-green-500/50 border border-white/10 disabled:opacity-40 disabled:cursor-not-allowed px-2 py-2 rounded text-xs font-semibold truncate transition-colors"
                  >
                    {p1Name}
                  </button>
                  <button
                    onClick={() => chooseWinner(cf, cf.p2_entrant_id || '', p2Name)}
                    disabled={busy || !cf.p2_entrant_id}
                    title={cf.p2_entrant_id ? `Award the set to ${p2Name}` : 'No start.gg entrant for this player'}
                    className="flex-1 bg-white/5 hover:bg-green-600/30 hover:border-green-500/50 border border-white/10 disabled:opacity-40 disabled:cursor-not-allowed px-2 py-2 rounded text-xs font-semibold truncate transition-colors"
                  >
                    {p2Name}
                  </button>
                </div>

                <div className="flex justify-center">
                  <button
                    onClick={() => dismiss(cf.id)}
                    disabled={busy}
                    className="text-[11px] text-textDim hover:text-white disabled:opacity-40 underline underline-offset-2 transition-colors"
                  >
                    {busy ? 'Working…' : 'Dismiss without reporting'}
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
