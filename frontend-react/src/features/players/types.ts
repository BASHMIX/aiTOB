export type ProvenanceSource = 'entrant_override' | 'player_profile' | 'provider_snapshot' | 'placeholder';

export interface EntrantScope {
  provider: string;
  tournament_slug: string;
  event_id: string;
  entrant_id: string;
}

export interface CharacterValue {
  name: string;
  id: string;
  image_url: string;
}

export interface PresentationField<T> {
  value: T | null;
  source: ProvenanceSource;
}

export interface ResolvedPresentation {
  display_name: PresentationField<string>;
  prefix: PresentationField<string>;
  country: PresentationField<string>;
  avatar_url: PresentationField<string>;
  character: PresentationField<CharacterValue>;
}

export interface PlayerPresentationV1 {
  version: 'v1';
  entrant: EntrantScope;
  player_profile_id: string | null;
  linked: boolean;
  presentation: ResolvedPresentation;
}

export interface PlayerProfile {
  id: string;
  workspace_id: string;
  discord_id?: string | null;
  display_name: string;
  avatar_url?: string | null;
  prefix?: string | null;
  country?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface PlayerProviderIdentity {
  id: string;
  player_profile_id: string;
  provider: string;
  provider_user_id: string;
  provider_gamer_tag?: string | null;
  verified: boolean;
  created_at: string;
  updated_at: string;
}

export interface PlayerGameProfile {
  id: string;
  player_profile_id: string;
  game_id: string;
  in_game_name?: string | null;
  in_game_id?: string | null;
}

export interface PlayerCharacterDefault {
  id: string;
  player_game_profile_id: string;
  character_id: string;
  character_name: string;
  character_image_url?: string | null;
  is_primary: boolean;
}

export interface TournamentEntrantOverride {
  id: string;
  workspace_id: string;
  provider: string;
  tournament_slug: string;
  event_id: string;
  entrant_id: string;
  player_profile_id?: string | null;
  display_name?: string | null;
  prefix?: string | null;
  country?: string | null;
  avatar_url?: string | null;
  character_id?: string | null;
  character_name?: string | null;
  character_image_url?: string | null;
  notes?: string | null;
  updated_by?: string | null;
  updated_at: string;
}

export interface PlayerCharacterDefaultItem {
  id: string;
  player_game_profile_id: string;
  character_id: string;
  character_name: string;
  character_image_url?: string | null;
  is_primary: boolean;
}

export interface PlayerGameProfileDetail {
  id: string;
  player_profile_id: string;
  game_id: string;
  in_game_name?: string | null;
  in_game_id?: string | null;
  character_defaults?: PlayerCharacterDefaultItem[];
}

export interface PlayerProfileDetailResponse extends PlayerProfile {
  provider_identities?: PlayerProviderIdentity[];
  game_profiles?: PlayerGameProfileDetail[];
}

export interface CreateProfilePayload {
  display_name: string;
  prefix?: string;
  country?: string;
  avatar_url?: string;
  discord_id?: string;
}

export interface UpdateProfilePayload {
  display_name?: string;
  prefix?: string;
  country?: string;
  avatar_url?: string;
  discord_id?: string;
  notes?: string;
}

export interface CreateGameProfilePayload {
  game_id: string;
  in_game_name?: string;
  in_game_id?: string;
}

export interface CreateCharacterDefaultPayload {
  character_id: string;
  character_name: string;
  character_image_url?: string;
  is_primary?: boolean;
}
