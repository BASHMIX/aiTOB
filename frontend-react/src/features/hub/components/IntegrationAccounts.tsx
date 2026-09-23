import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import startGgLogo from '@/assets/Start.gg.svg';

type AccountProviderType = 'discord' | 'challonge' | 'startgg';
type ProviderType = AccountProviderType;
type ProviderMeta = { label: string; icon: string; credential: string; identity: string; destination: string };
type Account = {
  id: string;
  provider_type: AccountProviderType;
  display_name: string;
  external_account_id: string;
  status: string;
  configured: boolean;
  credential_types: string[];
  destinations: { destination_type: string; display_name: string; configured: boolean; status?: string }[];
};

const providerMeta: Record<ProviderType, ProviderMeta> = {
  discord: { label: 'Discord', icon: '✦', credential: 'Bot token', identity: 'Application or bot ID', destination: 'No match-call channel configured' },
  challonge: { label: 'Challonge', icon: '⌘', credential: 'API key or account token', identity: 'Challonge account ID', destination: 'Tournament destinations are selected per tournament' },
  startgg: { label: 'Start.gg', icon: '◆', credential: 'API token', identity: 'Shared provider credential', destination: 'Configured above as a shared provider connection' },
};

// Integration records are durable configuration.  A value written by an
// older build or a future provider must not be able to take down the entire
// Connections workspace merely because it lacks a display definition here.
function getProviderMeta(provider: string | null | undefined): ProviderMeta {
  const known = providerMeta[provider as ProviderType];
  if (known) return known;
  const label = String(provider || 'Unknown provider');
  return {
    label,
    icon: '?',
    credential: 'credential',
    identity: 'Account identity',
    destination: 'No destination details available for this provider',
  };
}

function StatusPill({ configured, status }: { configured: boolean; status: string }) {
  const ready = configured && status === 'active';
  const tone = ready ? 'border-statusGreen/30 bg-statusGreen/10 text-statusGreen' : status === 'disabled' ? 'border-white/10 bg-white/5 text-textDim' : 'border-amber-400/30 bg-amber-400/10 text-amber-200';
  return <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${tone}`}>{ready ? 'Ready' : status === 'disabled' ? 'Disabled' : 'Needs setup'}</span>;
}

export function IntegrationAccounts() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [startggConfigured, setStartggConfigured] = useState(false);
  const [startggToken, setStartggToken] = useState('');
  const [startggClientId, setStartggClientId] = useState('');
  const [startggClientSecret, setStartggClientSecret] = useState('');
  const [startggClientConfigured, setStartggClientConfigured] = useState(false);
  const [startggTest, setStartggTest] = useState<string | null>(null);
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null);
  const [providerFilter, setProviderFilter] = useState<'all' | ProviderType>('all');
  const [draft, setDraft] = useState<{ provider_type: AccountProviderType; external_account_id: string; display_name: string }>({ provider_type: 'discord', external_account_id: '', display_name: '' });
  const [secrets, setSecrets] = useState<Record<string, string>>({});
  const [destinationDrafts, setDestinationDrafts] = useState<Record<string, { external_id: string; display_name: string }>>({});
  const [busy, setBusy] = useState<string | null>(null);

  const signInProvider = async (provider: 'startgg' | 'challonge') => {
    setBusy(`oauth:${provider}`);
    setMessage(null);
    try {
      const response = await axios.post(`/api/auth/providers/${provider}/connect`, { return_step: 'provider' });
      window.location.assign(response.data.authorization_url);
    } catch (error: any) {
      setMessage({ text: error.response?.data?.detail || `Could not start ${provider} sign-in.`, ok: false });
      setBusy(null);
    }
  };

  const load = async () => {
    try {
      const [accountsResponse, environmentResponse] = await Promise.all([
        axios.get('/api/integrations'),
        axios.get('/api/env'),
      ]);
      setAccounts(accountsResponse.data.accounts || []);
      // The connection endpoint deliberately returns a configured marker, not
      // the token. Keep this page write-only for credentials.
      setStartggConfigured(Boolean(environmentResponse.data?.STARTGG_API_TOKEN));
      setStartggClientId(environmentResponse.data?.STARTGG_CLIENT_ID || '');
      setStartggClientConfigured(Boolean(environmentResponse.data?.STARTGG_CLIENT_SECRET));
    } catch {
      setMessage({ text: 'Could not load integration accounts.', ok: false });
    }
  };
  useEffect(() => { void load(); }, []);

  const filteredAccounts = useMemo(() => accounts.filter((account) => providerFilter === 'all' || account.provider_type === providerFilter), [accounts, providerFilter]);
  const showStartgg = providerFilter === 'all' || providerFilter === 'startgg';
  const showAccountControls = true;
  const showMessage = (text: string, ok = true) => setMessage({ text, ok });

  const create = async () => {
    if (!draft.external_account_id.trim() || !draft.display_name.trim()) {
      showMessage('Enter a display name and account identity first.', false);
      return;
    }
    setBusy('create');
    try {
      await axios.post('/api/integrations', draft);
      setDraft({ provider_type: 'discord', external_account_id: '', display_name: '' });
      showMessage('Account created. Add its encrypted credential below.');
      await load();
    } catch (error: any) {
      showMessage(error.response?.data?.detail || 'Could not create account.', false);
    } finally {
      setBusy(null);
    }
  };

  const rotate = async (account: Account) => {
    const secret = secrets[account.id] || '';
    if (!secret) {
      showMessage(`Enter a ${getProviderMeta(account.provider_type).credential.toLowerCase()} first.`, false);
      return;
    }
    setBusy(`credential:${account.id}`);
    const secret_type = account.provider_type === 'discord' ? 'bot_token' : account.provider_type === 'startgg' ? 'access_token' : 'api_key';
    try {
      await axios.post(`/api/integrations/${account.id}/credentials`, { secret_type, secret });
      setSecrets((current) => ({ ...current, [account.id]: '' }));
      showMessage('Credential encrypted and saved. It is never returned to this page.');
      await load();
    } catch (error: any) {
      showMessage(error.response?.data?.detail || 'Credential update failed.', false);
    } finally {
      setBusy(null);
    }
  };

  const addDestination = async (account: Account) => {
    const destination = destinationDrafts[account.id] || { external_id: '', display_name: '' };
    if (!destination.external_id.trim()) {
      showMessage('Enter a channel ID before saving the destination.', false);
      return;
    }
    setBusy(`destination:${account.id}`);
    try {
      await axios.post(`/api/integrations/${account.id}/destinations`, {
        destination_type: 'match_call_channel',
        external_id: destination.external_id.trim(),
        display_name: destination.display_name.trim() || 'Match calls',
      });
      setDestinationDrafts((current) => ({ ...current, [account.id]: { external_id: '', display_name: '' } }));
      showMessage('Discord destination saved to this account.');
      await load();
    } catch (error: any) {
      showMessage(error.response?.data?.detail || 'Could not save destination.', false);
    } finally {
      setBusy(null);
    }
  };

  const saveStartggToken = async () => {
    const payload: Record<string, string> = {};
    if (startggToken.trim()) payload.STARTGG_API_TOKEN = startggToken.trim();
    if (startggClientId.trim()) payload.STARTGG_CLIENT_ID = startggClientId.trim();
    if (startggClientSecret.trim()) payload.STARTGG_CLIENT_SECRET = startggClientSecret.trim();
    if (!Object.keys(payload).length) {
      showMessage('Enter a Start.gg API token or OAuth application value before saving.', false);
      return;
    }
    setBusy('startgg:save');
    setStartggTest(null);
    try {
      await axios.patch('/api/env', payload);
      setStartggToken('');
      setStartggClientSecret('');
      if (payload.STARTGG_API_TOKEN) setStartggConfigured(true);
      if (payload.STARTGG_CLIENT_SECRET) setStartggClientConfigured(true);
      showMessage('Start.gg settings saved server-side. Secrets are never returned to this page.');
    } catch (error: any) {
      showMessage(error.response?.data?.detail || 'Could not save the Start.gg token.', false);
    } finally {
      setBusy(null);
    }
  };

  const testStartggConnection = async () => {
    setBusy('startgg:test');
    setStartggTest(null);
    try {
      const response = await axios.post('/api/settings/token-check');
      const result = response.data || {};
      if (result.valid && result.has_write_scope) {
        setStartggTest('Connected — the token has tournament-organizer write access.');
      } else if (result.valid) {
        setStartggTest('Connected — the token is valid, but tournament-organizer write access is missing.');
      } else {
        setStartggTest('Start.gg could not verify this token. Check the account permissions and try again.');
      }
    } catch {
      setStartggTest('Start.gg could not be reached for a token check.');
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-5 animate-fadeIn">
      <section className="rounded-xl border border-white/10 bg-cardDark p-4 shadow-sm sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-base font-bold text-white">Integration accounts</h2>
            <p className="mt-1 max-w-2xl text-xs leading-relaxed text-textDim">Each provider account owns its credentials and destinations. Secrets are encrypted server-side and never returned to the browser.</p>
          </div>
          <div className="flex rounded-lg border border-white/10 bg-black/20 p-1 text-xs font-bold">
            {(['all', 'discord', 'challonge', 'startgg'] as const).map((provider) => <button key={provider} type="button" onClick={() => setProviderFilter(provider)} className={`rounded-md px-2.5 py-1.5 transition-colors ${providerFilter === provider ? 'bg-accentYellow text-black' : 'text-textDim hover:text-white'}`}>{provider === 'all' ? 'All' : providerMeta[provider].label}</button>)}
          </div>
        </div>
        {message && <p role="status" className={`mt-4 rounded-lg border px-3 py-2 text-xs ${message.ok ? 'border-statusGreen/30 bg-statusGreen/10 text-statusGreen' : 'border-statusRed/30 bg-statusRed/10 text-statusRed'}`}>{message.text}</p>}
      </section>

      {showStartgg && <section className="rounded-xl border border-white/10 bg-cardDark p-4 shadow-sm sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-white/10 pb-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-sky-400/10 p-2">
              <img src={startGgLogo} alt="" aria-hidden="true" className="h-full w-full object-contain" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white">Start.gg</h2>
              <p className="mt-0.5 text-[11px] text-textDim">Tournament provider connection · shared service credential</p>
            </div>
          </div>
          <StatusPill configured={startggConfigured} status={startggConfigured ? 'active' : 'pending'} />
        </div>
        <p className="mt-3 text-xs leading-relaxed text-textDim">Use this token for Start.gg bracket reads and organizer actions. It is stored on the Hub and is never returned to the browser. Discord and Challonge use the account-scoped cards below.</p>
        <div className="mt-4 grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto_auto]">
          <input
            type="password"
            autoComplete="new-password"
            className="w-full rounded-lg border border-white/10 bg-appDark px-3 py-2 text-sm text-white outline-none focus:border-accentYellow/60"
            placeholder={startggConfigured ? 'Enter a new token only to replace the current one' : 'Paste Start.gg API token'}
            value={startggToken}
            onChange={(event) => setStartggToken(event.target.value)}
          />
          <button type="button" onClick={saveStartggToken} disabled={busy === 'startgg:save'} className="rounded-lg border border-accentYellow/35 bg-accentYellow/10 px-3 py-2 text-xs font-bold text-accentYellow transition-colors hover:bg-accentYellow/20 disabled:opacity-50">
            {busy === 'startgg:save' ? 'Saving…' : startggConfigured ? 'Rotate token' : 'Save token'}
          </button>
          <button type="button" onClick={() => void signInProvider('startgg')} disabled={busy === 'oauth:startgg'} className="rounded-lg border border-sky-300/30 bg-sky-300/10 px-3 py-2 text-xs font-bold text-sky-100 transition-colors hover:bg-sky-300/20 disabled:opacity-50">
            {busy === 'oauth:startgg' ? 'Opening…' : 'Sign in with Start.gg'}
          </button>
          <button type="button" onClick={testStartggConnection} disabled={!startggConfigured || busy === 'startgg:test'} className="rounded-lg border border-white/10 px-3 py-2 text-xs font-bold text-white transition-colors hover:bg-white/10 disabled:opacity-50">
            {busy === 'startgg:test' ? 'Testing…' : 'Test connection'}
          </button>
        </div>
        <div className="mt-3 rounded-lg border border-white/10 bg-black/10 p-3">
          <p className="text-[10px] font-mono uppercase tracking-wider text-textDim">Optional player OAuth application</p>
          <p className="mt-1 text-[11px] text-textDim">Only needed if aiTOB uses Start.gg player sign-in. These values do not replace the organizer API token.</p>
          <div className="mt-2 grid gap-2 md:grid-cols-2">
            <input className="rounded-lg border border-white/10 bg-appDark px-3 py-2 text-sm text-white outline-none focus:border-accentYellow/60" placeholder="OAuth Client ID" value={startggClientId} onChange={(event) => setStartggClientId(event.target.value)} />
            <input type="password" autoComplete="new-password" className="rounded-lg border border-white/10 bg-appDark px-3 py-2 text-sm text-white outline-none focus:border-accentYellow/60" placeholder={startggClientConfigured ? 'Enter only to replace OAuth Client Secret' : 'OAuth Client Secret'} value={startggClientSecret} onChange={(event) => setStartggClientSecret(event.target.value)} />
          </div>
        </div>
        {startggTest && <p role="status" className="mt-3 rounded-lg border border-white/10 bg-black/15 px-3 py-2 text-xs text-textDim">{startggTest}</p>}
      </section>}

      {showAccountControls && <section className="rounded-xl border border-white/10 bg-cardDark p-4 shadow-sm sm:p-5">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-sm font-bold text-white">Add an account</h2><p className="mt-1 text-xs text-textDim">Sign in to create a provider account automatically, or create an identity for a manual token.</p></div><div className="flex flex-wrap gap-2"><button type="button" onClick={() => void signInProvider('challonge')} disabled={busy === 'oauth:challonge'} className="rounded-lg border border-blue-300/30 bg-blue-300/10 px-3 py-2 text-xs font-bold text-blue-100 transition-colors hover:bg-blue-300/20 disabled:opacity-50">{busy === 'oauth:challonge' ? 'Opening…' : 'Sign in with Challonge'}</button></div></div>
        <div className="grid gap-3 md:grid-cols-3">
          <label className="space-y-1.5"><span className="text-[10px] font-mono uppercase tracking-wider text-textDim">Provider</span><select className="w-full rounded-lg border border-white/10 bg-appDark px-3 py-2 text-sm text-white outline-none focus:border-accentYellow/60" value={draft.provider_type} onChange={(event) => setDraft({ ...draft, provider_type: event.target.value as AccountProviderType })}><option value="discord">Discord</option><option value="challonge">Challonge</option><option value="startgg">Start.gg</option></select></label>
          <label className="space-y-1.5"><span className="text-[10px] font-mono uppercase tracking-wider text-textDim">{providerMeta[draft.provider_type].identity}</span><input className="w-full rounded-lg border border-white/10 bg-appDark px-3 py-2 text-sm text-white outline-none focus:border-accentYellow/60" placeholder="Account identity" value={draft.external_account_id} onChange={(event) => setDraft({ ...draft, external_account_id: event.target.value })} /></label>
          <label className="space-y-1.5"><span className="text-[10px] font-mono uppercase tracking-wider text-textDim">Display name</span><input className="w-full rounded-lg border border-white/10 bg-appDark px-3 py-2 text-sm text-white outline-none focus:border-accentYellow/60" placeholder="e.g. FNC test bot" value={draft.display_name} onChange={(event) => setDraft({ ...draft, display_name: event.target.value })} /></label>
        </div>
        <button type="button" onClick={create} disabled={busy === 'create'} className="mt-4 rounded-lg bg-accentYellow px-3 py-2 text-xs font-bold text-black transition-colors hover:bg-yellow-300 disabled:opacity-50">{busy === 'create' ? 'Adding…' : 'Add account'}</button>
      </section>}

      <div className="space-y-3">
        {filteredAccounts.map((account) => {
          const meta = getProviderMeta(account.provider_type);
          const destination = destinationDrafts[account.id] || { external_id: '', display_name: '' };
          return <section key={account.id} className="rounded-xl border border-white/10 bg-cardDark p-4 shadow-sm sm:p-5">
            <div className="flex flex-wrap items-start justify-between gap-3 border-b border-white/10 pb-4"><div className="flex items-center gap-3"><div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accentYellow/10 text-sm text-accentYellow">{meta.icon}</div><div><h2 className="text-sm font-bold text-white">{account.display_name}</h2><p className="mt-0.5 text-[11px] text-textDim">{meta.label} · account-scoped</p></div></div><StatusPill configured={account.configured} status={account.status} /></div>
            <div className="mt-4 grid gap-4 lg:grid-cols-2"><div className="rounded-lg border border-white/10 bg-black/15 p-3"><p className="text-[10px] font-mono uppercase tracking-wider text-textDim">Identity</p><p className="mt-1 break-all text-xs text-white">{account.external_account_id}</p><p className="mt-2 text-[11px] text-textDim">Credential: {account.credential_types.length ? 'encrypted and configured' : 'not configured'}</p></div><div className="rounded-lg border border-white/10 bg-black/15 p-3"><p className="text-[10px] font-mono uppercase tracking-wider text-textDim">Destinations</p>{account.destinations.length ? <div className="mt-2 space-y-1">{account.destinations.map((item) => <p key={`${item.destination_type}:${item.display_name}`} className="text-xs text-white">{item.display_name || item.destination_type}</p>)}</div> : <p className="mt-1 text-xs text-textDim">{meta.destination}</p>}</div></div>
            <div className="mt-4 grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]"><input type="password" autoComplete="new-password" className="w-full rounded-lg border border-white/10 bg-appDark px-3 py-2 text-sm text-white outline-none focus:border-accentYellow/60" placeholder={`Replace ${meta.credential}`} value={secrets[account.id] || ''} onChange={(event) => setSecrets((current) => ({ ...current, [account.id]: event.target.value }))} /><button type="button" onClick={() => rotate(account)} disabled={busy === `credential:${account.id}`} className="rounded-lg border border-accentYellow/35 bg-accentYellow/10 px-3 py-2 text-xs font-bold text-accentYellow transition-colors hover:bg-accentYellow/20 disabled:opacity-50">{busy === `credential:${account.id}` ? 'Saving…' : 'Rotate credential'}</button></div>
            {account.provider_type === 'discord' && <div className="mt-3 rounded-lg border border-white/10 bg-black/10 p-3"><p className="text-[10px] font-mono uppercase tracking-wider text-textDim">Add match-call destination</p><div className="mt-2 grid gap-2 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]"><input className="rounded-lg border border-white/10 bg-appDark px-3 py-2 text-sm text-white outline-none focus:border-accentYellow/60" placeholder="Channel ID" value={destination.external_id} onChange={(event) => setDestinationDrafts((current) => ({ ...current, [account.id]: { ...destination, external_id: event.target.value } }))} /><input className="rounded-lg border border-white/10 bg-appDark px-3 py-2 text-sm text-white outline-none focus:border-accentYellow/60" placeholder="Display name (optional)" value={destination.display_name} onChange={(event) => setDestinationDrafts((current) => ({ ...current, [account.id]: { ...destination, display_name: event.target.value } }))} /><button type="button" onClick={() => addDestination(account)} disabled={busy === `destination:${account.id}`} className="rounded-lg border border-white/10 px-3 py-2 text-xs font-bold text-white transition-colors hover:bg-white/10 disabled:opacity-50">{busy === `destination:${account.id}` ? 'Saving…' : 'Save destination'}</button></div></div>}
          </section>;
        })}
        {!filteredAccounts.length && <section className="rounded-xl border border-dashed border-white/15 bg-cardDark/50 px-4 py-8 text-center text-sm text-textDim">No {providerFilter === 'all' ? '' : providerMeta[providerFilter].label} accounts yet.</section>}
      </div>
    </div>
  );
}
