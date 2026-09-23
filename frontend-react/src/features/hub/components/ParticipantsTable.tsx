import { useState, useEffect } from 'react';
import { useHubStore } from '@/store/useHubStore';
import axios from 'axios';
import { countryCode, countryFlagUrl } from '@/utils/country';
import { resolveAvatarUrl } from '../../players/presentation';
import { EntrantPresentationEditor } from '../../players/EntrantPresentationEditor';
import { listPlayerProfiles } from '../../players/api';
import type { PlayerProfile } from '../../players/types';

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

function CountryFlag({ value }: { value: unknown }) {
  const code = countryCode(value);
  const src = countryFlagUrl(value);
  if (!code || !src) return <span>—</span>;
  return <img src={src} alt={`${code} flag`} title={code} className="h-4 w-6 rounded-[2px] border border-white/10 object-cover shadow-sm" />;
}

export function ParticipantsTable({ characters = [], gameName = '' }: ParticipantsTableProps) {
  const { tournaments, currentSlug, currentEventId, events } = useHubStore();
  const [editingEntrant, setEditingEntrant] = useState<any | null>(null);
  const [overrides, setOverrides] = useState<Record<string, any>>({});
  const [links, setLinks] = useState<Record<string, any>>({});
  const [profiles, setProfiles] = useState<PlayerProfile[]>([]);
  const currentTournament = tournaments.find((t) => t.slug === currentSlug);
  const effectiveEventId = currentEventId || currentTournament?.event_id || '';

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
        const [overridesResponse, profilesResponse, linksResponse] = await Promise.all([
          currentSlug && effectiveEventId
            ? axios.get('/api/players/overrides', { params: { tournament_slug: currentSlug, event_id: effectiveEventId } })
            : axios.get('/api/players/overrides'),
          listPlayerProfiles(),
          currentSlug ? axios.get('/api/players/links', { params: { tournament_slug: currentSlug, event_id: effectiveEventId || undefined } }) : Promise.resolve({ data: { links: {} } }),
        ]);
        setOverrides(overridesResponse.data || {});
        setProfiles(profilesResponse);
        setLinks(linksResponse.data?.links || {});
      } catch (e) {
        console.error("Failed to fetch participant data", e);
      }
    };
    fetchParticipantData();
  }, [currentSlug, effectiveEventId]);

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

  const handleEditClick = (entrant: any) => setEditingEntrant(entrant);

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
        event_id: effectiveEventId,
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
    formData.append('tournament_slug', currentSlug);
    formData.append('event_id', effectiveEventId);
    try {
      const res = await axios.post(`/api/players/overrides/${id}/avatar`, formData);
      const newUrl = res.data.avatar_url;
      setOverrides(prev => ({ ...prev, [id]: { ...prev[id], avatar_url: newUrl } }));
    } catch (e: any) {
      const msg = e.response?.data?.detail || e.response?.data?.message || "Failed to upload avatar";
      alert(msg);
    }
  };

  const handleLink = async (entrantId: string, playerProfileId: string) => {
    if (!currentSlug || !playerProfileId) return;
    try {
      const response = await axios.put('/api/players/links', {
        tournament_slug: currentSlug,
        entrant_id: String(entrantId),
        player_profile_id: playerProfileId,
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
            if (confirm("Reset all overrides for this event? This cannot be undone.")) {
              await axios.delete('/api/players/overrides', {
                params: { tournament_slug: currentSlug, event_id: effectiveEventId },
              });
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
              <th className="px-2 py-2">Player Profile</th>
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
              const nameCandidates = normalizedName
                ? profiles.filter(profile => normalizePlayerName(String(profile.display_name || '')) === normalizedName)
                : [];
              const suggestedProfile = nameCandidates.length === 1 ? nameCandidates[0] : null;
              return (
                <tr key={e.id || i} className="border-b border-white/5 hover:bg-white/5">
                  <td className="px-2 py-2 text-textDim">{e.gamertag || e.name || e}</td>
                  <td className="px-2 py-2 min-w-36">
                    {characters.length > 0 ? (
                      <div className="flex items-center gap-2">
                        <select
                          value={ov.character || ov.character_name || link?.default_character_name || e.character || ''}
                          onChange={event => handleCharacterChange(String(e.id), characters.find(character => character.name === event.target.value) || null)}
                          className="w-36 bg-appDark border border-white/10 rounded px-2 py-1 text-xs text-white focus:border-accentYellow focus:ring-1 focus:ring-accentYellow"
                          aria-label={`Choose ${gameName || 'game'} character for ${entrantName}`}
                        >
                          <option value="">Not selected</option>
                          {characters.map(character => <option key={character.id} value={character.name}>{character.name}</option>)}
                        </select>
                        {(ov.character_image_url || link?.default_character_image_url) && (
                          <img src={ov.character_image_url || link?.default_character_image_url} alt={ov.character || ov.character_name || link?.default_character_name || 'Character'} className="h-6 w-6 rounded object-contain border border-white/10" />
                        )}
                      </div>
                    ) : (
                      <span className="text-textDim" title="No character catalog was returned for the selected event">—</span>
                    )}
                  </td>
                  <td className="px-2 py-2 min-w-48">
                    {link ? (
                      <div className="flex items-center gap-2">
                        <span className="text-statusGreen text-xs whitespace-nowrap">Linked to: <strong>{link.display_name || link.gamer_tag || 'Player profile'}</strong></span>
                        <button
                          onClick={() => handleUnlink(e.id)}
                          className="text-textDim hover:text-red-400 text-[10px] uppercase font-bold"
                        >
                          Unlink
                        </button>
                      </div>
                    ) : (
                      <div className="flex flex-col gap-1">
                        {suggestedProfile && (
                          <button
                            onClick={() => handleLink(e.id, suggestedProfile.id)}
                            className="text-left text-[10px] text-accentYellow hover:text-yellow-300"
                            title="Exact safe match. Click to confirm the link."
                          >
                            Suggested: {suggestedProfile.display_name}
                          </button>
                        )}
                        <select
                          value=""
                          onChange={event => handleLink(e.id, event.target.value)}
                          className="max-w-44 bg-appDark border border-white/10 rounded px-1 py-1 text-[10px] text-textDim"
                          aria-label={`Link ${entrantName} to a player profile`}
                        >
                          <option value="">Link profile…</option>
                          {profiles.map(profile => (
                            <option key={profile.id} value={profile.id}>
                              {profile.prefix ? `${profile.prefix} | ` : ''}{profile.display_name}{profile.country ? ` · ${profile.country}` : ''}
                            </option>
                          ))}
                        </select>
                      </div>
                    )}
                  </td>
                  <td className="px-2 py-2">
                    <div className="relative group w-8 h-8">
                      <img 
                        src={resolveAvatarUrl(
                          ov.avatar_url,
                          link?.avatar_url || link?.avatar_path,
                          e.participants?.[0]?.user?.images?.find((img: any) => img.type === 'profile')?.url || e.participants?.[0]?.user?.images?.[0]?.url
                        )}
                        alt={e.gamertag || e.name || 'avatar'}
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
                  <>
                      <td className="px-2 py-2 font-medium">{ov.name || ov.display_name || link?.display_name || link?.gamer_tag || e.display_name || e.gamertag || e.name || '—'}</td>
                      <td className="px-2 py-2">{ov.prefix || ov.team || link?.prefix || link?.team || e.prefix || e.team || '—'}</td>
                      <td className="px-2 py-2"><CountryFlag value={ov.country || link?.country || e.country} /></td>
                      <td className="px-2 py-2">{ov.cfn || link?.cfn_id || e.cfn || '—'}</td>
                      <td className="px-2 py-2">
                        <div className="flex gap-2">
                          <button onClick={() => handleEditClick(e)} className="text-accentYellow hover:text-yellow-400 text-xs font-bold">Edit</button>
                          {(ov.name || ov.display_name || ov.prefix || ov.team || ov.country || ov.cfn || ov.character || ov.character_name || ov.avatar_url) && (
                            <button 
                              onClick={async () => {
                                if (confirm(`Reset overrides for ${e.gamertag || e.name}?`)) {
                                  await axios.delete(`/api/players/overrides/${e.id}`, {
                                    params: { tournament_slug: currentSlug, event_id: effectiveEventId },
                                  });

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
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {editingEntrant && (
        <EntrantPresentationEditor
          entrant={editingEntrant}
          currentSlug={currentSlug}
          currentEventId={effectiveEventId || undefined}
          link={links[String(editingEntrant.id)]}
          override={overrides[String(editingEntrant.id)]}
          characters={characters}
          gameName={gameName}
          onSave={(saved) => {
            setOverrides(prev => ({ ...prev, [String(editingEntrant.id)]: saved }));
            setEditingEntrant(null);
          }}
          onReset={() => {
            setOverrides(prev => {
              const next = { ...prev };
              delete next[String(editingEntrant.id)];
              return next;
            });
            setEditingEntrant(null);
          }}
          onClose={() => setEditingEntrant(null)}
        />
      )}
    </div>
  );
}
