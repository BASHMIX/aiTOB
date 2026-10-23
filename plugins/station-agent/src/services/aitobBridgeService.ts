import { AitobSettings } from '../types/telemetry';

export interface MatchUpdatePayload {
  setId: string;
  matchTitle: string;
  roundName: string;
  bestOf: number;
  tournamentName?: string;
  p1: {
    displayName: string;
    score: number;
    sponsorPrefix?: string;
    characterId?: number;
    characterName?: string;
  };
  p2: {
    displayName: string;
    score: number;
    sponsorPrefix?: string;
    characterId?: number;
    characterName?: string;
  };
}

/**
 * Normalizes input: handles users pasting full OBS overlay URLs
 * into either stationId or pairingToken fields.
 */
export function parseStationConnectionDetails(rawStationId: string, rawToken: string, rawServerUrl: string) {
  let stationId = (rawStationId || '').trim();
  let token = (rawToken || '').trim();
  let serverUrl = (rawServerUrl || 'http://localhost:8000').trim().replace(/\/+$/, '');

  // If stationId or token is an OBS URL, extract access_token and slot/station
  for (const input of [token, stationId]) {
    if (input.includes('access_token=') || input.includes('slot=')) {
      try {
        const hashIdx = input.indexOf('#');
        if (hashIdx !== -1) {
          const hashParams = new URLSearchParams(input.substring(hashIdx + 1));
          const t = hashParams.get('access_token');
          if (t) token = t;
        }
        const qIdx = input.indexOf('?');
        if (qIdx !== -1) {
          const searchPart = hashIdx !== -1 ? input.substring(qIdx, hashIdx) : input.substring(qIdx);
          const qParams = new URLSearchParams(searchPart);
          const slot = qParams.get('slot');
          if (slot) stationId = slot;
          const t = qParams.get('access_token');
          if (t && !token) token = t;
        }
      } catch {
        // ignore parse error
      }
    }
  }

  // Normalize station identifier slug: "Station 1" -> "station_1"
  const normalizedStationId = stationId.toLowerCase().replace(/\s+/g, '_').replace(/-/g, '_');

  return {
    stationId: normalizedStationId || stationId || 'station_1',
    displayStationId: stationId || 'station_1',
    token,
    serverUrl,
  };
}

class AitobBridgeService {
  private ws: WebSocket | null = null;
  private isConnected: boolean = false;
  private pingInterval: any = null;
  private reconnectTimeout: any = null;
  private onMatchUpdateCallback?: (match: MatchUpdatePayload) => void;
  private onStatusChangeCallback?: (connected: boolean) => void;

  private settings: AitobSettings = {
    serverUrl: 'http://localhost:8000',
    stationId: 'station_1',
    pairingToken: '',
    connected: false,
    activeSetId: null,
    matchTitle: 'Ready',
    bestOf: 5,
  };

  public getSettings(): AitobSettings {
    return { ...this.settings, connected: this.isConnected };
  }

  public connect(
    settings: AitobSettings,
    onMatchUpdate?: (match: MatchUpdatePayload) => void,
    onStatusChange?: (connected: boolean) => void
  ): void {
    this.settings = { ...settings };
    if (onMatchUpdate) this.onMatchUpdateCallback = onMatchUpdate;
    if (onStatusChange) this.onStatusChangeCallback = onStatusChange;

    this.disconnect();

    const { stationId, token, serverUrl } = parseStationConnectionDetails(
      this.settings.stationId,
      this.settings.pairingToken,
      this.settings.serverUrl
    );

    // 1. Fetch initial match telemetry via REST
    this.fetchCurrentMatch(serverUrl, stationId, token);

    // 2. Open WebSocket for live match updates
    const wsBase = serverUrl.replace(/^http:/, 'ws:').replace(/^https:/, 'wss:');
    const wsUrl = `${wsBase}/ws/overlay/${encodeURIComponent(stationId)}`;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log(`[aiTOB Bridge] Connected to station WebSocket: ${wsUrl}`);
        // Send authentication handshake immediately
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
          this.ws.send(JSON.stringify({ type: 'authenticate', token }));
        }

        // Start ping heartbeat
        if (this.pingInterval) clearInterval(this.pingInterval);
        this.pingInterval = setInterval(() => {
          if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, 15000);
      };

      this.ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          console.log('[aiTOB Bridge] Incoming message:', payload);

          if (payload.type === 'authenticated') {
            this.isConnected = true;
            this.settings.connected = true;
            this.onStatusChangeCallback?.(true);
            // Re-fetch fresh match data now that authenticated
            this.fetchCurrentMatch(serverUrl, stationId, token);
          } else if (payload.type === 'match_update' || payload.type === 'state_update') {
            // Server notified that station match changed -> pull fresh projection
            this.fetchCurrentMatch(serverUrl, stationId, token);
          }
        } catch (e) {
          console.warn('[aiTOB Bridge] Malformed WebSocket message:', event.data);
        }
      };

      this.ws.onerror = (err) => {
        console.warn('[aiTOB Bridge] WebSocket error:', err);
      };

      this.ws.onclose = () => {
        this.cleanupSocket();
        this.isConnected = false;
        this.settings.connected = false;
        this.onStatusChangeCallback?.(false);
      };
    } catch (e) {
      this.cleanupSocket();
      this.isConnected = false;
      this.settings.connected = false;
      this.onStatusChangeCallback?.(false);
    }
  }

  public async fetchCurrentMatch(serverUrl: string, stationId: string, token: string): Promise<void> {
    const endpoint = `${serverUrl}/obs/${encodeURIComponent(stationId)}/data`;
    try {
      const response = await fetch(endpoint, {
        headers: token ? { 'X-Overlay-Token': token } : {},
      });

      if (!response.ok) {
        if (response.status === 401) {
          console.warn('[aiTOB Bridge] 401 Unauthorized: A valid Pairing Token or OBS Link is required.');
        }
        return;
      }

      const data = await response.json();
      const activeMatch = data.active_match;

      if (!activeMatch) {
        console.log('[aiTOB Bridge] No active match assigned to station yet.');
        return;
      }

      const isSwapped = Boolean(activeMatch.swapped);
      const p1Data = isSwapped ? {
        name: activeMatch.p2_name,
        score: activeMatch.p2_score,
        prefix: activeMatch.p2_prefix,
        character: activeMatch.p2_character,
        characterId: activeMatch.p2_character_id,
      } : {
        name: activeMatch.p1_name,
        score: activeMatch.p1_score,
        prefix: activeMatch.p1_prefix,
        character: activeMatch.p1_character,
        characterId: activeMatch.p1_character_id,
      };

      const p2Data = isSwapped ? {
        name: activeMatch.p1_name,
        score: activeMatch.p1_score,
        prefix: activeMatch.p1_prefix,
        character: activeMatch.p1_character,
        characterId: activeMatch.p1_character_id,
      } : {
        name: activeMatch.p2_name,
        score: activeMatch.p2_score,
        prefix: activeMatch.p2_prefix,
        character: activeMatch.p2_character,
        characterId: activeMatch.p2_character_id,
      };

      const payload: MatchUpdatePayload = {
        setId: String(activeMatch.set_id || ''),
        matchTitle: activeMatch.round_name || 'Tournament Match',
        roundName: activeMatch.round_name || '',
        bestOf: Number(activeMatch.best_of || 5),
        tournamentName: data.tournament_name || 'Tournament',
        p1: {
          displayName: p1Data.name || 'Player 1',
          score: Number(p1Data.score ?? 0),
          sponsorPrefix: p1Data.prefix || '',
          characterName: p1Data.character || '',
          characterId: p1Data.characterId ? Number(p1Data.characterId) : undefined,
        },
        p2: {
          displayName: p2Data.name || 'Player 2',
          score: Number(p2Data.score ?? 0),
          sponsorPrefix: p2Data.prefix || '',
          characterName: p2Data.character || '',
          characterId: p2Data.characterId ? Number(p2Data.characterId) : undefined,
        },
      };

      // Mark connected if successful HTTP response received
      this.isConnected = true;
      this.settings.connected = true;
      this.onStatusChangeCallback?.(true);

      console.log('[aiTOB Bridge] Successfully loaded live match:', payload);
      this.onMatchUpdateCallback?.(payload);
    } catch (err) {
      console.warn('[aiTOB Bridge] Failed to fetch match telemetry:', err);
    }
  }

  private cleanupSocket(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
    if (this.ws) {
      try {
        this.ws.close();
      } catch {
        // ignore
      }
      this.ws = null;
    }
  }

  public disconnect(): void {
    this.cleanupSocket();
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    this.isConnected = false;
  }

  public async syncCharacters(
    p1Character?: string,
    p2Character?: string,
    p1CharacterId?: number,
    p2CharacterId?: number,
    setId?: string
  ): Promise<void> {
    const { stationId, token, serverUrl } = parseStationConnectionDetails(
      this.settings.stationId,
      this.settings.pairingToken,
      this.settings.serverUrl
    );

    const payload = {
      type: 'sync_characters',
      p1_character: p1Character,
      p2_character: p2Character,
      p1_character_id: p1CharacterId,
      p2_character_id: p2CharacterId,
      set_id: setId || this.settings.activeSetId,
    };

    // 1. Send via WebSocket if open for immediate transmission
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify(payload));
      } catch (e) {
        // ignore ws send error
      }
    }

    // 2. Also send via REST endpoint for reliable persistence
    try {
      await fetch(`${serverUrl}/obs/${encodeURIComponent(stationId)}/sync-telemetry`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'X-Overlay-Token': token } : {}),
        },
        body: JSON.stringify(payload),
      });
    } catch (e) {
      console.warn('[aiTOB Bridge] Failed to sync characters via REST:', e);
    }
  }

  public async syncScore(
    p1Score: number,
    p2Score: number,
    setId?: string
  ): Promise<void> {
    const { stationId, token, serverUrl } = parseStationConnectionDetails(
      this.settings.stationId,
      this.settings.pairingToken,
      this.settings.serverUrl
    );

    const payload = {
      type: 'sync_score',
      p1_score: p1Score,
      p2_score: p2Score,
      set_id: setId || this.settings.activeSetId,
    };

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify(payload));
      } catch (e) {
        // ignore ws send error
      }
    }

    try {
      await fetch(`${serverUrl}/obs/${encodeURIComponent(stationId)}/sync-telemetry`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'X-Overlay-Token': token } : {}),
        },
        body: JSON.stringify(payload),
      });
    } catch (e) {
      console.warn('[aiTOB Bridge] Failed to sync score via REST:', e);
    }
  }

  public async submitMatchResult(
    setId: string,
    p1Score: number,
    p2Score: number,
    winner: 'p1' | 'p2',
    autoConfirm: boolean = false
  ): Promise<{ success: boolean; message: string; completed?: boolean }> {
    const { stationId, token, serverUrl } = parseStationConnectionDetails(
      this.settings.stationId,
      this.settings.pairingToken,
      this.settings.serverUrl
    );
    const endpoint = `${serverUrl}/obs/${encodeURIComponent(stationId)}/submit-result`;
    console.log(`[aiTOB Bridge] Submitting final match result to: ${endpoint}`);

    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'X-Station-Token': token, 'X-Overlay-Token': token } : {}),
        },
        body: JSON.stringify({
          set_id: setId,
          p1_score: p1Score,
          p2_score: p2Score,
          winner,
          auto_confirm: autoConfirm,
          auto_reported_by: 'aiTOB-SF6-Station-Agent',
          timestamp: new Date().toISOString(),
        }),
      });

      if (response.ok) {
        const resJson = await response.json();
        return {
          success: true,
          message: resJson.message || 'Result successfully submitted to aiTOB Platform!',
          completed: resJson.completed,
        };
      } else {
        const text = await response.text();
        return { success: false, message: `Submission failed: ${response.status} - ${text}` };
      }
    } catch (err: any) {
      return { success: false, message: `Connection error: ${err.message || err}` };
    }
  }
}

export const aitobBridgeService = new AitobBridgeService();
