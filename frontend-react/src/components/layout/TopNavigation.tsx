import { useState } from 'react';
import { useHubStore } from '@/store/useHubStore';
import axios from 'axios';

export function TopNavigation() {
  const { tournaments, setTournaments, currentSlug, setCurrentSlug, status, setMatches } = useHubStore();
  const [isRefreshing, setIsRefreshing] = useState(false);

  const globalRefresh = async () => {
    setIsRefreshing(true);
    try {
      const [tourneysRes, matchesRes] = await Promise.all([
        axios.get('/api/tournaments'),
        axios.get('/api/active-matches')
      ]);
      setTournaments(tourneysRes.data.tournaments || []);
      setMatches(matchesRes.data.matches || []);
    } catch (err) {
      console.error("Manual refresh failed", err);
    } finally {
      setIsRefreshing(false);
    }
  };

  const deleteTournament = async () => {
    if (!currentSlug || !confirm(`Are you sure you want to delete the tournament '${currentSlug}'?`)) return;
    try {
      await axios.delete(`/api/tournaments/${currentSlug}`);
      // Refresh the tournament list from the server to be sure
      const tourneysRes = await axios.get('/api/tournaments');
      const updatedTournaments = tourneysRes.data.tournaments || [];
      setTournaments(updatedTournaments);
      
      // Select the next available or null
      if (updatedTournaments.length > 0) {
        setCurrentSlug(updatedTournaments[0].slug);
      } else {
        setCurrentSlug(null);
      }
    } catch (err) {
      console.error("Failed to delete tournament", err);
      alert("Failed to delete tournament.");
    }
  };

  const logout = useHubStore(state => state.logout);

  return (
    <nav className="bg-cardDark rounded-md p-3 flex flex-wrap items-center justify-between gap-4 text-sm shadow-md">
      <div className="flex items-center gap-4 font-medium text-white">
        <button 
          onClick={logout}
          className="text-textDim hover:text-accentYellow transition-colors flex items-center gap-2"
        >
          <span>🚪</span> Logout
        </button>
        <div className="flex items-center gap-2 border-l border-white/20 pl-4">
          <span>Tournament:</span>
          <select 
            className="bg-transparent border-none text-white focus:ring-0 text-sm p-0 cursor-pointer hover:text-accentYellow font-bold"
            value={currentSlug || ''}
            onChange={(e) => setCurrentSlug(e.target.value)}
          >
            <option className="text-black" value="">[ Select Tournament ▼ ]</option>
            {tournaments.map((t) => (
              <option key={t.slug} className="text-black" value={t.slug}>
                [ {t.name} ▼ ]
              </option>
            ))}
          </select>
          {currentSlug && (
            <div className="flex items-center gap-2 ml-2">
              <button 
                onClick={globalRefresh}
                disabled={isRefreshing}
                className={`text-textDim hover:text-accentYellow transition-colors ${isRefreshing ? 'animate-spin' : ''}`}
                title="Refresh All Data"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="w-4 h-4">
                  <path d="M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" />
                </svg>
              </button>
              <button 
                onClick={deleteTournament}
                className="text-[#ff4444] hover:text-[#cc2222] transition-colors"
                title="Delete Tournament"
              >
                🗑️
              </button>
            </div>
          )}
        </div>
        <a className="border-l border-white/20 pl-4 hover:text-accentYellow transition-colors" href="#">Settings</a>
      </div>
      
      <div className="flex items-center gap-4 font-mono text-xs">
        <span className="text-textDim">Status:</span>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${status.startgg_api ? 'bg-statusGreen shadow-[0_0_8px_rgba(34,197,94,0.4)]' : 'bg-statusRed shadow-[0_0_8px_rgba(239,68,68,0.4)]'}`}></span>
          <span>Start.gg</span>
        </div>
        <div className="flex items-center gap-2 border-l border-white/20 pl-4">
          <span className={`w-2 h-2 rounded-full ${status.discord_bot ? 'bg-statusGreen shadow-[0_0_8px_rgba(34,197,94,0.4)]' : 'bg-statusRed shadow-[0_0_8px_rgba(239,68,68,0.4)]'}`}></span>
          <span>Bot</span>
        </div>
        <div className="flex items-center gap-2 border-l border-white/20 pl-4">
          <span className={`w-2 h-2 rounded-full ${status.websockets ? 'bg-statusGreen shadow-[0_0_8px_rgba(34,197,94,0.4)]' : 'bg-statusRed shadow-[0_0_8px_rgba(239,68,68,0.4)]'}`}></span>
          <span>WS</span>
        </div>
      </div>
    </nav>
  );
}
