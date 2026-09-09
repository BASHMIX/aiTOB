import { useEffect, useState } from 'react';
import axios from 'axios';

type Config = {
  provider_type: 'gemini' | 'openai'; model: string; mode: 'disabled' | 'read_only' | 'propose_only';
  request_limit: number; token_limit: number; context_char_limit: number; response_char_limit: number;
  request_timeout_seconds: number; policy_version: string; key_configured: boolean;
  last_test_status: string; last_tested_at?: string | null; last_test_message?: string | null;
};

export function AISettings() {
  const [config, setConfig] = useState<Config | null>(null);
  const [apiKey, setApiKey] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try { setConfig((await axios.get('/api/ai/config')).data); }
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
      if (apiKey.trim()) await axios.put('/api/ai/config/key', { api_key: apiKey.trim() });
      setApiKey(''); await load(); setMessage('AI & Automation settings saved.');
    } catch (error: any) { setMessage(error?.response?.data?.message || 'Could not save AI service settings.'); }
    finally { setBusy(false); }
  };
  const migrate = async () => {
    setBusy(true); setMessage('');
    try { const result = (await axios.post('/api/ai/config/migrate-legacy-key')).data; await load(); setMessage(result.migrated ? 'Legacy key copied into the encrypted AI service store. The legacy value was retained.' : 'No legacy AI key was found.'); }
    catch (error: any) { setMessage(error?.response?.data?.message || 'Legacy-key migration failed.'); }
    finally { setBusy(false); }
  };
  const test = async () => {
    setBusy(true); setMessage('');
    try { const result = (await axios.post('/api/ai/config/test')).data; await load(); setMessage(result.message || (result.ok ? 'Connection verified.' : 'Connection test failed.')); }
    catch (error: any) { setMessage(error?.response?.data?.message || 'Connection test failed.'); }
    finally { setBusy(false); }
  };

  if (!config) return <p className="py-8 text-center text-sm text-textDim">Loading AI & Automation settings…</p>;
  return <section className="space-y-5 animate-fadeIn">
    <div className="rounded-xl border border-accentYellow/20 bg-accentYellow/5 p-4 text-xs text-textDim">
      <b className="text-accentYellow">Organizer Assistant policy</b>
      <p className="mt-1">The Assistant is API-owned, tournament-scoped, and never executes or approves actions. In propose-only mode it can create a pending Call or announcement proposal only.</p>
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
    <div className="rounded-xl border border-white/10 bg-cardDark p-4">
      <div className="flex flex-wrap items-center justify-between gap-2"><div><p className="text-sm font-semibold text-white">Encrypted service key</p><p className="mt-1 text-xs text-textDim">{config.key_configured ? 'Configured — never returned to the browser.' : 'Not configured.'}</p></div><button type="button" onClick={migrate} disabled={busy} className="rounded border border-white/15 px-3 py-2 text-xs text-textDim hover:text-white disabled:opacity-40">Import legacy key once</button></div>
      <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="Enter a replacement key; leave empty to retain" className="mt-3 w-full rounded-md border border-white/10 bg-appDark px-3 py-2 text-sm text-white" />
      <p className="mt-2 text-[10px] text-textDim">The encryption master key belongs to the service environment, not this database. Legacy Gemini settings are retained until a later audited removal.</p>
    </div>
    <div className="flex flex-wrap items-center gap-3"><button type="button" onClick={save} disabled={busy} className="rounded bg-accentYellow px-4 py-2 text-xs font-bold text-black disabled:opacity-40">Save AI & Automation</button><button type="button" onClick={test} disabled={busy || !config.key_configured} className="rounded border border-white/15 px-4 py-2 text-xs font-bold text-white disabled:opacity-40">Test connection</button><span className="text-xs text-textDim">Last test: {config.last_test_status}{config.last_tested_at ? ` · ${new Date(config.last_tested_at).toLocaleString()}` : ''}</span></div>
    {config.last_test_message && <p className="text-xs text-textDim">{config.last_test_message}</p>}
    {message && <p className="text-xs text-textDim">{message}</p>}
    <p className="border-t border-white/10 pt-3 text-[10px] text-textDim">The former “Hub Agent System Prompt” did not control Organizer Assistant permissions and is no longer used here. Policy and mode enforce its boundaries; no style text can grant execution authority.</p>
  </section>;
}
