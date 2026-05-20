import { useEffect } from 'react';
import { useHubStore } from '@/store/useHubStore';
import { StationCard } from './StationCard';
import axios from 'axios';

export function ActiveStreamsStatus() {
  const { stations, setStations } = useHubStore();

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

  return (
    <section className="bg-cardDark/50 backdrop-blur-md rounded-lg p-4 shadow-md flex flex-col gap-3 border border-white/10 relative z-10">
      <div className="flex justify-between items-center border-b border-white/10 pb-2">
        <h2 className="text-accentYellow font-bold text-lg tracking-wide uppercase">Active Streams Status</h2>
        <div className="flex gap-3 text-xs font-medium text-textDim">
          <button onClick={loadStations} className="hover:text-white transition-colors">Load Saved</button>
          <button onClick={addStation} className="hover:text-white transition-colors">Add Station</button>
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {stations.length === 0 ? (
          <div className="text-center p-5 text-textDim text-sm col-span-full">No stations</div>
        ) : (
          stations.map(s => <StationCard key={s.id} station={s} onReload={loadStations} />)
        )}
      </div>
    </section>
  );
}
