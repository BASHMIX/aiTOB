import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';

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
type DiscordChannel = { id: string; name: string; ready: boolean };

const providerMeta: Record<ProviderType, ProviderMeta> = {
  discord: { label: 'Discord', icon: '✦', credential: 'Managed by aiTOB', identity: 'Connected server ID', destination: 'No match-call channel configured' },
  challonge: { label: 'Challonge', icon: '⌘', credential: 'API key or account token', identity: 'Challonge account ID', destination: 'Tournament destinations are selected per tournament' },
  startgg: { label: 'Start.gg', icon: '◆', credential: 'API token', identity: 'Start.gg account ID', destination: 'Tournament destinations are selected per tournament' },
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
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null);
  const [providerFilter, setProviderFilter] = useState<'all' | ProviderType>('all');
  const [draft, setDraft] = useState<{ provider_type: 'challonge' | 'startgg'; credential: string }>({ provider_type: 'challonge', credential: '' });
  const [secrets, setSecrets] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [discordChannels, setDiscordChannels] = useState<Record<string, DiscordChannel[]>>({});
  const [selectedDiscordChannel, setSelectedDiscordChannel] = useState<Record<string, string>>({});

  const connectDiscord = async () => {
    setBusy('oauth:discord');
    setMessage(null);
    try {
      const response = await axios.post('/api/integrations/discord/authorize', { return_step: 'connections' });
      window.location.assign(response.data.authorization_url);
    } catch (error: any) {
      setMessage({ text: error.response?.data?.detail || 'Could not start Discord installation.', ok: false });
      setBusy(null);
    }
  };

  const load = async () => {
    try {
      const accountsResponse = await axios.get('/api/integrations');
      setAccounts((accountsResponse.data.accounts || []).filter((account: Account) => ['discord', 'challonge', 'startgg'].includes(account.provider_type)));
    } catch {
      setMessage({ text: 'Could not load integration accounts.', ok: false });
    }
  };
  useEffect(() => { void load(); }, []);

  const filteredAccounts = useMemo(() => accounts.filter((account) => providerFilter === 'all' || account.provider_type === providerFilter), [accounts, providerFilter]);
  const showAccountControls = true;
  const showMessage = (text: string, ok = true) => setMessage({ text, ok });

  const connectProvider = async () => {
    if (!draft.credential.trim()) {
      showMessage(`Enter your ${providerMeta[draft.provider_type].credential.toLowerCase()} first.`, false);
      return;
    }
    setBusy('connect-provider');
    try {
      const response = await axios.post('/api/integrations/provider-credentials/connect', draft);
      const accountName = response.data.account?.display_name || providerMeta[draft.provider_type].label;
      setDraft((current) => ({ ...current, credential: '' }));
      showMessage(`${accountName} verified and connected with this Workspace credential.`);
      await load();
    } catch (error: any) {
      showMessage(error.response?.data?.detail || 'Could not verify this provider credential.', false);
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

  const loadDiscordChannels = async (account: Account) => {
    setBusy(`discord:resources:${account.id}`);
    try {
      const response = await axios.post(`/api/integrations/${account.id}/discord/recheck`);
      setDiscordChannels((current) => ({ ...current, [account.id]: response.data.channels || [] }));
      showMessage('Discord permissions refreshed. Select a ready channel.');
    } catch (error: any) {
      showMessage(error.response?.data?.detail || 'Could not read Discord channels.', false);
    } finally { setBusy(null); }
  };

  const saveDiscordChannel = async (account: Account) => {
    const channelId = selectedDiscordChannel[account.id] || '';
    if (!channelId) return showMessage('Select a Discord channel first.', false);
    setBusy(`discord:save:${account.id}`);
    try {
      await axios.post(`/api/integrations/${account.id}/discord/destinations`, {
        channel_id: channelId,
        destination_type: 'match_call_channel',
      });
      showMessage('Match channel saved.');
      await load();
    } catch (error: any) {
      showMessage(error.response?.data?.detail || 'Could not save the Discord channel.', false);
    } finally { setBusy(null); }
  };

  const testDiscordChannel = async (account: Account) => {
    const channelId = selectedDiscordChannel[account.id] || '';
    if (!channelId) return showMessage('Select a Discord channel first.', false);
    setBusy(`discord:test:${account.id}`);
    try {
      await axios.post(`/api/integrations/${account.id}/discord/test-message`, { channel_id: channelId });
      showMessage('Test message delivered to Discord.');
    } catch (error: any) {
      showMessage(error.response?.data?.detail || 'Discord test message failed.', false);
    } finally { setBusy(null); }
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

      {showAccountControls && <section className="rounded-xl border border-white/10 bg-cardDark p-4 shadow-sm sm:p-5">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-sm font-bold text-white">Connect your provider account</h2><p className="mt-1 max-w-2xl text-xs text-textDim">Bring your own credential. aiTOB verifies it with the provider, reads the real account identity, and stores the credential encrypted for this Workspace only.</p></div><button type="button" onClick={() => void connectDiscord()} disabled={busy === 'oauth:discord'} className="rounded-lg border border-indigo-300/30 bg-indigo-300/10 px-3 py-2 text-xs font-bold text-indigo-100 transition-colors hover:bg-indigo-300/20 disabled:opacity-50">{busy === 'oauth:discord' ? 'Opening…' : 'Connect Discord'}</button></div>
        <div className="grid gap-3 md:grid-cols-[minmax(12rem,0.45fr)_minmax(0,1fr)]">
          <label className="space-y-1.5"><span className="text-[10px] font-mono uppercase tracking-wider text-textDim">Provider</span><select className="w-full rounded-lg border border-white/10 bg-appDark px-3 py-2 text-sm text-white outline-none focus:border-accentYellow/60" value={draft.provider_type} onChange={(event) => setDraft({ ...draft, provider_type: event.target.value as 'challonge' | 'startgg' })}><option value="challonge">Challonge</option><option value="startgg">Start.gg</option></select></label>
          <label className="space-y-1.5"><span className="text-[10px] font-mono uppercase tracking-wider text-textDim">{providerMeta[draft.provider_type].credential}</span><input type="password" autoComplete="new-password" className="w-full rounded-lg border border-white/10 bg-appDark px-3 py-2 text-sm text-white outline-none focus:border-accentYellow/60" placeholder={draft.provider_type === 'startgg' ? 'Paste your Start.gg API token' : 'Paste your Challonge API key'} value={draft.credential} onChange={(event) => setDraft({ ...draft, credential: event.target.value })} /></label>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3"><button type="button" onClick={connectProvider} disabled={busy === 'connect-provider'} className="rounded-lg bg-accentYellow px-3 py-2 text-xs font-bold text-black transition-colors hover:bg-yellow-300 disabled:opacity-50">{busy === 'connect-provider' ? 'Verifying…' : `Verify & connect ${providerMeta[draft.provider_type].label}`}</button><p className="text-[11px] text-textDim">Account ID and display name are read from the provider; they are never entered manually.</p></div>
      </section>}

      <div className="space-y-3">
        {filteredAccounts.map((account) => {
          const meta = getProviderMeta(account.provider_type);
          return <section key={account.id} className="rounded-xl border border-white/10 bg-cardDark p-4 shadow-sm sm:p-5">
            <div className="flex flex-wrap items-start justify-between gap-3 border-b border-white/10 pb-4"><div className="flex items-center gap-3"><div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accentYellow/10 text-sm text-accentYellow">{meta.icon}</div><div><h2 className="text-sm font-bold text-white">{account.display_name}</h2><p className="mt-0.5 text-[11px] text-textDim">{meta.label} · account-scoped</p></div></div><StatusPill configured={account.configured} status={account.status} /></div>
            <div className="mt-4 grid gap-4 lg:grid-cols-2"><div className="rounded-lg border border-white/10 bg-black/15 p-3"><p className="text-[10px] font-mono uppercase tracking-wider text-textDim">Identity</p><p className="mt-1 break-all text-xs text-white">{account.external_account_id}</p><p className="mt-2 text-[11px] text-textDim">{account.provider_type === 'discord' ? 'Managed aiTOB application installation' : `Credential: ${account.credential_types.length ? 'encrypted and configured' : 'not configured'}`}</p></div><div className="rounded-lg border border-white/10 bg-black/15 p-3"><p className="text-[10px] font-mono uppercase tracking-wider text-textDim">Destinations</p>{account.destinations.length ? <div className="mt-2 space-y-1">{account.destinations.map((item) => <p key={`${item.destination_type}:${item.display_name}`} className="text-xs text-white">{item.display_name || item.destination_type}</p>)}</div> : <p className="mt-1 text-xs text-textDim">{meta.destination}</p>}</div></div>
            {account.provider_type !== 'discord' && <div className="mt-4 grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]"><input type="password" autoComplete="new-password" className="w-full rounded-lg border border-white/10 bg-appDark px-3 py-2 text-sm text-white outline-none focus:border-accentYellow/60" placeholder={`Replace ${meta.credential}`} value={secrets[account.id] || ''} onChange={(event) => setSecrets((current) => ({ ...current, [account.id]: event.target.value }))} /><button type="button" onClick={() => rotate(account)} disabled={busy === `credential:${account.id}`} className="rounded-lg border border-accentYellow/35 bg-accentYellow/10 px-3 py-2 text-xs font-bold text-accentYellow transition-colors hover:bg-accentYellow/20 disabled:opacity-50">{busy === `credential:${account.id}` ? 'Saving…' : 'Rotate credential'}</button></div>}
            {account.provider_type === 'discord' && <div className="mt-3 rounded-lg border border-indigo-300/20 bg-indigo-300/5 p-3"><div className="flex flex-wrap items-center justify-between gap-2"><div><p className="text-[10px] font-mono uppercase tracking-wider text-indigo-200">Managed aiTOB bot</p><p className="mt-1 text-xs text-textDim">Refresh permissions, choose a named channel, then send a test message.</p></div><button type="button" onClick={() => void loadDiscordChannels(account)} className="rounded-lg border border-white/10 px-3 py-2 text-xs font-bold text-white hover:bg-white/10">Refresh channels</button></div>{discordChannels[account.id] && <div className="mt-3 grid gap-2 md:grid-cols-[minmax(0,1fr)_auto_auto]"><select value={selectedDiscordChannel[account.id] || ''} onChange={(event) => setSelectedDiscordChannel((current) => ({ ...current, [account.id]: event.target.value }))} className="rounded-lg border border-white/10 bg-appDark px-3 py-2 text-sm text-white"><option value="">Select a channel</option>{discordChannels[account.id].map((channel) => <option key={channel.id} value={channel.id} disabled={!channel.ready}>#{channel.name}{channel.ready ? '' : ' — missing permissions'}</option>)}</select><button type="button" onClick={() => void saveDiscordChannel(account)} className="rounded-lg border border-white/10 px-3 py-2 text-xs font-bold text-white hover:bg-white/10">Save channel</button><button type="button" onClick={() => void testDiscordChannel(account)} className="rounded-lg bg-accentYellow px-3 py-2 text-xs font-bold text-black">Send test</button></div>}</div>}
          </section>;
        })}
        {!filteredAccounts.length && <section className="rounded-xl border border-dashed border-white/15 bg-cardDark/50 px-4 py-8 text-center text-sm text-textDim">No {providerFilter === 'all' ? '' : providerMeta[providerFilter].label} accounts yet.</section>}
      </div>
    </div>
  );
}
