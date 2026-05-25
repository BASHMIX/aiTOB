import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { useEditorStore } from '@/store/useEditorStore';
import { Sidebar } from './components/Sidebar';
import { DraggableElement } from './components/DraggableElement';
import { TopBar } from './components/TopBar';
import { BottomBar } from './components/BottomBar';
import { LayersPanel } from './components/LayersPanel';

export function EditorDashboard() {
  const [searchParams] = useSearchParams();
  const stationId = searchParams.get('station_id') || 'station_1';
  
  const store = useEditorStore();
  const wsRef = useRef<WebSocket | null>(null);
  
  const [scale, setScale] = useState<number | null>(null);
  const [autoScale, setAutoScale] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);
  const [contextMenu, setContextMenu] = useState<{x: number, y: number, id: string} | null>(null);
  
  const [presets, setPresets] = useState<{name: string, config: any}[]>([]);
  const [activeOverlayName, setActiveOverlayName] = useState<string>('');
  
  // PowerPoint Slide Selection Modal states
  const [isLoadModalOpen, setIsLoadModalOpen] = useState(false);
  const [allSavedOverlays, setAllSavedOverlays] = useState<{name: string, config: any}[]>([]);

  useEffect(() => {
    const handleGlobalClick = () => setContextMenu(null);
    window.addEventListener('click', handleGlobalClick);
    return () => window.removeEventListener('click', handleGlobalClick);
  }, []);

  const fetchGlobalOverlays = async () => {
    try {
      const res = await axios.get('/api/overlays');
      const list = res.data.overlays || [];
      const parsed = list.map((o: any) => ({
        ...o,
        config: typeof o.config === 'string' ? JSON.parse(o.config) : o.config
      }));
      setAllSavedOverlays(parsed);
    } catch (e) {
      console.error("Failed to fetch global overlays", e);
    }
  };

  const fetchActiveMatch = async () => {
    try {
      const res = await axios.get('/api/active-matches');
      const matches = res.data.matches || [];
      const connectedMatch = matches.find((m: any) => m.station_id === stationId);
      store.setActiveMatch(connectedMatch || null);
    } catch (e) {
      console.error("Failed to fetch active match", e);
    }
  };

  const fetchPresets = async () => {
    try {
      // 1. Fetch station details to find active overlay and associated portfolio
      const resStations = await axios.get('/api/stations');
      const currentStation = (resStations.data.stations || []).find((s: any) => s.id === stationId);
      
      const loadedOverlayName = currentStation?.active_overlay || '';
      setActiveOverlayName(loadedOverlayName);
      
      const overlaysList = currentStation?.overlays || [];
      const associatedOverlayNames = new Set(overlaysList.map((o: any) => o.overlay_name));

      // 2. Fetch overlays configurations
      const resOverlays = await axios.get('/api/overlays');
      const list = resOverlays.data.overlays || [];
      const parsed = list.map((o: any) => ({
        ...o,
        config: typeof o.config === 'string' ? JSON.parse(o.config) : o.config
      }));

      // Filter presets list to only show the ones associated with the station
      const filtered = parsed.filter((o: any) => associatedOverlayNames.has(o.name));
      setPresets(filtered);
      
      // Auto-trigger the PowerPoint big load screen if station has no active overlay slide configured
      if (!loadedOverlayName) {
        setIsLoadModalOpen(true);
        fetchGlobalOverlays();
      }

      // Load active configuration into canvas
      if (loadedOverlayName) {
        const currentPreset = parsed.find((p: any) => p.name === loadedOverlayName);
        if (currentPreset && currentPreset.config) {
          store.setElements(currentPreset.config.elements || {});
          store.setGlobalSettings(
            currentPreset.config.background_url || '', 
            currentPreset.config.global_font_url || '', 
            currentPreset.config.global_font_family || ''
          );
          store.setSelectedId(null);
        } else {
          store.setElements({});
          store.setGlobalSettings('', '', '');
        }
      } else {
        store.setElements({});
        store.setGlobalSettings('', '', '');
      }
    } catch (e) {
      console.error("Failed to fetch presets", e);
    }
  };

  // Connection and Synchronization
  useEffect(() => {
    let ws: WebSocket;
    const connect = () => {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${proto}//${window.location.host}/ws/overlay/${encodeURIComponent(stationId)}`;
      ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        store.setStatusMsg(`Live [Station: ${stationId}]`);
        document.title = `Editor [${stationId}]`;
      };
      
      ws.onclose = () => {
        store.setStatusMsg("Reconnecting...");
        setTimeout(connect, 3000);
      };

      ws.onmessage = (e) => {
        const data = JSON.parse(e.data);
        
        // Handle real-time telemetry updates
        if (data.type === 'match_update') {
          fetchActiveMatch();
          return;
        }
        
        // Handle real-time layout loading from Hub switching
        if (data.type === 'overlay_loaded') {
          fetchPresets();
          return;
        }

        // Direct layout adjustments pushed from other Editors
        if (data.elements) {
          // Fully overwrite elements to reflect exact pixel coordinates pushed
          store.setElements(data.elements);
        }
        store.setGlobalSettings(data.background_url || '', data.global_font_url || '', data.global_font_family || '');
      };
    };

    connect();
    fetchPresets();
    fetchActiveMatch();
    fetchGlobalOverlays();
    
    return () => {
      if (ws) {
        ws.onclose = null;
        ws.close();
      }
    };
  }, [stationId]);

  // Scaling logic using ResizeObserver to ensure stable measurement on initial paint and reflows
  useEffect(() => {
    if (!autoScale) return;
    const container = containerRef.current;
    if (!container) return;

    const handleResize = () => {
      const { clientWidth, clientHeight } = container;
      if (clientWidth > 100 && clientHeight > 100) {
        const newScale = Math.min((clientWidth - 100) / 1920, (clientHeight - 100) / 1080);
        setScale(newScale);
      }
    };

    handleResize();

    const observer = new ResizeObserver(() => {
      handleResize();
    });
    observer.observe(container);

    window.addEventListener('resize', handleResize);
    return () => {
      observer.disconnect();
      window.removeEventListener('resize', handleResize);
    };
  }, [autoScale]);

  const handlePush = async () => {
    if (!activeOverlayName) {
      alert("No active overlay slide loaded. Please load an overlay template or create a new one first before saving.");
      return;
    }
    store.setStatusMsg('Saving...');
    try {
      // Fail-safe sanitization: Round all element coordinates and sizes to strict integers before saving
      const roundedElements = { ...store.elements };
      for (const id in roundedElements) {
        roundedElements[id] = {
          ...roundedElements[id],
          x: Math.round(roundedElements[id].x),
          y: Math.round(roundedElements[id].y),
          width: roundedElements[id].width ? Math.round(roundedElements[id].width) : undefined,
          height: roundedElements[id].height ? Math.round(roundedElements[id].height) : undefined,
        };
      }

      const config = {
        elements: roundedElements,
        background_url: store.background_url,
        global_font_url: store.global_font_url,
        global_font_family: store.global_font_family
      };

      // Save configuration in user overlays in DB
      await axios.post('/api/overlays', { name: activeOverlayName, config });
      
      // Auto-associate overlay preset with station if not already assigned
      const resStations = await axios.get('/api/stations');
      const currentStation = (resStations.data.stations || []).find((s: any) => s.id === stationId);
      const isAssigned = (currentStation?.overlays || []).some((o: any) => o.overlay_name === activeOverlayName);
      if (!isAssigned) {
        await axios.post(`/api/stations/${stationId}/overlays`, { overlay_name: activeOverlayName });
      }

      store.setStatusMsg('Saved');
      
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify(config));
      }
      fetchPresets(); // Refresh thumbnails
    } catch (e) {
      store.setStatusMsg('Save failed');
    }
  };

  const handleLoadGlobalOverlay = async (name: string) => {
    try {
      store.setStatusMsg('Loading slide...');
      // 1. Associate with station overlays portfolio
      await axios.post(`/api/stations/${stationId}/overlays`, { overlay_name: name });
      // 2. Set as active overlay
      await axios.post(`/api/stations/${stationId}/active-overlay`, { overlay_name: name });
      
      setIsLoadModalOpen(false);
      fetchPresets();
      store.setStatusMsg('Slide loaded');
    } catch (e) {
      console.error("Failed to load global overlay", e);
      store.setStatusMsg('Load failed');
    }
  };

  const handleDeletePreset = async (name: string) => {
    if (!name || !confirm(`Delete and disassociate '${name}'?`)) return;
    try {
      await axios.delete(`/api/stations/${stationId}/overlays/${encodeURIComponent(name)}`);
      await axios.delete(`/api/overlays/${encodeURIComponent(name)}`);
      if (activeOverlayName === name) {
        await axios.post(`/api/stations/${stationId}/active-overlay`, { overlay_name: null });
      }
      fetchPresets();
    } catch (e) {
      alert("Delete failed");
    }
  };

  const handleRename = async (newName: string) => {
    if (!activeOverlayName || newName === activeOverlayName) return;
    try {
      await axios.post('/api/overlays/rename', { old_name: activeOverlayName, new_name: newName });
      await axios.post(`/api/stations/${stationId}/active-overlay`, { overlay_name: newName });
      fetchPresets();
    } catch (e) {
      alert("Rename failed");
    }
  };

  const copyStyle = (id: string) => {
    const el = store.elements[id];
    if (el) {
      store.setClipboardStyle({
        fontSize: el.fontSize,
        color: el.color,
        borderRadius: el.borderRadius,
        width: el.width,
        height: el.height,
        zIndex: el.zIndex,
        fontWeight: el.fontWeight,
        fontStyle: el.fontStyle,
        textAlign: el.textAlign,
        strokeWidth: el.strokeWidth,
        strokeColor: el.strokeColor,
        shadowColor: el.shadowColor,
        shadowBlur: el.shadowBlur,
        shadowOffsetX: el.shadowOffsetX,
        shadowOffsetY: el.shadowOffsetY,
      });
      store.setStatusMsg("Style Copied 📋");
    }
  };

  const pasteStyle = (id: string) => {
    if (store.clipboardStyle) {
      store.updateElement(id, store.clipboardStyle);
      store.setStatusMsg("Style Pasted 📋");
    }
  };

  const copyPosition = (id: string) => {
    const el = store.elements[id];
    if (el) {
      store.setClipboardPosition({
        x: el.x,
        y: el.y,
      });
      store.setStatusMsg("Position Copied 📍");
    }
  };

  const pastePosition = (id: string) => {
    if (store.clipboardPosition) {
      store.updateElement(id, {
        x: store.clipboardPosition.x,
        y: store.clipboardPosition.y,
      });
      store.setStatusMsg("Position Pasted 📍");
    }
  };

  const bringToFront = (id: string) => {
    const maxZ = Math.max(0, ...Object.values(store.elements).map(el => el.zIndex || 1));
    store.updateElement(id, { zIndex: maxZ + 1 });
  };

  const sendToBack = (id: string) => {
    const minZ = Math.min(0, ...Object.values(store.elements).map(el => el.zIndex || 1));
    store.updateElement(id, { zIndex: minZ - 1 });
  };

  return (
    <div className="flex flex-col h-screen bg-[#1a1a1a] overflow-hidden text-white font-sans">
      <TopBar 
        slot={activeOverlayName || "No Slide Active"} 
        stationId={stationId}
        onRename={handleRename} 
        onSave={handlePush} 
        onLoadClick={() => {
          fetchGlobalOverlays();
          setIsLoadModalOpen(true);
        }}
        status={store.statusMsg} 
      />

      <div className="flex flex-grow overflow-hidden">
        <Sidebar onPush={handlePush} />
        
        <div 
          ref={containerRef}
          className="flex-grow overflow-auto bg-[#1a1a1a] relative flex flex-col"
          onClick={(e) => { if (e.target === containerRef.current) store.setSelectedId(null); }}
        >
          <div 
            className="flex-grow flex items-center justify-center p-8 min-w-max min-h-max"
            onClick={(e) => { if (e.target === e.currentTarget) store.setSelectedId(null); }}
          >
            <div 
              style={{
                width: `${1920 * (scale || 1)}px`,
                height: `${1080 * (scale || 1)}px`,
                position: 'relative'
              }}
            >
              <div 
                className="absolute top-0 left-0 w-[1920px] h-[1080px] bg-checkerboard shadow-[0_0_50px_rgba(0,0,0,0.5)] origin-top-left transition-transform duration-300 overflow-hidden"
                style={{ 
                  transform: `scale(${scale || 1})`,
                  fontFamily: store.global_font_family || 'inherit'
                }}
                onClick={(e) => { if (e.target === e.currentTarget) store.setSelectedId(null); }}
              >
                {store.background_url && (
                  <div 
                    className="absolute inset-0 bg-cover bg-center pointer-events-none"
                    style={{ backgroundImage: `url('${store.background_url}')` }}
                  />
                )}
                
                {scale !== null && Object.entries(store.elements)
                  .sort((a, b) => (a[1].zIndex || 1) - (b[1].zIndex || 1))
                  .map(([id, el]) => (
                    <DraggableElement 
                      key={`${activeOverlayName}_${id}`} 
                      id={id} 
                      element={el} 
                      scale={scale} 
                      onContextMenu={(e) => {
                        e.preventDefault();
                        store.setSelectedId(id);
                        setContextMenu({ x: e.clientX, y: e.clientY, id });
                      }}
                    />
                  ))}
              </div>
            </div>
          </div>
        </div>
        <LayersPanel />
      </div>

      <BottomBar 
        scale={scale || 1} 
        onScaleChange={(s) => { setScale(s); setAutoScale(false); }}
        presets={presets}
        currentSlot={activeOverlayName}
        onSelectPreset={async (name) => {
          store.setStatusMsg('Switching overlay...');
          try {
            await axios.post(`/api/stations/${stationId}/active-overlay`, { overlay_name: name });
            fetchPresets();
          } catch (e) {
            console.error("Failed to switch overlay", e);
            store.setStatusMsg('Failed to switch');
          }
        }}
        onNewPreset={async () => {
          const name = prompt("New Preset Name:");
          if (!name) return;
          try {
            await axios.post('/api/overlays', { 
              name, 
              config: { elements: {}, background_url: '', global_font_url: '', global_font_family: '' } 
            });
            await axios.post(`/api/stations/${stationId}/overlays`, { overlay_name: name });
            await axios.post(`/api/stations/${stationId}/active-overlay`, { overlay_name: name });
            fetchPresets();
          } catch (e) {
            console.error("Failed to create preset", e);
          }
        }}
        onDeletePreset={handleDeletePreset}
      />

      {/* Visual PowerPoint Slide Selection Modal */}
      {isLoadModalOpen && (
        <div className="fixed inset-0 bg-black/85 backdrop-blur-md flex items-center justify-center z-[99999] p-8 animate-fadeIn">
          <div className="bg-[#222] border border-white/10 rounded-2xl p-8 max-w-6xl w-full max-h-[85vh] flex flex-col relative shadow-2xl">
            {/* Close btn */}
            <button 
              onClick={() => setIsLoadModalOpen(false)}
              className="absolute top-6 right-6 w-10 h-10 rounded-full bg-white/5 border border-white/10 flex items-center justify-center hover:bg-red-500 hover:text-white transition-all text-lg font-bold text-white"
              title="Close modal"
            >
              ✕
            </button>

            <h2 className="text-[#00ffcc] text-2xl font-black uppercase tracking-wider mb-2">Load Overlay Slide</h2>
            <p className="text-[#aaa] text-sm mb-6">Select a saved overlay preset from the database to load onto this station ({stationId}).</p>

            <div className="flex-grow overflow-y-auto pr-2 grid grid-cols-1 md:grid-cols-3 gap-6">
              {allSavedOverlays.length === 0 ? (
                <div className="col-span-3 text-center py-20 text-white/40">
                  <p className="text-lg font-bold mb-2">No saved overlays found in DB</p>
                  <p className="text-xs">Create and save a layout in the editor first to populate this list.</p>
                </div>
              ) : (
                allSavedOverlays.map((o) => {
                  const elCount = Object.keys(o.config?.elements || {}).length;
                  return (
                    <div 
                      key={o.name}
                      onClick={() => handleLoadGlobalOverlay(o.name)}
                      className="border border-white/10 rounded-xl p-5 bg-[#2b2b2b] hover:border-[#00ffcc] hover:bg-[#333] transition-all cursor-pointer flex flex-col group relative shadow-md overflow-hidden"
                    >
                      <div className="absolute top-3 right-3 bg-[#00ffcc]/10 text-[#00ffcc] border border-[#00ffcc]/20 rounded-full px-2.5 py-0.5 text-[9px] font-bold uppercase tracking-wide">
                        {elCount} Elements
                      </div>
                      
                      {/* Slide Thumbnail Preview Grid */}
                      <div className="w-full h-28 bg-[#1a1a1a] rounded-lg border border-white/5 mb-4 relative flex flex-col items-center justify-center overflow-hidden">
                        {o.config?.background_url ? (
                          <div 
                            className="absolute inset-0 bg-cover bg-center opacity-40 pointer-events-none" 
                            style={{ backgroundImage: `url('${o.config.background_url}')` }} 
                          />
                        ) : (
                          <div className="absolute inset-0 bg-checkerboard opacity-25 pointer-events-none" />
                        )}
                        <span className="text-white/80 text-xs font-semibold z-10 group-hover:scale-105 transition-transform pointer-events-none">
                          {o.name}
                        </span>
                      </div>

                      <h3 className="font-bold text-white group-hover:text-[#00ffcc] transition-colors">{o.name}</h3>
                      <p className="text-[11px] text-[#aaa] mt-1 truncate pointer-events-none">
                        Font: {o.config?.global_font_family || 'System Default'}
                      </p>
                      
                      <button 
                        className="w-full mt-4 py-2 bg-[#00ffcc] text-[#111] font-bold rounded-lg text-xs uppercase tracking-wider hover:bg-[#00d4aa] transition-colors"
                      >
                        Load Slide
                      </button>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      )}

      {contextMenu && (
        <div 
          className="fixed bg-[#333] border border-[#555] rounded shadow-2xl py-1 z-[9999] min-w-[150px] text-xs"
          style={{ left: contextMenu.x, top: contextMenu.y }}
        >
          <button className="w-full text-left px-4 py-2 hover:bg-accentYellow hover:text-black" onClick={() => bringToFront(contextMenu.id)}>Bring to Front</button>
          <button className="w-full text-left px-4 py-2 hover:bg-accentYellow hover:text-black" onClick={() => sendToBack(contextMenu.id)}>Send to Back</button>
          <div className="h-px bg-white/10 my-1" />
          <button className="w-full text-left px-4 py-2 hover:bg-accentYellow hover:text-black" onClick={() => copyStyle(contextMenu.id)}>Copy Style</button>
          {store.clipboardStyle && (
            <button className="w-full text-left px-4 py-2 hover:bg-accentYellow hover:text-black" onClick={() => pasteStyle(contextMenu.id)}>Paste Style</button>
          )}
          <div className="h-px bg-white/10 my-1" />
          <button className="w-full text-left px-4 py-2 hover:bg-accentYellow hover:text-black" onClick={() => copyPosition(contextMenu.id)}>Copy Position</button>
          {store.clipboardPosition && (
            <button className="w-full text-left px-4 py-2 hover:bg-accentYellow hover:text-black" onClick={() => pastePosition(contextMenu.id)}>Paste Position</button>
          )}
        </div>
      )}
    </div>
  );
}
