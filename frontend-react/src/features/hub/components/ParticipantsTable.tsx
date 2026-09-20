import { useState, useEffect } from 'react';
import { useHubStore } from '@/store/useHubStore';
import axios from 'axios';
import { countryCode, countryFlagEmoji } from '@/utils/country';

interface CharacterOption {
  id: string;
  name: string;
  image_url?: string;
  images?: Array<{ url: string; type?: string }>;
}

interface ParticipantsTableProps {
  characters?: CharacterOption[];
  gameName?: string;
}

function flagForCountry(value: unknown): string {
  const raw = String(value || '').trim();
  if (!raw) return '—';
  return countryFlagEmoji(raw) || raw;
}

export function ParticipantsTable({ characters = [], gameName = '' }: ParticipantsTableProps) {
  const { tournaments, currentSlug, currentEventId, events } = useHubStore();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ name: '', prefix: '', country: '', cfn: '' });
  const [overrides, setOverrides] = useState<Record<string, any>>({});
  const [links, setLinks] = useState<Record<string, any>>({});
  const [players, setPlayers] = useState<any[]>([]);

  const normalizePlayerName = (value: string) => value
    .toLocaleLowerCase()
    .normalize('NFKC')
    .replace(/[\u064B-\u065F\u0670]/g, '')
    .replace(/[أإآ]/g, 'ا')
    .replace(/ى/g, 'ي')
    .replace(/[^\p{L}\p{N}]/gu, '');


  useEffect(() => {
    const fetchParticipantData = async () => {
      try {
        const [overridesResponse, playersResponse, linksResponse] = await Promise.all([
          axios.get('/api/players/overrides'),
          axios.get('/api/players'),
          currentSlug ? axios.get('/api/players/links', { params: { tournament_slug: currentSlug } }) : Promise.resolve({ data: { links: {} } }),
        ]);
        setOverrides(overridesResponse.data || {});
        setPlayers(playersResponse.data?.players || []);
        setLinks(linksResponse.data?.links || {});
      } catch (e) {
        console.error("Failed to fetch participant data", e);
      }
    };
    fetchParticipantData();
  }, [currentSlug]);

  const currentTournament = tournaments.find((t) => t.slug === currentSlug);

  if (!currentSlug) return <div className="text-center p-5 text-textDim text-sm">Select a tournament</div>;
  if (!currentTournament || !currentTournament.raw_data) return <div className="text-center p-5 text-textDim text-sm">No data</div>;
  // Multi-event tournaments must pick an event before attendees are shown (no cross-game mixing).
  if (events.length > 1 && !currentEventId) {
    return <div className="text-center p-5 text-textDim text-sm">Select an <span className="text-accentYellow font-bold">Event</span> above to view its attendees.</div>;
  }

  let entrants = [];
  try {
    const raw = JSON.parse(currentTournament.raw_data);
    if (raw.mock) {
      entrants = raw.entrants || [];
    } else {
      // Scope to the SELECTED event (not always the first) to avoid cross-game contamination.
      const evList = raw.events || raw.tournament?.events || [];
      const event = currentEventId
        ? (evList.find((ev: any) => String(ev.id) === String(currentEventId)) || {})
        : (evList[0] || {});
      entrants = event.entrants?.nodes || raw.entrants?.nodes || [];

      // If still empty but we have participants directly
      if (entrants.length === 0 && raw.participants) {
        entrants = raw.participants;
      }
    }
  } catch (e) {
    console.error("Parse error in ParticipantsTable", e);
    return <div className="text-center p-5 text-textDim text-sm">Error parsing tournament data. Try "Refresh Metadata" in settings.</div>;
  }

  if (entrants.length === 0) return <div className="text-center p-5 text-textDim text-sm">No participants found. Try "Refresh Metadata" in settings.</div>;

  const handleEditClick = async (entrant: any) => {
    setEditingId(entrant.id);
    try {
      const res = await axios.get(`/api/players/overrides/${entrant.id}`);
      const ov = res.data;
      setEditForm({
        name: ov.display_name || entrant.gamertag || entrant.name || '',
        prefix: ov.prefix || ov.team || entrant.prefix || entrant.team || '',
        country: ov.country || entrant.country || '',
        cfn: ov.cfn || entrant.cfn || ''
      });
    } catch (e) {
      setEditForm({
        name: entrant.gamertag || entrant.name || '',
        prefix: entrant.prefix || entrant.team || '',
        country: entrant.country || '',
        cfn: entrant.cfn || ''
      });
    }
  };

  const handleSave = async (id: string) => {
    const rawCountry = editForm.country.trim();
    const normalizedCountry = rawCountry ? countryCode(rawCountry) : '';
    if (rawCountry && !normalizedCountry) {
      alert('Enter a valid country code or English country name (for example: JO, UK, USA, Jordan).');
      return;
    }
    const normalizedForm = { ...editForm, country: normalizedCountry || '' };
    try {
      await axios.patch(`/api/players/overrides/${id}`, normalizedForm);
      setOverrides(prev => ({ ...prev, [id]: { ...prev[id], ...normalizedForm } }));
      setEditingId(null);
    } catch (e) {
      alert("Failed to save override");
    }
  };

  const handleCharacterChange = async (entrantId: string, character: CharacterOption | null) => {
    const previous = overrides[entrantId] || {};
    const next = {
      character: character?.name || '',
      character_id: character?.id || '',
      character_image_url: character?.image_url || character?.images?.[0]?.url || '',
    };
    setOverrides(prev => ({ ...prev, [entrantId]: { ...prev[entrantId], ...next } }));
    try {
      await axios.patch(`/api/players/overrides/${entrantId}`, {
        ...next,
        tournament_slug: currentSlug,
        event_id: currentEventId || currentTournament?.event_id || '',
      });
    } catch (e: any) {
      setOverrides(prev => ({ ...prev, [entrantId]: previous }));
      alert(e?.response?.data?.detail || 'Failed to save character selection');
    }
  };

  const handleAvatarUpload = async (id: string, file: File, discordId?: string) => {
    const formData = new FormData();
    formData.append('avatar', file);
    if (discordId) formData.append('discord_id', discordId);
    try {
      const res = await axios.post(`/api/players/overrides/${id}/avatar`, formData);
      const newUrl = res.data.avatar_url;
      setOverrides(prev => ({ ...prev, [id]: { ...prev[id], avatar_url: newUrl } }));
    } catch (e: any) {
      const msg = e.response?.data?.detail || e.response?.data?.message || "Failed to upload avatar";
      alert(msg);
    }
  };

  const handleLink = async (entrantId: string, discordId: string) => {
    if (!currentSlug || !discordId) return;
    try {
      const response = await axios.put('/api/players/links', {
        tournament_slug: currentSlug,
        entrant_id: String(entrantId),
        discord_id: discordId,
      });
      setLinks(prev => ({ ...prev, [String(entrantId)]: response.data.link }));
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Failed to link player');
    }
  };

  const handleUnlink = async (entrantId: string) => {
    if (!currentSlug) return;
    try {
      await axios.delete('/api/players/links', {
        params: { tournament_slug: currentSlug, entrant_id: String(entrantId) },
      });
      setLinks(prev => {
        const next = { ...prev };
        delete next[String(entrantId)];
        return next;
      });
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Failed to unlink player');
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
              <th className="px-2 py-2">Gamertag</th>
              <th className="px-2 py-2 min-w-36">Character</th>
              <th className="px-2 py-2">aiTOB Player</th>
              <th className="px-2 py-2">Avatar</th>
              <th className="px-2 py-2">Display Name</th>
              <th className="px-2 py-2">Prefix</th>
              <th className="px-2 py-2">Flag</th>
              <th className="px-2 py-2">CFN</th>
              <th className="px-2 py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {entrants.map((e: any, i: number) => {
              const ov = overrides[e.id] || {};
              const link = links[String(e.id)];
              const entrantName = typeof e === 'string' ? e : String(e.gamertag || e.name || '');
              const normalizedName = normalizePlayerName(entrantName);
              const startggCandidate = e.provider_user_id
                ? players.filter(player => String(player.startgg_id || '') === String(e.provider_user_id))
                : [];
              const nameCandidates = normalizedName
                ? players.filter(player => normalizePlayerName(String(player.gamer_tag || '')) === normalizedName)
                : [];
              const suggestedPlayer = startggCandidate.length === 1
                ? startggCandidate[0]
                : nameCandidates.length === 1 ? nameCandidates[0] : null;
              return (
                <tr key={e.id || i} className="border-b border-white/5 hover:bg-white/5">
                  <td className="px-2 py-2 text-textDim">{e.gamertag || e.name || e}</td>
                  <td className="px-2 py-2 min-w-36">
                    {characters.length > 0 ? (
                      <div className="flex items-center gap-2">
                        <select
                          value={ov.character || e.character || ''}
                          onChange={event => handleCharacterChange(String(e.id), characters.find(character => character.name === event.target.value) || null)}
                          className="w-36 bg-appDark border border-white/10 rounded px-2 py-1 text-xs text-white focus:border-accentYellow focus:ring-1 focus:ring-accentYellow"
                          aria-label={`Choose ${gameName || 'game'} character for ${entrantName}`}
                        >
                          <option value="">Not selected</option>
                          {characters.map(character => <option key={character.id} value={character.name}>{character.name}</option>)}
                        </select>
                        {ov.character_image_url && (
                          <img src={ov.character_image_url} alt="" className="h-6 w-6 rounded object-contain border border-white/10" />
                        )}
                      </div>
                    ) : (
                      <span className="text-textDim" title="No character catalog was returned for the selected event">—</span>
                    )}
                  </td>
                  <td className="px-2 py-2 min-w-48">
                    {link ? (
                      <div className="flex items-center gap-2">
                        <span className="text-statusGreen text-xs whitespace-nowrap">Linked to: <strong>{link.gamer_tag}</strong></span>
                        <button
                          onClick={() => handleUnlink(e.id)}
                          className="text-textDim hover:text-red-400 text-[10px] uppercase font-bold"
                        >
                          Unlink
                        </button>
                      </div>
                    ) : (
                      <div className="flex flex-col gap-1">
                        {suggestedPlayer && (
                          <button
                            onClick={() => handleLink(e.id, suggestedPlayer.discord_id)}
                            className="text-left text-[10px] text-accentYellow hover:text-yellow-300"
                            title="Exact safe match. Click to confirm the link."
                          >
                            Suggested: {suggestedPlayer.gamer_tag || suggestedPlayer.discord_id}
                          </button>
                        )}
                        <select
                          value=""
                          onChange={event => handleLink(e.id, event.target.value)}
                          className="max-w-44 bg-appDark border border-white/10 rounded px-1 py-1 text-[10px] text-textDim"
                          aria-label={`Link ${entrantName} to an aiTOB player`}
                        >
                          <option value="">Link to player…</option>
                          {players.map(player => (
                            <option key={player.discord_id} value={player.discord_id}>
                              {player.gamer_tag || player.discord_id}
                            </option>
                          ))}
                        </select>
                      </div>
                    )}
                  </td>
                  <td className="px-2 py-2">
                    <div className="relative group w-8 h-8">
                      <img 
                        src={ov.avatar_url || (e.participants?.[0]?.user?.images?.find((img: any) => img.type === 'profile')?.url) || '/static/player_placeholder.jpg'} 
                        className="w-8 h-8 rounded-full border border-white/10 object-cover" 
                      />
                      <label className="absolute inset-0 bg-black/50 hidden group-hover:flex items-center justify-center cursor-pointer rounded-full transition-opacity">
                        <span className="text-[10px] font-bold text-white">UP</span>
                        <input 
                          type="file" 
                          className="hidden" 
                          accept="image/*"
                           onChange={(ev) => ev.target.files?.[0] && handleAvatarUpload(e.id, ev.target.files[0], links[String(e.id)]?.discord_id)}
                        />
                      </label>
                    </div>
                  </td>
                  {editingId === e.id ? (
                    <>
                      <td className="px-2 py-1"><input className="w-full bg-appDark border border-white/10 rounded px-2 py-1 text-xs" value={editForm.name} onChange={ev => setEditForm({...editForm, name: ev.target.value})} placeholder="Display Name" /></td>
                      <td className="px-2 py-1"><input className="w-full bg-appDark border border-white/10 rounded px-2 py-1 text-xs" value={editForm.prefix} onChange={ev => setEditForm({...editForm, prefix: ev.target.value})} placeholder="Prefix" /></td>
                      <td className="px-2 py-1"><input className="w-full min-w-24 bg-appDark border border-white/10 rounded px-2 py-1 text-xs uppercase" value={editForm.country} onChange={ev => setEditForm({...editForm, country: ev.target.value})} placeholder="JO / UK / USA" title="ISO code or English country name" /></td>
                      <td className="px-2 py-1"><input className="w-full bg-appDark border border-white/10 rounded px-2 py-1 text-xs" value={editForm.cfn} onChange={ev => setEditForm({...editForm, cfn: ev.target.value})} placeholder="CFN" /></td>
                      <td className="px-2 py-1 flex gap-2">
                        <button onClick={() => handleSave(e.id)} className="text-statusGreen hover:text-green-400 text-xs font-bold">Save</button>
                        <button onClick={() => setEditingId(null)} className="text-textDim hover:text-white text-xs">Cancel</button>
                      </td>
                    </>
                  ) : (
                    <>
                      <td className="px-2 py-2 font-medium">{ov.name || e.display_name || e.gamertag || e.name || '—'}</td>
                      <td className="px-2 py-2">{ov.prefix || ov.team || e.prefix || e.team || '—'}</td>
                      <td className="px-2 py-2 uppercase" title={ov.country || e.country || undefined}>{flagForCountry(ov.country || e.country)}</td>
                      <td className="px-2 py-2">{ov.cfn || e.cfn || '—'}</td>
                      <td className="px-2 py-2">
                        <div className="flex gap-2">
                          <button onClick={() => handleEditClick(e)} className="text-accentYellow hover:text-yellow-400 text-xs font-bold">Edit</button>
                          {(ov.name || ov.prefix || ov.team || ov.country || ov.cfn || ov.character || ov.avatar_url) && (
                            <button 
                              onClick={async () => {
                                if (confirm(`Reset overrides for ${e.gamertag || e.name}?`)) {
                                  await axios.delete(`/api/players/overrides/${e.id}`);

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
