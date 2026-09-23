import { useEffect, useState } from 'react';
import { AlertCircle, ArrowLeft, ChevronRight, Grid2X2, List, Plus, RefreshCw, Search, ShieldCheck, Trophy, Users, X } from 'lucide-react';
import type { CreateProfilePayload, PlayerProfile } from './types';
import { listPlayerProfiles, createPlayerProfile } from './api';
import { PLACEHOLDER_AVATAR } from './presentation';
import { countryCode, countryFlagUrl } from '@/utils/country';
import PlayerProfileDetail from './components/PlayerProfileDetail';

type ArchiveView = 'cards' | 'rows';
const CountryFlag = ({ country, className = '' }: { country?: string | null; className?: string }) => {
  const code = countryCode(country);
  const src = countryFlagUrl(country);
  if (!code || !src) return <span className={className}>—</span>;
  return <img src={src} alt={`${code} flag`} title={code} className={`h-4 w-6 rounded-[2px] border border-white/15 object-cover shadow-sm ${className}`} />;
};

export const PlayerArchivePage: React.FC = () => {
  const [profiles, setProfiles] = useState<PlayerProfile[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [view, setView] = useState<ArchiveView>('cards');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createForm, setCreateForm] = useState<CreateProfilePayload>({ display_name: '', prefix: '', country: '', avatar_url: '', discord_id: '' });
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const fetchProfiles = async (query = searchQuery) => {
    try {
      setLoading(true);
      setError(null);
      const list = await listPlayerProfiles({ query });
      setProfiles(list);
      setSelectedProfileId((current) => list.some((profile) => profile.id === current) ? current : (list[0]?.id || null));
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to fetch player profiles');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void fetchProfiles(); }, []);

  const handleCreateSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!createForm.display_name.trim()) return;
    try {
      setIsCreating(true);
      setCreateError(null);
      const created = await createPlayerProfile(createForm);
      setShowCreateModal(false);
      setCreateForm({ display_name: '', prefix: '', country: '', avatar_url: '', discord_id: '' });
      await fetchProfiles();
      setSelectedProfileId(created.id);
    } catch (err: any) {
      setCreateError(err?.response?.data?.detail || 'Failed to create profile');
    } finally {
      setIsCreating(false);
    }
  };

  return <main className="mx-auto max-w-[1500px] space-y-6 px-4 py-6 sm:px-6 lg:px-8" data-testid="player-archive-page">
    <section className="relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-[#172235] via-[#101722] to-[#080b10] p-5 shadow-2xl sm:p-7">
      <div className="pointer-events-none absolute -right-20 -top-24 h-72 w-72 rounded-full bg-accentYellow/10 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-24 left-1/3 h-56 w-56 rounded-full bg-sky-500/10 blur-3xl" />
      <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex items-start gap-4"><div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-accentYellow/35 bg-accentYellow/10 text-accentYellow shadow-[0_0_36px_rgba(251,191,36,.16)]"><Trophy className="h-7 w-7" /></div><div><p className="text-[10px] font-black uppercase tracking-[.24em] text-accentYellow">aiTOB Player Club</p><h1 className="mt-1 text-3xl font-black tracking-tight text-white sm:text-4xl">Player Archive</h1><p className="mt-2 max-w-2xl text-sm leading-relaxed text-textDim">بطاقات لاعب دائمة: الهوية، العلم، الصورة، الألعاب والشخصيات. اربطها مباشرة بمشتركي أي بطولة من الـHub.</p></div></div>
        <div className="flex flex-wrap gap-2"><a href="/admin/hub" className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-white/15 bg-black/20 px-4 text-xs font-bold text-white transition hover:bg-white/10"><ArrowLeft className="h-4 w-4" /> Back to aiTOB</a><button type="button" onClick={() => setShowCreateModal(true)} className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-accentYellow px-4 text-xs font-black text-black transition hover:bg-yellow-300" data-testid="create-profile-button"><Plus className="h-4 w-4" /> New Player Profile</button></div>
      </div>
      <div className="relative mt-6 grid max-w-xl grid-cols-3 gap-2 sm:gap-3"><div className="rounded-2xl border border-white/10 bg-black/20 px-3 py-3"><p className="text-[10px] font-bold uppercase tracking-wider text-textDim">Profiles</p><p className="mt-1 text-2xl font-black text-white">{profiles.length}</p></div><div className="rounded-2xl border border-white/10 bg-black/20 px-3 py-3"><p className="text-[10px] font-bold uppercase tracking-wider text-textDim">With Discord</p><p className="mt-1 text-2xl font-black text-white">{profiles.filter((p) => p.discord_id).length}</p></div><div className="rounded-2xl border border-white/10 bg-black/20 px-3 py-3"><p className="text-[10px] font-bold uppercase tracking-wider text-textDim">Ready to link</p><p className="mt-1 text-2xl font-black text-statusGreen">{profiles.length}</p></div></div>
    </section>

    <section className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(400px,.75fr)]"><div className="space-y-4"><div className="flex flex-col gap-3 rounded-2xl border border-white/10 bg-cardDark p-3 shadow-lg sm:flex-row sm:items-center sm:justify-between"><form onSubmit={(event) => { event.preventDefault(); void fetchProfiles(searchQuery); }} className="flex flex-1 gap-2"><label className="relative flex-1"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-textDim" /><input type="search" placeholder="Search player, team, country…" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} className="min-h-10 w-full rounded-xl border border-white/10 bg-appDark pl-9 pr-3 text-sm text-white outline-none focus:border-accentYellow/60" data-testid="search-profiles-input" /></label><button type="submit" className="rounded-xl border border-white/10 px-3 text-xs font-bold text-white hover:bg-white/10">Search</button><button type="button" onClick={() => { setSearchQuery(''); void fetchProfiles(''); }} className="rounded-xl border border-white/10 px-3 text-textDim hover:bg-white/10 hover:text-white" title="Refresh player archive"><RefreshCw className="h-4 w-4" /></button></form><div className="flex rounded-xl border border-white/10 bg-black/20 p-1" aria-label="Archive layout"><button type="button" onClick={() => setView('cards')} className={`rounded-lg p-2 ${view === 'cards' ? 'bg-accentYellow text-black' : 'text-textDim hover:text-white'}`} title="Card view"><Grid2X2 className="h-4 w-4" /></button><button type="button" onClick={() => setView('rows')} className={`rounded-lg p-2 ${view === 'rows' ? 'bg-accentYellow text-black' : 'text-textDim hover:text-white'}`} title="List view"><List className="h-4 w-4" /></button></div></div>
      {loading ? <div className="rounded-2xl border border-white/10 bg-cardDark p-12 text-center text-sm text-textDim">Loading player archive…</div> : error ? <div className="rounded-2xl border border-statusRed/30 bg-statusRed/10 p-4 text-sm text-statusRed">{error}</div> : profiles.length === 0 ? <div className="rounded-2xl border border-dashed border-white/15 bg-cardDark/60 p-16 text-center"><Users className="mx-auto h-10 w-10 text-textDim" /><h2 className="mt-3 font-bold text-white">No player profiles yet</h2><p className="mt-1 text-sm text-textDim">Create the first profile, then link it to a tournament entrant from Participants & Overrides.</p></div> : <div className={view === 'cards' ? 'grid gap-3 sm:grid-cols-2 2xl:grid-cols-3' : 'space-y-2'} data-testid="profiles-list">{profiles.map((profile) => { const selected = profile.id === selectedProfileId; return <button key={profile.id} type="button" onClick={() => setSelectedProfileId(profile.id)} className={`group w-full overflow-hidden border text-left transition ${view === 'cards' ? 'rounded-2xl' : 'rounded-xl'} ${selected ? 'border-accentYellow/70 bg-accentYellow/[.08] shadow-[0_0_24px_rgba(251,191,36,.1)]' : 'border-white/10 bg-cardDark hover:border-white/25 hover:bg-white/[.035]'}`} data-testid={`profile-item-${profile.id}`}><div className={`flex ${view === 'cards' ? 'min-h-40 flex-col justify-between p-4' : 'items-center gap-3 p-3'}`}><div className={view === 'cards' ? 'flex items-start justify-between' : 'contents'}><img src={profile.avatar_url || PLACEHOLDER_AVATAR} alt={profile.display_name} className={`${view === 'cards' ? 'h-16 w-16 rounded-2xl' : 'h-12 w-12 rounded-xl'} border border-white/15 bg-black/20 object-cover shadow-lg`} onError={(event) => { event.currentTarget.src = PLACEHOLDER_AVATAR; }} /><span className={`flex h-7 min-w-8 items-center justify-center rounded-full border border-white/10 bg-black/20 px-1.5 py-1 text-xs font-bold ${view === 'cards' ? '' : 'ml-auto'}`}><CountryFlag country={profile.country} /></span></div><div className={view === 'cards' ? '' : 'min-w-0 flex-1'}><div className="flex items-center gap-2"><span className="truncate text-base font-black text-white">{profile.display_name}</span>{profile.prefix && <span className="rounded bg-white/10 px-1.5 py-0.5 text-[10px] font-bold text-textDim">{profile.prefix}</span>}</div><p className="mt-1 truncate text-[11px] text-textDim">{profile.discord_id ? `Discord linked · ${profile.discord_id}` : 'Profile ready for tournament link'}</p></div>{view === 'cards' && <div className="mt-3 flex items-center justify-between border-t border-white/10 pt-3 text-[10px] font-bold uppercase tracking-wider text-textDim"><span>{profile.country ? 'Country registered' : 'No country'}</span><ChevronRight className="h-4 w-4 text-accentYellow" /></div>}</div></button>; })}</div>}</div>
      <aside className="xl:sticky xl:top-4">{selectedProfileId ? <PlayerProfileDetail key={selectedProfileId} profileId={selectedProfileId} onProfileUpdated={() => void fetchProfiles()} onProfileDeleted={() => void fetchProfiles()} /> : <div className="rounded-2xl border border-dashed border-white/15 bg-cardDark/60 p-12 text-center text-textDim"><ShieldCheck className="mx-auto h-10 w-10" /><p className="mt-3 text-sm">Select a player card to inspect and edit the profile.</p></div>}</aside></section>

    {showCreateModal && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm" data-testid="create-profile-modal"><div className="w-full max-w-md rounded-3xl border border-white/10 bg-[#111923] p-6 shadow-2xl"><div className="flex items-start justify-between border-b border-white/10 pb-4"><div><p className="text-[10px] font-black uppercase tracking-[.18em] text-accentYellow">Player Club</p><h2 className="mt-1 text-xl font-black text-white">New Player Profile</h2></div><button type="button" onClick={() => setShowCreateModal(false)} className="rounded-lg p-2 text-textDim hover:bg-white/10 hover:text-white"><X className="h-4 w-4" /></button></div>{createError && <p className="mt-4 flex items-center gap-2 rounded-xl border border-statusRed/30 bg-statusRed/10 p-3 text-xs text-statusRed"><AlertCircle className="h-4 w-4" />{createError}</p>}<form onSubmit={handleCreateSubmit} className="mt-5 space-y-4"><label className="block text-xs font-bold text-textDim">Display name *<input required data-testid="create-profile-name-input" value={createForm.display_name} onChange={(event) => setCreateForm({ ...createForm, display_name: event.target.value })} placeholder="e.g. FNC | BASHMIX" className="mt-1.5 min-h-10 w-full rounded-xl border border-white/10 bg-appDark px-3 text-sm text-white outline-none focus:border-accentYellow/60" /></label><div className="grid grid-cols-2 gap-3"><label className="block text-xs font-bold text-textDim">Team / Prefix<input value={createForm.prefix || ''} onChange={(event) => setCreateForm({ ...createForm, prefix: event.target.value })} className="mt-1.5 min-h-10 w-full rounded-xl border border-white/10 bg-appDark px-3 text-sm text-white outline-none focus:border-accentYellow/60" /></label><label className="block text-xs font-bold text-textDim">Country code<input maxLength={3} value={createForm.country || ''} onChange={(event) => setCreateForm({ ...createForm, country: event.target.value.toUpperCase() })} placeholder="JO" className="mt-1.5 min-h-10 w-full rounded-xl border border-white/10 bg-appDark px-3 text-sm text-white outline-none focus:border-accentYellow/60" /></label></div><label className="block text-xs font-bold text-textDim">Discord ID <span className="font-normal">(optional)</span><input value={createForm.discord_id || ''} onChange={(event) => setCreateForm({ ...createForm, discord_id: event.target.value })} className="mt-1.5 min-h-10 w-full rounded-xl border border-white/10 bg-appDark px-3 text-sm text-white outline-none focus:border-accentYellow/60" /></label><p className="rounded-xl border border-sky-300/20 bg-sky-300/5 p-3 text-xs text-sky-100">Save first, then use <strong>Upload Photo</strong> on the player card to add an image.</p><div className="flex justify-end gap-2 border-t border-white/10 pt-4"><button type="button" onClick={() => setShowCreateModal(false)} className="rounded-xl px-4 py-2 text-xs font-bold text-textDim hover:bg-white/10 hover:text-white">Cancel</button><button type="submit" data-testid="create-profile-submit" disabled={isCreating} className="rounded-xl bg-accentYellow px-4 py-2 text-xs font-black text-black disabled:opacity-50">{isCreating ? 'Creating…' : 'Create profile'}</button></div></form></div></div>}
  </main>;
};

export default PlayerArchivePage;
