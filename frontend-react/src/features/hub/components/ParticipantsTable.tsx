import { useState, useEffect } from 'react';
import { useHubStore } from '@/store/useHubStore';
import axios from 'axios';

export function ParticipantsTable() {
  const { tournaments, currentSlug } = useHubStore();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ name: '', team: '', country: '', cfn: '' });
  const [overrides, setOverrides] = useState<Record<string, any>>({});

  useEffect(() => {
    const fetchAllOverrides = async () => {
      try {
        const res = await axios.get('/api/players/overrides');
        setOverrides(res.data || {});
      } catch (e) {
        console.error("Failed to fetch overrides", e);
      }
    };
    fetchAllOverrides();
  }, [currentSlug]);

  const currentTournament = tournaments.find((t) => t.slug === currentSlug);

  if (!currentSlug) return <div className="text-center p-5 text-textDim text-sm">Select a tournament</div>;
  if (!currentTournament || !currentTournament.raw_data) return <div className="text-center p-5 text-textDim text-sm">No data</div>;

  let entrants = [];
  try {
    const raw = JSON.parse(currentTournament.raw_data);
    entrants = raw.mock ? raw.entrants : raw.tournament?.events?.[0]?.entrants?.nodes || [];
  } catch (e) {
    return <div className="text-center p-5 text-textDim text-sm">Parse error</div>;
  }

  if (entrants.length === 0) return <div className="text-center p-5 text-textDim text-sm">No participants</div>;

  const handleEditClick = async (entrant: any) => {
    setEditingId(entrant.id);
    try {
      const res = await axios.get(`/api/players/override/${entrant.id}`);
      const ov = res.data;
      setEditForm({
        name: ov.display_name || entrant.name || '',
        team: ov.team || entrant.team || '',
        country: ov.country || entrant.country || '',
        cfn: ov.cfn || entrant.cfn || ''
      });
    } catch (e) {
      setEditForm({
        name: entrant.name || '',
        team: entrant.team || '',
        country: entrant.country || '',
        cfn: entrant.cfn || ''
      });
    }
  };

  const handleSave = async (id: string) => {
    try {
      await axios.patch(`/api/players/override/${id}`, editForm);
      setOverrides(prev => ({ ...prev, [id]: { ...prev[id], ...editForm } }));
      setEditingId(null);
    } catch (e) {
      alert("Failed to save override");
    }
  };

  const handleAvatarUpload = async (id: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await axios.post(`/api/players/avatar/${id}`, formData);
      const newUrl = res.data.avatar_url;
      setOverrides(prev => ({ ...prev, [id]: { ...prev[id], avatar_url: newUrl } }));
    } catch (e: any) {
      const msg = e.response?.data?.detail || "Failed to upload avatar";
      alert(msg);
    }
  };

  return (
    <div>
      <div className="border-b border-white/20 flex justify-between items-center mb-2">
        <div className="flex gap-4 text-sm font-medium text-textDim">
          <button className="pb-1 text-white border-b-2 border-accentYellow">Participants & Overrides</button>
        </div>
        <button 
          onClick={async () => {
            if (confirm("Reset ALL overrides? This cannot be undone.")) {
              await axios.delete('/api/players/overrides');
              setOverrides({});
            }
          }}
          className="text-[10px] bg-red-500/20 hover:bg-red-500/40 text-red-400 px-2 py-1 rounded border border-red-500/30 transition-colors uppercase font-bold"
        >
          Reset All Overrides
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm text-white">
          <thead className="text-xs text-textDim uppercase bg-appDark/50">
            <tr>
              <th className="px-2 py-2">Start.gg Name</th>
              <th className="px-2 py-2">Avatar</th>
              <th className="px-2 py-2">Display Name</th>
              <th className="px-2 py-2">Team</th>
              <th className="px-2 py-2">Flag</th>
              <th className="px-2 py-2">CFN</th>
              <th className="px-2 py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {entrants.map((e: any, i: number) => {
              const ov = overrides[e.id] || {};
              return (
                <tr key={e.id || i} className="border-b border-white/5 hover:bg-white/5">
                  <td className="px-2 py-2 text-textDim">{e.name || e}</td>
                  <td className="px-2 py-2">
                    <div className="relative group w-8 h-8">
                      <img 
                        src={ov.avatar_url || e.avatarUrl || '/static/player_placeholder.jpg'} 
                        className="w-8 h-8 rounded-full border border-white/10 object-cover" 
                      />
                      <label className="absolute inset-0 bg-black/50 hidden group-hover:flex items-center justify-center cursor-pointer rounded-full transition-opacity">
                        <span className="text-[10px] font-bold text-white">UP</span>
                        <input 
                          type="file" 
                          className="hidden" 
                          accept="image/*"
                          onChange={(ev) => ev.target.files?.[0] && handleAvatarUpload(e.id, ev.target.files[0])}
                        />
                      </label>
                    </div>
                  </td>
                  {editingId === e.id ? (
                    <>
                      <td className="px-2 py-1"><input className="w-full bg-appDark border border-white/10 rounded px-2 py-1 text-xs" value={editForm.name} onChange={ev => setEditForm({...editForm, name: ev.target.value})} placeholder="Display Name" /></td>
                      <td className="px-2 py-1"><input className="w-full bg-appDark border border-white/10 rounded px-2 py-1 text-xs" value={editForm.team} onChange={ev => setEditForm({...editForm, team: ev.target.value})} placeholder="Prefix" /></td>
                      <td className="px-2 py-1"><input className="w-full bg-appDark border border-white/10 rounded px-2 py-1 text-xs" value={editForm.country} onChange={ev => setEditForm({...editForm, country: ev.target.value})} placeholder="e.g. US" /></td>
                      <td className="px-2 py-1"><input className="w-full bg-appDark border border-white/10 rounded px-2 py-1 text-xs" value={editForm.cfn} onChange={ev => setEditForm({...editForm, cfn: ev.target.value})} placeholder="CFN" /></td>
                      <td className="px-2 py-1 flex gap-2">
                        <button onClick={() => handleSave(e.id)} className="text-statusGreen hover:text-green-400 text-xs font-bold">Save</button>
                        <button onClick={() => setEditingId(null)} className="text-textDim hover:text-white text-xs">Cancel</button>
                      </td>
                    </>
                  ) : (
                    <>
                      <td className="px-2 py-2 font-medium">{ov.name || e.displayName || e.name || '—'}</td>
                      <td className="px-2 py-2">{ov.team || e.team || '—'}</td>
                      <td className="px-2 py-2 uppercase">{ov.country || e.country || '—'}</td>
                      <td className="px-2 py-2">{ov.cfn || e.cfn || '—'}</td>
                      <td className="px-2 py-2">
                        <div className="flex gap-2">
                          <button onClick={() => handleEditClick(e)} className="text-accentYellow hover:text-yellow-400 text-xs font-bold">Edit</button>
                          {(ov.name || ov.team || ov.country || ov.cfn || ov.avatar_url) && (
                            <button 
                              onClick={async () => {
                                if (confirm(`Reset overrides for ${e.name}?`)) {
                                  await axios.delete(`/api/players/override/${e.id}`);
                                  setOverrides(prev => {
                                    const next = { ...prev };
                                    delete next[e.id];
                                    return next;
                                  });
                                }
                              }}
                              className="text-textDim hover:text-red-400 text-[10px] uppercase font-bold"
                            >
                              Reset
                            </button>
                          )}
                        </div>
                      </td>
                    </>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
