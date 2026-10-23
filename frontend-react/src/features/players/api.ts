import axios from 'axios';
import type {
  PlayerProfile,
  PlayerProfileDetailResponse,
  CreateProfilePayload,
  UpdateProfilePayload,
  CreateGameProfilePayload,
  CreateCharacterDefaultPayload,
  PlayerCharacterDefaultItem,
  PlayerGameProfileDetail,
  PlayerPresentationV1,
} from './types';

const BASE_URL = '/api/player-profiles';

export async function listPlayerProfiles(params?: {
  limit?: number;
  offset?: number;
  query?: string;
}): Promise<PlayerProfile[]> {
  const response = await axios.get<{ profiles: PlayerProfile[] }>(BASE_URL, {
    params: {
      limit: params?.limit ?? 100,
      offset: params?.offset ?? 0,
      query: params?.query || undefined,
    },
  });
  return response.data.profiles ?? [];
}

export async function getPlayerProfile(profileId: string): Promise<PlayerProfileDetailResponse> {
  const response = await axios.get<PlayerProfileDetailResponse>(`${BASE_URL}/${encodeURIComponent(profileId)}`);
  return response.data;
}
export async function createPlayerProfile(payload: CreateProfilePayload): Promise<PlayerProfile> {
  const response = await axios.post<PlayerProfile>(BASE_URL, payload);
  return response.data;
}

export async function updatePlayerProfile(
  profileId: string,
  payload: UpdateProfilePayload,
): Promise<PlayerProfile> {
  const response = await axios.patch<PlayerProfile>(`${BASE_URL}/${encodeURIComponent(profileId)}`, payload);
  return response.data;
}

export async function uploadPlayerProfileAvatar(profileId: string, file: File): Promise<PlayerProfile> {
  const form = new FormData();
  form.append('avatar', file);
  const response = await axios.post<{ profile: PlayerProfile }>(
    `${BASE_URL}/${encodeURIComponent(profileId)}/avatar`,
    form,
  );
  return response.data.profile;
}

export async function deletePlayerProfile(profileId: string): Promise<{ ok: boolean; message: string }> {
  const response = await axios.delete<{ ok: boolean; message: string }>(
    `${BASE_URL}/${encodeURIComponent(profileId)}`,
  );
  return response.data;
}

export async function createGameProfile(
  profileId: string,
  payload: CreateGameProfilePayload,
): Promise<PlayerGameProfileDetail> {
  const response = await axios.post<PlayerGameProfileDetail>(
    `${BASE_URL}/${encodeURIComponent(profileId)}/game-profiles`,
    payload,
  );
  return response.data;
}

export async function listGameProfiles(profileId: string): Promise<PlayerGameProfileDetail[]> {
  const response = await axios.get<{ game_profiles: PlayerGameProfileDetail[] }>(
    `${BASE_URL}/${encodeURIComponent(profileId)}/game-profiles`,
  );
  return response.data.game_profiles ?? [];
}

export async function createCharacterDefault(
  profileId: string,
  gameProfileId: string,
  payload: CreateCharacterDefaultPayload,
): Promise<PlayerCharacterDefaultItem> {
  const response = await axios.post<PlayerCharacterDefaultItem>(
    `${BASE_URL}/${encodeURIComponent(profileId)}/game-profiles/${encodeURIComponent(gameProfileId)}/character-defaults`,
    payload,
  );
  return response.data;
}

export async function resolvePresentationV1(params: {
  tournamentSlug: string;
  eventId: string;
  entrantId: string;
  provider?: string;
}): Promise<PlayerPresentationV1> {
  const response = await axios.get<PlayerPresentationV1>(`${BASE_URL}/presentation/v1`, {
    params: {
      provider: params.provider ?? 'startgg',
      tournament_slug: params.tournamentSlug,
      event_id: params.eventId,
      entrant_id: params.entrantId,
    },
  });
  return response.data;
}

export interface PromoteOverridePayload {
  tournament_slug: string;
  event_id: string;
  entrant_id: string;
  provider?: string;
}

export async function promoteEntrantOverride(
  payload: PromoteOverridePayload
): Promise<{ ok: boolean; profile?: PlayerProfile }> {
  const response = await axios.post<{ ok: boolean; profile?: PlayerProfile }>(
    `${BASE_URL}/promote-override`,
    {
      tournament_slug: payload.tournament_slug,
      event_id: payload.event_id,
      entrant_id: payload.entrant_id,
      provider: payload.provider ?? 'startgg',
    }
  );
  return response.data;
}
