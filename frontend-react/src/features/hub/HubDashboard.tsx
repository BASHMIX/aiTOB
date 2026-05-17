import { useEffect, useState, useCallback } from 'react';
import { TopNavigation } from '@/components/layout/TopNavigation';
import { TournamentSettings } from './components/TournamentSettings';
import { ActiveMatchStatus } from './components/ActiveMatchStatus';
import { ActiveStreamsStatus } from './components/ActiveStreamsStatus';
import { MatchDashboard } from './components/MatchDashboard';
import { Conflicts } from './components/Conflicts';
import { BotFeed } from './components/BotFeed';
import { GeneralSettings } from './components/GeneralSettings';
import { useHubStore } from '@/store/useHubStore';
import { useHubSocket } from '@/hooks/useHubSocket';
import axios from 'axios';

const PREFERRED_SLUG = 'FNC1stStartGG';

export function HubDashboard() {
  const {
    setTournaments,
    setStatus,
    setMatches,
    currentSlug,
    setCurrentSlug
  } = useHubStore();

  const [isRefetching, setIsRefetching] = useState(false);
  const [activeTab, setActiveTab] = useState<'active' | 'registration' | 'system'>('active');

  const loadData = useCallback(async () => {
    setIsRefetching(true);
    try {
      // Critical: load tournaments & matches (these always work)
      const [tourneysRes, matchesRes] = await Promise.all([
        axios.get('/api/tournaments'),
        axios.get('/api/active-matches'),
      ]);

      const tourneys = tourneysRes.data.tournaments || [];
      setTournaments(tourneys);

      // Only load matches if a tournament is selected
      const slug = currentSlug || localStorage.getItem('hub_current_slug');
      if (slug) {
        setMatches(matchesRes.data.matches || []);
      } else {
        setMatches([]);
      }

      // Auto-select: restore from localStorage or pick first
      if (!slug && tourneys.length > 0) {
        const preferred = tourneys.find((t: any) => t.slug?.toLowerCase() === PREFERRED_SLUG.toLowerCase());
        if (preferred) setCurrentSlug(preferred.slug);
        else setCurrentSlug(tourneys[0].slug);
      }

      // Best-effort: status & settings (404 won't break anything)
      try {
        const statusRes = await axios.get('/api/status');
        setStatus({
          startgg_api: statusRes.data.startgg_api,
          websockets: true,
          discord_bot: statusRes.data.discord_bot || false
        });
      } catch { /* /api/status not available yet */ }

      try {
        const settingsRes = await axios.get('/api/settings');
        const sets = settingsRes.data.settings || {};
        if (sets.current_theme) {
          document.documentElement.setAttribute('data-theme', sets.current_theme);
        }
      } catch { /* /api/settings not available yet */ }

    } catch (err) {
      console.error("Error fetching hub data", err);
    } finally {
      setIsRefetching(false);
    }
  }, [currentSlug, setCurrentSlug, setMatches, setStatus, setTournaments]);

  // ── WebSocket Integration ──
  useHubSocket(useCallback((evt) => {
    if (evt.type === 'match_update') {
      loadData();
    }
  }, [loadData]));

  useEffect(() => {
    loadData();
  }, []);

  return (
    <div className="flex flex-col gap-4 h-full">
      <header className="flex items-center justify-between gap-4 pb-2 border-b border-white/10">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded overflow-hidden flex items-center justify-center">
            <img src="/assets/favicon.ico" alt="Logo" className="w-full h-full object-contain" />
          </div>
          <div className="flex flex-col">
            <h1 className="text-2xl font-bold text-white tracking-wide">FNC Tournament Hub</h1>
            <span className="text-[10px] text-yellow-400/50 font-mono uppercase tracking-widest">Tournament Manager</span>
          </div>
        </div>
      </header>

      <TopNavigation />

      <main className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-4 items-start h-[calc(100vh-140px)]">
        {/* Left Column (Tabs) */}
        <div className="lg:col-span-6 xl:col-span-7 flex flex-col gap-4 h-full pb-10">
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
              SYSTEM
            </button>
          </div>

          <div className="flex-1 overflow-y-auto pr-2 custom-scrollbar">
            {activeTab === 'active' && (
              <div className="flex flex-col gap-4 animate-fadeIn">
                <ActiveMatchStatus />
                <ActiveStreamsStatus />
              </div>
            )}
            {activeTab === 'registration' && (
              <div className="animate-fadeIn">
                <TournamentSettings />
              </div>
            )}
            {activeTab === 'system' && (
              <div className="animate-fadeIn">
                <GeneralSettings />
              </div>
            )}
          </div>
        </div>

        {/* Middle Column (Match Dashboard) */}
        <div className="lg:col-span-3 bg-cardDark rounded-lg shadow-md flex flex-col h-full border border-white/5 overflow-hidden">
          <div className="p-3 border-b border-white/10 flex items-center justify-between">
            <h2 className="text-accentYellow font-bold text-sm tracking-widest uppercase">Match Dashboard</h2>
            <button
              onClick={loadData}
              disabled={isRefetching}
              className={`p-1 hover:bg-white/5 rounded transition-colors ${isRefetching ? 'animate-spin opacity-50' : ''}`}
              title="Refresh All Data"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="w-3.5 h-3.5 text-textDim">
                <path d="M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" />
              </svg>
            </button>
          </div>
          <MatchDashboard />
        </div>

        {/* Right Column */}
        <div className="lg:col-span-3 xl:col-span-2 flex flex-col gap-4 h-full pr-1">
          <Conflicts />
          <BotFeed />
        </div>
      </main>
    </div>
  );
}
