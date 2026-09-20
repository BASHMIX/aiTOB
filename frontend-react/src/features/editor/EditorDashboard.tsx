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
  const [selectionBox, setSelectionBox] = useState<{ x: number; y: number; width: number; height: number } | null>(null);
  const selectionStart = useRef<{ x: number; y: number } | null>(null);
  const marqueeMoved = useRef(false);
  const suppressNextCanvasClick = useRef(false);

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

  // Load every saved Google Font in the editor preview. A per-element font
  // selection must be available here as well as in the OBS browser source.
  useEffect(() => {
    const urls = Array.from(new Set([
      store.global_font_url,
      ...store.font_library.map(font => font.url || ''),
    ].filter(Boolean)));
    urls.forEach((url, index) => {
      const id = `editor-dyn-font-${index}`;
      let link = document.getElementById(id) as HTMLLinkElement | null;
      if (!link) {
        link = document.createElement('link');
        link.id = id;
        link.rel = 'stylesheet';
        document.head.appendChild(link);
      }
      if (link.href !== url) link.href = url;
    });
    document.querySelectorAll('link[id^="editor-dyn-font-"]').forEach((node) => {
      const index = Number(node.id.replace('editor-dyn-font-', ''));
      if (!urls[index]) node.remove();
    });
  }, [store.global_font_url, store.font_library]);

  useEffect(() => {
    const handleHistoryShortcut = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey)) return;
      const key = event.key.toLowerCase();
      if (key === 'z') {
        event.preventDefault();
        if (event.shiftKey) useEditorStore.getState().redo();
        else useEditorStore.getState().undo();
      } else if (key === 'y') {
        event.preventDefault();
        useEditorStore.getState().redo();
      }
    };
    window.addEventListener('keydown', handleHistoryShortcut);
    return () => window.removeEventListener('keydown', handleHistoryShortcut);
  }, []);

  const canvasPoint = (event: MouseEvent | React.MouseEvent | React.PointerEvent) => {
    const canvas = document.querySelector<HTMLElement>('[data-overlay-canvas="true"]');
    if (!canvas) return { x: 0, y: 0 };
    const bounds = canvas.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(1920, (event.clientX - bounds.left) / (scale || 1))),
      y: Math.max(0, Math.min(1080, (event.clientY - bounds.top) / (scale || 1))),
    };
  };

  const updateSelectionBox = (event: React.MouseEvent | React.PointerEvent) => {
    const start = selectionStart.current;
    if (!start) return;
    const point = canvasPoint(event);
    if (Math.abs(point.x - start.x) > 3 || Math.abs(point.y - start.y) > 3) marqueeMoved.current = true;
    setSelectionBox({ x: Math.min(start.x, point.x), y: Math.min(start.y, point.y), width: Math.abs(point.x - start.x), height: Math.abs(point.y - start.y) });
  };

  const finishSelection = (event: React.MouseEvent | React.PointerEvent) => {
    const start = selectionStart.current;
    if (!start) return;
    const point = canvasPoint(event);
    const canvas = document.querySelector<HTMLElement>('[data-overlay-canvas="true"]');
    const bounds = canvas?.getBoundingClientRect();
    const left = Math.min(start.x, point.x);
    const top = Math.min(start.y, point.y);
    const right = Math.max(start.x, point.x);
    const bottom = Math.max(start.y, point.y);
    const screenLeft = (bounds?.left || 0) + left * (scale || 1);
    const screenTop = (bounds?.top || 0) + top * (scale || 1);
    const screenRight = (bounds?.left || 0) + right * (scale || 1);
    const screenBottom = (bounds?.top || 0) + bottom * (scale || 1);
    const ids = Array.from(document.querySelectorAll<HTMLElement>('[data-overlay-element-id]')).filter((node) => {
      const rect = node.getBoundingClientRect();
      return rect.left < screenRight && rect.right > screenLeft && rect.top < screenBottom && rect.bottom > screenTop;
    }).map((node) => node.dataset.overlayElementId!).filter(Boolean);
    store.setSelectedIds(ids);
    suppressNextCanvasClick.current = marqueeMoved.current;
    selectionStart.current = null;
    marqueeMoved.current = false;
    window.removeEventListener('mousemove', updateSelectionBox as unknown as EventListener);
    setSelectionBox(null);
  };

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
                data-overlay-canvas="true"
                className="absolute top-0 left-0 w-[1920px] h-[1080px] bg-checkerboard shadow-[0_0_50px_rgba(0,0,0,0.5)] origin-top-left transition-transform duration-300 overflow-hidden select-none"
                style={{ 
                  transform: `scale(${scale || 1})`,
                  fontFamily: store.global_font_family || 'inherit'
                }}
                onClick={(e) => {
                  if (suppressNextCanvasClick.current) {
                    suppressNextCanvasClick.current = false;
                    return;
                  }
                  if (e.target === e.currentTarget) store.setSelectedId(null);
                }}
                onDragStart={(event) => event.preventDefault()}
                onMouseDown={(event) => {
                  if (event.button !== 0 || (event.target as HTMLElement).closest('[data-overlay-element]')) return;
                  const point = canvasPoint(event);
                  selectionStart.current = point;
                  marqueeMoved.current = false;
                  setSelectionBox({ x: point.x, y: point.y, width: 0, height: 0 });
                  if (!event.ctrlKey && !event.metaKey && !event.shiftKey) store.setSelectedIds([]);
                  window.addEventListener('mousemove', updateSelectionBox as unknown as EventListener);
                  window.addEventListener('mouseup', finishSelection as unknown as EventListener, { once: true });
                }}
                onMouseMove={updateSelectionBox}
                onMouseUp={finishSelection}
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
                {selectionBox && (
                  <div
                    className="absolute pointer-events-none border border-[#00ffcc] bg-[#00ffcc]/10 z-[999]"
                    style={{ left: selectionBox.x, top: selectionBox.y, width: selectionBox.width, height: selectionBox.height }}
                  />
                )}
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
