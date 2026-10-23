import axios from 'axios';
import type {
  CutoffKind,
  OutputProfile,
  SceneDocumentV2,
  StandingEntrySnapshot,
} from '@/scene/types';

export interface ResultVersionSummary {
  id: string;
  tournament_slug: string;
  provider_type: 'startgg' | 'challonge';
  event_id: string;
  event_name: string;
  game_id?: string | null;
  game_name?: string | null;
  capture_status: 'final' | 'provisional';
  readiness_state: 'final' | 'provisional' | 'stale';
  provider_state_raw: string;
  provider_revision?: string | null;
  observed_at: string;
  finalized_at?: string | null;
  warnings: ReadinessWarning[];
  entry_count: number;
}

export interface ReadinessWarning {
  code: string;
  severity: 'info' | 'warning' | 'blocking';
  entrant_id?: string | null;
  message: string;
}

export interface ResultVersionDetail extends ResultVersionSummary {
  entries: StandingEntrySnapshot[];
  page: {
    number: number;
    size: number;
    total_entries: number;
    has_more: boolean;
  };
}

export interface RefreshResultsResponse {
  reused: boolean;
  version: ResultVersionDetail;
  readiness_state: 'final' | 'provisional' | 'stale';
}

export interface CreateMediaOutputPayload {
  output_kind: 'static' | 'live';
  overlay_name?: string;
  scene: SceneDocumentV2;
  cutoff: CutoffKind;
  page_number?: number;
  output_profile: OutputProfile;
}

export interface MediaOutputResponse {
  id: string;
  result_version_id: string;
  output_kind: 'static' | 'live';
  scene_hash: string;
  cutoff: CutoffKind;
  page_number: number;
  output_profile: OutputProfile;
  created_at: string;
}

export interface ResultsStationSummary {
  id: string;
  name: string;
}

export interface RecordExportReceiptPayload {
  byte_size: number;
  sha256: string;
}

export interface ExportReceiptResponse {
  output_id: string;
  recorded: boolean;
}

export async function getLatestEventResults(
  tournamentSlug: string,
  eventId: string,
): Promise<ResultVersionDetail | null> {
  try {
    const res = await axios.get<ResultVersionDetail>(
      `/api/tournaments/${encodeURIComponent(tournamentSlug)}/events/${encodeURIComponent(eventId)}/results/latest`,
    );
    return res.data;
  } catch (err: any) {
    if (err.response?.status === 404) {
      return null;
    }
    throw err;
  }
}

export async function refreshEventResults(
  tournamentSlug: string,
  eventId: string,
  options?: { force?: boolean; presentation_mode?: string },
): Promise<RefreshResultsResponse> {
  const res = await axios.post<RefreshResultsResponse>(
    `/api/tournaments/${encodeURIComponent(tournamentSlug)}/events/${encodeURIComponent(eventId)}/results/refresh`,
    {
      force: options?.force ?? false,
      presentation_mode: options?.presentation_mode ?? 'current',
    },
  );
  return res.data;
}

export async function getResultVersion(
  versionId: string,
  options?: { cutoff?: CutoffKind; page?: number; page_size?: number },
): Promise<ResultVersionDetail> {
  const res = await axios.get<ResultVersionDetail>(
    `/api/results-media/versions/${encodeURIComponent(versionId)}`,
    {
      params: {
        cutoff: options?.cutoff,
        page: options?.page ?? 1,
        page_size: options?.page_size ?? 16,
      },
    },
  );
  return res.data;
}

export async function createMediaOutput(
  versionId: string,
  payload: CreateMediaOutputPayload,
): Promise<MediaOutputResponse> {
  const res = await axios.post<MediaOutputResponse>(
    `/api/results-media/versions/${encodeURIComponent(versionId)}/outputs`,
    payload,
  );
  return res.data;
}

export async function recordExportReceipt(
  outputId: string,
  payload: RecordExportReceiptPayload,
): Promise<ExportReceiptResponse> {
  const res = await axios.post<ExportReceiptResponse>(
    `/api/results-media/outputs/${encodeURIComponent(outputId)}/export-receipt`,
    payload,
  );
  return res.data;
}

export async function listResultsStations(): Promise<ResultsStationSummary[]> {
  const res = await axios.get<{ stations?: ResultsStationSummary[] }>('/api/stations');
  return Array.isArray(res.data.stations) ? res.data.stations : [];
}

export interface ResultsSessionData {
  station_id: string;
  media_output_id?: string | null;
  state: 'cleared' | 'ready' | 'live' | 'held' | 'complete' | 'error';
  cue_index: number;
  session_revision: number;
  error_code?: string | null;
  updated_at: string;
}

export type PlaybackCommand =
  | 'take_live'
  | 'play_all'
  | 'next'
  | 'previous'
  | 'hold'
  | 'restart'
  | 'clear';

export async function getStationResultsSession(stationId: string): Promise<ResultsSessionData> {
  const res = await axios.get<ResultsSessionData>(
    `/api/stations/${encodeURIComponent(stationId)}/results-session`,
  );
  return res.data;
}

export async function bindStationResultsSession(
  stationId: string,
  payload: { media_output_id: string; expected_revision: number },
): Promise<ResultsSessionData> {
  const res = await axios.put<ResultsSessionData>(
    `/api/stations/${encodeURIComponent(stationId)}/results-session`,
    payload,
  );
  return res.data;
}

export async function sendStationResultsCommand(
  stationId: string,
  payload: { command: PlaybackCommand; expected_revision: number },
): Promise<ResultsSessionData> {
  const res = await axios.post<ResultsSessionData>(
    `/api/stations/${encodeURIComponent(stationId)}/results-session/commands`,
    payload,
  );
  return res.data;
}
