import { useEffect, useState } from 'react';
import { ParticipantsTable } from './ParticipantsTable';
import { useHubStore } from '@/store/useHubStore';
import axios from 'axios';

export function TournamentSettings() {
  const { currentSlug, setCurrentSlug, tournaments, providerProfile, setProviderProfile } = useHubStore();
  const currentTournament = tournaments.find(t => t.slug === currentSlug);
  let tournamentMeta: any = {};
  try { tournamentMeta = currentTournament?.raw_data ? JSON.parse(currentTournament.raw_data) : {}; } catch { /* malformed legacy data */ }
  const startAt = tournamentMeta.starts_at;
  const remoteState = String(tournamentMeta.provider_state || '').toLowerCase();
  const [slugInput, setSlugInput] = useState('');
  const [providerType, setProviderType] = useState<'startgg' | 'challonge'>(() =>
    (sessionStorage.getItem('aitoB.importProvider') as 'startgg' | 'challonge') || 'startgg');
  const [useSubdomain, setUseSubdomain] = useState(false);
  const [subdomain, setSubdomain] = useState('');
  const [preview, setPreview] = useState<any>(null);
  const [providerUsage, setProviderUsage] = useState<{ used: number; limit: number | null; remaining: number | null } | null>(null);
  const [challongeConnection, setChallongeConnection] = useState<{ enabled: boolean; connected: boolean } | null>(null);

  useEffect(() => {
    let active = true;
    axios.get('/api/providers/challonge/connection')
      .then(res => { if (active) setChallongeConnection(res.data); })
      .catch(() => { if (active) setChallongeConnection(null); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!currentSlug) {
      setProviderProfile(null);
      return;
    }
    let active = true;
    axios.get(`/api/tournaments/${encodeURIComponent(currentSlug)}/provider-profile`)
      .then(res => { if (active) setProviderProfile(res.data); })
      .catch(() => { if (active) setProviderProfile(null); });
    return () => { active = false; };
  }, [currentSlug, setProviderProfile]);

  useEffect(() => {
    if (currentTournament?.provider_type !== 'challonge') {
      setProviderUsage(null);
      return;
    }
    axios.get('/api/providers/challonge/usage')
      .then(res => setProviderUsage(res.data))
      .catch(() => setProviderUsage(null));
  }, [currentTournament?.provider_type, currentSlug]);



  const addTournament = async () => {
    const slug = slugInput.trim();
    if (!slug) return;
    try {
      const res = await axios.post('/api/tournaments', providerType === 'challonge'
        ? { provider_type: 'challonge', identifier: slug, ...(useSubdomain && subdomain.trim() ? { subdomain: subdomain.trim() } : {}) }
        : { provider_type: 'startgg', slug });
      setSlugInput('');
      
      const tourneysRes = await axios.get('/api/tournaments');
      const updatedTournaments = tourneysRes.data.tournaments || [];
      useHubStore.getState().setTournaments(updatedTournaments);
      
      // Always switch to the new one
      const added = updatedTournaments.find((t: any) => t.slug === (preview?.provider_tournament_id ? `challonge:${preview.provider_tournament_id}` : slug));
      if (added) {
        setCurrentSlug(added.slug);
      } else if (updatedTournaments.length > 0) {
        setCurrentSlug(updatedTournaments[0].slug);
      }
      
      alert(res.data.message || "Tournament added.");
    } catch (e: any) {
      console.error(e);
      const detail = e?.response?.data?.message || e?.response?.data?.detail || e?.message;
      alert(`Failed to add tournament${detail ? `: ${detail}` : '.'}`);
    }
  };

  const changeProvider = (next: 'startgg' | 'challonge') => {
    setProviderType(next); sessionStorage.setItem('aitoB.importProvider', next); setPreview(null);
  };
  const resolveChallonge = async () => {
    if (!slugInput.trim()) return;
    try {
      const res = await axios.post('/api/providers/challonge/tournaments/resolve', {
        identifier: slugInput.trim(), ...(useSubdomain && subdomain.trim() ? { subdomain: subdomain.trim() } : {})
      });
      setPreview(res.data);
    } catch (e: any) { alert(e.response?.data?.message || e.response?.data?.detail || 'Could not resolve Challonge tournament.'); }
  };

  const deleteTournament = async () => {
    if (!currentSlug) return;
    if (!confirm(`Are you sure you want to delete the tournament '${currentSlug}'?`)) return;
    try {
      await axios.delete(`/api/tournaments/${encodeURIComponent(currentSlug)}`);
      
      const tourneysRes = await axios.get('/api/tournaments');
      const updatedTournaments = tourneysRes.data.tournaments || [];
      useHubStore.getState().setTournaments(updatedTournaments);
      
      if (updatedTournaments.length > 0) {
        setCurrentSlug(updatedTournaments[0].slug);
      } else {
        setCurrentSlug(null);
      }
      alert("Tournament removed.");
    } catch (e) {
      console.error(e);
      alert("Failed to remove tournament.");
    }
  };

  const resetHubData = async () => {
    if (!currentSlug) return;
    if (!confirm(`⚠️ FORCE RESET ⚠️\n\nThis will wipe ALL local match data for '${currentSlug}'.\nUse this ONLY if you reset the bracket on Start.gg and want to start fresh.\n\nContinue?`)) return;
    try {
      await axios.post(`/api/tournaments/${encodeURIComponent(currentSlug)}/reset-hub`);
      alert("Hub data reset. The dashboard will now fetch fresh data from Start.gg.");
      globalRefresh();
    } catch (e) {
      console.error(e);
      alert("Reset failed.");
    }
  };

  const globalRefresh = async () => {
    try {
      const [tourneysRes, matchesRes] = await Promise.all([
        axios.get('/api/tournaments'),
        axios.get('/api/active-matches')
      ]);
      useHubStore.getState().setTournaments(tourneysRes.data.tournaments || []);
      useHubStore.getState().setMatches(matchesRes.data.matches || []);
    } catch (e) {
      console.error(e);
      alert("Refresh failed.");
    }
  };

  const providerSyncLabel = currentTournament?.provider_last_synced_at
    ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(currentTournament.provider_last_synced_at))
    : 'Not synced yet';

  return (
    <div className="bg-cardDark rounded-lg p-4 shadow-md flex flex-col md:flex-row gap-6 border border-white/5">
      {/* Tournament Data Table */}
      <div className="flex-1 flex flex-col gap-3">
        <h2 className="text-accentYellow font-bold text-lg tracking-wide uppercase border-b border-white/10 pb-2">
          Tournament Data
        </h2>
        <div className="flex justify-between items-center bg-appDark p-2 rounded border border-white/10">
          <span className="text-sm font-mono truncate mr-2 text-textDim">
            {currentSlug ? `Active: ${currentTournament?.name || currentSlug} · ${providerProfile?.display_name || (currentTournament?.provider_type === 'challonge' ? 'Challonge' : 'Start.gg')}${currentTournament?.provider_sync_status === 'error' ? ' · Sync needs attention' : ''}` : 'No Tournament Selected'}
          </span>
          <div className="flex gap-2">
            <button 
              onClick={globalRefresh}
              className="bg-btnActive text-white text-xs px-3 py-1.5 rounded hover:bg-white/20 transition-colors flex items-center gap-1"
            >
              Refresh Hub
            </button>
            <button 
              onClick={async () => {
                if (!currentSlug) return;
                try {
                  const res = await axios.post(`/api/tournaments/${encodeURIComponent(currentSlug)}/refresh`);
                  alert(res.data.message);
                  globalRefresh();
                } catch (e: any) { alert(e?.response?.data?.message || e?.response?.data?.detail || "Refresh failed."); }
              }}
              className="bg-blue-900/50 text-blue-200 border border-blue-800 text-xs px-3 py-1.5 rounded hover:bg-blue-900 transition-colors flex items-center gap-1"
            >
              Refresh Metadata
            </button>
            <button 
              onClick={resetHubData}
              className="bg-orange-900/50 text-orange-200 border border-orange-800 text-xs px-3 py-1.5 rounded hover:bg-orange-900 transition-colors flex items-center gap-1"
            >
              Reset Hub Data
            </button>
            <button 
              onClick={deleteTournament}
              className="bg-red-900/50 text-red-200 border border-red-800 text-xs px-3 py-1.5 rounded hover:bg-red-900 transition-colors flex items-center gap-1"
            >
              Remove
            </button>
          </div>
        </div>
        {providerProfile && (
          <div className="rounded border border-white/10 bg-appDark/60 px-2 py-1.5 text-[10px] text-textDim flex flex-wrap gap-x-3 gap-y-1">
            <span className="font-semibold text-white/80">{providerProfile.display_name} · {providerProfile.contract_version.toUpperCase()}</span>
            {providerProfile.actions.map(action => (
              <span key={action.action} title={action.reason || undefined}>
                {action.action.replaceAll('_', ' ')}: {action.availability === 'remote' ? 'Provider-supported' : action.availability === 'local' ? 'Hub-local' : 'Unavailable'}
              </span>
            ))}
          </div>
        )}
        {currentTournament?.provider_type === 'challonge' && (
          <div className="rounded border border-blue-800/50 bg-blue-950/20 p-2 space-y-2 text-xs text-textDim">
            <div className="flex flex-wrap items-center gap-3">
              <span>Start: {startAt ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(startAt)) : 'Not scheduled'}</span>
              <span>State: {remoteState || 'unknown'}</span>
              <button disabled title="Provider lifecycle controls are not enabled in Phase 4." className="bg-statusGreen/20 border border-statusGreen/40 text-statusGreen px-3 py-1 rounded disabled:opacity-40 disabled:cursor-not-allowed">
                Start Tournament (coming later)
              </button>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button onClick={async () => {
                if (!currentSlug) return;
                try {
                  const res = await axios.post(`/api/tournaments/${encodeURIComponent(currentSlug)}/sync/bracket`);
                  alert(res.data.message);
                  await globalRefresh();
                  const usage = await axios.get('/api/providers/challonge/usage');
                  setProviderUsage(usage.data);
                } catch (e: any) { alert(e?.response?.data?.message || e?.response?.data?.detail || 'Bracket sync failed.'); }
              }} className="bg-blue-900/60 border border-blue-700 text-blue-100 px-2 py-1 rounded">
                Sync Bracket
              </button>
              <span className="text-[10px]">Last provider sync: {providerSyncLabel} · Data freshness: {currentTournament.provider_sync_status || 'stale'}</span>
              <label className="ml-auto flex items-center gap-1 text-[10px]">
                Mode
                <select value={currentTournament.challonge_sync_mode || 'economy'} onChange={async event => {
                  try {
                    await axios.patch(`/api/tournaments/${encodeURIComponent(currentSlug!)}/settings`, { challonge_sync_mode: event.target.value });
                    await globalRefresh();
                  } catch (e: any) { alert(e?.response?.data?.message || 'Could not change sync mode.'); }
                }} className="bg-appDark border border-white/10 rounded px-1 py-0.5 text-textDim">
                  <option value="economy">Economy</option>
                  <option value="live">Live (5 min)</option>
                </select>
              </label>
            </div>
            <label className="flex items-center gap-2 text-[10px]">
              <input type="checkbox" checked={currentTournament.economy_sync_on_stale_open !== 0} onChange={async event => {
                try {
                  await axios.patch(`/api/tournaments/${encodeURIComponent(currentSlug!)}/settings`, { economy_sync_on_stale_open: event.target.checked });
                  await globalRefresh();
                } catch (e: any) { alert(e?.response?.data?.message || 'Could not update Economy refresh policy.'); }
              }} />
              Economy: refresh once in background when a stale dashboard opens (no polling)
            </label>
            {providerUsage && <div className="text-[10px] text-blue-200">Tracked by this aiTOB build this month: {providerUsage.used} request(s). Challonge account-wide usage is shown in its Developer Portal.</div>}
          </div>
        )}
        <ParticipantsTable />
      </div>

      {/* Register Tournament */}
      <div className="md:w-1/3 flex flex-col gap-3 pl-0 md:pl-4 border-t md:border-t-0 md:border-l border-white/10 pt-4 md:pt-0">
        <h2 className="text-accentYellow font-bold text-lg tracking-wide uppercase border-b border-white/10 pb-2">
          Register Tournament
        </h2>
        <div className="flex gap-2" role="radiogroup" aria-label="Tournament provider">
          {(['startgg', 'challonge'] as const).map(p => <button key={p} role="radio" aria-checked={providerType === p}
            onClick={() => changeProvider(p)} className={`text-xs px-3 py-1.5 rounded border ${providerType === p ? 'bg-accentYellow text-black border-accentYellow' : 'border-white/20 text-textDim'}`}>
            {p === 'startgg' ? 'Start.gg' : 'Challonge'}
          </button>)}
        </div>
        <div className="text-sm mb-1 text-textDim">{providerType === 'startgg' ? 'Start.gg Tournament Slug or URL' : 'Challonge numeric ID, URL, or slug'}</div>
        {providerType === 'challonge' && <div className="text-xs text-textDim" role="status">
          {challongeConnection?.enabled
            ? challongeConnection.connected ? 'Challonge connected · identity preview is available.' : 'Challonge is enabled, but no account is connected.'
            : 'Challonge identity import is disabled for this Hub.'}
        </div>}
        <div className="flex gap-2">
          <input 
            className="w-full bg-appDark border border-white/10 rounded px-3 py-1.5 text-sm text-white focus:border-accentYellow focus:ring-1 focus:ring-accentYellow" 
            placeholder="e.g. tournament/slug" 
            type="text"
            value={slugInput}
            onChange={e => setSlugInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && addTournament()}
          />
          {providerType === 'challonge' && <button disabled={!challongeConnection?.enabled || !challongeConnection?.connected} onClick={resolveChallonge} className="bg-blue-900/50 text-blue-200 text-xs px-3 py-1.5 rounded disabled:opacity-40 disabled:cursor-not-allowed">Preview</button>}
          <button 
            onClick={addTournament}
            disabled={providerType === 'challonge' && (!challongeConnection?.enabled || !challongeConnection?.connected)}
            className="bg-btnActive text-white text-xs px-3 py-1.5 rounded hover:bg-white/20 transition-colors whitespace-nowrap disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Add
          </button>
        </div>
        {providerType === 'challonge' && <>
          <label className="text-xs text-textDim flex gap-2 items-center"><input type="checkbox" checked={useSubdomain} onChange={e => setUseSubdomain(e.target.checked)} /> Use subdomain/community (optional)</label>
          {useSubdomain && <input className="w-full bg-appDark border border-white/10 rounded px-3 py-1.5 text-sm text-white" placeholder="e.g. fnc-jo" value={subdomain} onChange={e => setSubdomain(e.target.value)} />}
          {preview && <div className="text-xs p-2 rounded bg-blue-900/20 border border-blue-800 text-blue-100">Resolved: <b>{preview.name}</b> · stable ID {preview.provider_tournament_id}{preview.subdomain ? ` · ${preview.subdomain}` : ''}</div>}
        </>}
      </div>
    </div>
  );
}
