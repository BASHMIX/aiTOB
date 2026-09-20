import { useMemo, useState } from 'react';
import type { IntegrationAccount, ProviderResolution, ProviderScope, ProviderType } from '../types';

export interface ProviderStepValue {
  provider_type?: ProviderType;
  provider_account_id?: string;
  locator?: string;
  challonge_subdomain?: string;
  selected_scope_id?: string;
  resolution?: ProviderResolution | null;
}

interface ProviderStepProps {
  value: ProviderStepValue;
  accounts: IntegrationAccount[];
  onChange: (value: ProviderStepValue) => void;
  onResolve?: (value: { providerAccountId: string; locator: string; subdomain?: string }) => void | Promise<void>;
  onSelectScope?: (externalScopeId: string) => void | Promise<void>;
  onConnect?: (provider: ProviderType) => void | Promise<void>;
  resolving?: boolean;
  error?: string | null;
}

const inputClass = 'mt-1 w-full rounded-lg border border-white/10 bg-appDark px-3 py-2.5 text-sm text-white outline-none transition focus:border-accentYellow/60';
const providerLabels: Record<ProviderType, string> = { startgg: 'Start.gg', challonge: 'Challonge' };

function displayFact(value: unknown): string | null {
  if (typeof value === 'string' && value.trim()) return value;
  if (value && typeof value === 'object' && 'value' in value) {
    const fact = value as { value?: unknown };
    return typeof fact.value === 'string' && fact.value.trim() ? fact.value : null;
  }
  return null;
}

function scopeTitle(scope: ProviderScope): string {
  return displayFact(scope.name) || scope.canonical_slug || scope.external_id;
}

export function ProviderStep({
  value,
  accounts,
  onChange,
  onResolve,
  onSelectScope,
  onConnect,
  resolving = false,
  error = null,
}: ProviderStepProps) {
  const [localError, setLocalError] = useState<string | null>(null);
  const provider = value.provider_type || 'startgg';
  const providerAccounts = useMemo(
    () => accounts.filter((account) => account.provider_type === provider && account.status !== 'disabled'),
    [accounts, provider],
  );
  const resolution = value.resolution;
  const scopes = resolution?.scopes || [];
  const selectedScope = value.selected_scope_id || resolution?.selected_scope?.external_id || '';

  const setProvider = (next: ProviderType) => {
    setLocalError(null);
    onChange({ ...value, provider_type: next, provider_account_id: '', locator: '', challonge_subdomain: '', resolution: null, selected_scope_id: '' });
  };

  const resolve = async () => {
    const accountId = value.provider_account_id?.trim();
    const locator = value.locator?.trim();
    if (!accountId) {
      setLocalError('Choose a connected provider account first.');
      return;
    }
    if (!locator) {
      setLocalError(provider === 'startgg' ? 'Enter an Event slug or tournament URL.' : 'Enter the Challonge tournament identifier.');
      return;
    }
    setLocalError(null);
    await onResolve?.({ providerAccountId: accountId, locator, subdomain: value.challonge_subdomain?.trim() || undefined });
  };

  return (
    <div className="space-y-6" data-testid="provider-step">
      <div>
        <h2 className="text-2xl font-semibold text-white">Connect a provider</h2>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-textDim">
          Choose one of your workspace connections, then enter the exact Event or bracket to import. The wizard never silently chooses the first Event.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {(Object.keys(providerLabels) as ProviderType[]).map((item) => {
          const active = provider === item;
          return (
            <button
              key={item}
              type="button"
              aria-pressed={active}
              onClick={() => setProvider(item)}
              className={`rounded-xl border p-4 text-left transition ${active ? 'border-accentYellow/60 bg-accentYellow/10' : 'border-white/10 bg-black/10 hover:border-white/25'}`}
            >
              <span className="flex items-center justify-between gap-3">
                <span className="font-semibold text-white">{providerLabels[item]}</span>
                <span className="text-lg" aria-hidden="true">{item === 'startgg' ? '◆' : '⌘'}</span>
              </span>
              <span className="mt-1 block text-xs text-textDim">{item === 'startgg' ? 'Select a specific Event slug or URL.' : 'Manage one exact Challonge bracket.'}</span>
            </button>
          );
        })}
      </div>

      <div className="rounded-xl border border-white/10 bg-black/10 p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-white">{providerLabels[provider]} connection</h3>
            <p className="mt-1 text-xs text-textDim">Credentials are managed once in Workspace integrations and are never copied into this draft.</p>
          </div>
          <button type="button" onClick={() => void onConnect?.(provider)} className="min-h-11 rounded-lg border border-accentYellow/40 px-3 py-2 text-xs font-bold text-accentYellow hover:bg-accentYellow/10">
            {providerAccounts.length ? `Sign in another ${providerLabels[provider]} account` : `Sign in with ${providerLabels[provider]}`}
          </button>
        </div>

        <label className="mt-4 block text-xs font-medium text-textDim" htmlFor="provider-account">Account</label>
        <select
          id="provider-account"
          value={value.provider_account_id || ''}
          onChange={(event) => onChange({ ...value, provider_account_id: event.target.value, resolution: null, selected_scope_id: '' })}
          className={inputClass}
        >
          <option value="">Choose a connected account</option>
          {providerAccounts.map((account) => (
            <option key={account.id} value={account.id}>
              {account.display_name} {account.configured ? '· ready' : '· credential required'}
            </option>
          ))}
        </select>
        {!providerAccounts.length && <p className="mt-2 text-xs text-amber-200">No active {providerLabels[provider]} connection is available yet.</p>}

        <div className="mt-4 grid gap-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
          <label className="block text-xs font-medium text-textDim" htmlFor="provider-locator">
            {provider === 'startgg' ? 'Event slug or tournament URL' : 'Tournament identifier or URL'}
            <input
              id="provider-locator"
              value={value.locator || ''}
              onChange={(event) => onChange({ ...value, locator: event.target.value, resolution: null, selected_scope_id: '' })}
              className={inputClass}
              placeholder={provider === 'startgg' ? 'event-slug or start.gg/... URL' : 'bracket-slug or challonge.com/... URL'}
              autoComplete="off"
            />
          </label>
          {provider === 'challonge' && (
            <label className="block text-xs font-medium text-textDim" htmlFor="challonge-subdomain">
              Subdomain <span className="font-normal">(optional)</span>
              <input
                id="challonge-subdomain"
                value={value.challonge_subdomain || ''}
                onChange={(event) => onChange({ ...value, challonge_subdomain: event.target.value, resolution: null, selected_scope_id: '' })}
                className={inputClass}
                placeholder="community"
              />
            </label>
          )}
          <button type="button" onClick={() => void resolve()} disabled={resolving} className="min-h-11 rounded-lg bg-accentYellow px-4 py-2.5 text-xs font-bold text-black transition hover:brightness-110 disabled:cursor-wait disabled:opacity-50">
            {resolving ? 'Looking up…' : 'Find event'}
          </button>
        </div>
      </div>

      {(localError || error) && <p role="alert" className="rounded-lg border border-statusRed/30 bg-statusRed/10 px-3 py-2 text-sm text-red-200">{localError || error}</p>}

      {resolution?.tournament && (
        <section className="rounded-xl border border-statusGreen/25 bg-statusGreen/5 p-4" aria-label="Provider result">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-[10px] font-mono uppercase tracking-wider text-statusGreen">Provider result</p>
              <h3 className="mt-1 text-lg font-semibold text-white">{displayFact(resolution.tournament.name) || resolution.tournament.canonical_slug || 'Tournament found'}</h3>
              <p className="mt-1 text-xs text-textDim">{displayFact(resolution.tournament.game) || 'Game not provided'}{displayFact(resolution.tournament.state) ? ` · ${displayFact(resolution.tournament.state)}` : ''}</p>
            </div>
            {resolution.provenance?.source && <span className="rounded-full border border-white/10 px-2 py-1 text-[10px] text-textDim">Source: {resolution.provenance.source}</span>}
          </div>
          {scopes.length > 1 && <p className="mt-4 rounded-lg border border-amber-300/20 bg-amber-300/5 px-3 py-2 text-xs text-amber-100">Choose the exact Event to continue. We will not select one automatically.</p>}
          {scopes.length > 0 && (
            <div className="mt-4 grid gap-2">
              {scopes.map((scope) => {
                const active = scope.external_id === selectedScope;
                return (
                  <button key={scope.external_id} type="button" aria-pressed={active} onClick={() => { onChange({ ...value, selected_scope_id: scope.external_id }); void onSelectScope?.(scope.external_id); }} className={`flex min-h-11 items-center justify-between rounded-lg border px-3 py-2 text-left transition ${active ? 'border-accentYellow/50 bg-accentYellow/10' : 'border-white/10 hover:border-white/25'}`}>
                    <span><span className="block text-sm font-medium text-white">{scopeTitle(scope)}</span><span className="block text-[11px] text-textDim">{scope.kind || 'Event'} · {scope.external_id}</span></span>
                    <span className="text-xs text-accentYellow">{active ? 'Selected' : 'Select'}</span>
                  </button>
                );
              })}
            </div>
          )}
          {!scopes.length && <p className="mt-3 text-xs text-amber-100">The provider returned no selectable Event or bracket scope.</p>}
        </section>
      )}
    </div>
  );
}
