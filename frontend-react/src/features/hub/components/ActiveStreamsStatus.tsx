import { useEffect, useRef } from 'react';
import { useHubStore } from '@/store/useHubStore';
import { StationCard } from './StationCard';
import axios from 'axios';
import { usePermission } from '@/hooks/usePermission';

export function ActiveStreamsStatus() {
  const canManageStations = usePermission('station.manage');
  const canManageOverlays = usePermission('overlay.manage');
  const { stations, setStations } = useHubStore();
  const scrollRef = useRef<HTMLDivElement>(null);

  const loadStations = async () => {
    try {
      const res = await axios.get('/api/stations');
      setStations(res.data.stations || []);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadStations();
  }, []);

  const addStation = async () => {
    const name = prompt('Station name:');
    if (!name) return;
    const id = 'station_' + Date.now();
    await axios.post('/api/stations', { id, name });
    loadStations();
  };

  const scrollLeft = () => {
    scrollRef.current?.scrollBy({ left: -380, behavior: 'smooth' });
  };

  const scrollRight = () => {
    scrollRef.current?.scrollBy({ left: 380, behavior: 'smooth' });
  };

  return (
    <section className="bg-cardDark/50 rounded-lg p-4 shadow-md flex flex-col gap-3 border border-white/10 relative">
      <div className="flex justify-between items-center border-b border-white/10 pb-2 relative z-30 bg-[#161c28] -mx-2 px-3 pt-1 rounded-t">
        <div className="flex items-center gap-2">
          <h2 className="text-accentYellow font-bold text-lg tracking-wide uppercase">Active Streams Status</h2>
          {stations.length > 0 && (
            <span className="px-2 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-white/10 text-white border border-white/15">
              {stations.length} Station{stations.length > 1 ? 's' : ''}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 text-xs font-medium text-textDim">
          {stations.length > 2 && (
            <div className="flex items-center gap-1 bg-black/30 p-1 rounded-md border border-white/10 mr-1">
              <button
                type="button"
                onClick={scrollLeft}
                className="p-1 rounded text-textDim hover:text-white hover:bg-white/10 transition-colors"
                title="Scroll Left"
                aria-label="Scroll Left"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M15 19l-7-7 7-7" />
                </svg>
              </button>
              <button
                type="button"
                onClick={scrollRight}
                className="p-1 rounded text-textDim hover:text-white hover:bg-white/10 transition-colors"
                title="Scroll Right"
                aria-label="Scroll Right"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M9 5l7 7-7 7" />
                </svg>
              </button>
            </div>
          )}
          <button onClick={loadStations} className="hover:text-white transition-colors">Load Saved</button>
          {canManageStations && <button onClick={addStation} className="hover:text-white transition-colors font-bold text-accentYellow">+ Add Station</button>}
        </div>
      </div>
      <div
        ref={scrollRef}
        className="flex items-stretch gap-3.5 overflow-x-auto pb-2 scrollbar-none [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden snap-x scroll-smooth relative z-10"
      >
        {stations.length === 0 ? (
          <div className="w-full text-center py-6 px-4 text-textDim text-sm bg-black/10 rounded-lg border border-dashed border-white/10">
            No stations configured. Add a station to route video overlays.
          </div>
        ) : (
          stations.map(s => (
            <div key={s.id} className="min-w-[340px] sm:min-w-[380px] max-w-[440px] shrink-0 snap-start">
              <StationCard station={s} onReload={loadStations} canManageStations={canManageStations} canManageOverlays={canManageOverlays} />
            </div>
          ))
        )}
      </div>
    </section>
  );
}
