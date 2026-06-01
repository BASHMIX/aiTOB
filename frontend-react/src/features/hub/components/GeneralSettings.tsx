import { useState, useEffect } from 'react';
import axios from 'axios';
import { useHubStore } from '@/store/useHubStore';

export function GeneralSettings() {
  const [env, setEnv] = useState<any>({});
  const [settings, setSettings] = useState<any>({});
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null);

  const hubPassword = useHubStore(state => state.hubPassword);
  const setHubPassword = useHubStore(state => state.setHubPassword);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [envRes, settingsRes] = await Promise.all([
        axios.get('/api/env'),
        axios.get('/api/settings')
      ]);
      setEnv(envRes.data);
      setSettings(settingsRes.data.settings);
    } catch (e) {
      console.error('Failed to load settings', e);
    }
  };

  const showMsg = (text: string, ok = true) => {
    setMessage({ text, ok });
    setTimeout(() => setMessage(null), 4000);
  };

  const saveEnv = async () => {
    setIsSaving(true);
    try {
      // We only send back the values that are editable
      const res = await axios.patch('/api/env', env);
      showMsg(res.data.message);
    } catch (e) {
      showMsg('Failed to update connections', false);
    } finally {
      setIsSaving(false);
    }
  };

  const reconnect = async () => {
    setIsSaving(true);
    try {
      await axios.post('/api/reconnect');
      showMsg('Reconnecting... Checking status now.');
      // Refresh to update the TopNavigation indicators
      setTimeout(() => window.location.reload(), 1000);
    } catch (e) {
      showMsg('Reconnect failed.', false);
    } finally {
      setIsSaving(false);
    }
  };

  const saveSettings = async () => {
    setIsSaving(true);
    try {
      await axios.patch('/api/settings', settings);
      showMsg('Global settings saved.');
    } catch (e) {
      showMsg('Failed to save settings', false);
    } finally {
      setIsSaving(false);
    }
  };

  const updateSetting = (key: string, val: string) => {
    setSettings({ ...settings, [key]: val });
  };

  const updateEnv = (key: string, val: string) => {
    setEnv({ ...env, [key]: val });
  };

  return (
    <div className="flex flex-col gap-6 animate-fadeIn pb-10">
      {/* Header */}
      <div className="flex justify-between items-center border-b border-white/10 pb-4">
        <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
          <span className="text-accentYellow">⚙️</span> System Settings
        </h1>
        {message && (
          <div className={`px-4 py-2 rounded text-sm font-medium animate-slideDown ${message.ok ? 'bg-statusGreen/20 text-statusGreen border border-statusGreen/30' : 'bg-statusRed/20 text-statusRed border border-statusRed/30'}`}>
            {message.text}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        
        {/* Connection Settings (.env) */}
        <section className="bg-cardDark rounded-xl p-6 shadow-xl border border-white/5 flex flex-col gap-5">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-lg bg-accentYellow/10 flex items-center justify-center text-accentYellow">
              🔌
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">Connections</h2>
              <p className="text-xs text-textDim italic">Modify environment variables (.env)</p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-mono text-gray-400 uppercase tracking-widest">Start.gg API Token</label>
              <input 
                className="bg-appDark border border-white/10 rounded-md px-4 py-2 text-sm text-white focus:border-accentYellow outline-none transition-all"
                type="password"
                placeholder="Keep empty to leave unchanged"
                onChange={e => updateEnv('STARTGG_API_TOKEN', e.target.value)}
              />
              <p className="text-[10px] text-gray-500 italic">Current: {env.STARTGG_API_TOKEN || 'Not set'}</p>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-mono text-gray-400 uppercase tracking-widest">Discord Public Channel ID</label>
              <input 
                className="bg-appDark border border-white/10 rounded-md px-4 py-2 text-sm text-white focus:border-accentYellow outline-none"
                value={env.MATCH_CALL_CHANNEL_ID || ''}
                onChange={e => updateEnv('MATCH_CALL_CHANNEL_ID', e.target.value)}
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-mono text-gray-400 uppercase tracking-widest">Start.gg Client ID</label>
                <input
                  className="bg-appDark border border-white/10 rounded-md px-4 py-2 text-sm text-white focus:border-accentYellow outline-none"
                  value={env.STARTGG_CLIENT_ID || ''}
                  onChange={e => updateEnv('STARTGG_CLIENT_ID', e.target.value)}
                  placeholder="OAuth app client_id"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-mono text-gray-400 uppercase tracking-widest">Start.gg Client Secret</label>
                <input
                  className="bg-appDark border border-white/10 rounded-md px-4 py-2 text-sm text-white focus:border-accentYellow outline-none"
                  type="password"
                  placeholder="Keep empty to leave unchanged"
                  onChange={e => updateEnv('STARTGG_CLIENT_SECRET', e.target.value)}
                />
                <p className="text-[10px] text-gray-500 italic">Current: {env.STARTGG_CLIENT_SECRET ? '••••••••' : 'Not set'}</p>
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-mono text-gray-400 uppercase tracking-widest">Discord Bot Token</label>
              <input
                className="bg-appDark border border-white/10 rounded-md px-4 py-2 text-sm text-white focus:border-accentYellow outline-none"
                type="password"
                placeholder="Keep empty to leave unchanged"
                onChange={e => updateEnv('DISCORD_BOT_TOKEN', e.target.value)}
              />
              <p className="text-[10px] text-gray-500 italic">Current: {env.DISCORD_BOT_TOKEN ? '••••••••' : 'Not set'} · Restart the bot process after rotating.</p>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-mono text-gray-400 uppercase tracking-widest">API Base URL</label>
              <input
                className="bg-appDark border border-white/10 rounded-md px-4 py-2 text-sm text-white focus:border-accentYellow outline-none"
                value={env.API_BASE_URL || ''}
                onChange={e => updateEnv('API_BASE_URL', e.target.value)}
                placeholder="http://localhost:8000"
              />
              <p className="text-[10px] text-gray-500 italic">Used to build the OAuth callback link the bot sends to players.</p>
            </div>

            <div className="flex flex-col gap-1.5 pt-4 border-t border-white/5">
              <label className="text-xs font-mono text-gray-400 uppercase tracking-widest">Local Hub Password (UI Access)</label>
              <input 
                className="bg-appDark border border-white/10 rounded-md px-4 py-2 text-sm text-white focus:border-accentYellow outline-none"
                type="password"
                value={hubPassword}
                onChange={e => setHubPassword(e.target.value)}
                placeholder="Enter password to authenticate with API"
              />
              <p className="text-[10px] text-gray-500 italic">This must match the HUB_PASSWORD in your .env file.</p>
            </div>
          </div>

          <div className="flex gap-3 mt-4">
            <button 
              onClick={saveEnv}
              disabled={isSaving}
              className="flex-1 bg-accentYellow hover:bg-yellow-500 text-black font-bold py-2.5 rounded-lg transition-all shadow-lg active:scale-95 disabled:opacity-50"
            >
              Update Connections
            </button>
            <button 
              onClick={reconnect}
              disabled={isSaving}
              className="px-6 bg-accentYellow/10 hover:bg-accentYellow/20 border border-accentYellow/30 text-accentYellow font-bold py-2.5 rounded-lg transition-all active:scale-95 disabled:opacity-50"
            >
              Reconnect
            </button>
          </div>
        </section>

        {/* Bot Customization Section */}
        <section className="bg-cardDark rounded-xl p-6 shadow-xl border border-white/5 flex flex-col gap-5">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center text-blue-400">
              🤖
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">Bot Behavior</h2>
              <p className="text-xs text-textDim italic">Customize AI prompts and responses</p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-mono text-gray-400 uppercase tracking-widest">Dashboard Theme</label>
              <select 
                className="bg-appDark border border-white/10 rounded-md px-4 py-2 text-sm text-white focus:border-accentYellow outline-none"
                value={settings.current_theme || 'default'}
                onChange={e => {
                  updateSetting('current_theme', e.target.value);
                  // Apply theme immediately for preview
                  document.documentElement.setAttribute('data-theme', e.target.value);
                }}
              >
                <option value="default">Default (Classic Dark)</option>
                <option value="pro">Pro Edition (Neon/Glass)</option>
                <option value="vibrant">Vibrant (Pink/Purple)</option>
              </select>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-mono text-gray-400 uppercase tracking-widest">Global Language</label>
              <select 
                className="bg-appDark border border-white/10 rounded-md px-4 py-2 text-sm text-white focus:border-accentYellow outline-none"
                value={settings.global_language || 'ar'}
                onChange={e => updateSetting('global_language', e.target.value)}
              >
                <option value="ar">Arabic (Default)</option>
                <option value="en">English</option>
                <option value="both">Bilingual</option>
              </select>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-mono text-gray-400 uppercase tracking-widest">AI Provider</label>
                <select 
                  className="bg-appDark border border-white/10 rounded-md px-4 py-2 text-sm text-white focus:border-accentYellow outline-none"
                  value={env.AI_PROVIDER || 'gemini'}
                  onChange={e => updateEnv('AI_PROVIDER', e.target.value)}
                >
                  <option value="gemini">Google Gemini</option>
                  <option value="openai">OpenAI</option>
                </select>
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-mono text-gray-400 uppercase tracking-widest">Model Name</label>
                <input 
                  className="bg-appDark border border-white/10 rounded-md px-4 py-2 text-sm text-white focus:border-accentYellow outline-none"
                  value={env.AI_MODEL || 'gemini-2.5-flash'}
                  onChange={e => updateEnv('AI_MODEL', e.target.value)}
                  placeholder="e.g. gemini-2.5-flash"
                />
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-mono text-gray-400 uppercase tracking-widest">AI API Key (Gemini/OpenAI)</label>
              <input 
                className="bg-appDark border border-white/10 rounded-md px-4 py-2 text-sm text-white focus:border-accentYellow outline-none"
                type="password"
                placeholder="Keep empty to leave unchanged"
                onChange={e => updateEnv('GEMINI_API_KEY', e.target.value)}
              />
              <p className="text-[10px] text-gray-500 italic">Current: {env.GEMINI_API_KEY || 'Not set'}</p>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-mono text-gray-400 uppercase tracking-widest">Match Threads Channel ID</label>
              <input
                className="bg-appDark border border-white/10 rounded-md px-4 py-2 text-sm text-white focus:border-accentYellow outline-none"
                value={settings.match_threads_channel_id || ''}
                onChange={e => updateSetting('match_threads_channel_id', e.target.value)}
                placeholder="Discord channel ID for per-match threads"
              />
              <p className="text-[10px] text-gray-500 italic">If empty, the bot falls back to the first available text channel — risky for live events.</p>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-mono text-gray-400 uppercase tracking-widest">Registration Welcome Message</label>
              <textarea 
                rows={3}
                className="bg-appDark border border-white/10 rounded-md px-4 py-2 text-sm text-white focus:border-accentYellow outline-none resize-none"
                value={settings.registration_msg || 'Welcome to the AI Tournament Organizer! Click below to register.'}
                onChange={e => updateSetting('registration_msg', e.target.value)}
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-mono text-gray-400 uppercase tracking-widest">Question: CFN ID</label>
              <input 
                className="bg-appDark border border-white/10 rounded-md px-4 py-2 text-sm text-white focus:border-accentYellow outline-none"
                value={settings.q_cfn_id || ''}
                placeholder="e.g. Please enter your CFN ID."
                onChange={e => updateSetting('q_cfn_id', e.target.value)}
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-mono text-gray-400 uppercase tracking-widest">Question: Avatar</label>
              <input 
                className="bg-appDark border border-white/10 rounded-md px-4 py-2 text-sm text-white focus:border-accentYellow outline-none"
                value={settings.q_avatar || ''}
                placeholder="e.g. Please upload your avatar."
                onChange={e => updateSetting('q_avatar', e.target.value)}
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-mono text-gray-400 uppercase tracking-widest">Question: Language</label>
              <input 
                className="bg-appDark border border-white/10 rounded-md px-4 py-2 text-sm text-white focus:border-accentYellow outline-none"
                value={settings.q_language || ''}
                placeholder="e.g. Choose your language: 1. Arabic, 2. English"
                onChange={e => updateSetting('q_language', e.target.value)}
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-mono text-gray-400 uppercase tracking-widest">Hub Agent System Prompt</label>
              <textarea 
                rows={6}
                className="bg-appDark border border-white/10 rounded-md px-4 py-2 text-xs text-gray-300 font-mono focus:border-accentYellow outline-none resize-none"
                value={settings.bot_system_prompt || ''}
                placeholder="Describe how the AI should behave..."
                onChange={e => updateSetting('bot_system_prompt', e.target.value)}
              />
            </div>
          </div>

          <button
            onClick={saveSettings}
            disabled={isSaving}
            className="mt-4 bg-blue-600 hover:bg-blue-500 text-white font-bold py-2.5 rounded-lg transition-all shadow-lg active:scale-95 disabled:opacity-50"
          >
            Save Bot Settings
          </button>
        </section>

      </div>

      {/* ── Maintenance & Workflows ─────────────────────────────────────── */}
      <MaintenancePanel onMessage={showMsg} />
    </div>
  );
}


function MaintenancePanel({ onMessage }: { onMessage: (text: string, ok?: boolean) => void }) {
  const [busyReload, setBusyReload] = useState(false);
  const [busyToken, setBusyToken] = useState(false);

  const reloadWorkflows = async () => {
    setBusyReload(true);
    try {
      const res = await axios.post('/api/workflows/reload');
      onMessage(res.data.message || 'Workflows reloaded', true);
    } catch (e: any) {
      onMessage(e.response?.data?.detail || 'Reload failed', false);
    } finally {
      setBusyReload(false);
    }
  };

  const retestToken = async () => {
    setBusyToken(true);
    try {
      await axios.post('/api/settings/token-check');
      onMessage('Token re-tested. Check the header for status.', true);
    } catch (e: any) {
      onMessage(e.response?.data?.detail || 'Token test failed', false);
    } finally {
      setBusyToken(false);
    }
  };

  return (
    <section className="bg-cardDark rounded-xl p-6 shadow-xl border border-white/5 flex flex-col gap-4">
      <div className="flex items-center gap-3 mb-1">
        <div className="w-10 h-10 rounded-lg bg-purple-500/10 flex items-center justify-center text-purple-300">
          🛠️
        </div>
        <div>
          <h2 className="text-lg font-bold text-white">Maintenance & Workflows</h2>
          <p className="text-xs text-textDim italic">Hot-reload config and re-probe credentials without restarting</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="flex flex-col gap-2 p-4 rounded-lg bg-black/30 border border-white/5">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-gray-200">Match Workflow Transitions</span>
            <button
              onClick={reloadWorkflows}
              disabled={busyReload}
              className="px-3 py-1.5 text-xs font-bold rounded-md bg-purple-500/20 hover:bg-purple-500/30 border border-purple-500/40 text-purple-200 transition-all disabled:opacity-50"
            >
              {busyReload ? 'Reloading…' : '♻️ Reload workflows.json'}
            </button>
          </div>
          <p className="text-[11px] text-textDim leading-relaxed">
            Re-reads <code className="text-purple-300">docs/workflows.json</code> live. Takes effect on the next match transition. Use for hot-fixes during an event.
          </p>
        </div>

        <div className="flex flex-col gap-2 p-4 rounded-lg bg-black/30 border border-white/5">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-gray-200">Re-test Start.gg Token</span>
            <button
              onClick={retestToken}
              disabled={busyToken}
              className="px-3 py-1.5 text-xs font-bold rounded-md bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-amber-200 transition-all disabled:opacity-50"
            >
              {busyToken ? 'Probing…' : '🔑 Probe scopes'}
            </button>
          </div>
          <p className="text-[11px] text-textDim leading-relaxed">
            Confirms the API token has T.O. write scope on your tournament. Result shows in the header banner.
          </p>
        </div>
      </div>
    </section>
  );
}
