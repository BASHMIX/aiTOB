import axios from 'axios';

export function StationCard({ station, onReload }: { station: any, onReload: () => void }) {
  
  const removeStation = async () => {
    if (!confirm('Remove station?')) return;
    await axios.delete(`/api/stations/${station.id}`);
    onReload();
  };

  const removeOverlay = async (overlayName: string) => {
    await axios.delete(`/api/stations/${station.id}/overlays/${overlayName}`);
    onReload();
  };

  const addOverlay = async () => {
    try {
      const res = await axios.get('/api/overlays');
      const names = (res.data.overlays || []).map((o: any) => o.name);
      const name = prompt('Overlay name to add:\n' + names.join(', '));
      if (!name) return;
      await axios.post(`/api/stations/${station.id}/overlays`, { overlay_name: name });
      onReload();
    } catch (e) {
      console.error(e);
    }
  };

  const renameStation = async (newName: string) => {
    if (!newName.trim()) return;
    await axios.patch(`/api/stations/${station.id}`, { name: newName.trim() });
  };

  const copyLink = () => {
    navigator.clipboard.writeText(`${location.origin}/obs?slot=${station.id}`);
    alert('OBS link copied!');
  };

  return (
    <div id={`station-${station.id}`} className="border border-white/20 rounded-lg p-3 bg-appDark">
      <div className="flex justify-between items-center mb-3 pb-2 border-b border-white/10">
        <div className="flex items-center gap-2">
          <span className="text-white">📺</span>
          <h3 
            className="font-bold text-white focus:outline-none focus:border-b" 
            contentEditable 
            suppressContentEditableWarning
            onBlur={(e) => renameStation(e.currentTarget.textContent || '')}
          >
            {station.name}
          </h3>
        </div>
        <div className="flex gap-2 text-textDim">
          <button onClick={() => window.open(`/admin/editor?slot=${station.id}`)} className="hover:text-white">Edit</button>
          <button onClick={removeStation} className="hover:text-statusRed">🗑</button>
        </div>
      </div>
      <div className="text-xs text-center text-textDim mb-2">Stream Overlays</div>
      <ul className="flex flex-col gap-2 text-sm text-white">
        {(station.overlays || []).map((o: any) => (
          <li key={o.overlay_name} className="flex justify-between items-center group border-t border-white/5 pt-2">
            <span>{o.overlay_name}</span>
            <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
              <button onClick={() => removeOverlay(o.overlay_name)} className="text-statusRed hover:text-red-400">✖</button>
              <button onClick={copyLink} className="text-textDim hover:text-white">📋</button>
              <button onClick={() => window.open(`/admin/editor?slot=${station.id}`)} className="text-textDim hover:text-white">✏️</button>
            </div>
          </li>
        ))}
      </ul>
      <button 
        onClick={addOverlay} 
        className="w-full mt-3 py-1.5 text-xs text-textDim hover:text-white border border-dashed border-white/20 rounded flex justify-center items-center gap-1 transition-colors"
      >
        <span>+ Add Overlay</span>
      </button>
    </div>
  );
}
