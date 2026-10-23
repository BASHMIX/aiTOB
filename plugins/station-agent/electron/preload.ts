import { contextBridge, ipcRenderer } from 'electron';

export interface TelemetryPayload {
  data: {
    game?: string;
    round_timer?: number;
    match_state?: string;
    round_number?: number;
    p1?: {
      character_id?: number;
      character_name?: string;
      current_hp?: number;
      max_hp?: number;
      rounds_won?: number;
      super_art?: number;
      drive_gauge?: number;
    };
    p2?: {
      character_id?: number;
      character_name?: string;
      current_hp?: number;
      max_hp?: number;
      rounds_won?: number;
      super_art?: number;
      drive_gauge?: number;
    };
  };
  rinfo: {
    address: string;
    port: number;
  };
  timestamp: number;
  packetCount: number;
}

export interface UdpStatusPayload {
  status: 'LISTENING' | 'ERROR' | 'BOUND';
  port: number;
  address?: string;
  message?: string;
}

const api = {
  onGameTelemetry: (callback: (payload: TelemetryPayload) => void) => {
    const subscription = (_event: any, value: TelemetryPayload) => callback(value);
    ipcRenderer.on('game-telemetry', subscription);
    return () => {
      ipcRenderer.removeListener('game-telemetry', subscription);
    };
  },

  onUdpStatus: (callback: (status: UdpStatusPayload) => void) => {
    const subscription = (_event: any, value: UdpStatusPayload) => callback(value);
    ipcRenderer.on('udp-status', subscription);
    return () => {
      ipcRenderer.removeListener('udp-status', subscription);
    };
  },

  getAppInfo: () => ipcRenderer.invoke('get-app-info'),
  restartUdp: () => ipcRenderer.invoke('restart-udp'),
  simulateTelemetry: (data: any) => ipcRenderer.invoke('simulate-telemetry', data),
  updateGameConnection: (config: any) => ipcRenderer.invoke('update-game-connection', config),
  installMod: (gamePath: string, port: number) => ipcRenderer.invoke('install-mod', { gamePath, port }),
  selectDirectory: () => ipcRenderer.invoke('select-directory'),
};

contextBridge.exposeInMainWorld('api', api);

declare global {
  interface Window {
    api: typeof api;
  }
}
