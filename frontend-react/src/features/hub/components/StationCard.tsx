import axios from 'axios';
import { useState } from 'react';
import { StationSettingsModal } from './StationSettingsModal';

export function StationCard({ station, onReload }: { station: any, onReload: () => void }) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  
  const removeStation = async () => {
    if (!confirm('Remove station?')) return;
    await axios.delete(`/api/stations/${station.id}`);
    onReload();
  };

  const removeOverlay = async (overlayName: string) => {
    await axios.delete(`/api/stations/${station.id}/overlays/${overlayName}`);
    
    // If the removed overlay was active, unset it
    if (station.active_overlay === overlayName) {
      await axios.post(`/api/stations/${station.id}/active-overlay`, { overlay_name: null });
    }
    onReload();
  };

  const addOverlay = async () => {
    try {
      const res = await axios.get('/api/overlays');
      const names = (res.data.overlays || []).map((o: any) => o.name);
      const name = prompt('Overlay name to add to this station:\n' + names.join(', '));
      if (!name) return;
      await axios.post(`/api/stations/${station.id}/overlays`, { overlay_name: name });
      
      // Auto-activate if no overlay is currently active
      if (!station.active_overlay) {
        await axios.post(`/api/stations/${station.id}/active-overlay`, { overlay_name: name });
      }
      onReload();
    } catch (e) {
      console.error(e);
    }
  };

  const loadOverlay = async () => {
    try {
      const res = await axios.get('/api/overlays');
      const names = (res.data.overlays || []).map((o: any) => o.name);
      if (names.length === 0) {
        alert("No overlays found. Open the editor to create and save a new overlay template!");
        return;
      }
      const name = prompt(`Select overlay preset to load on ${station.name}:\n` + names.join(', '));
      if (!name) return;
      
      if (!names.includes(name)) {
        alert("Selected overlay does not exist.");
        return;
      }

      // Associate overlay first if not already associated
      const alreadyAssigned = (station.overlays || []).some((o: any) => o.overlay_name === name);
      if (!alreadyAssigned) {
        await axios.post(`/api/stations/${station.id}/overlays`, { overlay_name: name });
      }
      
      // Load active overlay
      await axios.post(`/api/stations/${station.id}/active-overlay`, { overlay_name: name });
      onReload();
    } catch (e) {
      console.error(e);
    }
  };

  const activateOverlay = async (name: string) => {
    try {
      await axios.post(`/api/stations/${station.id}/active-overlay`, { overlay_name: name });
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
          <button
            onClick={() => setSettingsOpen(true)}
            title="Station settings (stream, bot, overlay)"
            className="hover:text-white"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
              <circle cx="12" cy="12" r="3"></circle>
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
            </svg>
          </button>
          <button onClick={() => window.open(`/admin/editor?station_id=${station.id}`)} className="hover:text-white">Edit</button>
          <button onClick={removeStation} className="hover:text-statusRed">🗑</button>
        </div>
      </div>
      <div className="text-xs text-center text-textDim mb-2">Stream Overlays</div>
      <ul className="flex flex-col gap-2 text-sm text-white">
        {(station.overlays || []).map((o: any) => {
          const isActive = station.active_overlay === o.overlay_name;
          return (
            <li key={o.overlay_name} className="flex justify-between items-center group border-t border-white/5 pt-2">
              <button 
                onClick={() => activateOverlay(o.overlay_name)}
                className={`font-semibold transition-colors flex items-center gap-1.5 ${
                  isActive ? 'text-[#00ffcc] hover:text-[#00d4aa]' : 'text-textDim hover:text-white'
                }`}
                title="Click to activate/load this overlay on stream"
              >
                <span>{isActive ? '🟢' : '⚫'}</span>
                <span>{o.overlay_name}</span>
              </button>
              <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                <button onClick={() => removeOverlay(o.overlay_name)} className="text-statusRed hover:text-red-400">✖</button>
                <button onClick={copyLink} className="text-textDim hover:text-white">📋</button>
                <button onClick={() => window.open(`/admin/editor?station_id=${station.id}`)} className="text-textDim hover:text-white">✏️</button>
              </div>
            </li>
          );
        })}
      </ul>
      <div className="flex gap-2 mt-3">
        <button
          onClick={addOverlay}
          className="flex-1 py-1.5 text-xs text-textDim hover:text-white border border-dashed border-white/20 rounded flex justify-center items-center gap-1 transition-colors"
        >
          <span>+ Add</span>
        </button>
        <button
          onClick={loadOverlay}
          className="flex-1 py-1.5 text-xs text-textDim hover:text-white border border-dashed border-white/20 rounded flex justify-center items-center gap-1 transition-colors"
          title="Load existing saved overlay onto this station"
        >
          <span>📂 Load</span>
        </button>
      </div>

      {settingsOpen && (
        <StationSettingsModal
          station={station}
          onClose={() => setSettingsOpen(false)}
          onSaved={onReload}
        />
      )}
    </div>
  );
}
