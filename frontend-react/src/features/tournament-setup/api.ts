import axios, { type AxiosError } from 'axios';
import type {
  AIConfig,
  AIProvider,
  DraftSection,
  IntegrationAccount,
  ProviderOAuthAvailability,
  ProblemDetail,
  SetupDraft,
  WizardStep,
} from './types';

const setupApi = axios.create({ headers: { 'Content-Type': 'application/json' } });

export async function listIntegrationAccounts(): Promise<IntegrationAccount[]> {
  const response = await setupApi.get<{ accounts?: IntegrationAccount[] }>('/api/integrations');
  return response.data.accounts ?? [];
}

export async function getProviderOAuthAvailability(): Promise<ProviderOAuthAvailability> {
  const response = await setupApi.get<{ oauth?: Partial<ProviderOAuthAvailability> }>('/api/auth/providers/capabilities');
  return {
    startgg: Boolean(response.data.oauth?.startgg),
    challonge: Boolean(response.data.oauth?.challonge),
  };
}

export async function createSetupDraft(): Promise<SetupDraft> {
  const response = await setupApi.post<SetupDraft>('/api/tournament-setup/drafts');
  return response.data;
}

export async function getSetupDraft(draftId: string): Promise<SetupDraft> {
  const response = await setupApi.get<SetupDraft>(`/api/tournament-setup/drafts/${encodeURIComponent(draftId)}`);
  return response.data;
}

export async function reopenTournamentSetup(tournamentSlug: string): Promise<SetupDraft> {
  const response = await setupApi.post<SetupDraft>(
    `/api/tournament-setup/tournaments/${encodeURIComponent(tournamentSlug)}/edit`,
  );
  return response.data;
}

export async function patchSetupDraft(
  draftId: string,
  revision: number,
  section: DraftSection,
  value: Record<string, unknown>,
  currentStep?: WizardStep,
): Promise<SetupDraft> {
  const response = await setupApi.patch<SetupDraft>(
    `/api/tournament-setup/drafts/${encodeURIComponent(draftId)}`,
    { section, value, current_step: currentStep },
    { headers: { 'If-Match': `"${revision}"` } },
  );
  return response.data;
}

export async function resolveProviderScope(
  draftId: string,
  revision: number,
  providerAccountId: string,
  locator: string,
  challongeSubdomain?: string,
): Promise<SetupDraft> {
  const response = await setupApi.post<SetupDraft>(
    `/api/tournament-setup/drafts/${encodeURIComponent(draftId)}/provider-resolution`,
    {
      revision,
      provider_account_id: providerAccountId,
      locator,
      ...(challongeSubdomain?.trim() ? { challonge_subdomain: challongeSubdomain.trim() } : {}),
    },
  );
  return response.data;
}

export async function selectProviderScope(
  draftId: string,
  revision: number,
  externalScopeId: string,
): Promise<SetupDraft> {
  const response = await setupApi.put<SetupDraft>(
    `/api/tournament-setup/drafts/${encodeURIComponent(draftId)}/provider-scope`,
    { revision, external_scope_id: externalScopeId },
  );
  return response.data;
}

export async function getAIConfig(): Promise<AIConfig> {
  const response = await setupApi.get<AIConfig>('/api/ai/config');
  return response.data;
}

export async function patchAIConfig(value: Partial<AIConfig>): Promise<AIConfig> {
  const response = await setupApi.patch<AIConfig>('/api/ai/config', value);
  return response.data;
}

export async function setAIConnectionCredential(provider: AIProvider, apiKey: string): Promise<AIConfig> {
  await setupApi.put(`/api/ai/connections/${provider}/credential`, { api_key: apiKey });
  return getAIConfig();
}

export async function testAIConnection(provider: AIProvider, model?: string): Promise<{ ok?: boolean; message?: string }> {
  const response = await setupApi.post<{ ok?: boolean; message?: string }>(
    `/api/ai/connections/${provider}/test`,
    model?.trim() ? { model: model.trim() } : undefined,
  );
  return response.data;
}

export async function materializeSetupDraft(draftId: string, revision: number): Promise<{ tournament_id: string; status: string }> {
  const response = await setupApi.post(`/api/tournament-setup/drafts/${encodeURIComponent(draftId)}/materialize`, { revision });
  return response.data;
}

export async function activateSetupDraft(draftId: string, revision: number, idempotencyKey = crypto.randomUUID()): Promise<{ tournament_id: string; status: string }> {
  const response = await setupApi.post(`/api/tournament-setup/drafts/${encodeURIComponent(draftId)}/activate`, { revision, idempotency_key: idempotencyKey });
  return response.data;
}

export function getApiErrorMessage(error: unknown, fallback: string): string {
  const response = (error as AxiosError<ProblemDetail> | undefined)?.response;
  const detail = response?.data?.message ?? response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (detail && typeof detail === 'object') {
    const nested = detail.message ?? detail.detail ?? detail.code;
    if (typeof nested === 'string' && nested.trim()) return nested;
  }
  return fallback;
}
