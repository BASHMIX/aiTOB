import { useEffect, useRef, useCallback } from 'react';

type HubEvent = { type: string; [key: string]: unknown };

/**
 * Connects to /ws/hub and calls `onEvent` whenever the server
 * broadcasts a message. Reconnects automatically on disconnect.
 *
 * The backend broadcasts { type: "match_update" } after every
 * admin action, bot action, or timer event — so callers just
 * need to re-fetch their data when they receive that event.
 */
export function useHubSocket(onEvent: (evt: HubEvent) => void) {
  const wsRef = useRef<WebSocket | null>(null);
  const onEventRef = useRef(onEvent);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const destroyed = useRef(false);

  // Always use latest callback without re-connecting
  onEventRef.current = onEvent;

  const connect = useCallback(() => {
    if (destroyed.current) return;

    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    // Use the same host:port as the page so it works through
    // both Vite dev proxy (:5173 → /ws → backend) and direct API access (:8000)
    const url = `${proto}://${window.location.host}/ws/hub`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      console.debug('[HubSocket] connected');
    };

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data) as HubEvent;
        onEventRef.current(data);
      } catch {
        // ignore malformed messages
      }
    };

    ws.onclose = () => {
      if (destroyed.current) return;
      console.debug('[HubSocket] disconnected — reconnecting in 3s');
      reconnectTimer.current = setTimeout(connect, 3000);
    };

    ws.onerror = () => {
      ws.close(); // triggers onclose → reconnect
    };
  }, []);

  useEffect(() => {
    destroyed.current = false;
    connect();
    return () => {
      destroyed.current = true;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        const ws = wsRef.current;
        ws.onopen = null;
        ws.onclose = null;
        ws.onerror = null;
        ws.onmessage = null;
        // Don't close a connecting socket — browser warns. Let it open then close.
        if (ws.readyState === WebSocket.OPEN) {
          ws.close();
        } else if (ws.readyState === WebSocket.CONNECTING) {
          // Schedule close once it opens (avoids browser warning)
          ws.addEventListener('open', () => ws.close(), { once: true });
        }
      }
    };
  }, [connect]);
}
