import { useEffect, useState } from 'react';
import type { AIConfig, AIProvider, AssistantMode, AssistantSetupDraft } from '../types';

interface AssistantStepProps {
  value: AssistantSetupDraft;
  aiConfig?: AIConfig | null;
  apiKey?: string;
  onChange: (value: AssistantSetupDraft) => void;
  onApiKeyChange?: (value: string) => void;
  onSaveKey?: (provider: AIProvider, apiKey: string) => void | Promise<void>;
  onSaveSettings?: (value: AssistantSetupDraft) => void | Promise<void>;
  onTest?: (provider: AIProvider, model?: string) => void | Promise<void>;
  busy?: boolean;
  error?: string | null;
}

const inputClass = 'mt-1 w-full rounded-lg border border-white/10 bg-appDark px-3 py-2.5 text-sm text-white outline-none transition focus:border-accentYellow/60';
const providers: Array<{ id: AIProvider; label: string; detail: string }> = [
  { id: 'gemini', label: 'Google Gemini', detail: 'Use your own Google AI API key.' },
  { id: 'openai', label: 'OpenAI', detail: 'Use your own OpenAI API key.' },
];

function numberValue(value: number | undefined, fallback: number): number {
  return Number.isFinite(value) ? Number(value) : fallback;
}

export function AssistantStep({ value, aiConfig, apiKey = '', onChange, onApiKeyChange, onSaveKey, onSaveSettings, onTest, busy = false, error = null }: AssistantStepProps) {
  const provider = value.provider_type || aiConfig?.provider_type || 'gemini';
  const [key, setKey] = useState(apiKey);
  const [message, setMessage] = useState<string | null>(null);
  useEffect(() => setKey(apiKey), [apiKey]);
  const patch = (next: Partial<AssistantSetupDraft>) => onChange({ ...value, ...next });
  const saveKey = async () => {
    if (!key.trim()) { setMessage('Enter a new API key to save it.'); return; }
    setMessage(null);
    await onSaveKey?.(provider, key.trim());
    setKey('');
    onApiKeyChange?.('');
    setMessage('Key saved securely. It will never be shown again.');
  };

  return (
    <div className="space-y-6" data-testid="assistant-step">
      <div>
        <h2 className="text-2xl font-semibold text-white">Organizer AI assistant</h2>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-textDim">The assistant configuration belongs to this Workspace and applies to its tournaments. Bring your own Gemini or OpenAI key; aiTOB does not resell tokens.</p>
      </div>

      <div className="rounded-xl border border-accentYellow/20 bg-accentYellow/5 p-4 text-xs leading-relaxed text-textDim">
        <strong className="text-accentYellow">Your existing assistant controls stay active.</strong> Choose the provider and model, then keep read-only or propose-only behavior. The assistant cannot approve or execute tournament actions.
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {providers.map((item) => {
          const active = provider === item.id;
          const card = aiConfig?.connections?.[item.id];
          return (
            <button type="button" key={item.id} aria-pressed={active} onClick={() => patch({ provider_type: item.id })} className={`rounded-xl border p-4 text-left transition ${active ? 'border-accentYellow/60 bg-accentYellow/10' : 'border-white/10 bg-black/10 hover:border-white/25'}`}>
              <span className="flex items-center justify-between gap-3"><span className="font-semibold text-white">{item.label}</span><span className={`rounded-full border px-2 py-0.5 text-[10px] ${card?.configured ? 'border-statusGreen/30 text-statusGreen' : 'border-white/10 text-textDim'}`}>{card?.configured ? 'Key configured' : 'No key'}</span></span>
              <span className="mt-1 block text-xs text-textDim">{item.detail}</span>
            </button>
          );
        })}
      </div>

      <section className="rounded-xl border border-white/10 bg-black/10 p-4 sm:p-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="text-xs font-medium text-textDim" htmlFor="assistant-model">Model
            <input id="assistant-model" value={value.model || aiConfig?.model || ''} onChange={(event) => patch({ model: event.target.value })} className={inputClass} placeholder={provider === 'gemini' ? 'gemini-2.0-flash' : 'gpt-4o-mini'} />
          </label>
          <label className="text-xs font-medium text-textDim" htmlFor="assistant-mode">Operating mode
            <select id="assistant-mode" value={(value.mode || aiConfig?.mode || 'read_only') as AssistantMode} onChange={(event) => patch({ mode: event.target.value as AssistantMode })} className={inputClass}>
              <option value="disabled">Disabled</option><option value="read_only">Read only</option><option value="propose_only">Propose only · organizer approval required</option>
            </select>
          </label>
        </div>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <label className="text-xs font-medium text-textDim" htmlFor="assistant-request-limit">Requests / hour<input id="assistant-request-limit" type="number" min="1" value={numberValue(value.request_limit ?? aiConfig?.request_limit, 60)} onChange={(event) => patch({ request_limit: Number(event.target.value) })} className={inputClass} /></label>
          <label className="text-xs font-medium text-textDim" htmlFor="assistant-token-limit">Tokens / hour<input id="assistant-token-limit" type="number" min="256" value={numberValue(value.token_limit ?? aiConfig?.token_limit, 100000)} onChange={(event) => patch({ token_limit: Number(event.target.value) })} className={inputClass} /></label>
          <label className="text-xs font-medium text-textDim" htmlFor="assistant-context-limit">Context characters<input id="assistant-context-limit" type="number" min="512" value={numberValue(value.context_char_limit ?? aiConfig?.context_char_limit, 12000)} onChange={(event) => patch({ context_char_limit: Number(event.target.value) })} className={inputClass} /></label>
          <label className="text-xs font-medium text-textDim" htmlFor="assistant-timeout">Timeout seconds<input id="assistant-timeout" type="number" min="3" max="120" value={numberValue(value.request_timeout_seconds ?? aiConfig?.request_timeout_seconds, 30)} onChange={(event) => patch({ request_timeout_seconds: Number(event.target.value) })} className={inputClass} /></label>
        </div>
      </section>

      <section className="rounded-xl border border-white/10 bg-black/10 p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="text-sm font-semibold text-white">Workspace API key</h3><p className="mt-1 text-xs text-textDim">Write-only field for {providers.find((item) => item.id === provider)?.label}. Existing keys are represented only by a safe status.</p></div><span className={`rounded-full border px-2 py-1 text-[10px] ${aiConfig?.connections?.[provider]?.configured ? 'border-statusGreen/30 text-statusGreen' : 'border-amber-300/30 text-amber-200'}`}>{aiConfig?.connections?.[provider]?.configured ? 'Configured' : 'Required for AI'}</span></div>
        <div className="mt-4 flex flex-col gap-3 sm:flex-row"><input type="password" autoComplete="new-password" aria-label={`${provider} API key`} value={key} onChange={(event) => { setKey(event.target.value); onApiKeyChange?.(event.target.value); }} placeholder="Paste a new key to replace the current one" className={`${inputClass} mt-0`} /><button type="button" onClick={() => void saveKey()} disabled={busy || !key.trim()} className="min-h-11 rounded-lg border border-accentYellow/40 px-4 py-2 text-xs font-bold text-accentYellow hover:bg-accentYellow/10 disabled:opacity-50">{busy ? 'Saving…' : 'Save key'}</button></div>
        <div className="mt-4 flex flex-wrap gap-3"><button type="button" onClick={() => void onSaveSettings?.({ ...value, provider_type: provider })} disabled={busy} className="min-h-11 rounded-lg bg-accentYellow px-4 py-2 text-xs font-bold text-black disabled:opacity-50">Save assistant settings</button><button type="button" onClick={() => void onTest?.(provider, value.model || aiConfig?.model)} disabled={busy || !aiConfig?.connections?.[provider]?.configured} className="min-h-11 rounded-lg border border-white/15 px-4 py-2 text-xs font-bold text-white disabled:opacity-50">Test connection</button><span className="self-center text-xs text-textDim">Last test: {aiConfig?.last_test_status || 'not tested'}</span></div>
        {(message || error) && <p role="status" className="mt-3 text-xs text-textDim">{message || error}</p>}
      </section>
    </div>
  );
}
