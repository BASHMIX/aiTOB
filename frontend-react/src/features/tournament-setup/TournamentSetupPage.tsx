import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import axios from 'axios';
import { AssistantStep } from './components/AssistantStep';
import { DiscordStep } from './components/DiscordStep';
import { ProviderStep, type ProviderStepValue } from './components/ProviderStep';
import { parseDiscordOAuthReturn, useTournamentSetupStore } from './store';
import type { AssistantSetupDraft, DiscordSetupDraft, WizardStep } from './types';

const WIZARD_STEPS: Array<{ id: WizardStep; label: string; description: string }> = [
  { id: 'provider', label: 'Provider & event', description: 'Connect an account and choose the exact event.' },
  { id: 'tournament', label: 'Tournament', description: 'Review provider facts, branding, and operating defaults.' },
  { id: 'discord', label: 'Discord', description: 'Choose the guild, channels, and bot behavior.' },
  { id: 'assistant', label: 'AI assistant', description: 'Configure the workspace-owned assistant connection.' },
  { id: 'review', label: 'Review & add', description: 'Check readiness, save, and add the ready card to the Hub.' },
];

function resolveStep(step: string | undefined): WizardStep {
  return WIZARD_STEPS.some((candidate) => candidate.id === step) ? (step as WizardStep) : 'provider';
}

const emptyProvider: ProviderStepValue = { provider_type: 'startgg', provider_account_id: '', locator: '', challonge_subdomain: '', resolution: null };

export function TournamentSetupPage() {
  const { draftId, step } = useParams<{ draftId?: string; step?: string }>();
  const navigate = useNavigate();
  const currentStep = resolveStep(step);
  const currentIndex = WIZARD_STEPS.findIndex((candidate) => candidate.id === currentStep);
  // `/new` has no draft id yet. Keep a distinct route key so the initial
  // create-draft request is not mistaken for an already-loaded undefined id.
  const loadedFor = useRef<string | null>(null);
  const [providerForm, setProviderForm] = useState<ProviderStepValue>(emptyProvider);
  const [assistantForm, setAssistantForm] = useState<AssistantSetupDraft>({});
  const [discordForm, setDiscordForm] = useState<DiscordSetupDraft>({});
  const [discordConnectionNotice, setDiscordConnectionNotice] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState<'materialize' | null>(null);
  const [providerConnectionError, setProviderConnectionError] = useState<string | null>(null);
  const draft = useTournamentSetupStore((state) => state.draft);
  const accounts = useTournamentSetupStore((state) => state.accounts);
  const aiConfig = useTournamentSetupStore((state) => state.aiConfig);
  const loading = useTournamentSetupStore((state) => state.loading);
  const saving = useTournamentSetupStore((state) => state.saving);
  const resolving = useTournamentSetupStore((state) => state.resolving);
  const error = useTournamentSetupStore((state) => state.error);
  const saveState = useTournamentSetupStore((state) => state.saveState);
  const load = useTournamentSetupStore((state) => state.load);
  const setDraft = useTournamentSetupStore((state) => state.setDraft);
  const saveSection = useTournamentSetupStore((state) => state.saveSection);
  const resolveProvider = useTournamentSetupStore((state) => state.resolveProvider);
  const selectScope = useTournamentSetupStore((state) => state.selectScope);
  const saveAISettings = useTournamentSetupStore((state) => state.saveAISettings);
  const saveAIKey = useTournamentSetupStore((state) => state.saveAIKey);
  const testAI = useTournamentSetupStore((state) => state.testAI);
  const materialize = useTournamentSetupStore((state) => state.materialize);

  useEffect(() => {
    const routeKey = draftId || '__new__';
    if (loadedFor.current === routeKey) return;
    loadedFor.current = routeKey;
    void load(draftId).then((loadedDraft) => {
      const oauthParams = new URLSearchParams(window.location.search);
      const discordOAuth = parseDiscordOAuthReturn(window.location.search);
      const oauthAccountId = oauthParams.get('account_id') || '';
      const oauthOutcome = oauthParams.get('provider_oauth');
      if (oauthOutcome === 'failed') setProviderConnectionError('Provider sign-in failed. Check the provider application settings and try again.');
      else if (oauthOutcome === 'cancelled') setProviderConnectionError('Provider sign-in was cancelled.');
      setProviderForm({
        provider_type: loadedDraft.provider_scope?.provider || loadedDraft.provider_scope?.provider_type || 'startgg',
        provider_account_id: oauthAccountId || loadedDraft.provider_scope?.account_id || '',
        locator: displayLocator(loadedDraft.provider_scope?.locator) || displayLocator(loadedDraft.provider_scope?.tournament?.canonical_slug) || '',
        resolution: loadedDraft.provider_scope || null,
      });
      setAssistantForm(loadedDraft.assistant_setup || {});
      setDiscordForm(loadedDraft.discord_setup || {});
      setDiscordConnectionNotice(discordOAuth.notice);
      if (discordOAuth.outcome) window.history.replaceState({}, '', window.location.pathname);
      if (!draftId) navigate(`/admin/tournaments/setup/${loadedDraft.id}/provider`, { replace: true });
    }).catch(() => undefined);
  }, [draftId, load, navigate]);

  // Debounced, revisioned autosave keeps a reload resumable without sending a
  // request for every character typed into a field. Provider scope is excluded
  // here: discovery and exact-event selection already persist the canonical
  // provider resolution through their dedicated endpoints. Writing the view
  // model back as provider_scope would lose the tournament/event facts.
  useEffect(() => {
    if (!draft || loading || currentStep !== 'assistant') return;
    const timer = window.setTimeout(() => { void saveSection('assistant_setup', assistantForm as Record<string, unknown>, currentStep); }, 650);
    return () => window.clearTimeout(timer);
  }, [assistantForm, currentStep, draft?.id, loading, saveSection]);
  useEffect(() => {
    if (!draft || loading || currentStep !== 'discord') return;
    const timer = window.setTimeout(() => { void saveSection('discord_setup', discordForm as Record<string, unknown>, currentStep); }, 650);
    return () => window.clearTimeout(timer);
  }, [discordForm, currentStep, draft?.id, loading, saveSection]);
  useEffect(() => {
    if (!draft || loading || currentStep !== 'tournament') return;
    const timer = window.setTimeout(() => {
      void saveSection('tournament_review', draft.tournament_review, currentStep);
    }, 650);
    return () => window.clearTimeout(timer);
  }, [draft?.id, draft?.tournament_review?.display_name, draft?.tournament_review?.provider_dq_timer_seconds, currentStep, loading, saveSection]);

  const goTo = (next: WizardStep) => { if (draft) navigate(`/admin/tournaments/setup/${draft.id}/${next}`); };
  const providerType = providerForm.provider_type || 'startgg';
  const selectedScope = providerForm.resolution?.selected_scope || draft?.provider_scope?.selected_scope;
  const handleMaterialize = async () => {
    setActionBusy('materialize');
    const result = await materialize();
    setActionBusy(null);
    if (result) navigate('/admin/hub');
  };

  const handleProviderConnect = async (provider: 'startgg' | 'challonge') => {
    setProviderConnectionError(null);
    try {
      const response = await axios.post(`/api/auth/providers/${provider}/connect`, {
        draft_id: draft?.id,
        return_step: currentStep,
      });
      window.location.assign(response.data.authorization_url);
    } catch (error: any) {
      setProviderConnectionError(error.response?.data?.detail || `Could not start ${provider} sign-in.`);
    }
  };

  if (loading || !draft) {
    return (
      <main className="min-h-screen bg-appDark px-4 py-12 text-white">
        <div className="mx-auto max-w-3xl rounded-2xl border border-white/10 bg-cardDark p-8 text-center">
          <p className="text-sm text-textDim">{loading ? 'Loading tournament setup…' : 'Could not load tournament setup.'}</p>
          {error && <p role="alert" className="mt-3 text-sm text-red-200">{error}</p>}
          {!loading && error && (
            <div className="mt-5 flex flex-wrap justify-center gap-3">
              <button type="button" onClick={() => void load(draftId)} className="min-h-11 rounded-lg bg-accentYellow px-4 py-2 text-xs font-bold text-black">Retry</button>
              <Link to="/admin/hub" className="min-h-11 rounded-lg border border-white/15 px-4 py-2 text-xs font-bold text-white">Back to hub</Link>
            </div>
          )}
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-appDark px-4 py-8 text-white sm:px-6 lg:px-10" dir="ltr">
      <div className="mx-auto max-w-6xl">
        <header className="mb-8 flex flex-wrap items-start justify-between gap-4">
          <div><p className="mb-2 text-xs font-mono uppercase tracking-[0.2em] text-textDim">aiTOB setup</p><h1 className="text-3xl font-bold tracking-tight">Create tournament</h1><p className="mt-2 max-w-2xl text-sm text-textDim">Set up the provider event, operations, Discord registration, and your Workspace assistant in one guided flow.</p></div>
          <div className="flex items-center gap-3"><span role="status" className="text-xs text-textDim">{saving ? 'Saving…' : saveState === 'saved' ? 'All changes saved' : 'Unsaved changes'}</span><Link to="/admin/hub" className="min-h-11 rounded-lg border border-white/10 px-4 py-2.5 text-sm text-textLight transition hover:border-white/30 hover:bg-white/5">Back to hub</Link></div>
        </header>

        <nav aria-label="Tournament setup steps" className="mb-8 overflow-x-auto pb-2"><ol className="flex min-w-max gap-2 sm:gap-3">{WIZARD_STEPS.map((wizardStep, index) => { const isCurrent = wizardStep.id === currentStep; const isComplete = draft.completed_steps.includes(wizardStep.id) || index < currentIndex; return <li key={wizardStep.id} className="flex items-center gap-2 sm:gap-3"><button type="button" onClick={() => goTo(wizardStep.id)} aria-current={isCurrent ? 'step' : undefined} className={`flex min-h-11 min-w-[9.5rem] items-center gap-3 rounded-xl border px-3 py-2 text-left ${isCurrent ? 'border-accentYellow/60 bg-accentYellow/10' : 'border-white/10 bg-cardDark/70 hover:border-white/25'}`}><span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${isCurrent ? 'bg-accentYellow text-black' : isComplete ? 'bg-statusGreen/20 text-statusGreen' : 'bg-white/10 text-textDim'}`}>{isComplete && !isCurrent ? '✓' : index + 1}</span><span><span className="block text-sm font-semibold">{wizardStep.label}</span><span className="sr-only">{wizardStep.description}</span></span></button>{index < WIZARD_STEPS.length - 1 && <span aria-hidden="true" className="text-white/20">→</span>}</li>; })}</ol></nav>

        <section className="rounded-2xl border border-white/10 bg-cardDark/80 p-6 shadow-2xl sm:p-8" aria-labelledby="setup-step-title">
          <p className="mb-3 text-xs font-mono uppercase tracking-[0.18em] text-accentYellow">Step {currentIndex + 1} of {WIZARD_STEPS.length}</p>
          {currentStep === 'provider' && <ProviderStep value={providerForm} accounts={accounts} resolving={resolving} error={providerConnectionError || error} onChange={setProviderForm} onResolve={async ({ providerAccountId, locator, subdomain }) => { const updated = await resolveProvider(providerAccountId, locator, subdomain); if (updated) setProviderForm((current) => ({ ...current, resolution: updated.provider_scope || null })); }} onSelectScope={async (scopeId) => { const updated = await selectScope(scopeId); if (updated) setProviderForm((current) => ({ ...current, resolution: updated.provider_scope || current.resolution, selected_scope_id: scopeId })); }} onConnect={handleProviderConnect} />}
          {currentStep === 'tournament' && <div className="space-y-6"><div><h2 id="setup-step-title" className="text-2xl font-semibold">Review tournament</h2><p className="mt-2 text-sm text-textDim">Provider facts remain read-only. Add local branding and operating defaults as overrides.</p></div><div className="grid gap-4 sm:grid-cols-2"><Info label="Tournament" value={displayFact(draft.provider_scope?.tournament?.name) || 'Choose an Event in the provider step'} /><Info label="Game" value={displayFact(selectedScope?.game) || displayFact(draft.provider_scope?.tournament?.game) || '—'} /><Info label="Provider state" value={displayFact(selectedScope?.state) || displayFact(draft.provider_scope?.tournament?.state) || '—'} /><Info label="Exact scope" value={displayFact(selectedScope?.name) || selectedScope?.canonical_slug || selectedScope?.external_id || 'Not selected'} /></div><label className="block text-xs font-medium text-textDim" htmlFor="local-tournament-name">Local display name<input id="local-tournament-name" value={String(draft.tournament_review.display_name || displayFact(draft.provider_scope?.tournament?.name) || '')} onChange={(event) => setDraft({ ...draft, tournament_review: { ...draft.tournament_review, display_name: event.target.value } })} className="mt-1 w-full rounded-lg border border-white/10 bg-appDark px-3 py-2.5 text-sm text-white" /></label>{providerType === 'startgg' && <label className="block text-xs font-medium text-textDim" htmlFor="provider-dq-timer">Start.gg match DQ timer (minutes)<input id="provider-dq-timer" type="number" min={1} max={120} value={Math.max(1, Math.round(Number(draft.tournament_review.provider_dq_timer_seconds ?? 600) / 60))} onChange={(event) => setDraft({ ...draft, tournament_review: { ...draft.tournament_review, provider_dq_timer_seconds: Math.max(60, Math.min(7200, Number(event.target.value || 1) * 60)) } })} className="mt-1 w-full rounded-lg border border-white/10 bg-appDark px-3 py-2.5 text-sm text-white" /><span className="mt-1 block text-[11px] leading-relaxed text-textDim">Mirror the DQ Timer configured for this Start.gg round. The public API does not expose or change that setting.</span></label>}<p className="rounded-lg border border-amber-300/20 bg-amber-300/5 px-3 py-2 text-xs text-amber-100">Start-in-wave monitoring and remote provider start require a fresh, explicit provider scope before activation.</p></div>}
          {currentStep === 'discord' && <DiscordStep draftId={draft.id} providerType={providerType} accounts={accounts} value={discordForm} onChange={setDiscordForm} connectionNotice={discordConnectionNotice} />}
          {currentStep === 'assistant' && <AssistantStep value={assistantForm} aiConfig={aiConfig} onChange={setAssistantForm} onSaveKey={async (provider, key) => { await saveAIKey(provider, key); }} onSaveSettings={async (settings) => { await saveAISettings(settings); }} onTest={async (provider, model) => { await testAI(provider, model); }} busy={saving} error={error} />}
          {currentStep === 'review' && <div className="space-y-6"><div><h2 id="setup-step-title" className="text-2xl font-semibold">Review and add to Hub</h2><p className="mt-2 text-sm text-textDim">Confirm the setup and add a ready tournament card to the Hub. Provider bracket start remains a separate action on that card.</p></div>{error && <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-red-300/30 bg-red-300/10 px-3 py-2 text-sm text-red-100"><span>{error}</span>{error.toLowerCase().includes('stale') && <button type="button" onClick={() => goTo('provider')} className="min-h-9 rounded-md border border-red-200/30 px-3 py-1 text-xs font-bold text-red-50 hover:bg-red-200/10">Recheck provider</button>}</div>}<div className="grid gap-3 sm:grid-cols-2"><ReviewCard title="Provider" status={selectedScope ? 'Ready' : 'Required'} detail={selectedScope ? `${providerType === 'startgg' ? 'Start.gg' : 'Challonge'} · ${displayFact(selectedScope.name) || selectedScope.external_id}` : 'Select an exact Event or bracket'} onEdit={() => goTo('provider')} /><ReviewCard title="Tournament" status={draft.tournament_review.display_name ? 'Ready' : 'Review'} detail={String(draft.tournament_review.display_name || displayFact(draft.provider_scope?.tournament?.name) || 'Local name is optional until review')} onEdit={() => goTo('tournament')} /><ReviewCard title="Discord registration" status={discordForm.registration?.enabled ? 'Enabled' : 'Skipped'} detail={discordForm.registration?.enabled ? 'Window and identity policy configured' : 'Optional'} onEdit={() => goTo('discord')} /><ReviewCard title="Workspace assistant" status={aiConfig?.connections?.[assistantForm.provider_type || aiConfig?.provider_type || 'gemini']?.configured ? 'Connected' : 'Optional'} detail={assistantForm.provider_type || aiConfig?.provider_type || 'gemini'} onEdit={() => goTo('assistant')} /></div><div className="flex flex-wrap gap-3"><button type="button" onClick={() => void saveSection('navigation', { action: 'save' }, 'review')} className="min-h-11 rounded-lg border border-white/15 px-4 py-2 text-xs font-bold text-white">Save draft</button><button type="button" disabled={!selectedScope || actionBusy !== null} onClick={() => void handleMaterialize()} className="min-h-11 rounded-lg bg-accentYellow px-4 py-2 text-xs font-bold text-black disabled:cursor-not-allowed disabled:opacity-40">{actionBusy === 'materialize' ? 'Adding…' : 'Add tournament to Hub'}</button><p className="self-center text-xs text-textDim">This does not start the provider bracket or dispatcher.</p></div></div>}
          {currentStep !== 'review' && <div className="mt-8 flex flex-wrap justify-between gap-3 border-t border-white/10 pt-5"><button type="button" onClick={() => goTo(WIZARD_STEPS[Math.max(0, currentIndex - 1)].id)} disabled={currentIndex === 0} className="min-h-11 rounded-lg border border-white/15 px-4 py-2 text-xs font-bold text-white disabled:opacity-30">Back</button><button type="button" onClick={() => goTo(WIZARD_STEPS[Math.min(WIZARD_STEPS.length - 1, currentIndex + 1)].id)} className="min-h-11 rounded-lg bg-accentYellow px-4 py-2 text-xs font-bold text-black">Continue</button></div>}
        </section>
      </div>
    </main>
  );
}

function Info({ label, value }: { label: string; value: string }) { return <div className="rounded-lg border border-white/10 bg-black/10 p-4"><p className="text-[10px] font-mono uppercase tracking-wider text-textDim">{label}</p><p className="mt-1 text-sm font-semibold text-white">{value}</p></div>; }
function ReviewCard({ title, status, detail, onEdit }: { title: string; status: string; detail: string; onEdit: () => void }) { return <article className="rounded-xl border border-white/10 bg-black/10 p-4"><div className="flex items-start justify-between gap-3"><div><h3 className="text-sm font-semibold text-white">{title}</h3><p className="mt-1 text-xs text-textDim">{detail}</p></div><span className="rounded-full border border-white/15 px-2 py-1 text-[10px] text-textDim">{status}</span></div><button type="button" onClick={onEdit} className="mt-4 min-h-11 text-xs font-bold text-accentYellow hover:underline">Edit step</button></article>; }

function displayFact(value: unknown): string | null {
  if (typeof value === 'string' && value.trim()) return value;
  if (value && typeof value === 'object' && 'value' in value) {
    const fact = value as { value?: unknown };
    return typeof fact.value === 'string' && fact.value.trim() ? fact.value : null;
  }
  return null;
}

function displayLocator(value: unknown): string | null {
  if (typeof value === 'string' && value.trim()) return value;
  if (value && typeof value === 'object') {
    const locator = value as { raw?: unknown; canonical?: unknown };
    for (const candidate of [locator.raw, locator.canonical]) {
      if (typeof candidate === 'string' && candidate.trim()) return candidate;
    }
  }
  return null;
}
