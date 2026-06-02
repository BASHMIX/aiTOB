import { useEffect, useState, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { useEditorStore } from '@/store/useEditorStore';
import { Sidebar } from './components/Sidebar';
import { DraggableElement } from './components/DraggableElement';
import { TopBar } from './components/TopBar';
import { BottomBar } from './components/BottomBar';
import { LayersPanel } from './components/LayersPanel';
import { LoadOverlayModal } from './components/LoadOverlayModal';
import { EditorContextMenu } from './components/EditorContextMenu';
import { useEditorData } from './hooks/useEditorData';
import { useEditorWebSocket } from './hooks/useEditorWebSocket';
import { useEditorScale } from './hooks/useEditorScale';
import { useContextMenuActions } from './hooks/useContextMenuActions';

export function EditorDashboard() {
  const [searchParams] = useSearchParams();
  const stationId = searchParams.get('station_id') || 'station_1';
  
  const store = useEditorStore();
  const [contextMenu, setContextMenu] = useState<{x: number, y: number, id: string} | null>(null);

  const wsRef = useRef<WebSocket | null>(null);

  const { scale, setScale, setAutoScale, containerRef } = useEditorScale();

  const {
    copyStyle, pasteStyle, copyPosition, pastePosition, bringToFront, sendToBack
  } = useContextMenuActions();

  const {
    presets,
    activeOverlayName,
    isLoadModalOpen,
    setIsLoadModalOpen,
    allSavedOverlays,
    fetchGlobalOverlays,
    fetchActiveMatch,
    fetchPresets,
    handlePush,
    handleLoadGlobalOverlay,
    handleDeletePreset,
    handleRename
  } = useEditorData(stationId, wsRef);

  useEditorWebSocket(stationId, wsRef, fetchActiveMatch, fetchPresets);

  useEffect(() => {
    fetchGlobalOverlays();
  }, [fetchGlobalOverlays]);

  useEffect(() => {
    const handleGlobalClick = () => setContextMenu(null);
    window.addEventListener('click', handleGlobalClick);
    return () => window.removeEventListener('click', handleGlobalClick);
  }, []);

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

      <LoadOverlayModal
        isOpen={isLoadModalOpen}
        onClose={() => setIsLoadModalOpen(false)}
        stationId={stationId}
        allSavedOverlays={allSavedOverlays}
        onLoad={handleLoadGlobalOverlay}
      />

      {contextMenu && (
        <EditorContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          id={contextMenu.id}
          hasClipboardStyle={!!store.clipboardStyle}
          hasClipboardPosition={!!store.clipboardPosition}
          onBringToFront={bringToFront}
          onSendToBack={sendToBack}
          onCopyStyle={copyStyle}
          onPasteStyle={pasteStyle}
          onCopyPosition={copyPosition}
          onPastePosition={pastePosition}
        />
      )}
    </div>
  );
}
