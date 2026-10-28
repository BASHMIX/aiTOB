import { useEffect, useState } from 'react';
import axios from 'axios';
import aiTobLogo from '@/assets/aitob-logo.svg';

interface WorkspaceBotSettings {
  workspace_id?: string;
  custom_rules_markdown: string;
  welcome_message: string;
  faq_help_text: string;
  enable_avatar_uploads: boolean;
  enable_match_threads: boolean;
  enable_rules_command: boolean;
  response_mode: 'direct_template' | 'llm_assistant' | 'disabled';
  language_mode: 'auto' | 'ar' | 'en' | 'both';
}

const DEFAULT_SETTINGS: WorkspaceBotSettings = {
  custom_rules_markdown: '',
  welcome_message: '',
  faq_help_text: '',
  enable_avatar_uploads: true,
  enable_match_threads: true,
  enable_rules_command: true,
  response_mode: 'direct_template',
  language_mode: 'auto',
};

export function BotSettingsWorkspace() {
  const [settings, setSettings] = useState<WorkspaceBotSettings>(DEFAULT_SETTINGS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null);
  const [previewTab, setPreviewTab] = useState<'rules' | 'welcome' | 'faq'>('rules');

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    setLoading(true);
    try {
      const res = await axios.get('/api/workspace/bot-settings');
      if (res.data?.settings) {
        setSettings({ ...DEFAULT_SETTINGS, ...res.data.settings });
      }
    } catch (err: any) {
      console.error('Failed to load bot settings', err);
    } finally {
      setLoading(false);
    }
  };

  const showMsg = (text: string, ok = true) => {
    setMessage({ text, ok });
    setTimeout(() => setMessage(null), 4500);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await axios.patch('/api/workspace/bot-settings', settings);
      if (res.data?.settings) {
        setSettings({ ...DEFAULT_SETTINGS, ...res.data.settings });
      }
      showMsg('Bot experience settings saved successfully.');
    } catch (err: any) {
      const errorMsg = err.response?.data?.message || err.response?.data?.detail;
      if (err.response?.status === 401) {
        showMsg('Your session has expired or authentication is required. Please log in again.', false);
      } else {
        showMsg(errorMsg || 'Failed to save bot settings.', false);
      }
    } finally {
      setSaving(false);
    }
  };

  const handleSendTestEmbed = async () => {
    setTesting(true);
    try {
      const res = await axios.post('/api/workspace/bot-settings/preview-test');
      showMsg(res.data?.message || 'Test message sent to Discord.', res.data?.ok !== false);
    } catch (err: any) {
      const errorMsg = err.response?.data?.message || err.response?.data?.detail;
      if (err.response?.status === 401) {
        showMsg('Your session has expired or authentication is required. Please log in again.', false);
      } else {
        showMsg(errorMsg || 'Failed to send preview test to Discord.', false);
      }
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return <p className="py-8 text-center text-sm text-textDim">Loading Discord Bot customization…</p>;
  }

  const effectiveRules = settings.custom_rules_markdown.trim() ||
    `• **Check-in:** Report promptly when your match is called.\n• **Station Assignment:** Play at your assigned station or stream setup.\n• **Fair Play:** Respect referee decisions, station rules, and opponents.\n• **Scores:** Report scores directly to the bracket manager or official desk.\n\n*(Default platform tournament rules)*`;

  const effectiveWelcome = settings.welcome_message.trim() ||
    `Welcome to the tournament! Click the button below to link your start.gg profile and verify your entrant status.`;

  const effectiveFaq = settings.faq_help_text.trim() ||
    `Need assistance? Use /rules for tournament guidelines, or mention an organizer if you need referee support.`;

  return (
    <div className="space-y-6 animate-fadeIn pb-12">
      {/* Header Banner */}
      <section className="rounded-xl border border-white/10 bg-cardDark p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-indigo-500/30 bg-indigo-500/10 text-xl text-indigo-400">
              ✦
            </div>
            <div>
              <h2 className="text-base font-bold text-white">Discord Bot Experience & Customization</h2>
              <p className="mt-1 max-w-2xl text-xs text-textDim leading-relaxed">
                Configure your server’s automated bot behavior, custom rules embeds, welcome messaging, and feature toggles. Changes take effect instantly for your tournament server.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleSendTestEmbed}
              disabled={testing}
              className="rounded-lg border border-white/15 bg-white/5 px-3 py-2 text-xs font-bold text-white transition-colors hover:bg-white/10 disabled:opacity-40"
            >
              {testing ? 'Sending…' : '📤 Send Test to Discord'}
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="rounded-lg bg-accentYellow px-4 py-2 text-xs font-bold text-black transition-transform active:scale-95 disabled:opacity-40"
            >
              {saving ? 'Saving…' : 'Save Changes'}
            </button>
          </div>
        </div>

        {message && (
          <div
            role="status"
            className={`mt-4 rounded-lg border px-3.5 py-2 text-xs ${
              message.ok
                ? 'border-statusGreen/30 bg-statusGreen/10 text-statusGreen'
                : 'border-statusRed/30 bg-statusRed/10 text-statusRed'
            }`}
          >
            {message.text}
          </div>
        )}
      </section>

      {/* Main Grid: Settings on Left, Discord Live Mockup on Right */}
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
        {/* Left Column: Configuration Controls */}
        <div className="space-y-6">
          {/* General Feature Flags */}
          <section className="rounded-xl border border-white/10 bg-cardDark p-5 shadow-sm space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <span>⚙️</span>
              <span>Feature Toggles & Language</span>
            </h3>

            <div className="grid gap-4 sm:grid-cols-2">
              <label className="flex flex-col gap-1.5 text-xs text-textDim">
                <span>Bot Primary Language</span>
                <select
                  value={settings.language_mode}
                  onChange={(e) => setSettings({ ...settings, language_mode: e.target.value as any })}
                  className="rounded-lg border border-white/10 bg-appDark px-3 py-2 text-sm text-white focus:border-accentYellow outline-none"
                >
                  <option value="auto">Auto (Match Discord User Locale)</option>
                  <option value="ar">Arabic (العربية)</option>
                  <option value="en">English</option>
                  <option value="both">Bilingual (عربي / English)</option>
                </select>
              </label>

              <label className="flex flex-col gap-1.5 text-xs text-textDim">
                <span>Response & Assistance Mode</span>
                <select
                  value={settings.response_mode}
                  onChange={(e) => setSettings({ ...settings, response_mode: e.target.value as any })}
                  className="rounded-lg border border-white/10 bg-appDark px-3 py-2 text-sm text-white focus:border-accentYellow outline-none"
                >
                  <option value="direct_template">Direct Template (Fast, 0 AI Token Cost)</option>
                  <option value="llm_assistant">AI Concierge (Organizer BYOC Key)</option>
                  <option value="disabled">Disabled (Silent)</option>
                </select>
              </label>
            </div>

            <div className="border-t border-white/10 pt-4 space-y-3">
              <label className="flex items-center justify-between gap-3 p-2.5 rounded-lg border border-white/5 bg-appDark/40 hover:bg-white/[0.02] cursor-pointer">
                <div>
                  <span className="text-xs font-semibold text-white block">Enable /rules Command</span>
                  <span className="text-[11px] text-textDim">Allow players to view tournament rules and guidelines with `/rules` in the server.</span>
                </div>
                <input
                  type="checkbox"
                  checked={settings.enable_rules_command}
                  onChange={(e) => setSettings({ ...settings, enable_rules_command: e.target.checked })}
                  className="h-4 w-4 rounded border-white/20 bg-appDark accent-accentYellow"
                />
              </label>

              <label className="flex items-center justify-between gap-3 p-2.5 rounded-lg border border-white/5 bg-appDark/40 hover:bg-white/[0.02] cursor-pointer">
                <div>
                  <span className="text-xs font-semibold text-white block">Enable Player Avatar Uploads</span>
                  <span className="text-[11px] text-textDim">Permit entrants to upload photo avatars with `/avatar`. When disabled, registration completes immediately and audit tools skip avatar checks.</span>
                </div>
                <input
                  type="checkbox"
                  checked={settings.enable_avatar_uploads}
                  onChange={(e) => setSettings({ ...settings, enable_avatar_uploads: e.target.checked })}
                  className="h-4 w-4 rounded border-white/20 bg-appDark accent-accentYellow"
                />
              </label>

              <label className="flex items-center justify-between gap-3 p-2.5 rounded-lg border border-white/5 bg-appDark/40 hover:bg-white/[0.02] cursor-pointer">
                <div>
                  <span className="text-xs font-semibold text-white block">Enable Match Discussion Threads</span>
                  <span className="text-[11px] text-textDim">Auto-create Discord threads for called matches. When disabled, the bot calls matches directly in the match channel without creating threads.</span>
                </div>
                <input
                  type="checkbox"
                  checked={settings.enable_match_threads}
                  onChange={(e) => setSettings({ ...settings, enable_match_threads: e.target.checked })}
                  className="h-4 w-4 rounded border-white/20 bg-appDark accent-accentYellow"
                />
              </label>
            </div>
          </section>

          {/* Message Customization */}
          <section className="rounded-xl border border-white/10 bg-cardDark p-5 shadow-sm space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <span>✍️</span>
              <span>Message & Embed Templates</span>
            </h3>

            {/* Custom Rules */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-white">Tournament Rules & Guidelines (/rules)</label>
                <span className="text-[10px] text-textDim font-mono">
                  {settings.custom_rules_markdown.length}/4000 chars
                </span>
              </div>
              <p className="text-[11px] text-textDim">Supports full Discord Markdown (e.g. `**bold**`, bullet points, emojis).</p>
              <textarea
                rows={6}
                value={settings.custom_rules_markdown}
                onChange={(e) => setSettings({ ...settings, custom_rules_markdown: e.target.value })}
                placeholder="Enter tournament schedule, set formats (FT2/FT3), controller rules, or prize pool notes..."
                className="w-full rounded-lg border border-white/10 bg-appDark p-3 text-xs text-white leading-relaxed focus:border-accentYellow outline-none resize-y"
              />
            </div>

            {/* Welcome Message */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-white">Registration Welcome Prompt (/register)</label>
                <span className="text-[10px] text-textDim font-mono">
                  {settings.welcome_message.length}/2000 chars
                </span>
              </div>
              <p className="text-[11px] text-textDim">Displayed when a player starts registration or clicks the setup button.</p>
              <textarea
                rows={3}
                value={settings.welcome_message}
                onChange={(e) => setSettings({ ...settings, welcome_message: e.target.value })}
                placeholder="Welcome to our tournament! Link your start.gg account to confirm your spot in the bracket."
                className="w-full rounded-lg border border-white/10 bg-appDark p-3 text-xs text-white leading-relaxed focus:border-accentYellow outline-none resize-none"
              />
            </div>

            {/* FAQ Text */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-white">Organizer Help & FAQ Notes (/help)</label>
                <span className="text-[10px] text-textDim font-mono">
                  {settings.faq_help_text.length}/2000 chars
                </span>
              </div>
              <p className="text-[11px] text-textDim">Important contact points, streaming links, or Discord referee handles.</p>
              <textarea
                rows={3}
                value={settings.faq_help_text}
                onChange={(e) => setSettings({ ...settings, faq_help_text: e.target.value })}
                placeholder="Tournament Desk: @Head-TO | Stream: https://twitch.tv/my_channel"
                className="w-full rounded-lg border border-white/10 bg-appDark p-3 text-xs text-white leading-relaxed focus:border-accentYellow outline-none resize-none"
              />
            </div>
          </section>
        </div>

        {/* Right Column: Live Discord Embed Mockup */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-textDim flex items-center gap-1.5">
              <span>👁️</span>
              <span>Live Discord Preview</span>
            </h3>
            <div className="flex rounded-lg border border-white/10 bg-black/20 p-0.5 text-[11px] font-semibold">
              <button
                type="button"
                onClick={() => setPreviewTab('rules')}
                className={`rounded px-2.5 py-1 transition-colors ${previewTab === 'rules' ? 'bg-accentYellow text-black' : 'text-textDim hover:text-white'}`}
              >
                /rules
              </button>
              <button
                type="button"
                onClick={() => setPreviewTab('welcome')}
                className={`rounded px-2.5 py-1 transition-colors ${previewTab === 'welcome' ? 'bg-accentYellow text-black' : 'text-textDim hover:text-white'}`}
              >
                /register
              </button>
              <button
                type="button"
                onClick={() => setPreviewTab('faq')}
                className={`rounded px-2.5 py-1 transition-colors ${previewTab === 'faq' ? 'bg-accentYellow text-black' : 'text-textDim hover:text-white'}`}
              >
                /help
              </button>
            </div>
          </div>

          {/* Discord Native Message Simulator */}
          <div className="rounded-xl border border-gray-800 bg-[#313338] p-4 text-[#dbdee1] font-sans shadow-2xl select-none">
            {/* Discord Message Header */}
            <div className="flex items-start gap-3">
              <img src={aiTobLogo} alt="aiTOB" className="h-10 w-10 rounded-full bg-[#1e1f22] p-1 shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-white text-sm hover:underline cursor-pointer">aiTOB</span>
                  <span className="rounded bg-[#5865F2] px-1 py-0.2 text-[9px] font-bold text-white uppercase tracking-wider">
                    APP
                  </span>
                  <span className="text-[11px] text-[#949ba4]">Today at {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                </div>

                {/* Preview Content */}
                {previewTab === 'rules' && (
                  <div className="mt-2.5 max-w-md rounded border-l-4 border-[#3b82f6] bg-[#2b2d31] p-3 text-xs leading-relaxed space-y-2">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-white text-sm">📋 Tournament Rules & Guidelines</span>
                    </div>
                    <p className="whitespace-pre-wrap text-[#dbdee1] text-[12px]">{effectiveRules}</p>
                    <div className="pt-2 border-t border-white/5 text-[10px] text-[#949ba4]">
                      aiTOB Tournament Organizer · Fair Play Guaranteed
                    </div>
                  </div>
                )}

                {previewTab === 'welcome' && (
                  <div className="mt-2.5 max-w-md rounded border-l-4 border-[#10b981] bg-[#2b2d31] p-3 text-xs leading-relaxed space-y-3">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-white text-sm">Tournament Registration</span>
                    </div>
                    <p className="whitespace-pre-wrap text-[#dbdee1] text-[12px]">{effectiveWelcome}</p>
                    <div className="flex gap-2 pt-1">
                      <div className="rounded bg-[#5865F2] px-3 py-1.5 text-xs font-semibold text-white text-center cursor-default">
                        🔗 Link Start.gg Profile
                      </div>
                    </div>
                  </div>
                )}

                {previewTab === 'faq' && (
                  <div className="mt-2.5 max-w-md rounded border-l-4 border-[#f59e0b] bg-[#2b2d31] p-3 text-xs leading-relaxed space-y-2">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-white text-sm">ℹ️ Tournament Assistance & FAQ</span>
                    </div>
                    <p className="whitespace-pre-wrap text-[#dbdee1] text-[12px]">{effectiveFaq}</p>
                    <div className="pt-2 border-t border-white/5 text-[10px] text-[#949ba4]">
                      aiTOB Assistant · Organizer Support
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Informational Callout */}
          <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/5 p-4 text-xs text-indigo-200/90 leading-relaxed space-y-1.5">
            <span className="font-bold text-indigo-300 block">💡 Multi-Tenant SaaS Architecture:</span>
            <p>
              Each connected Discord server reads its rules and preferences dynamically from this workspace. Players in your server will see your custom branding, rules, and language without interfering with other tournaments running on the platform.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
