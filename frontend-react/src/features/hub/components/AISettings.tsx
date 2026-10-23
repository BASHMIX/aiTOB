import { useEffect, useRef, useState } from 'react';
import axios from 'axios';

type Config = {
  provider_type: 'gemini' | 'openai'; model: string; mode: 'disabled' | 'read_only' | 'propose_only';
  request_limit: number; token_limit: number; context_char_limit: number; response_char_limit: number;
  request_timeout_seconds: number; policy_version: string; key_configured: boolean;
  last_test_status: string; last_tested_at?: string | null; last_test_message?: string | null;
  connections?: Record<'gemini' | 'openai', { configured: boolean; enabled: boolean; health?: string; last_tested_at?: string | null }>;
};

export function AISettings({ connectionOnly = false }: { connectionOnly?: boolean }) {
  const [config, setConfig] = useState<Config | null>(null);
  const [connectionProvider, setConnectionProvider] = useState<'gemini' | 'openai'>('gemini');
  const [apiKey, setApiKey] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const initializedConnectionProvider = useRef(false);

  const load = async () => {
    try {
      const loaded = (await axios.get('/api/ai/config')).data;
      setConfig(loaded);
      if (!initializedConnectionProvider.current) {
        setConnectionProvider(loaded.provider_type || 'gemini');
        initializedConnectionProvider.current = true;
      }
    }
    catch { setMessage('Could not load AI service configuration.'); }
  };
  useEffect(() => { void load(); }, []);
  const update = (key: keyof Config, value: string | number) => setConfig((current) => current ? { ...current, [key]: value } : current);

  const save = async () => {
    if (!config) return;
    setBusy(true); setMessage('');
    try {
      const { key_configured, last_test_status, last_tested_at, last_test_message, ...payload } = config;
      await axios.patch('/api/ai/config', payload);
      await load(); setMessage('AI & Automation settings saved. Your workspace uses its own provider billing.');
    } catch (error: any) { setMessage(error?.response?.data?.message || 'Could not save AI service settings.'); }
    finally { setBusy(false); }
  };
  const test = async () => {
    setBusy(true); setMessage('');
    try { const result = (await axios.post('/api/ai/config/test')).data; await load(); setMessage(result.message || (result.ok ? 'Connection verified.' : 'Connection test failed.')); }
    catch (error: any) { setMessage(error?.response?.data?.message || 'Connection test failed.'); }
    finally { setBusy(false); }
  };

  const saveConnection = async () => {
    if (!apiKey.trim()) { setMessage('Enter a workspace-owned API key first.'); return; }
    setBusy(true); setMessage('');
    try {
      await axios.put(`/api/ai/connections/${connectionProvider}/credential`, { api_key: apiKey.trim() });
      setApiKey(''); await load();
      setMessage(`${connectionProvider === 'gemini' ? 'Gemini' : 'OpenAI'} credential encrypted for this Workspace.`);
    } catch (error: any) { setMessage(error?.response?.data?.message || 'Could not save the AI provider credential.'); }
    finally { setBusy(false); }
  };

  const testConnection = async () => {
    setBusy(true); setMessage('');
    try {
      const result = (await axios.post(`/api/ai/connections/${connectionProvider}/test`, {})).data;
      await load(); setMessage(result.message || (result.ok ? 'Connection verified.' : 'Connection test failed.'));
    } catch (error: any) { setMessage(error?.response?.data?.message || 'Connection test failed.'); }
    finally { setBusy(false); }
  };

  if (!config) return <p className="py-8 text-center text-sm text-textDim">Loading AI & Automation settings…</p>;
  if (connectionOnly) {
    const connection = config.connections?.[connectionProvider];
    return <section className="rounded-xl border border-white/10 bg-cardDark p-4 shadow-sm sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-sm font-bold text-white">AI provider credentials</h2><p className="mt-1 max-w-2xl text-xs text-textDim">Bring your own Gemini or OpenAI key. It is encrypted for this Workspace and provider usage is billed directly to its owner.</p></div><span className={`rounded-full border px-2 py-1 text-[10px] font-bold uppercase ${connection?.configured ? 'border-statusGreen/30 text-statusGreen' : 'border-amber-300/30 text-amber-200'}`}>{connection?.configured ? 'Configured' : 'Credential required'}</span></div>
      <div className="mt-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200/90 leading-relaxed space-y-1">
        <p className="font-semibold text-amber-300">⚖️ تنبيه استهلاك مفاتيح الذكاء الاصطناعي (AI BYOC Notice):</p>
        <p>
          مفاتيح Google Gemini و OpenAI تُحفظ مشفرة وتُستخدم حصرياً لمساحة العمل الخاصة بك. جميع تكاليف وحصص الاستهلاك تُحسب مباشرة على حسابك لدى المزود دون أي وساطة مالية من aiTOB.
        </p>
        <p className="text-[11px] text-amber-300/80">
          اقتراحات الذكاء الاصطناعي استشارية بحتة. للمزيد، راجع <a href="/terms#ai-usage" target="_blank" rel="noopener noreferrer" className="underline hover:text-white">شروط الخدمة</a> و <a href="/privacy" target="_blank" rel="noopener noreferrer" className="underline hover:text-white">سياسة الخصوصية</a>.
        </p>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-[minmax(12rem,0.45fr)_minmax(0,1fr)]"><label className="space-y-1.5"><span className="text-[10px] font-mono uppercase tracking-wider text-textDim">AI provider</span><select value={connectionProvider} onChange={(event) => setConnectionProvider(event.target.value as 'gemini' | 'openai')} className="w-full rounded-lg border border-white/10 bg-appDark px-3 py-2 text-sm text-white"><option value="gemini">Google Gemini</option><option value="openai">OpenAI</option></select></label><label className="space-y-1.5"><span className="text-[10px] font-mono uppercase tracking-wider text-textDim">Workspace API key</span><input type="password" autoComplete="new-password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder="Enter a replacement key; leave empty to retain" className="w-full rounded-lg border border-white/10 bg-appDark px-3 py-2 text-sm text-white" /></label></div>
      <div className="mt-4 flex flex-wrap items-center gap-3"><button type="button" onClick={saveConnection} disabled={busy} className="rounded-lg bg-accentYellow px-3 py-2 text-xs font-bold text-black disabled:opacity-40">Save encrypted credential</button><button type="button" onClick={testConnection} disabled={busy || !connection?.configured} className="rounded-lg border border-white/15 px-3 py-2 text-xs font-bold text-white disabled:opacity-40">Test connection</button>{connection?.last_tested_at && <span className="text-[11px] text-textDim">Last tested: {new Date(connection.last_tested_at).toLocaleString()}</span>}</div>
      {message && <p className="mt-3 text-xs text-textDim">{message}</p>}
    </section>;
  }
  return <section className="space-y-5 animate-fadeIn">
    <div className="rounded-xl border border-accentYellow/20 bg-accentYellow/5 p-4 text-xs text-textDim">
      <b className="text-accentYellow">Organizer Assistant policy</b>
      <p className="mt-1">The Assistant is API-owned, tournament-scoped, and never executes or approves actions. In propose-only mode it can create a pending Call or announcement proposal only. Organizers retain sole authority and responsibility for all bracket decisions (<a href="/terms#ai-usage" target="_blank" rel="noopener noreferrer" className="underline hover:text-white">AI Terms</a>).</p>
    </div>
    <div className="grid gap-4 md:grid-cols-2">
      <label className="flex flex-col gap-1.5 text-xs text-textDim">Provider
        <select value={config.provider_type} onChange={(e) => update('provider_type', e.target.value)} className="rounded-md border border-white/10 bg-appDark px-3 py-2 text-sm text-white"><option value="gemini">Google Gemini</option><option value="openai">OpenAI</option></select>
      </label>
      <label className="flex flex-col gap-1.5 text-xs text-textDim">Model
        <input value={config.model} onChange={(e) => update('model', e.target.value)} className="rounded-md border border-white/10 bg-appDark px-3 py-2 text-sm text-white" />
      </label>
      <label className="flex flex-col gap-1.5 text-xs text-textDim">Operating mode
        <select value={config.mode} onChange={(e) => update('mode', e.target.value)} className="rounded-md border border-white/10 bg-appDark px-3 py-2 text-sm text-white"><option value="disabled">Disabled</option><option value="read_only">Read-only</option><option value="propose_only">Propose only — organizer approval required</option></select>
      </label>
      <label className="flex flex-col gap-1.5 text-xs text-textDim">Request timeout (seconds)
        <input type="number" min="3" max="120" value={config.request_timeout_seconds} onChange={(e) => update('request_timeout_seconds', Number(e.target.value))} className="rounded-md border border-white/10 bg-appDark px-3 py-2 text-sm text-white" />
      </label>
    </div>
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {([['request_limit', 'Requests / hour'], ['token_limit', 'Tokens / hour'], ['context_char_limit', 'Context characters'], ['response_char_limit', 'Response characters']] as Array<[keyof Config, string]>).map(([key, label]) => <label key={key} className="flex flex-col gap-1.5 text-xs text-textDim">{label}<input type="number" value={Number(config[key])} onChange={(e) => update(key, Number(e.target.value))} className="rounded-md border border-white/10 bg-appDark px-3 py-2 text-sm text-white" /></label>)}
    </div>
    <div className="rounded-xl border border-white/10 bg-cardDark p-4"><p className="text-sm font-semibold text-white">Active AI connection</p><p className="mt-1 text-xs text-textDim">{config.key_configured ? `${config.provider_type === 'gemini' ? 'Gemini' : 'OpenAI'} is configured with a Workspace-owned key.` : 'The selected provider needs a Workspace-owned key in Settings → Connections.'}</p><p className="mt-2 text-[10px] text-textDim">Credentials are managed only in Connections; this section controls assistant policy, model, and usage limits.</p></div>
    <div className="flex flex-wrap items-center gap-3"><button type="button" onClick={save} disabled={busy} className="rounded bg-accentYellow px-4 py-2 text-xs font-bold text-black disabled:opacity-40">Save AI & Automation</button><button type="button" onClick={test} disabled={busy || !config.key_configured} className="rounded border border-white/15 px-4 py-2 text-xs font-bold text-white disabled:opacity-40">Test connection</button><span className="text-xs text-textDim">Last test: {config.last_test_status}{config.last_tested_at ? ` · ${new Date(config.last_tested_at).toLocaleString()}` : ''}</span></div>
    {config.last_test_message && <p className="text-xs text-textDim">{config.last_test_message}</p>}
    {message && <p className="text-xs text-textDim">{message}</p>}
    <p className="border-t border-white/10 pt-3 text-[10px] text-textDim">The former “Hub Agent System Prompt” did not control Organizer Assistant permissions and is no longer used here. Policy and mode enforce its boundaries; no style text can grant execution authority.</p>
  </section>;
}
