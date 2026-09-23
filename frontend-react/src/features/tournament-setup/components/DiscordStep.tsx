import { useState } from 'react';
import axios from 'axios';
import type { DiscordSetupDraft, IntegrationAccount, RegistrationConfig } from '../types';
import { PlayerRegistrationCard } from './PlayerRegistrationCard';

type DiscordChannel = { id: string; name: string; ready: boolean };

function registrationValue(value?: RegistrationConfig): RegistrationConfig {
  return {
    enabled: value?.enabled ?? false,
    destination_external_id: value?.destination_external_id ?? '',
    opens_at: value?.opens_at ?? '',
    closes_at: value?.closes_at ?? '',
    display_timezone: value?.display_timezone ?? 'UTC',
    require_provider_registration: value?.require_provider_registration ?? true,
    gamertag_verification_policy: value?.gamertag_verification_policy ?? 'match_or_set_nickname',
    startgg_bio_verification_enabled: value?.startgg_bio_verification_enabled ?? false,
    image_policy: value?.image_policy ?? 'optional',
    verified_role_external_id: value?.verified_role_external_id ?? '',
  };
}

export function DiscordStep({ draftId, providerType, accounts, value, onChange, connectionNotice }: {
  draftId: string;
  providerType: 'startgg' | 'challonge';
  accounts: IntegrationAccount[];
  value: DiscordSetupDraft;
  onChange: (value: DiscordSetupDraft) => void;
  connectionNotice?: string | null;
}) {
  const registration = registrationValue(value.registration);
  const discordAccounts = accounts.filter((account) => account.provider_type === 'discord' && account.status === 'active');
  const [channels, setChannels] = useState<DiscordChannel[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const connect = async () => {
    setBusy('connect');
    setMessage(null);
    try {
      const response = await axios.post('/api/integrations/discord/authorize', { draft_id: draftId, return_step: 'discord' });
      window.location.assign(response.data.authorization_url);
    } catch (error: any) {
      setMessage(error.response?.data?.detail || 'Could not start Discord installation.');
      setBusy(null);
    }
  };

  const loadChannels = async (accountId: string) => {
    if (!accountId) return;
    setBusy('channels');
    setMessage(null);
    try {
      const response = await axios.post(`/api/integrations/${accountId}/discord/recheck`);
      setChannels(response.data.channels || []);
    } catch (error: any) {
      setMessage(error.response?.data?.detail || 'Could not read Discord channels.');
    } finally {
      setBusy(null);
    }
  };

  const selectAccount = async (accountId: string) => {
    const account = discordAccounts.find((item) => item.id === accountId);
    onChange({
      ...value,
      enabled: true,
      discord_account_id: accountId,
      guild_id: account?.external_account_id,
      guild_name: account?.display_name,
      destination_external_id: '',
    });
    await loadChannels(accountId);
  };

  const selectChannel = async (channelId: string) => {
    const channel = channels.find((item) => item.id === channelId);
    onChange({
      ...value,
      enabled: true,
      destination_external_id: channelId,
      destination_name: channel?.name,
      registration: { ...registration, destination_external_id: channelId },
    });
    if (!value.discord_account_id || !channelId) return;
    setBusy('save');
    try {
      await axios.post(`/api/integrations/${value.discord_account_id}/discord/destinations`, {
        channel_id: channelId,
        destination_type: 'match_call_channel',
      });
      setMessage('Channel saved and permissions verified.');
    } catch (error: any) {
      setMessage(error.response?.data?.detail || 'Could not save this channel.');
    } finally {
      setBusy(null);
    }
  };

  const sendTest = async () => {
    if (!value.discord_account_id || !value.destination_external_id) return;
    setBusy('test');
    try {
      await axios.post(`/api/integrations/${value.discord_account_id}/discord/test-message`, {
        channel_id: value.destination_external_id,
      });
      setMessage('Test message delivered successfully.');
    } catch (error: any) {
      setMessage(error.response?.data?.detail || 'Test message failed.');
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-5">
      <div><h2 id="setup-step-title" className="text-2xl font-semibold">Discord and registration</h2><p className="mt-2 text-sm text-textDim">Install the managed aiTOB bot, then bind this tournament to a verified channel. No bot token is entered here.</p></div>
      <label className="flex items-center gap-3 rounded-xl border border-white/10 bg-black/10 p-4"><input type="checkbox" checked={Boolean(value.enabled)} onChange={(event) => onChange({ ...value, enabled: event.target.checked })} /><span><strong className="block text-sm text-white">Enable Discord for this tournament</strong><span className="text-xs text-textDim">When disabled, match coordination remains manual in the Hub.</span></span></label>
      {value.enabled && (
        <div className="space-y-4 rounded-xl border border-indigo-300/20 bg-indigo-300/5 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="text-sm font-bold text-white">1. Connect a Discord server</h3><p className="mt-1 text-xs text-textDim">The installer must have Manage Server permission.</p></div><button type="button" onClick={() => void connect()} disabled={busy === 'connect'} className="rounded-lg bg-indigo-400 px-4 py-2 text-xs font-black text-black disabled:opacity-50">{busy === 'connect' ? 'Opening…' : 'Install / connect aiTOB'}</button></div>
          <label className="block text-xs font-bold text-textDim">Connected server<select value={value.discord_account_id || ''} onChange={(event) => void selectAccount(event.target.value)} className="mt-1.5 w-full rounded-lg border border-white/10 bg-appDark px-3 py-2.5 text-sm text-white"><option value="">Select an installed server</option>{discordAccounts.map((account) => <option key={account.id} value={account.id}>{account.display_name}</option>)}</select></label>
          {value.discord_account_id && <><div className="flex items-center justify-between gap-2"><h3 className="text-sm font-bold text-white">2. Select tournament channel</h3><button type="button" onClick={() => void loadChannels(value.discord_account_id || '')} className="text-xs font-bold text-accentYellow">Recheck permissions</button></div><select value={value.destination_external_id || ''} onChange={(event) => void selectChannel(event.target.value)} className="w-full rounded-lg border border-white/10 bg-appDark px-3 py-2.5 text-sm text-white"><option value="">Select a channel</option>{channels.map((channel) => <option key={channel.id} value={channel.id} disabled={!channel.ready}>#{channel.name}{channel.ready ? '' : ' — missing permissions'}</option>)}</select><button type="button" disabled={!value.destination_external_id || busy === 'test'} onClick={() => void sendTest()} className="rounded-lg border border-statusGreen/30 bg-statusGreen/10 px-4 py-2 text-xs font-bold text-statusGreen disabled:opacity-40">{busy === 'test' ? 'Sending…' : 'Send test message'}</button></>}
        </div>
      )}
      {(message || connectionNotice) && <p role="status" className="rounded-lg border border-white/10 bg-black/15 px-3 py-2 text-xs text-textDim">{message || connectionNotice}</p>}
      <PlayerRegistrationCard providerType={providerType} value={registration} onChange={(next) => onChange({ ...value, enabled: true, registration: next })} />
    </div>
  );
}
