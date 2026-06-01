import { useState, useCallback } from 'react';
import axios from 'axios';
import { useEditorStore } from '@/store/useEditorStore';

export function useEditorData(stationId: string, wsRef: React.MutableRefObject<WebSocket | null>) {

  const [presets, setPresets] = useState<{name: string, config: any}[]>([]);
  const [activeOverlayName, setActiveOverlayName] = useState<string>('');
  const [isLoadModalOpen, setIsLoadModalOpen] = useState(false);
  const [allSavedOverlays, setAllSavedOverlays] = useState<{name: string, config: any}[]>([]);

  const fetchGlobalOverlays = useCallback(async () => {
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
  }, []);

  const fetchActiveMatch = useCallback(async () => {
    try {
      const res = await axios.get('/api/active-matches');
      const matches = res.data.matches || [];
      const connectedMatch = matches.find((m: any) => m.station_id === stationId);
      useEditorStore.getState().setActiveMatch(connectedMatch || null);
    } catch (e) {
      console.error("Failed to fetch active match", e);
    }
  }, [stationId]);

  const fetchPresets = useCallback(async () => {
    try {
      const resStations = await axios.get('/api/stations');
      const currentStation = (resStations.data.stations || []).find((s: any) => s.id === stationId);

      const loadedOverlayName = currentStation?.active_overlay || '';
      setActiveOverlayName(loadedOverlayName);

      const overlaysList = currentStation?.overlays || [];
      const associatedOverlayNames = new Set(overlaysList.map((o: any) => o.overlay_name));

      const resOverlays = await axios.get('/api/overlays');
      const list = resOverlays.data.overlays || [];
      const parsed = list.map((o: any) => ({
        ...o,
        config: typeof o.config === 'string' ? JSON.parse(o.config) : o.config
      }));

      const filtered = parsed.filter((o: any) => associatedOverlayNames.has(o.name));
      setPresets(filtered);

      if (!loadedOverlayName) {
        setIsLoadModalOpen(true);
        fetchGlobalOverlays();
      }

      if (loadedOverlayName) {
        const currentPreset = parsed.find((p: any) => p.name === loadedOverlayName);
        if (currentPreset && currentPreset.config) {
          useEditorStore.getState().setElements(currentPreset.config.elements || {});
          useEditorStore.getState().setGlobalSettings(
            currentPreset.config.background_url || '',
            currentPreset.config.global_font_url || '',
            currentPreset.config.global_font_family || ''
          );
          useEditorStore.getState().setSelectedId(null);
        } else {
          useEditorStore.getState().setElements({});
          useEditorStore.getState().setGlobalSettings('', '', '');
        }
      } else {
        useEditorStore.getState().setElements({});
        useEditorStore.getState().setGlobalSettings('', '', '');
      }
    } catch (e) {
      console.error("Failed to fetch presets", e);
    }
  }, [stationId, fetchGlobalOverlays]);

  const handlePush = useCallback(async () => {
    if (!activeOverlayName) {
      alert("No active overlay slide loaded. Please load an overlay template or create a new one first before saving.");
      return;
    }
    const currentStore = useEditorStore.getState();
    currentStore.setStatusMsg('Saving...');
    try {
      const roundedElements = { ...currentStore.elements };
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
        background_url: currentStore.background_url,
        global_font_url: currentStore.global_font_url,
        global_font_family: currentStore.global_font_family
      };

      await axios.post('/api/overlays', { name: activeOverlayName, config });

      const resStations = await axios.get('/api/stations');
      const currentStation = (resStations.data.stations || []).find((s: any) => s.id === stationId);
      const isAssigned = (currentStation?.overlays || []).some((o: any) => o.overlay_name === activeOverlayName);
      if (!isAssigned) {
        await axios.post(`/api/stations/${stationId}/overlays`, { overlay_name: activeOverlayName });
      }

      useEditorStore.getState().setStatusMsg('Saved');

      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify(config));
      }
      fetchPresets();
    } catch (e) {
      useEditorStore.getState().setStatusMsg('Save failed');
    }
  }, [activeOverlayName, stationId, wsRef, fetchPresets]);

  const handleLoadGlobalOverlay = useCallback(async (name: string) => {
    try {
      useEditorStore.getState().setStatusMsg('Loading slide...');
      await axios.post(`/api/stations/${stationId}/overlays`, { overlay_name: name });
      await axios.post(`/api/stations/${stationId}/active-overlay`, { overlay_name: name });

      setIsLoadModalOpen(false);
      fetchPresets();
      useEditorStore.getState().setStatusMsg('Slide loaded');
    } catch (e) {
      console.error("Failed to load global overlay", e);
      useEditorStore.getState().setStatusMsg('Load failed');
    }
  }, [stationId, fetchPresets]);

  const handleDeletePreset = useCallback(async (name: string) => {
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
  }, [stationId, activeOverlayName, fetchPresets]);

  const handleRename = useCallback(async (newName: string) => {
    if (!activeOverlayName || newName === activeOverlayName) return;
    try {
      await axios.post('/api/overlays/rename', { old_name: activeOverlayName, new_name: newName });
      await axios.post(`/api/stations/${stationId}/active-overlay`, { overlay_name: newName });
      fetchPresets();
    } catch (e) {
      alert("Rename failed");
    }
  }, [stationId, activeOverlayName, fetchPresets]);

  return {
    presets,
    setPresets,
    activeOverlayName,
    setActiveOverlayName,
    isLoadModalOpen,
    setIsLoadModalOpen,
    allSavedOverlays,
    setAllSavedOverlays,
    fetchGlobalOverlays,
    fetchActiveMatch,
    fetchPresets,
    handlePush,
    handleLoadGlobalOverlay,
    handleDeletePreset,
    handleRename
  };
}
