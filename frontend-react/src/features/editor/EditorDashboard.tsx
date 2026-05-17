import { useEffect, useRef, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useEditorStore } from '@/store/useEditorStore';
import { Sidebar } from './components/Sidebar';
import { DraggableElement } from './components/DraggableElement';
import { TopBar } from './components/TopBar';
import { BottomBar } from './components/BottomBar';

export function EditorDashboard() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const slot = searchParams.get('slot') || 'default';
  
  const store = useEditorStore();
  const wsRef = useRef<WebSocket | null>(null);
  
  const [scale, setScale] = useState(1);
  const [autoScale, setAutoScale] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);
  const [contextMenu, setContextMenu] = useState<{x: number, y: number, id: string} | null>(null);
  
  const [presets, setPresets] = useState<{name: string, config: any}[]>([]);

  useEffect(() => {
    const handleGlobalClick = () => setContextMenu(null);
    window.addEventListener('click', handleGlobalClick);
    return () => window.removeEventListener('click', handleGlobalClick);
  }, []);

  const fetchPresets = async () => {
    try {
      const res = await axios.get('/api/overlays');
      const list = res.data.overlays || [];
      const parsed = list.map((o: any) => ({
        ...o,
        config: typeof o.config === 'string' ? JSON.parse(o.config) : o.config
      }));
      console.log(`Fetched ${parsed.length} presets. Current slot: ${slot}`);
      setPresets(parsed);
      
      // Load selected slot into canvas
      const currentPreset = parsed.find((p: any) => p.name === slot);
      console.log(`Current preset for ${slot}:`, currentPreset);
      if (currentPreset && currentPreset.config) {
        store.setElements(currentPreset.config.elements || {});
        store.setGlobalSettings(
          currentPreset.config.background_url || '', 
          currentPreset.config.global_font_url || '', 
          currentPreset.config.global_font_family || ''
        );
        store.setSelectedId(null);
      } else if (!currentPreset) {
        // If slot doesn't exist, clear canvas
        store.setElements({});
        store.setGlobalSettings('', '', '');
      }
    } catch (e) { console.error("Failed to fetch presets"); }
  };

  // Connection
  useEffect(() => {
    let ws: WebSocket;
    const connect = () => {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${proto}//${window.location.host}/ws/overlay/${encodeURIComponent(slot)}`;
      ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        store.setStatusMsg(`Live`);
        document.title = `Editor [${slot}]`;
      };
      
      ws.onclose = () => {
        store.setStatusMsg("Reconnecting...");
        setTimeout(connect, 3000);
      };

      let isInitialLoad = true;
      ws.onmessage = (e) => {
        const data = JSON.parse(e.data);
        // Important: Update store with incoming data from WS
        if (data.elements) {
          if (isInitialLoad) {
            store.setElements(data.elements);
            isInitialLoad = false;
          } else {
            store.mergeDynamicData(data.elements);
          }
        }
        store.setGlobalSettings(data.background_url || '', data.global_font_url || '', data.global_font_family || '');
      };
    };

    connect();
    fetchPresets();
    return () => {
      if (ws) {
        ws.onclose = null;
        ws.close();
      }
    };
  }, [slot]);

  // Scaling logic
  useEffect(() => {
    if (!autoScale) return;
    const handleResize = () => {
      if (containerRef.current) {
        const { clientWidth, clientHeight } = containerRef.current;
        const newScale = Math.min((clientWidth - 100) / 1920, (clientHeight - 100) / 1080);
        setScale(newScale);
      }
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [autoScale]);

  const handlePush = async () => {
    if (!slot) return;
    store.setStatusMsg('Saving...');
    try {
      const config = {
        elements: store.elements,
        background_url: store.background_url,
        global_font_url: store.global_font_url,
        global_font_family: store.global_font_family
      };
      await axios.post('/api/overlays', { name: slot, config });
      store.setStatusMsg('Saved');
      
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify(config));
      }
      fetchPresets(); // Refresh thumbnails
    } catch (e) {
      store.setStatusMsg('Save failed');
    }
  };

  const handleDeletePreset = async (name: string) => {
    if (!name || !confirm(`Delete '${name}'?`)) return;
    try {
      await axios.delete(`/api/overlays/${encodeURIComponent(name)}`);
      if (slot === name) navigate('/admin/editor'); // Redirect to default if deleting current
      fetchPresets();
    } catch (e) {
      alert("Delete failed");
    }
  };

  const handleRename = async (newName: string) => {
    if (newName === slot) return;
    try {
      await axios.post('/api/overlays/rename', { old_name: slot, new_name: newName });
      navigate(`/admin/editor?slot=${encodeURIComponent(newName)}`);
    } catch (e) {
      alert("Rename failed");
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
        slot={slot} 
        onRename={handleRename} 
        onSave={handlePush} 
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
                width: `${1920 * scale}px`,
                height: `${1080 * scale}px`,
                position: 'relative'
              }}
            >
              <div 
                className="absolute top-0 left-0 w-[1920px] h-[1080px] bg-checkerboard shadow-[0_0_50px_rgba(0,0,0,0.5)] origin-top-left transition-transform duration-300 overflow-hidden"
                style={{ 
                  transform: `scale(${scale})`,
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
                
                {Object.entries(store.elements)
              .sort((a, b) => (a[1].zIndex || 1) - (b[1].zIndex || 1))
              .map(([id, el]) => (
              <DraggableElement 
                key={id} 
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
      </div>

      <BottomBar 
        scale={scale} 
        onScaleChange={(s) => { setScale(s); setAutoScale(false); }}
        presets={presets}
        currentSlot={slot}
        onSelectPreset={(name) => navigate(`/admin/editor?slot=${encodeURIComponent(name)}`)}
        onNewPreset={() => {
          const name = prompt("New Preset Name:");
          if (name) navigate(`/admin/editor?slot=${encodeURIComponent(name)}`);
        }}
        onDeletePreset={handleDeletePreset}
      />

      {contextMenu && (
        <div 
          className="fixed bg-[#333] border border-[#555] rounded shadow-2xl py-1 z-[9999] min-w-[150px] text-xs"
          style={{ left: contextMenu.x, top: contextMenu.y }}
        >
          <button className="w-full text-left px-4 py-2 hover:bg-accentYellow hover:text-black" onClick={() => bringToFront(contextMenu.id)}>Bring to Front</button>
          <button className="w-full text-left px-4 py-2 hover:bg-accentYellow hover:text-black" onClick={() => sendToBack(contextMenu.id)}>Send to Back</button>
        </div>
      )}
    </div>
  );
}
