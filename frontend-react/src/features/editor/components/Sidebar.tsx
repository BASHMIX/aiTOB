import { useState, useEffect } from 'react';
import { useEditorStore } from '@/store/useEditorStore';
import axios from 'axios';

export function Sidebar({ onPush }: { onPush: () => void }) {
  const store = useEditorStore();
  const [profiles, setProfiles] = useState<string[]>([]);
  const [saveName, setSaveName] = useState('');
  const [selectedProfile, setSelectedProfile] = useState('');
  const [addId, setAddId] = useState('');
  const [isCollapsed, setIsCollapsed] = useState(false);

  const loadProfiles = async () => {
    try {
      const res = await axios.get('/api/overlays');
      setProfiles((res.data.overlays || []).map((o: any) => o.name));
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => { loadProfiles(); }, []);

  const saveProfile = async () => {
    if (!saveName.trim()) return;
    await axios.post('/api/overlays', { 
      name: saveName.trim(), 
      config: {
        elements: store.elements,
        background_url: store.background_url,
        global_font_url: store.global_font_url,
        global_font_family: store.global_font_family
      }
    });
    store.setStatusMsg(`Saved '${saveName}'`);
    loadProfiles();
  };

  const loadProfile = async () => {
    if (!selectedProfile) return;
    const res = await axios.get('/api/overlays');
    const profile = res.data.overlays.find((o: any) => o.name === selectedProfile);
    if (profile) {
      const cfg = JSON.parse(profile.config);
      store.setElements(cfg.elements || {});
      store.setGlobalSettings(cfg.background_url || '', cfg.global_font_url || '', cfg.global_font_family || '');
      store.setSelectedId(null);
    }
  };

  const deleteProfile = async () => {
    if (!selectedProfile || !confirm(`Delete '${selectedProfile}'?`)) return;
    await axios.delete(`/api/overlays/${encodeURIComponent(selectedProfile)}`);
    loadProfiles();
  };

  const selId = store.selectedId;
  const selEl = selId ? store.elements[selId] : null;

  // Handle global keydown for delete
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return;
      if ((e.key === 'Delete' || e.key === 'Backspace') && store.selectedId) {
        store.deleteElement(store.selectedId);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [store.selectedId]);

  const handleWheel = (e: React.WheelEvent<HTMLInputElement>, field: string, currentValue: any) => {
    if (!selId) return;
    const current = parseFloat(currentValue) || 0;
    const delta = e.deltaY < 0 ? 1 : -1;
    const step = e.shiftKey ? 10 : 1;
    store.updateElement(selId, { [field]: current + (delta * step) });
  };

  return (
    <div 
      className={`bg-[#2b2b2b] flex flex-col h-screen text-white text-[13px] transition-all duration-300 ease-in-out relative ${
        isCollapsed ? 'w-[64px] min-w-[64px] items-center px-2' : 'w-[360px] min-w-[360px] p-4'
      } overflow-y-auto overflow-x-hidden`}
    >
      <button 
        className={`absolute top-4 right-4 text-[#00ffcc] hover:text-white transition-transform duration-300 z-10 flex items-center justify-center w-8 h-8 rounded bg-[#333] hover:bg-[#444]`}
        style={{ transform: isCollapsed ? 'rotate(180deg)' : 'rotate(0deg)' }}
        onClick={() => setIsCollapsed(!isCollapsed)}
        title="Toggle Sidebar"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M15 18l-6-6 6-6" />
        </svg>
      </button>

      {/* COLLAPSED VIEW: Only Icons */}
      {isCollapsed && (
        <div className="flex flex-col gap-8 mt-16 items-center w-full">
          <button title="Layout Profiles" onClick={() => setIsCollapsed(false)} className="text-2xl hover:scale-110 transition-transform">📁</button>
          <button title="Global Settings" onClick={() => setIsCollapsed(false)} className="text-2xl hover:scale-110 transition-transform">⚙️</button>
          <button title="Add Elements" onClick={() => setIsCollapsed(false)} className="text-2xl hover:scale-110 transition-transform">➕</button>
          <button title="Element Settings" onClick={() => setIsCollapsed(false)} className="text-2xl hover:scale-110 transition-transform">✏️</button>
          <div className="flex-grow"></div>
          <button title="Push to OBS" onClick={onPush} className="text-2xl hover:scale-110 transition-transform mb-4">⬆️</button>
        </div>
      )}

      {/* EXPANDED VIEW: Full Form */}
      <div className={`flex flex-col w-full transition-opacity duration-300 ${isCollapsed ? 'opacity-0 hidden' : 'opacity-100'}`}>
        <h2 className="text-[#00ffcc] uppercase tracking-wide mb-3 font-bold pr-10">Layout Profiles</h2>
        <label className="text-[11px] text-[#999] uppercase tracking-wide mb-1 block">Save Current Layout</label>
        <div className="flex gap-2 mb-3">
          <input className="flex-1 bg-[#3a3a3a] border border-[#555] rounded px-2 py-1.5 focus:border-[#00ffcc] outline-none" placeholder="Profile name..." value={saveName} onChange={e => setSaveName(e.target.value)} />
          <button className="bg-[#00ffcc] text-[#111] font-bold px-4 rounded hover:bg-[#00d4aa]" onClick={saveProfile}>Save</button>
        </div>
        <label className="text-[11px] text-[#999] uppercase tracking-wide mb-1 block">Load / Delete</label>
        <div className="flex gap-2 mb-3">
          <select className="flex-1 bg-[#3a3a3a] border border-[#555] rounded px-2 py-1.5 focus:border-[#00ffcc] outline-none" value={selectedProfile} onChange={e => setSelectedProfile(e.target.value)}>
            <option value="">-- Profiles --</option>
            {profiles.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
          <button className="bg-[#00ffcc] text-[#111] font-bold px-3 rounded hover:bg-[#00d4aa]" onClick={loadProfile}>Load</button>
          <button className="bg-[#ff4444] text-white font-bold px-3 rounded hover:bg-[#cc2222]" onClick={deleteProfile}>🗑️</button>
        </div>
        <hr className="border-[#3a3a3a] my-3" />

        <h2 className="text-[#00ffcc] uppercase tracking-wide mb-3 font-bold">Global Settings</h2>
        <label className="text-[11px] text-[#999] uppercase tracking-wide mb-1 block">Background Image URL</label>
        <input className="w-full bg-[#3a3a3a] border border-[#555] rounded px-2 py-1.5 mb-3 focus:border-[#00ffcc] outline-none" placeholder="https://..." value={store.background_url} onChange={e => store.setGlobalSettings(e.target.value, store.global_font_url, store.global_font_family)} />
        
        <label className="text-[11px] text-[#999] uppercase tracking-wide mb-1 block">Google Font URL</label>
        <input className="w-full bg-[#3a3a3a] border border-[#555] rounded px-2 py-1.5 mb-3 focus:border-[#00ffcc] outline-none" placeholder="https://..." value={store.global_font_url} onChange={e => store.setGlobalSettings(store.background_url, e.target.value, store.global_font_family)} />
        
        <label className="text-[11px] text-[#999] uppercase tracking-wide mb-1 block">Font Family</label>
        <input className="w-full bg-[#3a3a3a] border border-[#555] rounded px-2 py-1.5 mb-3 focus:border-[#00ffcc] outline-none" placeholder="'Cairo', sans-serif" value={store.global_font_family} onChange={e => store.setGlobalSettings(store.background_url, store.global_font_url, e.target.value)} />
        <hr className="border-[#3a3a3a] my-3" />

        <h2 className="text-[#00ffcc] uppercase tracking-wide mb-3 font-bold">Add Elements</h2>
        <div className="flex gap-2 mb-3">
          <select className="flex-1 bg-[#3a3a3a] border border-[#555] rounded px-2 py-1.5 focus:border-[#00ffcc] outline-none" value={addId} onChange={e => setAddId(e.target.value)}>
            <option value="">-- Hidden / Deleted Elements --</option>
            {['p1_name', 'p2_name', 'p1_score', 'p2_score', 'p1_team', 'p2_team', 'tournament_round', 'tournament_name', 'p1_avatar', 'p2_avatar', 'p1_flag', 'p2_flag']
              .filter(id => !store.elements[id] || !store.elements[id].visible)
              .map((id) => (
                <option key={id} value={id}>{id}</option>
            ))}
          </select>
          <button 
            className="bg-[#00ffcc] text-[#111] font-bold px-3 rounded hover:bg-[#00d4aa]" 
            onClick={() => { if (addId) store.restoreElement(addId); }}
          >+ Add</button>
        </div>
        <hr className="border-[#3a3a3a] my-3" />

        <h2 className="text-[#00ffcc] uppercase tracking-wide mb-3 font-bold">Element Settings</h2>
        {!selEl || !selId ? (
          <p className="text-[#666] text-[12px]">Click an element on the canvas.</p>
        ) : (
          <div className="flex flex-col">
            <label className="text-[11px] text-[#999] uppercase tracking-wide mb-1 block">ID</label>
            <input className="w-full bg-[#222] border border-[#555] rounded px-2 py-1.5 mb-3 text-[#aaa]" readOnly value={selId} />

            {selEl.type === 'text' && (
              <>
                <label className="text-[11px] text-[#999] uppercase tracking-wide mb-1 block">Text</label>
                <input className="w-full bg-[#3a3a3a] border border-[#555] rounded px-2 py-1.5 mb-3" value={selEl.text} onChange={e => store.updateElement(selId, { text: e.target.value })} />
                
                <label className="text-[11px] text-[#999] uppercase tracking-wide mb-1 block">Font Size (px)</label>
                <input type="number" className="w-full bg-[#3a3a3a] border border-[#555] rounded px-2 py-1.5 mb-3" value={selEl.fontSize} onChange={e => store.updateElement(selId, { fontSize: parseFloat(e.target.value) })} onWheel={e => handleWheel(e, 'fontSize', selEl.fontSize)} />
                
                <label className="text-[11px] text-[#999] uppercase tracking-wide mb-1 block">Color</label>
                <input type="color" className="w-full h-[38px] p-1 bg-[#3a3a3a] border border-[#555] rounded mb-3 cursor-pointer" value={selEl.color} onChange={e => store.updateElement(selId, { color: e.target.value })} />
              </>
            )}

            {selEl.type === 'image' && (
              <>
                <label className="text-[11px] text-[#999] uppercase tracking-wide mb-1 block">Image URL / Path</label>
                <input className="w-full bg-[#3a3a3a] border border-[#555] rounded px-2 py-1.5 mb-3" value={selEl.src} onChange={e => store.updateElement(selId, { src: e.target.value })} />
                
                <div className="flex gap-2 mb-3">
                  <div className="flex-1">
                    <label className="text-[11px] text-[#999] uppercase tracking-wide mb-1 block">Width (px)</label>
                    <input type="number" className="w-full bg-[#3a3a3a] border border-[#555] rounded px-2 py-1.5" value={selEl.width} onChange={e => store.updateElement(selId, { width: parseFloat(e.target.value) })} onWheel={e => handleWheel(e, 'width', selEl.width)} />
                  </div>
                  <div className="flex-1">
                    <label className="text-[11px] text-[#999] uppercase tracking-wide mb-1 block">Height (px)</label>
                    <input type="number" className="w-full bg-[#3a3a3a] border border-[#555] rounded px-2 py-1.5" value={selEl.height} onChange={e => store.updateElement(selId, { height: parseFloat(e.target.value) })} onWheel={e => handleWheel(e, 'height', selEl.height)} />
                  </div>
                </div>
              </>
            )}

            <div className="flex gap-2 mb-4">
              <div className="flex-1">
                <label className="text-[11px] text-[#999] uppercase tracking-wide mb-1 block">X Position</label>
                <input type="number" className="w-full bg-[#3a3a3a] border border-[#555] rounded px-2 py-1.5" value={Math.round(selEl.x)} onChange={e => store.updateElement(selId, { x: parseFloat(e.target.value) })} onWheel={e => handleWheel(e, 'x', selEl.x)} />
              </div>
              <div className="flex-1">
                <label className="text-[11px] text-[#999] uppercase tracking-wide mb-1 block">Y Position</label>
                <input type="number" className="w-full bg-[#3a3a3a] border border-[#555] rounded px-2 py-1.5" value={Math.round(selEl.y)} onChange={e => store.updateElement(selId, { y: parseFloat(e.target.value) })} onWheel={e => handleWheel(e, 'y', selEl.y)} />
              </div>
            </div>

            <button className="bg-[#ff4444] text-white font-bold py-2 rounded hover:bg-[#cc2222]" onClick={() => store.deleteElement(selId)}>🗑️ Remove Element</button>
          </div>
        )}
        <hr className="border-[#3a3a3a] my-4" />

        <button className="bg-[#00ffcc] text-[#111] font-bold py-3 rounded hover:bg-[#00d4aa] text-[14px]" onClick={onPush}>⬆ Push to OBS</button>
        <p className="text-[11px] text-[#888] text-center mt-3">{store.statusMsg}</p>
      </div>
    </div>
  );
}
