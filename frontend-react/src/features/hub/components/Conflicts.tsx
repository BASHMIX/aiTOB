import { useState, useEffect } from 'react';
import axios from 'axios';

export function Conflicts() {
  const [conflicts, setConflicts] = useState([]);

  const loadConflicts = async () => {
    const res = await axios.get('/api/conflicts');
    setConflicts(res.data.conflicts || []);
  };

  useEffect(() => {
    loadConflicts();
  }, []);

  const resolve = async (id: string, resolution: string) => {
    await axios.post(`/api/conflicts/${id}/resolve`, { resolution });
    loadConflicts();
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
          conflicts.map((cf: any) => (
            <div key={cf.id} className="bg-appDark border border-red-500/30 rounded p-3 text-white">
              <div className="font-bold text-red-400 mb-2">Match #{cf.set_id} - Conflict!</div>
              <div className="ml-4 font-mono text-xs mb-3 text-textLight">
                1-P1 claims: {cf.p1_claim || '—'}<br/>
                2-P2 claims: {cf.p2_claim || '—'}
              </div>
              <div className="flex gap-2 justify-center text-xs">
                <button onClick={() => resolve(cf.id, 'accept_p1')} className="bg-white/10 hover:bg-white/20 px-2 py-1 rounded transition-colors">Accept 1</button>
                <button onClick={() => resolve(cf.id, 'accept_p2')} className="bg-white/10 hover:bg-white/20 px-2 py-1 rounded transition-colors">Accept 2</button>
                <button onClick={() => resolve(cf.id, 'dismissed')} className="bg-btnActive hover:bg-white/20 px-2 py-1 rounded transition-colors">Dismiss</button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
