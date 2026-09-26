import { useState, useEffect } from 'react';
import axios from 'axios';
import { IntegrationAccounts } from './IntegrationAccounts';

type GeneralSettingsSection = 'all' | 'connections' | 'bot' | 'system';

export function GeneralSettings({ section = 'all', embedded = false }: { section?: GeneralSettingsSection; embedded?: boolean }) {
  const [env, setEnv] = useState<any>({});
  const [settings, setSettings] = useState<any>({});
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null);
  const [emailStatus, setEmailStatus] = useState<{ provider: string; configured: boolean; from_configured: boolean; reason: string } | null>(null);
  const [emailRecipient, setEmailRecipient] = useState('');
  const [emailTestBusy, setEmailTestBusy] = useState(false);


  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [envRes, settingsRes] = await Promise.all([
        axios.get('/api/env'),
        axios.get('/api/settings'),
      ]);
      setEnv(envRes.data);
      setSettings(settingsRes.data.settings);
    } catch (e) {
      console.error('Failed to load settings', e);
    }
    try {
      const emailRes = await axios.get('/api/platform/email/status');
      setEmailStatus(emailRes.data);
    } catch (e) {
      // Non-platform admins cannot inspect service-scoped email settings.
      setEmailStatus(null);
    }
  };

  const showMsg = (text: string, ok = true) => {
    setMessage({ text, ok });
    setTimeout(() => setMessage(null), 4000);
  };

  const saveEnv = async () => {
    setIsSaving(true);
    try {
      // Provider and Discord credentials are owned by Integration Accounts.
      // Never echo the full GET /env projection back into this legacy-safe
      // service setting endpoint: it contains configured markers for secrets.
      const res = await axios.patch('/api/env', { API_BASE_URL: env.API_BASE_URL || '' });
      const envRes = await axios.get('/api/env');
      setEnv(envRes.data);
      showMsg(res.data.message || 'Connections saved.');
    } catch (e: any) {
      showMsg(e.response?.data?.message || 'Failed to update connections. Check the Hub password and API connection.', false);
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

  const sendEmailTest = async () => {
    if (!emailRecipient.trim() || emailTestBusy) return;
    setEmailTestBusy(true);
    try {
      const response = await axios.post('/api/platform/email/test', { recipient: emailRecipient.trim() });
      showMsg(response.data.sent ? 'Email test accepted by the configured provider.' : 'Email test was not sent; inspect the provider configuration.', response.data.sent);
    } catch (error: any) {
      showMsg(error.response?.data?.detail || 'Email test failed.', false);
    } finally { setEmailTestBusy(false); }
  };

  const showConnections = section === 'all' || section === 'connections';
  const showSystem = section === 'all' || section === 'system';
  const showBot = section === 'all' || section === 'bot';

  return (
      <div className="flex flex-col gap-6 animate-fadeIn pb-10">
      {section === 'all' && <IntegrationAccounts />}
      {/* Header */}
      {!embedded && <div className="flex justify-between items-center border-b border-white/10 pb-4">
        <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
          <span className="text-accentYellow">⚙️</span> System Settings
        </h1>
        {message && (
          <div className={`px-4 py-2 rounded text-sm font-medium animate-slideDown ${message.ok ? 'bg-statusGreen/20 text-statusGreen border border-statusGreen/30' : 'bg-statusRed/20 text-statusRed border border-statusRed/30'}`}>
            {message.text}
          </div>
        )}
      </div>}

      {message && embedded && (
        <div className={`px-4 py-2 rounded text-sm font-medium animate-slideDown ${message.ok ? 'bg-statusGreen/20 text-statusGreen border border-statusGreen/30' : 'bg-statusRed/20 text-statusRed border border-statusRed/30'}`}>
          {message.text}
        </div>
      )}

      <div className={`grid grid-cols-1 gap-8 ${showConnections && showBot ? 'lg:grid-cols-2' : ''}`}>
        
        {/* Runtime-only settings. Provider credentials are configured in the
            dedicated provider cards above, not duplicated here. */}
        {showConnections && <section className="bg-cardDark rounded-xl p-6 shadow-xl border border-white/10 flex flex-col gap-5">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-lg bg-accentYellow/10 flex items-center justify-center text-accentYellow">
              🔌
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">Service link</h2>
              <p className="text-xs text-textDim italic">Public Hub address used by managed integrations and player links.</p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="rounded-md border border-indigo-300/20 bg-indigo-300/5 p-4">
              <p className="text-xs font-mono uppercase tracking-widest text-indigo-200">Managed integrations</p>
              <p className="mt-1 text-[11px] leading-relaxed text-gray-400">
                Discord uses the platform-managed aiTOB bot. Tournament and AI providers use credentials owned and billed by this Workspace through the connection cards above.
              </p>
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

          </div>

          <div className="flex gap-3 mt-4">
            <button 
              onClick={saveEnv}
              disabled={isSaving}
              className="flex-1 bg-accentYellow hover:bg-yellow-500 text-black font-bold py-2.5 rounded-lg transition-all shadow-lg active:scale-95 disabled:opacity-50"
            >
              Update service URL
            </button>
            <button 
              onClick={reconnect}
              disabled={isSaving}
              className="px-6 bg-accentYellow/10 hover:bg-accentYellow/20 border border-accentYellow/30 text-accentYellow font-bold py-2.5 rounded-lg transition-all active:scale-95 disabled:opacity-50"
            >
              Reconnect
            </button>
          </div>
        </section>}

        {/* Bot Customization Section */}
        {showBot && <section className="bg-cardDark rounded-xl p-6 shadow-xl border border-white/5 flex flex-col gap-5">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center text-blue-400">
              🤖
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">Bot Behavior</h2>
              <p className="text-xs text-textDim italic">Registration messages and Discord workflow wording</p>
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

          </div>

          <button
            onClick={saveSettings}
            disabled={isSaving}
            className="mt-4 bg-blue-600 hover:bg-blue-500 text-white font-bold py-2.5 rounded-lg transition-all shadow-lg active:scale-95 disabled:opacity-50"
          >
            Save Bot Settings
          </button>
        </section>}

      </div>

      {showSystem && <section className="rounded-xl border border-white/10 bg-cardDark p-5 shadow-sm">
        {emailStatus ? <>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div><h2 className="text-sm font-bold text-white">Account email delivery</h2><p className="mt-1 text-xs text-textDim">Configured through service environment variables; API keys and passwords are never shown here.</p></div>
            <span className={`rounded-full border px-2 py-1 text-[10px] font-bold uppercase ${emailStatus.configured ? 'border-statusGreen/40 text-statusGreen' : 'border-statusOrange/40 text-statusOrange'}`}>{emailStatus.configured ? `${emailStatus.provider} ready` : 'Not configured'}</span>
          </div>
          <p className="mt-3 text-xs text-textDim">From address: <span className="font-semibold text-white">{emailStatus.from_configured ? 'configured' : 'missing'}</span> · {emailStatus.reason}</p>
          <div className="mt-3 flex flex-wrap gap-2"><input type="email" value={emailRecipient} onChange={(event) => setEmailRecipient(event.target.value)} placeholder="Recipient for a test message" className="min-w-[220px] flex-1 rounded-lg border border-white/10 bg-appDark px-3 py-2 text-sm text-white" /><button type="button" onClick={sendEmailTest} disabled={emailTestBusy || !emailRecipient.includes('@')} className="rounded-lg border border-accentYellow/50 px-3 py-2 text-xs font-bold text-accentYellow disabled:opacity-40">{emailTestBusy ? 'Sending…' : 'Send test email'}</button></div>
          <p className="mt-2 text-[10px] text-textDim">Resend: set <code>RESEND_API_KEY</code> and <code>EMAIL_FROM</code>. SMTP: set <code>SMTP_HOST</code>, <code>SMTP_PORT</code>, <code>SMTP_USERNAME</code>, <code>SMTP_PASSWORD</code>, and <code>SMTP_FROM</code>.</p>
        </> : <>
          <h2 className="text-sm font-bold text-white">Account email delivery</h2>
          <p className="mt-1 text-xs leading-relaxed text-textDim">Service-level email configuration and delivery tests are restricted to the Platform Admin (Super Admin). Workspace Owners and tournament roles cannot inspect or change provider secrets.</p>
          <p className="mt-2 text-[10px] text-textDim">Ask a Platform Admin to open this System section to view the safe status and send an explicit test message. No API key or password is displayed in the interface.</p>
        </>}
      </section>}

      {/* ── Maintenance & Workflows ─────────────────────────────────────── */}
      {showSystem && <MaintenancePanel onMessage={showMsg} />}
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
    <details className="group rounded-xl border border-white/10 bg-cardDark shadow-sm">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-4 text-sm font-bold text-white marker:content-none">
        <span className="flex items-center gap-3"><span className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-500/10 text-purple-300">🛠️</span>Advanced maintenance</span>
        <span className="text-xs font-normal text-textDim group-open:hidden">Show tools</span>
        <span className="hidden text-xs font-normal text-textDim group-open:inline">Hide tools</span>
      </summary>
      <div className="border-t border-white/10 p-5">
        <p className="mb-4 text-xs leading-relaxed text-textDim">Emergency operator tools only. They reload local workflow configuration or re-check Start.gg permissions; they do not change tournament results.</p>
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
      </div>
    </details>
  );
}
