import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';

type AccountProviderType = 'discord' | 'challonge' | 'startgg';
type ProviderType = AccountProviderType;
type ProviderMeta = {
  label: string;
  icon: string;
  category: string;
  credential: string;
  identity: string;
  destination: string;
  roleDescription: string;
  features: string[];
};

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
  discord: {
    label: 'Discord',
    icon: '💬',
    category: 'Communication & Match Calls',
    credential: 'Managed by aiTOB Bot',
    identity: 'Discord Server (Guild) ID',
    destination: 'No match-call announcement channel configured yet',
    roleDescription: 'The live interaction and communication layer for your tournament server.',
    features: [
      'Automated match calls & check-in pings directly in server channels',
      'Player registration & verification commands (/register)',
      'Tournament guidelines & schedule lookups (/rules, /help)',
      'Dedicated match discussion threads with referee coordination',
    ],
  },
  startgg: {
    label: 'Start.gg',
    icon: '🏆',
    category: 'Official Esports Bracket Provider',
    credential: 'API Personal Access Token',
    identity: 'Start.gg Account Identity',
    destination: 'Tournament destinations are bound per tournament draft',
    roleDescription: 'The premier esports platform for official brackets, seeding, and roster syncing.',
    features: [
      'Authoritative Double Elimination, Swiss, and Group pools bracket sync',
      'Verified attendee & player entrant roster synchronization',
      'Real-time set progression and winner advancement',
      'Official Start.gg score reporting and native Double-DQ management',
    ],
  },
  challonge: {
    label: 'Challonge',
    icon: '⚔️',
    category: 'Community & League Provider',
    credential: 'API Key',
    identity: 'Challonge Username / Account ID',
    destination: 'Tournament destinations are bound per tournament draft',
    roleDescription: 'Flexible and lightweight bracket provider for local leagues and rapid community tournaments.',
    features: [
      'Fast bracket synchronization for community and casual events',
      'Round-Robin, Swiss, and Single/Double Elimination support',
      'Direct score entry and organizer-directed single DQ',
      'Lightweight bracket embedding and live stream score integration',
    ],
  },
};

function getProviderMeta(provider: string | null | undefined): ProviderMeta {
  const known = providerMeta[provider as ProviderType];
  if (known) return known;
  const label = String(provider || 'Unknown provider');
  return {
    label,
    icon: '🔌',
    category: 'Integration',
    credential: 'API credential',
    identity: 'Account identity',
    destination: 'No destination details available',
    roleDescription: 'External service integration.',
    features: ['Service connectivity'],
  };
}

function StatusPill({ configured, status }: { configured: boolean; status: string }) {
  const ready = configured && status === 'active';
  const tone = ready
    ? 'border-statusGreen/30 bg-statusGreen/10 text-statusGreen'
    : status === 'disabled'
    ? 'border-white/10 bg-white/5 text-textDim'
    : 'border-amber-400/30 bg-amber-400/10 text-amber-200';
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${tone}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${ready ? 'bg-statusGreen' : 'bg-amber-400'}`} />
      {ready ? 'Connected & Active' : status === 'disabled' ? 'Disabled' : 'Action Required'}
    </span>
  );
}

export function IntegrationAccounts() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null);
  const [providerFilter, setProviderFilter] = useState<'all' | ProviderType>('all');
  const [draft, setDraft] = useState<{ provider_type: 'challonge' | 'startgg'; credential: string }>({
    provider_type: 'challonge',
    credential: '',
  });
  const [secrets, setSecrets] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [discordChannels, setDiscordChannels] = useState<Record<string, DiscordChannel[]>>({});
  const [selectedDiscordChannel, setSelectedDiscordChannel] = useState<Record<string, string>>({});

  const showMessage = (text: string, ok = true) => setMessage({ text, ok });

  const load = async () => {
    try {
      const accountsResponse = await axios.get('/api/integrations');
      setAccounts(
        (accountsResponse.data.accounts || []).filter((account: Account) =>
          ['discord', 'challonge', 'startgg'].includes(account.provider_type)
        )
      );
    } catch {
      setMessage({ text: 'Could not load integration accounts.', ok: false });
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const filteredAccounts = useMemo(
    () => accounts.filter((account) => providerFilter === 'all' || account.provider_type === providerFilter),
    [accounts, providerFilter]
  );

  const connectDiscord = async () => {
    setBusy('oauth:discord');
    setMessage(null);
    try {
      const response = await axios.post('/api/integrations/discord/authorize', { return_step: 'connections' });
      window.location.assign(response.data.authorization_url);
    } catch (error: any) {
      setMessage({ text: error.response?.data?.detail || error.response?.data?.message || 'Could not start Discord installation.', ok: false });
      setBusy(null);
    }
  };

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
      showMessage(`${accountName} verified and connected successfully with your Workspace credential.`);
      await load();
    } catch (error: any) {
      showMessage(error.response?.data?.detail || error.response?.data?.message || 'Could not verify this provider credential.', false);
    } finally {
      setBusy(null);
    }
  };

  const rotate = async (account: Account) => {
    const secret = secrets[account.id] || '';
    if (!secret) {
      showMessage(`Enter a new ${getProviderMeta(account.provider_type).credential.toLowerCase()} first.`, false);
      return;
    }
    setBusy(`credential:${account.id}`);
    const secret_type = account.provider_type === 'discord' ? 'bot_token' : account.provider_type === 'startgg' ? 'access_token' : 'api_key';
    try {
      await axios.post(`/api/integrations/${account.id}/credentials`, { secret_type, secret });
      setSecrets((current) => ({ ...current, [account.id]: '' }));
      showMessage('Credential encrypted and saved securely. It is never returned to the browser.');
      await load();
    } catch (error: any) {
      showMessage(error.response?.data?.detail || error.response?.data?.message || 'Credential update failed.', false);
    } finally {
      setBusy(null);
    }
  };

  const loadDiscordChannels = async (account: Account) => {
    setBusy(`discord:resources:${account.id}`);
    try {
      const response = await axios.post(`/api/integrations/${account.id}/discord/recheck`);
      setDiscordChannels((current) => ({ ...current, [account.id]: response.data.channels || [] }));
      showMessage('Discord channel list refreshed. Select your match announcement channel.');
    } catch (error: any) {
      showMessage(error.response?.data?.detail || error.response?.data?.message || 'Could not read Discord channels.', false);
    } finally {
      setBusy(null);
    }
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
      showMessage('Match notification channel saved successfully.');
      await load();
    } catch (error: any) {
      showMessage(error.response?.data?.detail || error.response?.data?.message || 'Could not save the Discord channel.', false);
    } finally {
      setBusy(null);
    }
  };

  const testDiscordChannel = async (account: Account) => {
    const channelId = selectedDiscordChannel[account.id] || '';
    if (!channelId) return showMessage('Select a Discord channel first.', false);
    setBusy(`discord:test:${account.id}`);
    try {
      await axios.post(`/api/integrations/${account.id}/discord/test-message`, { channel_id: channelId });
      showMessage('Test message delivered to Discord channel successfully.');
    } catch (error: any) {
      showMessage(error.response?.data?.detail || error.response?.data?.message || 'Discord test message failed.', false);
    } finally {
      setBusy(null);
    }
  };

  // Quick lookup of connected statuses for top summary
  const isDiscordConnected = accounts.some((a) => a.provider_type === 'discord' && a.status === 'active');
  const isStartggConnected = accounts.some((a) => a.provider_type === 'startgg' && a.status === 'active');
  const isChallongeConnected = accounts.some((a) => a.provider_type === 'challonge' && a.status === 'active');

  return (
    <div className="space-y-6 animate-fadeIn pb-8">
      {/* Header Banner */}
      <section className="rounded-xl border border-white/10 bg-cardDark p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <span>🔌</span>
              <span>Connections & Tournament Integrations</span>
            </h2>
            <p className="mt-1 max-w-2xl text-xs leading-relaxed text-textDim">
              Connect your Discord community server and official tournament bracket providers. Each credential is encrypted server-side with AES-256 and isolated to your workspace.
            </p>
          </div>
          <div className="flex rounded-lg border border-white/10 bg-black/20 p-1 text-xs font-bold">
            {(['all', 'discord', 'startgg', 'challonge'] as const).map((provider) => (
              <button
                key={provider}
                type="button"
                onClick={() => setProviderFilter(provider)}
                className={`rounded-md px-3 py-1.5 transition-colors ${
                  providerFilter === provider ? 'bg-accentYellow text-black' : 'text-textDim hover:text-white'
                }`}
              >
                {provider === 'all' ? 'All Integrations' : providerMeta[provider].label}
              </button>
            ))}
          </div>
        </div>

        {message && (
          <div
            role="status"
            className={`mt-4 rounded-lg border px-3.5 py-2.5 text-xs ${
              message.ok
                ? 'border-statusGreen/30 bg-statusGreen/10 text-statusGreen'
                : 'border-statusRed/30 bg-statusRed/10 text-statusRed'
            }`}
          >
            {message.text}
          </div>
        )}
      </section>

      {/* Provider Channels Comparison Guide */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-mono uppercase tracking-widest text-textDim">
            Understanding Your Connection Channels
          </h3>
          <span className="text-[11px] text-textDim font-mono">
            {accounts.length} Active Connection{accounts.length === 1 ? '' : 's'}
          </span>
        </div>

        <div className="grid gap-4 lg:grid-cols-3">
          {/* Discord Card */}
          <div className={`rounded-xl border p-4 transition-all ${
            isDiscordConnected
              ? 'border-indigo-500/30 bg-indigo-500/5'
              : 'border-white/10 bg-cardDark hover:border-white/20'
          }`}>
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <span className="text-xl">💬</span>
                <div>
                  <h4 className="text-sm font-bold text-white">Discord</h4>
                  <p className="text-[10px] font-mono uppercase tracking-wider text-indigo-300">Community & Operations</p>
                </div>
              </div>
              <span className={`h-2.5 w-2.5 rounded-full ${isDiscordConnected ? 'bg-statusGreen shadow-glowGreen' : 'bg-gray-500'}`} title={isDiscordConnected ? 'Connected' : 'Not Connected'} />
            </div>

            <p className="mt-3 text-xs text-textDim leading-relaxed min-h-[3.25rem]">
              {providerMeta.discord.roleDescription}
            </p>

            <div className="mt-3 border-t border-white/5 pt-3 space-y-1.5">
              <p className="text-[10px] font-bold uppercase tracking-wider text-textDim">Key Capabilities:</p>
              <ul className="text-[11px] text-gray-300 space-y-1 list-disc list-inside">
                <li>Automated station match calls</li>
                <li>Player check-ins & pings</li>
                <li>/rules & /register slash commands</li>
                <li>Private match coordination threads</li>
              </ul>
            </div>
          </div>

          {/* Start.gg Card */}
          <div className={`rounded-xl border p-4 transition-all ${
            isStartggConnected
              ? 'border-sky-500/30 bg-sky-500/5'
              : 'border-white/10 bg-cardDark hover:border-white/20'
          }`}>
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <span className="text-xl">🏆</span>
                <div>
                  <h4 className="text-sm font-bold text-white">Start.gg</h4>
                  <p className="text-[10px] font-mono uppercase tracking-wider text-sky-300">Official Esports Brackets</p>
                </div>
              </div>
              <span className={`h-2.5 w-2.5 rounded-full ${isStartggConnected ? 'bg-statusGreen shadow-glowGreen' : 'bg-gray-500'}`} title={isStartggConnected ? 'Connected' : 'Not Connected'} />
            </div>

            <p className="mt-3 text-xs text-textDim leading-relaxed min-h-[3.25rem]">
              {providerMeta.startgg.roleDescription}
            </p>

            <div className="mt-3 border-t border-white/5 pt-3 space-y-1.5">
              <p className="text-[10px] font-bold uppercase tracking-wider text-textDim">Key Capabilities:</p>
              <ul className="text-[11px] text-gray-300 space-y-1 list-disc list-inside">
                <li>Double Elimination, Pools & Swiss</li>
                <li>Official player registration sync</li>
                <li>Real-time score & result reporting</li>
                <li>Native Double-DQ handling</li>
              </ul>
            </div>
          </div>

          {/* Challonge Card */}
          <div className={`rounded-xl border p-4 transition-all ${
            isChallongeConnected
              ? 'border-orange-500/30 bg-orange-500/5'
              : 'border-white/10 bg-cardDark hover:border-white/20'
          }`}>
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <span className="text-xl">⚔️</span>
                <div>
                  <h4 className="text-sm font-bold text-white">Challonge</h4>
                  <p className="text-[10px] font-mono uppercase tracking-wider text-orange-300">Community Tournaments</p>
                </div>
              </div>
              <span className={`h-2.5 w-2.5 rounded-full ${isChallongeConnected ? 'bg-statusGreen shadow-glowGreen' : 'bg-gray-500'}`} title={isChallongeConnected ? 'Connected' : 'Not Connected'} />
            </div>

            <p className="mt-3 text-xs text-textDim leading-relaxed min-h-[3.25rem]">
              {providerMeta.challonge.roleDescription}
            </p>

            <div className="mt-3 border-t border-white/5 pt-3 space-y-1.5">
              <p className="text-[10px] font-bold uppercase tracking-wider text-textDim">Key Capabilities:</p>
              <ul className="text-[11px] text-gray-300 space-y-1 list-disc list-inside">
                <li>Fast community & local event sync</li>
                <li>Round-Robin & Swiss group stages</li>
                <li>Direct score & game updates</li>
                <li>Organizer-controlled single-player DQ</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Connect New Account Section */}
      <section className="rounded-xl border border-white/10 bg-cardDark p-5 shadow-sm space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-white/10 pb-4">
          <div>
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <span>➕</span>
              <span>Connect a Provider Account</span>
            </h3>
            <p className="mt-1 max-w-2xl text-xs text-textDim leading-relaxed">
              Bring Your Own Credential (BYOC). aiTOB validates your key directly with the provider, reads the authenticated account name, and stores it with AES-256 encryption.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void connectDiscord()}
            disabled={busy === 'oauth:discord'}
            className="rounded-lg border border-indigo-400/30 bg-indigo-500/15 px-3.5 py-2 text-xs font-bold text-indigo-200 transition-colors hover:bg-indigo-500/25 disabled:opacity-50 flex items-center gap-2"
          >
            <span aria-hidden="true">💬</span>
            <span>{busy === 'oauth:discord' ? 'Opening…' : 'Connect Discord'}</span>
          </button>
        </div>

        {/* BYOC Security Notice in English */}
        <div className="rounded-lg border border-amber-500/25 bg-amber-500/10 p-3.5 text-xs text-amber-200/90 leading-relaxed space-y-1">
          <div className="font-bold flex items-center gap-1.5 text-amber-300 text-xs uppercase tracking-wider">
            <span>🔒</span>
            <span>Bring Your Own Credential (BYOC) Security & Terms</span>
          </div>
          <p className="text-[11px] text-gray-300">
            You are connecting with your own provider API credentials. Credentials are encrypted server-side and never exposed to client browsers or other workspaces. You remain responsible for monitoring your provider rate limits and adhering to Start.gg / Challonge developer terms of service.
          </p>
        </div>

        {/* Input Form for Bracket Providers */}
        <div className="grid gap-3 sm:grid-cols-[minmax(12rem,0.35fr)_minmax(0,1fr)]">
          <label className="space-y-1.5">
            <span className="text-[10px] font-mono uppercase tracking-wider text-textDim">Bracket Provider</span>
            <select
              aria-label="Provider"
              className="w-full rounded-lg border border-white/10 bg-appDark px-3 py-2 text-sm text-white outline-none focus:border-accentYellow"
              value={draft.provider_type}
              onChange={(event) =>
                setDraft({ ...draft, provider_type: event.target.value as 'challonge' | 'startgg' })
              }
            >
              <option value="challonge">Challonge (API Key)</option>
              <option value="startgg">Start.gg (API Token)</option>
            </select>
          </label>

          <label className="space-y-1.5">
            <span className="text-[10px] font-mono uppercase tracking-wider text-textDim">
              {providerMeta[draft.provider_type].credential}
            </span>
            <input
              type="password"
              autoComplete="new-password"
              className="w-full rounded-lg border border-white/10 bg-appDark px-3 py-2 text-sm text-white outline-none focus:border-accentYellow"
              placeholder={
                draft.provider_type === 'startgg'
                  ? 'Paste your Start.gg API token'
                  : 'Paste your Challonge API key'
              }
              value={draft.credential}
              onChange={(event) => setDraft({ ...draft, credential: event.target.value })}
            />
          </label>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
          <button
            type="button"
            onClick={connectProvider}
            disabled={busy === 'connect-provider'}
            className="rounded-lg bg-accentYellow px-4 py-2 text-xs font-bold text-black transition-transform active:scale-95 hover:bg-yellow-400 disabled:opacity-50"
          >
            {busy === 'connect-provider' ? 'Verifying…' : `Verify & connect ${providerMeta[draft.provider_type].label}`}
          </button>
          <p className="text-[11px] text-textDim">
            {draft.provider_type === 'startgg' ? (
              <span>
                Need a token? Generate one in{' '}
                <a
                  href="https://start.gg/admin/profile/developer"
                  target="_blank"
                  rel="noreferrer"
                  className="text-sky-400 underline hover:text-sky-300"
                >
                  Start.gg Developer Settings
                </a>
              </span>
            ) : (
              <span>
                Need an API key? Find yours in{' '}
                <a
                  href="https://challonge.com/settings/developer"
                  target="_blank"
                  rel="noreferrer"
                  className="text-orange-400 underline hover:text-orange-300"
                >
                  Challonge API Settings
                </a>
              </span>
            )}
          </p>
        </div>
      </section>

      {/* Active Connected Accounts List */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-mono uppercase tracking-widest text-textDim">
            Configured Workspace Connections
          </h3>
          <span className="text-xs text-textDim">
            Showing {filteredAccounts.length} of {accounts.length}
          </span>
        </div>

        {filteredAccounts.map((account) => {
          const meta = getProviderMeta(account.provider_type);
          return (
            <section
              key={account.id}
              className="rounded-xl border border-white/10 bg-cardDark p-5 shadow-sm space-y-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-3 border-b border-white/10 pb-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-white/5 text-lg">
                    {meta.icon}
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-white flex items-center gap-2">
                      <span>{account.display_name}</span>
                      <span className="rounded bg-white/10 px-1.5 py-0.5 text-[10px] font-mono text-gray-300 uppercase">
                        {meta.label}
                      </span>
                    </h4>
                    <p className="mt-0.5 text-[11px] text-textDim">
                      {meta.category} · Workspace-Scoped
                    </p>
                  </div>
                </div>
                <StatusPill configured={account.configured} status={account.status} />
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-lg border border-white/5 bg-black/20 p-3 space-y-1">
                  <p className="text-[10px] font-mono uppercase tracking-wider text-textDim">
                    {meta.identity}
                  </p>
                  <p className="break-all text-xs font-mono text-white">
                    {account.external_account_id}
                  </p>
                  <p className="text-[11px] text-textDim">
                    {account.provider_type === 'discord'
                      ? 'Managed aiTOB bot application installation'
                      : 'AES-256 Encrypted & Active'}
                  </p>
                </div>

                <div className="rounded-lg border border-white/5 bg-black/20 p-3 space-y-1">
                  <p className="text-[10px] font-mono uppercase tracking-wider text-textDim">
                    Channel Targets & Destinations
                  </p>
                  {account.destinations.length ? (
                    <div className="space-y-1 mt-1">
                      {account.destinations.map((item) => (
                        <p key={`${item.destination_type}:${item.display_name}`} className="text-xs text-white flex items-center gap-1.5">
                          <span className="text-statusGreen">●</span>
                          <span>{item.display_name || item.destination_type}</span>
                        </p>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-textDim mt-1">{meta.destination}</p>
                  )}
                </div>
              </div>

              {/* Discord-Specific Channel Configuration */}
              {account.provider_type === 'discord' && (
                <div className="rounded-lg border border-indigo-400/20 bg-indigo-500/5 p-4 space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="text-xs font-bold text-white flex items-center gap-1.5">
                        <span>📢</span>
                        <span>Match Announcement Channel</span>
                      </p>
                      <p className="text-[11px] text-textDim">
                        Choose the Discord channel where the bot calls matches, tags players, and posts updates.
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => void loadDiscordChannels(account)}
                      disabled={busy === `discord:resources:${account.id}`}
                      className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-bold text-white hover:bg-white/10 disabled:opacity-50"
                    >
                      {busy === `discord:resources:${account.id}` ? 'Loading…' : 'Refresh Channels'}
                    </button>
                  </div>

                  {discordChannels[account.id] && (
                    <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto_auto] pt-2">
                      <select
                        aria-label="Discord Channel"
                        value={selectedDiscordChannel[account.id] || ''}
                        onChange={(event) =>
                          setSelectedDiscordChannel((current) => ({
                            ...current,
                            [account.id]: event.target.value,
                          }))
                        }
                        className="rounded-lg border border-white/10 bg-appDark px-3 py-2 text-sm text-white outline-none focus:border-accentYellow"
                      >
                        <option value="">Select a channel…</option>
                        {discordChannels[account.id].map((channel) => (
                          <option key={channel.id} value={channel.id} disabled={!channel.ready}>
                            #{channel.name} {channel.ready ? '' : '(missing send permissions)'}
                          </option>
                        ))}
                      </select>
                      <button
                        type="button"
                        onClick={() => void saveDiscordChannel(account)}
                        disabled={busy === `discord:save:${account.id}`}
                        className="rounded-lg border border-white/15 bg-white/10 px-3.5 py-2 text-xs font-bold text-white hover:bg-white/15 disabled:opacity-50"
                      >
                        {busy === `discord:save:${account.id}` ? 'Saving…' : 'Save Channel'}
                      </button>
                      <button
                        type="button"
                        onClick={() => void testDiscordChannel(account)}
                        disabled={busy === `discord:test:${account.id}`}
                        className="rounded-lg bg-accentYellow px-3.5 py-2 text-xs font-bold text-black hover:bg-yellow-400 disabled:opacity-50"
                      >
                        {busy === `discord:test:${account.id}` ? 'Testing…' : 'Send Test'}
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* Credential Rotation for Start.gg and Challonge */}
              {account.provider_type !== 'discord' && (
                <div className="border-t border-white/5 pt-3">
                  <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
                    <input
                      type="password"
                      autoComplete="new-password"
                      className="w-full rounded-lg border border-white/10 bg-appDark px-3 py-2 text-sm text-white outline-none focus:border-accentYellow"
                      placeholder={`Replace ${meta.credential} with a new token...`}
                      value={secrets[account.id] || ''}
                      onChange={(event) =>
                        setSecrets((current) => ({ ...current, [account.id]: event.target.value }))
                      }
                    />
                    <button
                      type="button"
                      onClick={() => rotate(account)}
                      disabled={busy === `credential:${account.id}`}
                      className="rounded-lg border border-accentYellow/35 bg-accentYellow/10 px-3.5 py-2 text-xs font-bold text-accentYellow transition-colors hover:bg-accentYellow/20 disabled:opacity-50"
                    >
                      {busy === `credential:${account.id}` ? 'Saving…' : 'Update Key'}
                    </button>
                  </div>
                </div>
              )}
            </section>
          );
        })}

        {!filteredAccounts.length && (
          <section className="rounded-xl border border-dashed border-white/15 bg-cardDark/40 px-4 py-10 text-center text-sm text-textDim space-y-1">
            <p className="font-semibold text-white">No {providerFilter === 'all' ? '' : providerMeta[providerFilter].label} connections yet.</p>
            <p className="text-xs">Use the connect form above to link your tournament accounts.</p>
          </section>
        )}
      </div>
    </div>
  );
}
