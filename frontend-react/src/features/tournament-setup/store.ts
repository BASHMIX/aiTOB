import { create } from 'zustand';
import {
  createSetupDraft,
  getAIConfig,
  getApiErrorMessage,
  getSetupDraft,
  listIntegrationAccounts,
  patchAIConfig,
  patchSetupDraft,
  resolveProviderScope,
  selectProviderScope,
  setAIConnectionCredential,
  testAIConnection,
  materializeSetupDraft,
  activateSetupDraft,
} from './api';
import type {
  AIConfig,
  AIProvider,
  DraftSection,
  IntegrationAccount,
  ProviderResolution,
  SetupDraft,
  WizardStep,
} from './types';

interface SetupStore {
  draft: SetupDraft | null;
  accounts: IntegrationAccount[];
  aiConfig: AIConfig | null;
  loading: boolean;
  saving: boolean;
  resolving: boolean;
  error: string | null;
  saveState: 'idle' | 'saved' | 'error';
  load: (draftId?: string) => Promise<SetupDraft>;
  setDraft: (draft: SetupDraft) => void;
  updateSection: (section: DraftSection, value: Record<string, unknown>) => void;
  saveSection: (section: DraftSection, value: Record<string, unknown>, currentStep?: WizardStep) => Promise<SetupDraft | null>;
  resolveProvider: (providerAccountId: string, locator: string, subdomain?: string) => Promise<SetupDraft | null>;
  selectScope: (externalScopeId: string) => Promise<SetupDraft | null>;
  saveAISettings: (value: Partial<AIConfig>) => Promise<AIConfig | null>;
  saveAIKey: (provider: AIProvider, apiKey: string) => Promise<AIConfig | null>;
  testAI: (provider: AIProvider, model?: string) => Promise<{ ok?: boolean; message?: string } | null>;
  materialize: () => Promise<{ tournament_id: string; status: string } | null>;
  activate: () => Promise<{ tournament_id: string; status: string } | null>;
  clearError: () => void;
}

function updateDraftSection(draft: SetupDraft, section: DraftSection, value: Record<string, unknown>): SetupDraft {
  if (section === 'provider_scope') return { ...draft, provider_scope: value as SetupDraft['provider_scope'] };
  if (section === 'tournament_review') return { ...draft, tournament_review: value };
  if (section === 'operating_profile') return { ...draft, operating_profile: value };
  if (section === 'discord_setup') return { ...draft, discord_setup: value as SetupDraft['discord_setup'] };
  if (section === 'assistant_setup') return { ...draft, assistant_setup: value as SetupDraft['assistant_setup'] };
  return { ...draft };
}

export const useTournamentSetupStore = create<SetupStore>((set, get) => ({
  draft: null,
  accounts: [],
  aiConfig: null,
  loading: false,
  saving: false,
  resolving: false,
  error: null,
  saveState: 'idle',
  load: async (draftId) => {
    set({ loading: true, error: null });
    try {
      const [draft, accounts, aiConfig] = await Promise.all([
        draftId ? getSetupDraft(draftId) : createSetupDraft(),
        listIntegrationAccounts(),
        getAIConfig(),
      ]);
      set({ draft, accounts, aiConfig, loading: false, saveState: 'saved' });
      return draft;
    } catch (error) {
      const message = getApiErrorMessage(error, 'Could not load tournament setup.');
      set({ loading: false, error: message, saveState: 'error' });
      throw new Error(message);
    }
  },
  setDraft: (draft) => set({ draft, error: null }),
  updateSection: (section, value) => set((state) => state.draft ? { draft: updateDraftSection(state.draft, section, value), saveState: 'idle' } : state),
  saveSection: async (section, value, currentStep) => {
    const draft = get().draft;
    if (!draft) return null;
    set({ saving: true, error: null, saveState: 'idle' });
    try {
      const updated = await patchSetupDraft(draft.id, draft.revision, section, value, currentStep);
      set({ draft: updated, saving: false, saveState: 'saved' });
      return updated;
    } catch (error) {
      const message = getApiErrorMessage(error, 'Could not save this setup step.');
      set({ saving: false, error: message, saveState: 'error' });
      return null;
    }
  },
  resolveProvider: async (providerAccountId, locator, subdomain) => {
    const draft = get().draft;
    if (!draft) return null;
    set({ resolving: true, error: null });
    try {
      const updated = await resolveProviderScope(draft.id, draft.revision, providerAccountId, locator, subdomain);
      set({ draft: updated, resolving: false, saveState: 'saved' });
      return updated;
    } catch (error) {
      set({ resolving: false, error: getApiErrorMessage(error, 'Could not resolve this provider event.') });
      return null;
    }
  },
  selectScope: async (externalScopeId) => {
    const draft = get().draft;
    if (!draft) return null;
    set({ resolving: true, error: null });
    try {
      const updated = await selectProviderScope(draft.id, draft.revision, externalScopeId);
      set({ draft: updated, resolving: false, saveState: 'saved' });
      return updated;
    } catch (error) {
      set({ resolving: false, error: getApiErrorMessage(error, 'Could not select this event.') });
      return null;
    }
  },
  saveAISettings: async (value) => {
    try {
      const config = await patchAIConfig(value);
      set({ aiConfig: config, error: null });
      return config;
    } catch (error) {
      set({ error: getApiErrorMessage(error, 'Could not save assistant settings.') });
      return null;
    }
  },
  saveAIKey: async (provider, apiKey) => {
    try {
      const config = await setAIConnectionCredential(provider, apiKey);
      set({ aiConfig: config, error: null });
      return config;
    } catch (error) {
      set({ error: getApiErrorMessage(error, 'Could not save the API key.') });
      return null;
    }
  },
  testAI: async (provider, model) => {
    try {
      return await testAIConnection(provider, model);
    } catch (error) {
      const message = getApiErrorMessage(error, 'Connection test failed.');
      set({ error: message });
      return null;
    }
  },
  materialize: async () => {
    const draft = get().draft;
    if (!draft) return null;
    try {
      const result = await materializeSetupDraft(draft.id, draft.revision);
      const updated = await getSetupDraft(draft.id);
      set({ draft: updated, error: null, saveState: 'saved' });
      return result;
    }
    catch (error) { set({ error: getApiErrorMessage(error, 'Could not save the tournament.') }); return null; }
  },
  activate: async () => {
    const draft = get().draft;
    if (!draft) return null;
    try {
      const result = await activateSetupDraft(draft.id, draft.revision);
      const updated = await getSetupDraft(draft.id);
      set({ draft: updated, error: null, saveState: 'saved' });
      return result;
    }
    catch (error) { set({ error: getApiErrorMessage(error, 'Could not activate aiTOB management.') }); return null; }
  },
  clearError: () => set({ error: null }),
}));

export type { ProviderResolution };
