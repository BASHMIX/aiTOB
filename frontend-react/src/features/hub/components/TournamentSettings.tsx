import { useState } from 'react';
import { ParticipantsTable } from './ParticipantsTable';
import { useHubStore } from '@/store/useHubStore';
import axios from 'axios';

export function TournamentSettings() {
  const { currentSlug, setCurrentSlug } = useHubStore();
  const [slugInput, setSlugInput] = useState('');



  const addTournament = async () => {
    const slug = slugInput.trim();
    if (!slug) return;
    try {
      const res = await axios.post('/api/tournaments', { slug });
      setSlugInput('');
      
      const tourneysRes = await axios.get('/api/tournaments');
      const updatedTournaments = tourneysRes.data.tournaments || [];
      useHubStore.getState().setTournaments(updatedTournaments);
      
      // Always switch to the new one
      const added = updatedTournaments.find((t: any) => t.slug === slug);
      if (added) {
        setCurrentSlug(added.slug);
      } else if (updatedTournaments.length > 0) {
        setCurrentSlug(updatedTournaments[0].slug);
      }
      
      alert(res.data.message || "Tournament added.");
    } catch (e) {
      console.error(e);
      alert("Failed to add tournament. Check console for details.");
    }
  };

  const deleteTournament = async () => {
    if (!currentSlug) return;
    if (!confirm(`Are you sure you want to delete the tournament '${currentSlug}'?`)) return;
    try {
      await axios.delete(`/api/tournaments/${encodeURIComponent(currentSlug)}`);
      
      const tourneysRes = await axios.get('/api/tournaments');
      const updatedTournaments = tourneysRes.data.tournaments || [];
      useHubStore.getState().setTournaments(updatedTournaments);
      
      if (updatedTournaments.length > 0) {
        setCurrentSlug(updatedTournaments[0].slug);
      } else {
        setCurrentSlug(null);
      }
      alert("Tournament removed.");
    } catch (e) {
      console.error(e);
      alert("Failed to remove tournament.");
    }
  };

  const resetHubData = async () => {
    if (!currentSlug) return;
    if (!confirm(`⚠️ FORCE RESET ⚠️\n\nThis will wipe ALL local match data for '${currentSlug}'.\nUse this ONLY if you reset the bracket on Start.gg and want to start fresh.\n\nContinue?`)) return;
    try {
      await axios.post(`/api/tournaments/${encodeURIComponent(currentSlug)}/reset-hub`);
      alert("Hub data reset. The dashboard will now fetch fresh data from Start.gg.");
      globalRefresh();
    } catch (e) {
      console.error(e);
      alert("Reset failed.");
    }
  };

  const globalRefresh = async () => {
    try {
      const [tourneysRes, matchesRes] = await Promise.all([
        axios.get('/api/tournaments'),
        axios.get('/api/active-matches')
      ]);
      useHubStore.getState().setTournaments(tourneysRes.data.tournaments || []);
      useHubStore.getState().setMatches(matchesRes.data.matches || []);
    } catch (e) {
      console.error(e);
      alert("Refresh failed.");
    }
  };

  return (
    <div className="bg-cardDark rounded-lg p-4 shadow-md flex flex-col md:flex-row gap-6 border border-white/5">
      {/* Tournament Data Table */}
      <div className="flex-1 flex flex-col gap-3">
        <h2 className="text-accentYellow font-bold text-lg tracking-wide uppercase border-b border-white/10 pb-2">
          Tournament Data
        </h2>
        <div className="flex justify-between items-center bg-appDark p-2 rounded border border-white/10">
          <span className="text-sm font-mono truncate mr-2 text-textDim">
            {currentSlug ? `Active: ${currentSlug}` : 'No Tournament Selected'}
          </span>
          <div className="flex gap-2">
            <button 
              onClick={globalRefresh}
              className="bg-btnActive text-white text-xs px-3 py-1.5 rounded hover:bg-white/20 transition-colors flex items-center gap-1"
            >
              Refresh Hub
            </button>
            <button 
              onClick={async () => {
                if (!currentSlug) return;
                try {
                  const res = await axios.post(`/api/tournaments/${encodeURIComponent(currentSlug)}/refresh`);
                  alert(res.data.message);
                  globalRefresh();
                } catch (e) { alert("Refresh failed."); }
              }}
              className="bg-blue-900/50 text-blue-200 border border-blue-800 text-xs px-3 py-1.5 rounded hover:bg-blue-900 transition-colors flex items-center gap-1"
            >
              Refresh Metadata
            </button>
            <button 
              onClick={resetHubData}
              className="bg-orange-900/50 text-orange-200 border border-orange-800 text-xs px-3 py-1.5 rounded hover:bg-orange-900 transition-colors flex items-center gap-1"
            >
              Reset Hub Data
            </button>
            <button 
              onClick={deleteTournament}
              className="bg-red-900/50 text-red-200 border border-red-800 text-xs px-3 py-1.5 rounded hover:bg-red-900 transition-colors flex items-center gap-1"
            >
              Remove
            </button>
          </div>
        </div>
        <ParticipantsTable />
      </div>

      {/* Register Tournament */}
      <div className="md:w-1/3 flex flex-col gap-3 pl-0 md:pl-4 border-t md:border-t-0 md:border-l border-white/10 pt-4 md:pt-0">
        <h2 className="text-accentYellow font-bold text-lg tracking-wide uppercase border-b border-white/10 pb-2">
          Register Tournament
        </h2>
        <div className="text-sm mb-1 text-textDim">Start.gg Tournament Slug</div>
        <div className="flex gap-2">
          <input 
            className="w-full bg-appDark border border-white/10 rounded px-3 py-1.5 text-sm text-white focus:border-accentYellow focus:ring-1 focus:ring-accentYellow" 
            placeholder="e.g. tournament/slug" 
            type="text"
            value={slugInput}
            onChange={e => setSlugInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && addTournament()}
          />
          <button 
            onClick={addTournament}
            className="bg-btnActive text-white text-xs px-3 py-1.5 rounded hover:bg-white/20 transition-colors whitespace-nowrap"
          >
            Add
          </button>
        </div>
      </div>
    </div>
  );
}
