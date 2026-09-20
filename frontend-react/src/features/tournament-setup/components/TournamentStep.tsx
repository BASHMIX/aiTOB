import type { ProviderResolution } from '../types';

export function TournamentStep({ resolution, displayName, onDisplayNameChange }: { resolution?: ProviderResolution | null; displayName: string; onDisplayNameChange: (value: string) => void }) {
  const tournament = resolution?.tournament;
  const selected = resolution?.selected_scope;
  return <div className="space-y-5">
    <div><h2 id="setup-step-title" className="text-2xl font-semibold">Review tournament</h2><p className="mt-2 text-sm text-textDim">Provider facts are read-only. Local branding and operating defaults are safe overrides.</p></div>
    <div className="grid gap-3 sm:grid-cols-2">{[['Tournament', tournament?.name], ['Game', tournament?.game], ['State', tournament?.state], ['Exact scope', selected?.name || selected?.canonical_slug || selected?.external_id]].map(([label, value]) => <div key={label} className="rounded-lg border border-white/10 bg-black/10 p-4"><p className="text-[10px] uppercase text-textDim">{label}</p><p className="mt-1 text-sm font-semibold">{value || '—'}</p></div>)}</div>
    <label className="block text-xs text-textDim" htmlFor="local-display-name">Local display name<input id="local-display-name" value={displayName} onChange={(event) => onDisplayNameChange(event.target.value)} className="mt-1 w-full rounded-lg border border-white/10 bg-appDark px-3 py-2.5 text-sm text-white" /></label>
    <p className="rounded-lg border border-amber-300/20 bg-amber-300/5 px-3 py-2 text-xs text-amber-100">Start-in-wave is observed truthfully; remote provider changes are never implied.</p>
  </div>;
}
