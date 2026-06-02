import { useEffect } from 'react';
import { useEditorStore } from '@/store/useEditorStore';

export function useEditorWebSocket(
  stationId: string,
  wsRef: React.MutableRefObject<WebSocket | null>,
  fetchActiveMatch: () => void,
  fetchPresets: () => void
) {
  useEffect(() => {
    let ws: WebSocket;
    const connect = () => {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${proto}//${window.location.host}/ws/overlay/${encodeURIComponent(stationId)}`;
      ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        useEditorStore.getState().setStatusMsg(`Live [Station: ${stationId}]`);
        document.title = `Editor [${stationId}]`;
      };

      ws.onclose = () => {
        useEditorStore.getState().setStatusMsg("Reconnecting...");
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
          useEditorStore.getState().setElements(data.elements);
        }
        useEditorStore.getState().setGlobalSettings(data.background_url || '', data.global_font_url || '', data.global_font_family || '');
      };
    };

    connect();
    fetchPresets();
    fetchActiveMatch();

    return () => {
      if (ws) {
        ws.onclose = null;
        ws.close();
      }
    };
  }, [stationId, fetchActiveMatch, fetchPresets, wsRef]);
}
