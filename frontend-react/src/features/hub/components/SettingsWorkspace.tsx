import { useMemo, useState } from 'react';
import axios from 'axios';
import { useHubStore } from '@/store/useHubStore';
import aiTobLogo from '@/assets/aitob-logo.svg';
import { GeneralSettings } from './GeneralSettings';
import { IntegrationAccounts } from './IntegrationAccounts';
import { TournamentSettings } from './TournamentSettings';
import { MatchOperationsSettings } from './MatchSettingsModal';
import { ActionProposalReview } from './ActionProposalReview';
import { AISettings } from './AISettings';
import { AccountSettings } from './AccountSettings';
import { RolesPermissions } from './RolesPermissions';
import { LegalSettingsSection } from './LegalSettingsSection';
import { BotSettingsWorkspace } from './BotSettingsWorkspace';
import { usePermission } from '@/hooks/usePermission';

type SettingsSection = 'overview' | 'account' | 'roles' | 'connections' | 'tournament' | 'match_operations' | 'bot' | 'ai_automation' | 'legal' | 'system';

const sections: Array<{ id: SettingsSection; icon: string; label: string; hint: string; permission?: string }> = [
  { id: 'overview', icon: '◉', label: 'Overview', hint: 'Health & attention' },
  { id: 'account', icon: '●', label: 'Account', hint: 'Workspace, security & members' },
  { id: 'roles', icon: '♙', label: 'Roles & Permissions', hint: 'Workspace access matrix' },
  { id: 'connections', icon: '⌁', label: 'Connections', hint: 'Accounts & destinations', permission: 'integrations.manage' },
  { id: 'tournament', icon: '⌘', label: 'Tournament', hint: 'Provider, sync & policy', permission: 'tournament.manage' },
  { id: 'match_operations', icon: '◈', label: 'Match operations', hint: 'Check-in, dispatch & timing', permission: 'tournament.manage' },
  { id: 'bot', icon: '✦', label: 'Bot experience', hint: 'Messages & instructions', permission: 'settings.manage' },
  { id: 'ai_automation', icon: '◌', label: 'AI & Automation', hint: 'Assistant provider & safety', permission: 'assistant.use' },
  { id: 'legal', icon: '⚖', label: 'Legal & Compliance', hint: 'Terms, privacy & player waiver' },
  { id: 'system', icon: '⚙', label: 'System', hint: 'Service configuration', permission: 'settings.manage' },
];

function HealthCard({ label, detail, healthy }: { label: string; detail: string; healthy: boolean }) {
  return (
    <div className="rounded-xl border border-white/10 bg-cardDark p-4 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-semibold text-white">{label}</span>
        <span className={`h-2.5 w-2.5 rounded-full ${healthy ? 'bg-statusGreen shadow-[0_0_10px_rgba(34,197,94,.55)]' : 'bg-statusRed shadow-[0_0_10px_rgba(239,68,68,.45)]'}`} />
      </div>
      <p className="mt-2 text-xs leading-relaxed text-textDim">{detail}</p>
    </div>
  );
}

function SettingsOverview() {
  const { status, tournaments, currentSlug } = useHubStore();
  const tournament = tournaments.find((item) => item.slug === currentSlug);
  const provider = tournament?.provider_type === 'challonge' ? 'Challonge' : 'Start.gg';
  return (
    <div className="space-y-5 animate-fadeIn">
      <div className="rounded-xl border border-accentYellow/20 bg-gradient-to-br from-accentYellow/10 via-cardDark to-cardDark p-5">
        <div className="flex items-center gap-3">
          <img src={aiTobLogo} alt="aiTOB" className="h-11 w-11" />
          <div>
            <h2 className="text-xl font-bold text-white">Operations overview</h2>
            <p className="mt-1 text-xs text-textDim">A fast view of the services that can affect tournament operations.</p>
          </div>
        </div>
        <div className="mt-4 rounded-lg border border-white/10 bg-black/15 px-3 py-2 text-xs text-textDim">
          Active tournament: <span className="font-semibold text-white">{tournament?.name || 'None selected'}</span>
          {tournament && <span> · Provider: <span className="font-semibold text-white">{provider}</span></span>}
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <HealthCard label="API & database" healthy={true} detail="The local Hub is available in this browser session." />
        <HealthCard label="Discord bot" healthy={Boolean(status.discord_bot)} detail={status.discord_bot ? 'Bot connection is reported online.' : 'Calls and Discord effects need attention.'} />
        <HealthCard
          label={provider}
          healthy={tournament?.provider_type === 'challonge' ? tournament.provider_sync_status !== 'error' : Boolean(status.startgg_api)}
          detail={tournament?.provider_type === 'challonge'
            ? (tournament.provider_sync_status === 'error' ? 'Provider sync needs attention.' : 'Bracket data is available from the local provider projection.')
            : (status.startgg_api ? 'Provider connection is available.' : 'Start.gg actions may be unavailable.')}
        />
        <HealthCard label="WebSocket" healthy={Boolean(status.websockets)} detail={status.websockets ? 'Live Hub updates are connected.' : 'Refresh the dashboard to retrieve local state.'} />
        <HealthCard label="Provider sync" healthy={tournament?.provider_sync_status !== 'error'} detail={tournament ? `Last state: ${tournament.provider_sync_status || 'not synced yet'}. Open Tournament for freshness and retry controls.` : 'Select a tournament to inspect provider freshness.'} />
        <HealthCard
          label="Dispatcher master"
          healthy={Boolean(status.auto_dispatcher)}
          detail={status.auto_dispatcher
            ? 'Global Kill Switch is armed. Open Match operations for the selected tournament’s actual service status.'
            : 'Global Kill Switch is off; automatic dispatch is paused everywhere.'}
        />
      </div>
    </div>
  );
}

function TournamentWorkflowSettings() {
  const { currentSlug, tournaments, setTournaments, matches } = useHubStore();
  const tournament = tournaments.find((item) => item.slug === currentSlug);
  const matchConfiguration = tournament as (typeof tournament & {
    auto_dispatch_enabled?: boolean;
    auto_dispatch_concurrency?: number;
    auto_dispatch_stop_at?: number;
    auto_dispatch_on_stream?: boolean;
    ignore_activity_guard?: boolean;
    check_in_source?: string;
    provider_dq_timer_seconds?: number | null;
  }) | undefined;

  const phaseGroups = useMemo(() => Array.from(new Set(
    matches
      .filter((match) => !currentSlug || match.tournament_slug === currentSlug)
      .map((match) => String(match.phase_group || ''))
      .filter(Boolean),
  )).sort(), [matches, currentSlug]);

  if (!currentSlug) {
    return <section className="rounded-xl border border-dashed border-white/15 bg-cardDark/50 px-5 py-8 text-center text-sm text-textDim">Select a tournament to configure its match operations.</section>;
  }

  return (
    <div className="animate-fadeIn">
        <MatchOperationsSettings
          key={currentSlug}
          currentSlug={currentSlug}
          initialAutoDqEnabled={tournament?.auto_dq_enabled ?? true}
          initialDqTimerSeconds={tournament?.dq_timer_seconds ?? 600}
          initialProviderDqTimerSeconds={matchConfiguration?.provider_dq_timer_seconds ?? null}
          initialBotManageLimit={tournament?.bot_manage_limit}
          initialBotManageFinish={tournament?.bot_manage_finish}
          initialAutoDispatchEnabled={Boolean(matchConfiguration?.auto_dispatch_enabled)}
          initialAutoDispatchConcurrency={Number(matchConfiguration?.auto_dispatch_concurrency ?? 1)}
          initialAutoDispatchStopAt={Number(matchConfiguration?.auto_dispatch_stop_at ?? 8)}
          initialAutoDispatchOnStream={Boolean(matchConfiguration?.auto_dispatch_on_stream)}
          initialIgnoreActivityGuard={Boolean(matchConfiguration?.ignore_activity_guard)}
          initialCheckInSource={matchConfiguration?.check_in_source || 'discord'}
          phaseGroups={phaseGroups}
          providerType={tournament?.provider_type}
          initialSetFormatDefault={tournament?.set_format_default || 'ft2'}
          initialSetFormatUpgradeRule={tournament?.set_format_upgrade_rule || 'finals_only'}
          initialSetFormatUpgraded={tournament?.set_format_upgraded || 'ft3'}
          onSave={() => {
            axios.get('/api/tournaments').then((response) => setTournaments(response.data.tournaments || []));
          }}
        />
        <ActionProposalReview tournamentSlug={currentSlug} />
    </div>
  );
}

export function SettingsWorkspace() {
  const requestedSection = new URLSearchParams(window.location.search).get('settings') as SettingsSection | null;
  const [section, setSection] = useState<SettingsSection>(sections.some((item) => item.id === requestedSection) ? requestedSection! : 'overview');
  const canIntegrations = usePermission('integrations.manage');
  const canTournament = usePermission('tournament.manage');
  const canSettings = usePermission('settings.manage');
  const canAssistant = usePermission('assistant.use');
  const allowed = sections.filter((item) => !item.permission || ({
    'integrations.manage': canIntegrations,
    'tournament.manage': canTournament,
    'settings.manage': canSettings,
    'assistant.use': canAssistant,
  } as Record<string, boolean>)[item.permission]);
  const selected = allowed.find((item) => item.id === section) || allowed[0];
  const activeSection = selected.id;

  return (
    <section className="min-h-0 animate-fadeIn lg:grid lg:grid-cols-[220px_minmax(0,1fr)] lg:gap-5">
      <aside className="mb-4 rounded-xl border border-white/10 bg-cardDark/80 p-2 lg:mb-0 lg:sticky lg:top-0 lg:h-fit">
        <div className="flex items-center gap-2 px-3 py-3">
          <img src={aiTobLogo} alt="aiTOB" className="h-7 w-7" />
          <div>
            <p className="text-xs font-bold tracking-wide text-white">SETTINGS</p>
            <p className="text-[10px] text-textDim">aiTOB operations</p>
          </div>
        </div>
        <nav className="flex gap-1 overflow-x-auto pb-1 lg:flex-col lg:overflow-visible" aria-label="Settings sections">
          {allowed.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setSection(item.id)}
              className={`min-w-max rounded-lg px-3 py-2.5 text-left transition-colors lg:min-w-0 ${activeSection === item.id ? 'bg-accentYellow text-black shadow-sm' : 'text-textDim hover:bg-white/5 hover:text-white'}`}
            >
              <span className="mr-2 inline-block w-4 text-center">{item.icon}</span>
              <span className="text-xs font-bold">{item.label}</span>
              <span className={`mt-0.5 block pl-6 text-[10px] ${activeSection === item.id ? 'text-black/65' : 'text-textDim/75'}`}>{item.hint}</span>
            </button>
          ))}
        </nav>
      </aside>

      <div className="min-w-0 rounded-xl border border-white/10 bg-appDark/30 p-4 sm:p-5">
        <header className="mb-5 border-b border-white/10 pb-4">
          <p className="text-[10px] font-mono uppercase tracking-[.18em] text-accentYellow">Settings / {selected.label}</p>
          <h1 className="mt-1 text-xl font-bold text-white">{selected.label}</h1>
          <p className="mt-1 text-xs text-textDim">{selected.hint}</p>
        </header>
        {activeSection === 'overview' && <SettingsOverview />}
        {activeSection === 'account' && <AccountSettings />}
        {activeSection === 'roles' && <RolesPermissions />}
        {activeSection === 'connections' && (
          <div className="space-y-5">
            <IntegrationAccounts />
            <AISettings connectionOnly />
          </div>
        )}
        {activeSection === 'tournament' && <TournamentSettings />}
        {activeSection === 'match_operations' && <TournamentWorkflowSettings />}
        {activeSection === 'bot' && <BotSettingsWorkspace />}
        {activeSection === 'ai_automation' && <AISettings />}
        {activeSection === 'legal' && <LegalSettingsSection />}
        {activeSection === 'system' && <GeneralSettings section="system" embedded />}
      </div>
    </section>
  );
}
