import { useState, useCallback } from 'react';
import axios from 'axios';
import { useEditorStore } from '@/store/useEditorStore';
import { normalizeScene } from '@/scene/normalizeScene';
import type { SceneDocumentV2 } from '@/scene/types';
import { exportSingleOverlaySlide, exportStationOverlayPackage, importOverlayPackageFile } from '@/utils/overlayBundle';
import type { EditorStarterTemplate } from '../starterTemplates';

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
      // The Editor must preview the same projection as OBS, including a
      // not-started Broadcast Preview match and provider metadata fallbacks.
      const res = await axios.get(`/api/stations/${encodeURIComponent(stationId)}/broadcast-state`);
      const broadcastData = res.data;
      const matchWithNext = broadcastData.active_match
        ? {
            ...broadcastData.active_match,
            next_match: broadcastData.next_match,
            next_match_tbd: broadcastData.next_match_tbd,
            busy_players: broadcastData.busy_players,
          }
        : (broadcastData.next_match
            ? {
                next_match: broadcastData.next_match,
                next_match_tbd: broadcastData.next_match_tbd,
                busy_players: broadcastData.busy_players,
              }
            : null);
      useEditorStore.getState().setActiveMatch(matchWithNext);
    } catch (e) {
      console.error("Failed to fetch active match", e);
      useEditorStore.getState().setActiveMatch(null);
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
          const normalized = normalizeScene(currentPreset.config);
          useEditorStore.getState().setElements(normalized.nodes as any);
          useEditorStore.getState().setGlobalSettings(
            currentPreset.config.background_url || '',
            currentPreset.config.global_font_url || '',
            currentPreset.config.global_font_family || ''
          );
          if (Array.isArray(currentPreset.config.font_library)) {
            useEditorStore.getState().setFontLibrary(currentPreset.config.font_library);
          }
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

      const sceneDoc: SceneDocumentV2 = {
        schemaVersion: 2,
        canvas: {
          width: 1920,
          height: 1080,
          backgroundUrl: currentStore.background_url,
          globalFontUrl: currentStore.global_font_url,
          globalFontFamily: currentStore.global_font_family,
          fontLibrary: currentStore.font_library,
        },
        dataSource: {
          kind: Object.values(roundedElements).some((el) => ['results-group', 'results-cards', 'result-card'].includes(el.type))
            ? 'tournament-results'
            : 'current-match',
        },
        rootIds: Object.values(roundedElements)
          .filter((el) => !el.parentId)
          .map((el) => el.id),
        nodes: roundedElements as any,
      };

      const config = {
        ...sceneDoc,
        elements: roundedElements,
        background_url: currentStore.background_url,
        global_font_url: currentStore.global_font_url,
        global_font_family: currentStore.global_font_family
        ,font_library: currentStore.font_library
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

  const handleExportCurrentSlide = useCallback(async () => {
    if (!activeOverlayName) {
      alert('No active overlay slide to export.');
      return;
    }
    const currentStore = useEditorStore.getState();
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
      schemaVersion: 2,
      canvas: {
        width: 1920,
        height: 1080,
        backgroundUrl: currentStore.background_url,
        globalFontUrl: currentStore.global_font_url,
        globalFontFamily: currentStore.global_font_family,
        fontLibrary: currentStore.font_library,
      },
      dataSource: {
        kind: Object.values(roundedElements).some((el) => ['results-group', 'results-cards', 'result-card'].includes(el.type))
          ? 'tournament-results'
          : 'current-match',
      },
      rootIds: Object.values(roundedElements).filter((el) => !el.parentId).map((el) => el.id),
      nodes: roundedElements as any,
      elements: roundedElements,
      background_url: currentStore.background_url,
      global_font_url: currentStore.global_font_url,
      global_font_family: currentStore.global_font_family,
      font_library: currentStore.font_library,
    };

    try {
      currentStore.setStatusMsg('Exporting slide…');
      await exportSingleOverlaySlide(activeOverlayName, config, (msg) => currentStore.setStatusMsg(msg));
      currentStore.setStatusMsg('Slide exported');
    } catch (e) {
      console.error('Export failed:', e);
      currentStore.setStatusMsg('Export failed');
      alert('Failed to export slide');
    }
  }, [activeOverlayName]);

  const handleExportAllStationSlides = useCallback(async () => {
    const currentStore = useEditorStore.getState();
    if (!presets || presets.length === 0) {
      alert('No overlay slides found on this station to export.');
      return;
    }
    try {
      currentStore.setStatusMsg('Exporting package…');
      await exportStationOverlayPackage(stationId, stationId, presets, (msg) => currentStore.setStatusMsg(msg));
      currentStore.setStatusMsg('Package exported');
    } catch (e) {
      console.error('Export package failed:', e);
      currentStore.setStatusMsg('Package export failed');
      alert('Failed to export station package');
    }
  }, [stationId, presets]);

  const handleImportFile = useCallback(async (file: File) => {
    const currentStore = useEditorStore.getState();
    try {
      currentStore.setStatusMsg('Importing package…');
      const result = await importOverlayPackageFile(file, stationId, (msg) => currentStore.setStatusMsg(msg));
      await fetchGlobalOverlays();
      await fetchPresets();
      currentStore.setStatusMsg(`Imported ${result.importedCount} slide(s)`);
      alert(`Successfully imported ${result.importedCount} slide(s): ${result.names.join(', ')}`);
    } catch (e: any) {
      console.error('Import failed:', e);
      currentStore.setStatusMsg('Import failed');
      alert(`Import failed: ${e?.message || 'Unknown error'}`);
    }
  }, [stationId, fetchPresets, fetchGlobalOverlays]);

  const handleLoadStarterTemplate = useCallback(async (template: EditorStarterTemplate) => {
    const currentStore = useEditorStore.getState();
    try {
      currentStore.setStatusMsg('Applying template…');
      const baseName = template.name;
      let targetName = baseName;
      let counter = 1;
      const existingNames = new Set(allSavedOverlays.map((o) => o.name));
      while (existingNames.has(targetName)) {
        targetName = `${baseName} (${counter++})`;
      }

      await axios.post('/api/overlays', { name: targetName, config: template.config });
      await axios.post(`/api/stations/${stationId}/overlays`, { overlay_name: targetName });
      await axios.post(`/api/stations/${stationId}/active-overlay`, { overlay_name: targetName });

      setIsLoadModalOpen(false);
      await fetchGlobalOverlays();
      await fetchPresets();
      currentStore.setStatusMsg(`Template loaded: ${targetName}`);
    } catch (e) {
      console.error('Failed to load starter template:', e);
      currentStore.setStatusMsg('Template load failed');
      alert('Failed to load starter template');
    }
  }, [stationId, allSavedOverlays, fetchPresets, fetchGlobalOverlays]);

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
    handleRename,
    handleExportCurrentSlide,
    handleExportAllStationSlides,
    handleImportFile,
    handleLoadStarterTemplate,
  };
}
