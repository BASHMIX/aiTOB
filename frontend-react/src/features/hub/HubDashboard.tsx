import { useEffect, useState, useCallback, useRef } from 'react';
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

// ── ComfyUI Bezier Node Connections ─────────────────────────────────────
function ConnectionLines() {
  const { matches } = useHubStore();
  const [lines, setLines] = useState<{ id: string; path: string }[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);

  // Connection exists if match is called/live and assigned to a station
  const activeMatches = matches.filter(
    (m) => (m.status === 'in_progress' || m.status === 'called') && m.station_id
  );

  const calculateLines = useCallback(() => {
    if (!containerRef.current) return;
    const containerRect = containerRef.current.getBoundingClientRect();
    const newLines: { id: string; path: string }[] = [];

    activeMatches.forEach((m) => {
      const matchEl = document.getElementById(`active-match-${m.set_id}`);
      const stationEl = document.getElementById(`station-${m.station_id}`);

      if (matchEl && stationEl) {
        const mRect = matchEl.getBoundingClientRect();
        const sRect = stationEl.getBoundingClientRect();

        // Start point: bottom center of the active match card
        const startX = (mRect.left + mRect.right) / 2 - containerRect.left;
        const startY = mRect.bottom - containerRect.top;

        // End point: top center of the station card
        const endX = (sRect.left + sRect.right) / 2 - containerRect.left;
        const endY = sRect.top - containerRect.top;

        // Curved Bezier node connection curve (down and then up)
        const cpY1 = startY + 60;
        const cpY2 = endY - 60;
        const path = `M ${startX} ${startY} C ${startX} ${cpY1}, ${endX} ${cpY2}, ${endX} ${endY}`;

        newLines.push({
          id: `${m.set_id}-${m.station_id}`,
          path,
        });
      }
    });

    // Check if lines actually changed to prevent state thrashing
    const serializedNew = JSON.stringify(newLines);
    const serializedOld = JSON.stringify(lines);
    if (serializedNew !== serializedOld) {
      setLines(newLines);
    }
  }, [activeMatches, lines]);

  useEffect(() => {
    calculateLines();

    if (!containerRef.current) return;
    
    // Listen to container resizing
    const observer = new ResizeObserver(() => {
      calculateLines();
    });
    observer.observe(containerRef.current);

    const handleScrollOrUpdate = () => {
      calculateLines();
    };

    // Listen to parent tab scroll container
    const scrollEl = containerRef.current.parentElement;
    if (scrollEl) {
      scrollEl.addEventListener('scroll', handleScrollOrUpdate);
    }
    
    window.addEventListener('resize', handleScrollOrUpdate);

    // Dynamic interval polling to keep paths aligned during animation expansions
    const iv = setInterval(calculateLines, 150);

    return () => {
      observer.disconnect();
      if (scrollEl) {
        scrollEl.removeEventListener('scroll', handleScrollOrUpdate);
      }
      window.removeEventListener('resize', handleScrollOrUpdate);
      clearInterval(iv);
    };
  }, [calculateLines]);

  return (
    <div ref={containerRef} className="absolute inset-0 pointer-events-none z-20">
      <svg className="w-full h-full absolute inset-0">
        <defs>
          <linearGradient id="flow-glow" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.85" />
            <stop offset="50%" stopColor="#eab308" stopOpacity="0.85" />
            <stop offset="100%" stopColor="#22c55e" stopOpacity="0.85" />
          </linearGradient>
          <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3.5" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>
        {lines.map((l) => (
          <g key={l.id}>
            {/* Background glowing line */}
            <path
              d={l.path}
              fill="none"
              stroke="#eab308"
              strokeWidth="5"
              strokeOpacity="0.18"
              filter="url(#glow)"
            />
            {/* Foreground node connection line with flow animation */}
            <path
              d={l.path}
              fill="none"
              stroke="url(#flow-glow)"
              strokeWidth="2.5"
              strokeDasharray="9,6"
              className="comfy-flow-line"
            />
          </g>
        ))}
      </svg>
      {/* Inline styles for the animated flow */}
      <style>{`
        @keyframes comfyFlow {
          to {
            stroke-dashoffset: -30;
          }
        }
        .comfy-flow-line {
          animation: comfyFlow 1.8s linear infinite;
        }
      `}</style>
    </div>
  );
}

// ── Main Dashboard ──────────────────────────────────────────────────────
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
      const [tourneysRes, matchesRes] = await Promise.all([
        axios.get('/api/tournaments'),
        axios.get('/api/active-matches'),
      ]);

      const tourneys = tourneysRes.data.tournaments || [];
      setTournaments(tourneys);

      const slug = currentSlug || localStorage.getItem('hub_current_slug');
      if (slug) {
        setMatches(matchesRes.data.matches || []);
      } else {
        setMatches([]);
      }

      if (!slug && tourneys.length > 0) {
        const preferred = tourneys.find((t: any) => t.slug?.toLowerCase() === PREFERRED_SLUG.toLowerCase());
        if (preferred) setCurrentSlug(preferred.slug);
        else setCurrentSlug(tourneys[0].slug);
      }

      try {
        const statusRes = await axios.get('/api/status');
        setStatus({
          startgg_api: statusRes.data.startgg_api,
          websockets: true,
          discord_bot: statusRes.data.discord_bot || false
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
    if (evt.type === 'match_update') {
      loadData();
    }
  }, [loadData]));

  useEffect(() => {
    loadData();
  }, []);

  return (
    <div className="flex flex-col gap-4 h-full relative">
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

          <div className="flex-1 overflow-y-auto pr-2 custom-scrollbar relative">
            {activeTab === 'active' && (
              <div className="flex flex-col gap-4 relative animate-fadeIn">
                <ConnectionLines />
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
        </div>
      </main>

      {/* Floating collapsible Bot Feed & Logs panel */}
      <BotFeed />
    </div>
  );
}
