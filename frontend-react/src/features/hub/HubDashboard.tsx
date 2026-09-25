import { useEffect, useState, useCallback } from 'react';
import { TopNavigation } from '@/components/layout/TopNavigation';
import { TournamentSettings } from './components/TournamentSettings';
import { ActiveMatchStatus } from './components/ActiveMatchStatus';
import { ActiveStreamsStatus } from './components/ActiveStreamsStatus';
import { TournamentOperationsCards } from './components/TournamentOperationsCards';
import { MatchDashboard } from './components/MatchDashboard';
import { OrganizerConsole, type OrganizerConsoleOpenRequest } from './components/OrganizerConsole';
import { NotificationCenter } from './components/NotificationCenter';
import { SettingsWorkspace } from './components/SettingsWorkspace';
import aiTobLogo from '@/assets/aitob-logo.svg';
import { DispatcherMasterSwitch } from './components/DispatcherMasterSwitch';
import { ConnectionLines } from './components/ConnectionLines';
import { useHubStore } from '@/store/useHubStore';
import { useHubSocket } from '@/hooks/useHubSocket';
import axios from 'axios';
import { usePermission } from '@/hooks/usePermission';

const PREFERRED_SLUG = 'FNC1stStartGG';

export function HubDashboard() {
  const canManageWorkspace = usePermission('workspace.manage');
  const canManageTournaments = usePermission('tournament.manage');
  const {
    setTournaments,
    status,
    setStatus,
    setMatches,
    currentSlug,
    setCurrentSlug,
    tournaments,
  } = useHubStore();
  const selectedTournament = tournaments.find((tournament) => tournament.slug === currentSlug);
  const isStartGgTournament = selectedTournament?.provider_type !== 'challonge';

  const [isRefetching, setIsRefetching] = useState(false);
  const [activeTab, setActiveTab] = useState<'active' | 'registration' | 'system'>('active');
  const [consoleOpenRequest, setConsoleOpenRequest] = useState<OrganizerConsoleOpenRequest | null>(null);
  const [notificationRefreshSignal, setNotificationRefreshSignal] = useState(0);

  const loadData = useCallback(async () => {
    setIsRefetching(true);
    try {
      const [tourneysRes, matchesRes] = await Promise.all([
        axios.get('/api/tournaments'),
        axios.get('/api/active-matches'),
      ]);

      const tourneys = tourneysRes.data.tournaments || [];
      setTournaments(tourneys);

      let slug = currentSlug || localStorage.getItem('hub_current_slug');
      if (!slug && tourneys.length > 0) {
        const preferred = tourneys.find((t: any) => t.slug?.toLowerCase() === PREFERRED_SLUG.toLowerCase());
        const defaultSlug = preferred ? preferred.slug : tourneys[0].slug;
        setCurrentSlug(defaultSlug);
        slug = defaultSlug;
      }

      if (slug) {
        // Selections saved before the operations-card feature existed must be
        // promoted once as well. setCurrentSlug is idempotent for the current
        // selection and records it in the pinned-card list.
        setCurrentSlug(slug);
        setMatches(matchesRes.data.matches || []);
      } else {
        setMatches([]);
      }

      try {
        const statusRes = await axios.get('/api/status');
        setStatus({
          startgg_api: statusRes.data.startgg_api,
          websockets: true,
          discord_bot: statusRes.data.discord_bot || false,
          token_scope: statusRes.data.token_scope || null,
          auto_dispatcher: !!statusRes.data.auto_dispatcher,
        });
      } catch { /* ignored */ }

      try {
        const settingsRes = await axios.get('/api/settings');
        const sets = settingsRes.data.settings || {};
        if (sets.current_theme) {
          document.documentElement.setAttribute('data-theme', sets.current_theme);
        }
      } catch { /* ignored */ }

    } catch (err) {
      console.error("Error fetching hub data", err);
    } finally {
      setIsRefetching(false);
    }
  }, [currentSlug, setCurrentSlug, setMatches, setStatus, setTournaments]);

  useHubSocket(useCallback((evt) => {
    if (evt.type === 'match_update' || evt.type === 'status_update') {
      setNotificationRefreshSignal((signal) => signal + 1);
      loadData();
    }
  }, [loadData]));

  useEffect(() => {
    loadData();
  }, []);

  const [testingToken, setTestingToken] = useState(false);

  return (
    <div className="flex flex-col gap-4 h-full relative">
      <header className="flex items-center justify-between gap-4 pb-2 border-b border-white/10">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 flex items-center justify-center">
            <img src={aiTobLogo} alt="aiTOB" className="h-full w-full" />
          </div>
          <div className="flex flex-col">
            <h1 className="text-2xl font-bold text-white tracking-wide">FNC Tournament Hub</h1>
            <span className="text-[10px] text-yellow-400/50 font-mono uppercase tracking-widest">Tournament Manager</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <NotificationCenter
            refreshSignal={notificationRefreshSignal}
            onOpenNotification={(target) => setConsoleOpenRequest({ ...target, requestId: `${Date.now()}-${target.focusKey || target.tab}` })}
          />
          {canManageWorkspace && <DispatcherMasterSwitch />}
        </div>
      </header>

      {isStartGgTournament && status.token_scope && (!status.token_scope.valid || !status.token_scope.has_write_scope) && (
        <div className="animate-fadeIn p-3.5 rounded-lg border border-red-500/35 bg-red-950/20 text-red-200 text-xs flex items-center justify-between gap-4 shadow-lg shadow-red-950/30 backdrop-blur-md transition-all hover:border-red-500/50">
          <div className="flex items-center gap-3">
            <span className="text-xl shrink-0 filter drop-shadow-sm select-none animate-pulse">⚠️</span>
            <div>
              <p className="font-bold text-red-400 text-sm tracking-wide">Start.gg Token Connection Impaired</p>
              <p className="text-red-300/85 mt-0.5 text-[11px] leading-relaxed">
                {status.token_scope.error || (
                  <>
                    Token loaded successfully for user <strong className="text-red-200">{status.token_scope.user_name}</strong>, but lacks <strong className="text-yellow-400 font-bold uppercase tracking-wider">Tournament Organizer (T.O.) administrative write scopes</strong> on Start.gg. Bracket score submissions and match activations will fail.
                  </>
                )}
              </p>
            </div>
          </div>
          <button 
            onClick={async () => {
              setTestingToken(true);
              try {
                await axios.post('/api/settings/token-check');
                await loadData();
              } catch (e) {
                console.error(e);
              } finally {
                setTestingToken(false);
              }
            }}
            disabled={testingToken}
            className="shrink-0 px-4 py-2 bg-red-500/15 hover:bg-red-500/30 disabled:opacity-50 border border-red-500/30 hover:border-red-500/50 rounded-md text-[10px] font-mono font-bold tracking-widest text-red-200 uppercase transition-all shadow-sm active:scale-95 flex items-center gap-1.5 cursor-pointer"
          >
            {testingToken ? (
              <>
                <svg className="animate-spin h-3 w-3 text-red-200" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                PROBING...
              </>
            ) : (
              'RE-TEST TOKEN'
            )}
          </button>
        </div>
      )}

      <TopNavigation />

      <main className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-4 items-start h-[calc(100vh-140px)]">
        {/* Left Column (Tabs) */}

        <div className="lg:col-span-9 xl:col-span-9 flex flex-col gap-4 h-full pb-10">
          <div className="flex items-center gap-1 bg-cardDark/50 p-1 rounded-lg border border-white/5 w-fit">
            <button
              onClick={() => setActiveTab('active')}
              className={`px-4 py-1.5 rounded-md text-xs font-bold transition-all ${activeTab === 'active' ? 'bg-accentYellow text-black' : 'text-textDim hover:text-white'}`}
            >
              ACTIVE
            </button>
            <button
              onClick={() => setActiveTab('registration')}
              className={`px-4 py-1.5 rounded-md text-xs font-bold transition-all ${activeTab === 'registration' ? 'bg-accentYellow text-black' : 'text-textDim hover:text-white'}`}
            >
              REGISTRATION
            </button>
            <button
              onClick={() => setActiveTab('system')}
              className={`px-4 py-1.5 rounded-md text-xs font-bold transition-all ${activeTab === 'system' ? 'bg-accentYellow text-black' : 'text-textDim hover:text-white'}`}
            >
              SETTINGS
            </button>
          </div>

          <div className="flex-1 overflow-y-auto pr-2 custom-scrollbar relative">
            {activeTab === 'active' && (
              <div className="flex flex-col gap-4 relative animate-fadeIn">
                <ConnectionLines />
                <TournamentOperationsCards />
                <ActiveMatchStatus />
                <ActiveStreamsStatus />
              </div>
            )}
            {activeTab === 'registration' && (
              <div className="animate-fadeIn">
                <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-accentYellow/20 bg-accentYellow/5 px-4 py-3">
                  <div>
                    <p className="text-sm font-semibold text-white">Tournament registration</p>
                    <p className="mt-1 text-xs text-textDim">Create a tournament with the guided provider, Discord, registration, and AI setup.</p>
                  </div>
                  {canManageTournaments && (
                    <a
                      href="/admin/tournaments/new"
                      className="inline-flex min-h-11 items-center rounded-lg bg-accentYellow px-4 py-2.5 text-xs font-bold text-black transition hover:brightness-110"
                    >
                      + NEW TOURNAMENT WIZARD
                    </a>
                  )}
                </div>
                <TournamentSettings />
              </div>
            )}
            {activeTab === 'system' && (
              <div className="animate-fadeIn">
                <SettingsWorkspace />
              </div>
            )}
          </div>
        </div>

        {/* Middle Column (Match Dashboard) */}
        <div data-match-dashboard className="lg:col-span-3 lg:col-start-10 bg-cardDark rounded-lg shadow-md flex flex-col h-full border border-white/5 overflow-hidden">
          <div className="p-3 border-b border-white/10 flex items-center justify-between">
            <h2 className="text-accentYellow font-bold text-sm tracking-widest uppercase">Match Dashboard</h2>
            <button
              onClick={loadData}
              disabled={isRefetching}
              className={`p-1 hover:bg-white/5 rounded transition-colors ${isRefetching ? 'animate-spin opacity-50' : ''}`}
              title="Sync Matches with Provider"
              aria-label="Sync Matches with Provider"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="w-3.5 h-3.5 text-textDim">
                <path d="M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" />
              </svg>
            </button>
          </div>
          <MatchDashboard />
        </div>

      </main>

      <OrganizerConsole openRequest={consoleOpenRequest} />
    </div>
  );
}
