export interface PlayerState {
  characterId: number;
  characterName: string;
  currentHp: number;
  maxHp: number;
  roundsWon: number;
  gameWins: number;
  maxCombo: number;
  scoreInSet: number;
  superArt: number;
  driveGauge: number;
  isBurnout?: boolean;
  displayName: string;
  sponsorPrefix?: string;
}

export type MatchStateEnum = 'IDLE' | 'CHARACTER_SELECT' | 'CHARACTER_SELECT_OR_MENU' | 'CUSTOM_ROOM_LOBBY' | 'FIGHTING' | 'ROUND_OVER' | 'MATCH_RESULTS' | 'MATCH_OVER' | 'TEST_PING';

export interface GameTelemetryData {
  game: string;
  roundTimer: number;
  roundNumber: number;
  matchState: MatchStateEnum;
  roomId?: string;
  p1: PlayerState;
  p2: PlayerState;
  lastUpdated: number;
}

export interface ObsSettings {
  enabled: boolean;
  ip: string;
  port: number;
  password?: string;
  scenePreMatch: string;
  sceneGameplay: string;
  sceneVictory: string;
  autoSwitch: boolean;
}

export interface AitobSettings {
  serverUrl: string;
  stationId: string;
  pairingToken: string;
  connected: boolean;
  activeSetId: string | null;
  matchTitle: string;
  bestOf: number;
}

export interface TelemetryLogEntry {
  id: string;
  timestamp: string;
  type: 'PACKET' | 'OBS' | 'AITOB' | 'SYSTEM';
  message: string;
  raw?: any;
}
