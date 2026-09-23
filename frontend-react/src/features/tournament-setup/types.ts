export type ProviderType = 'startgg' | 'challonge';
export type AIProvider = 'gemini' | 'openai';
export type AssistantMode = 'disabled' | 'read_only' | 'propose_only';
export type WizardStep = 'provider' | 'tournament' | 'discord' | 'assistant' | 'review';
export type DraftStatus = 'editing' | 'ready' | 'materialized' | 'abandoned';
export type DraftSection =
  | 'provider_scope'
  | 'tournament_review'
  | 'operating_profile'
  | 'discord_setup'
  | 'assistant_setup'
  | 'navigation';

export interface IntegrationAccount {
  id: string;
  provider_type: string;
  display_name: string;
  external_account_id: string;
  status: string;
  configured: boolean;
  credential_types?: string[];
  destinations?: IntegrationDestination[];
  metadata?: Record<string, unknown>;
}

export interface IntegrationDestination {
  destination_type: string;
  external_id?: string;
  display_name: string;
  configured?: boolean;
  status?: string;
}

export interface ProviderScope {
  external_id: string;
  canonical_slug?: string | null;
  name?: string | null;
  game?: string | null;
  start_at?: string | null;
  state?: string | null;
  kind?: string | null;
}

export interface ProviderResolution {
  provider?: ProviderType;
  provider_type?: ProviderType;
  account_id?: string;
  locator?: string;
  observed_at?: string | null;
  freshness?: { state?: string; observed_at?: string | null } | null;
  provenance?: { source?: string; locator?: string; observed_at?: string | null } | null;
  tournament?: {
    external_id?: string;
    canonical_slug?: string | null;
    name?: string | null;
    game?: string | null;
    start_at?: string | null;
    state?: string | null;
    image_url?: string | null;
  } | null;
  scopes?: ProviderScope[];
  selected_scope?: ProviderScope | null;
  resolution?: string;
  capabilities?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface SetupDraft {
  id: string;
  revision: number;
  status: DraftStatus;
  current_step: WizardStep;
  completed_steps: WizardStep[];
  provider_scope?: ProviderResolution | null;
  tournament_review: Record<string, unknown>;
  operating_profile: Record<string, unknown>;
  discord_setup: DiscordSetupDraft;
  assistant_setup: AssistantSetupDraft;
  validation: Record<string, ReadinessCheck[]>;
  materialized_tournament_id?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ReadinessCheck {
  code: string;
  step: WizardStep;
  field_path?: string | null;
  requirement: 'required' | 'optional';
  state: 'ready' | 'warning' | 'blocked';
  message: string;
}

export interface DiscordSetupDraft {
  enabled?: boolean;
  guild_id?: string;
  guild_name?: string;
  discord_account_id?: string;
  destination_external_id?: string;
  destination_name?: string;
  registration?: RegistrationConfig;
  [key: string]: unknown;
}

export interface RegistrationConfig {
  enabled: boolean;
  destination_external_id: string;
  opens_at: string;
  closes_at: string;
  display_timezone: string;
  require_provider_registration: boolean;
  gamertag_verification_policy: 'exact_discord_name' | 'set_server_nickname' | 'match_or_set_nickname';
  startgg_bio_verification_enabled: boolean;
  image_policy: 'disabled' | 'optional' | 'required';
  verified_role_external_id: string;
  announcement_policy?: Record<string, unknown>;
}

export interface AssistantSetupDraft {
  provider_type?: AIProvider;
  model?: string;
  mode?: AssistantMode;
  request_limit?: number;
  token_limit?: number;
  context_char_limit?: number;
  response_char_limit?: number;
  request_timeout_seconds?: number;
  policy_version?: string;
  [key: string]: unknown;
}

export interface AIConnectionCard {
  account_id?: string | null;
  configured: boolean;
  enabled: boolean;
  health: string;
  failure_category?: string | null;
  last_tested_at?: string | null;
  last_succeeded_at?: string | null;
  display_name?: string | null;
}

export interface AIConfig extends AssistantSetupDraft {
  provider_type: AIProvider;
  model: string;
  mode: AssistantMode;
  key_configured: boolean;
  selected_account_id?: string | null;
  active_provider?: AIProvider;
  connections?: Record<AIProvider, AIConnectionCard>;
  last_test_status?: string;
  last_tested_at?: string | null;
  last_test_message?: string | null;
}

export interface ProblemDetail {
  code?: string;
  message?: string;
  detail?: string | { code?: string; message?: string; detail?: string };
}
