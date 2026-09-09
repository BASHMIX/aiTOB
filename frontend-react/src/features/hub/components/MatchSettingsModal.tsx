import { useEffect, useState } from "react";
import axios from "axios";

interface MatchOperationsSettingsProps {
  currentSlug: string;
  initialAutoDqEnabled: boolean;
  initialDqTimerSeconds: number;
  initialBotManageLimit?: string;
  initialBotManageFinish?: string;
  initialAutoDispatchEnabled?: boolean;
  initialAutoDispatchConcurrency?: number;
  initialAutoDispatchStopAt?: number;
  initialAutoDispatchOnStream?: boolean;
  initialIgnoreActivityGuard?: boolean;
  initialCheckInSource?: string;
  phaseGroups: string[];
  providerType?: 'startgg' | 'challonge';
  onSave: () => void;
}

export function MatchOperationsSettings({
  currentSlug,
  initialAutoDqEnabled,
  initialDqTimerSeconds,
  initialBotManageLimit = "off",
  initialBotManageFinish = "off",
  initialAutoDispatchEnabled = false,
  initialAutoDispatchConcurrency = 1,
  initialAutoDispatchStopAt = 8,
  initialAutoDispatchOnStream = false,
  initialIgnoreActivityGuard = false,
  initialCheckInSource = "discord",
  phaseGroups,
  providerType = 'startgg',
  onSave,
}: MatchOperationsSettingsProps) {
  const [autoDqEnabled, setAutoDqEnabled] = useState(initialAutoDqEnabled);
  const [dqTimerMinutes, setDqTimerMinutes] = useState(Math.floor(initialDqTimerSeconds / 60));
  const [botManageLimit, setBotManageLimit] = useState(initialBotManageLimit);
  const [botManageFinish, setBotManageFinish] = useState(initialBotManageFinish);
  const [autoDispatchEnabled, setAutoDispatchEnabled] = useState(initialAutoDispatchEnabled);
  const [autoDispatchConcurrency, setAutoDispatchConcurrency] = useState(initialAutoDispatchConcurrency);
  const [autoDispatchStopAt, setAutoDispatchStopAt] = useState(initialAutoDispatchStopAt);
  const [autoDispatchOnStream, setAutoDispatchOnStream] = useState(initialAutoDispatchOnStream);
  const [ignoreActivityGuard, setIgnoreActivityGuard] = useState(initialIgnoreActivityGuard);
  const [checkInSource, setCheckInSource] = useState(initialCheckInSource);
  const [saving, setSaving] = useState(false);
  const [dispatcherStatus, setDispatcherStatus] = useState<{
    state: 'running' | 'paused_tournament' | 'paused_global' | 'service_offline';
    explanation: string;
  } | null>(null);
  const isChallonge = providerType === 'challonge';

  const refreshDispatcherStatus = async () => {
    try {
      const response = await axios.get(`/api/tournaments/${currentSlug}/dispatcher-status`);
      setDispatcherStatus(response.data);
    } catch {
      setDispatcherStatus({
        state: 'service_offline',
        explanation: 'Dispatcher status is unavailable. It will not be treated as running.',
      });
    }
  };

  useEffect(() => {
    void refreshDispatcherStatus();
  }, [currentSlug]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await axios.patch(`/api/tournaments/${currentSlug}/settings`, {
        auto_dq_enabled: autoDqEnabled,
        dq_timer_seconds: dqTimerMinutes * 60,
        bot_manage_limit: botManageLimit,
        bot_manage_finish: botManageFinish,
        auto_dispatch_enabled: autoDispatchEnabled,
        auto_dispatch_concurrency: autoDispatchConcurrency,
        auto_dispatch_stop_at: autoDispatchStopAt,
        auto_dispatch_on_stream: autoDispatchOnStream,
        ignore_activity_guard: ignoreActivityGuard,
        check_in_source: checkInSource,
      });
      await refreshDispatcherStatus();
      onSave();
    } catch (e) {
      console.error("Failed to save match settings", e);
      alert("Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  return (
      <section className="overflow-hidden rounded-xl border border-white/10 bg-cardDark shadow-sm animate-fadeIn">
        <div className="border-b border-white/10 px-5 py-4">
          <h2 className="text-base font-bold text-white tracking-wide">Match operations</h2>
          <p className="mt-1 text-xs text-textDim">Check-in, attendance timing, automated dispatch, and bot behavior for the selected tournament.</p>
        </div>
        
        <div className="p-5 flex flex-col gap-4 overflow-y-auto custom-scrollbar">
          {/* Check-in Source — Challonge owns no lifecycle/check-in state. */}
          <div className="flex flex-col gap-2 p-3 rounded-lg bg-black/40 border border-blue-500/30">
            <span className="text-sm font-bold text-blue-300">🎯 {isChallonge ? 'Attendance workflow' : 'Check-in Source'}</span>
            {isChallonge ? (
              <>
                <span className="rounded border border-white/10 bg-black/30 px-3 py-1.5 text-sm font-semibold text-white">Discord-run · local to aiTOB</span>
                <span className="text-[11px] text-textDim leading-snug">
                  aiTOB sends the Call, records Ready, manages the station and updates Discord/OBS. Challonge stays unchanged until a verified result is submitted.
                </span>
              </>
            ) : (
              <>
                <select
                  value={checkInSource}
                  onChange={e => setCheckInSource(e.target.value)}
                  className="w-full bg-black/40 border border-white/10 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500/50"
                >
                  <option value="discord" className="text-black">Discord-run (bot buttons + bot auto-DQ)</option>
                  <option value="startgg" className="text-black">Start.gg-run (start.gg check-in wave + DQ)</option>
                </select>
                <span className="text-[11px] text-textDim leading-snug">
                  <strong>Discord:</strong> bot posts "I'm Ready" buttons and runs the auto-DQ timer below.{' '}
                  <strong>Start.gg:</strong> bot posts a buttonless "check in on start.gg" notice and lets
                  start.gg own the check-in timer, notifications, and DQ. The Auto-DQ settings below have no
                  effect in Start.gg mode.
                </span>
              </>
            )}
          </div>

          {/* Challonge keeps reminder deadlines local, but never auto-submits a DQ. */}
          {!isChallonge && (
            <div className="flex items-center justify-between p-3 rounded-lg bg-black/25 border border-white/5">
              <div className="flex flex-col gap-0.5">
                <span className="text-sm font-semibold text-gray-200">Enable Auto DQ</span>
                <span className="text-xs text-textDim">Automatically DQ players who do not show up</span>
              </div>
              <input
                type="checkbox"
                checked={autoDqEnabled}
                onChange={e => setAutoDqEnabled(e.target.checked)}
                className="w-4 h-4 accent-accentYellow cursor-pointer rounded"
              />
            </div>
          )}

          {/* DQ Timer */}
          <div className="flex flex-col gap-2 p-3 rounded-lg bg-black/25 border border-white/5">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-gray-200">{isChallonge ? 'Attendance deadline (Minutes)' : 'DQ Timer (Minutes)'}</span>
              <input 
                type="number" 
                min={1} 
                max={60}
                value={dqTimerMinutes} 
                onChange={e => setDqTimerMinutes(Number(e.target.value))}
                className="w-20 bg-black/40 border border-white/10 rounded px-2.5 py-1 text-center text-sm font-medium text-white focus:outline-none focus:border-accentYellow/50"
              />
            </div>
            <span className="text-xs text-textDim">{isChallonge ? 'Deadline for Discord reminders. It never submits an automatic Challonge DQ.' : 'Grace period before auto-DQ after match is called'}</span>
          </div>

          {/* Bot Manage Limit (Till) */}
          <div className="flex flex-col gap-2 p-3 rounded-lg bg-black/25 border border-white/5">
            <span className="text-sm font-semibold text-gray-200">{isChallonge ? 'Bot management range' : 'Bot Manage Limit (Round/Pool)'}</span>
            <select
              value={botManageLimit}
              onChange={e => setBotManageLimit(e.target.value)}
              className="w-full bg-black/40 border border-white/10 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-accentYellow/50"
            >
              <option value="off" className="text-black">Disable Bot (Manual Call)</option>
              <option value="all" className="text-black">{isChallonge ? 'All eligible bracket rounds' : 'All Rounds (No Limit)'}</option>
              <option value="top8" className="text-black">{isChallonge ? 'Stop at final eight' : 'Pools up to Top 8 (Auto till Top 8)'}</option>
              <option value="top16" className="text-black">{isChallonge ? 'Stop at final sixteen' : 'Pools up to Top 16 (Auto till Top 16)'}</option>
              {!isChallonge && phaseGroups.map(pg => (
                <option key={pg} value={pg} className="text-black">
                  Only manage Pool: {pg}
                </option>
              ))}
            </select>
            <span className="text-xs text-textDim">{isChallonge ? 'Controls local Calls only; it never changes a Challonge match lifecycle.' : 'Define up to what stage the bot automatically manages matches'}</span>
          </div>

          {/* Bot Manage Finish */}
          <div className="flex flex-col gap-2 p-3 rounded-lg bg-black/25 border border-white/5">
            <span className="text-sm font-semibold text-gray-200">Result collection</span>
            <select
              value={botManageFinish}
              onChange={e => setBotManageFinish(e.target.value)}
              className="w-full bg-black/40 border border-white/10 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-accentYellow/50"
            >
              <option value="off" className="text-black">Off (Admins report manually)</option>
              <option value="on" className="text-black">On (DM Players to report & verify scores)</option>
              <option value="auto" className="text-black">Auto (Finish immediately on report)</option>
            </select>
            <span className="text-xs text-textDim">{isChallonge ? 'The bot may collect a result, but provider verification remains required before completion.' : 'Let the Discord bot DM players to collect and submit scores'}</span>
          </div>

          {/* ── Auto-Dispatcher ── */}
          <div className="flex flex-col gap-3 p-3 rounded-lg bg-black/40 border border-amber-500/30">
            <div className="flex items-center justify-between">
              <div className="flex flex-col gap-0.5">
                <span className="text-sm font-bold text-amber-300">🤖 Auto-Dispatcher</span>
                <span className="text-[11px] text-textDim">
                  Bot calls the next ready match automatically. Master switch (top bar) must also be ON.
                </span>
              </div>
              <input
                type="checkbox"
                checked={autoDispatchEnabled}
                onChange={e => setAutoDispatchEnabled(e.target.checked)}
                className="w-4 h-4 accent-amber-500 cursor-pointer rounded"
              />
            </div>

            <div className={`rounded-lg border px-3 py-2 text-[11px] leading-relaxed ${
              dispatcherStatus?.state === 'running'
                ? 'border-statusGreen/30 bg-statusGreen/5 text-green-200'
                : 'border-amber-500/25 bg-amber-500/5 text-amber-100'
            }`}>
              <div className="flex items-center justify-between gap-3">
                <span className="font-semibold">Actual status</span>
                <span className="font-bold uppercase tracking-wide">
                  {dispatcherStatus?.state === 'running' ? 'Running'
                    : dispatcherStatus?.state === 'paused_tournament' ? 'Paused for this tournament'
                    : dispatcherStatus?.state === 'paused_global' ? 'Paused by global Kill Switch'
                    : 'Service offline'}
                </span>
              </div>
              <p className="mt-1 text-textDim">{dispatcherStatus?.explanation || 'Checking the Dispatcher service…'}</p>
            </div>

            {autoDispatchEnabled && (
              <>
                <div className="flex items-center justify-between gap-3 pt-1 border-t border-white/5">
                  <div className="flex flex-col gap-0.5 min-w-0">
                    <span className="text-xs font-semibold text-gray-200">Concurrent matches</span>
                    <span className="text-[11px] text-textDim">Cap how many run at once. Start at 1.</span>
                  </div>
                  <input
                    type="number"
                    min={1}
                    max={20}
                    value={autoDispatchConcurrency}
                    onChange={e => setAutoDispatchConcurrency(Math.max(1, Math.min(20, Number(e.target.value))))}
                    className="w-16 bg-black/40 border border-white/10 rounded px-2 py-1 text-center text-sm text-white focus:outline-none focus:border-amber-500/50"
                  />
                </div>

                <div className="flex items-center justify-between gap-3 pt-1 border-t border-white/5">
                  <div className="flex flex-col gap-0.5 min-w-0">
                    <span className="text-xs font-semibold text-gray-200">Hand off to TO at ≤ N remaining</span>
                    <span className="text-[11px] text-textDim">Typically 8 (Top 8). 0 = run to the end.</span>
                  </div>
                  <input
                    type="number"
                    min={0}
                    max={64}
                    value={autoDispatchStopAt}
                    onChange={e => setAutoDispatchStopAt(Math.max(0, Math.min(64, Number(e.target.value))))}
                    className="w-16 bg-black/40 border border-white/10 rounded px-2 py-1 text-center text-sm text-white focus:outline-none focus:border-amber-500/50"
                  />
                </div>

                <label className="flex items-center justify-between gap-3 pt-1 border-t border-white/5 cursor-pointer">
                  <div className="flex flex-col gap-0.5 min-w-0">
                    <span className="text-xs font-semibold text-gray-200">Include on-stream matches</span>
                    <span className="text-[11px] text-textDim">Off by default. Featured matches remain a manual organizer Call.</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={autoDispatchOnStream}
                    onChange={e => setAutoDispatchOnStream(e.target.checked)}
                    className="w-4 h-4 accent-amber-500 cursor-pointer rounded shrink-0"
                  />
                </label>

                <div className="text-[11px] text-amber-300/70 bg-amber-500/5 border border-amber-500/20 rounded p-2 leading-relaxed space-y-1">
                  <p>Requires fresh bracket data and verified Discord links for both entrants. It never assigns a station.</p>
                  <p><strong>This tournament:</strong> turning this switch off cancels only its pending automatic Calls. <strong>Global Kill Switch:</strong> cancels pending automatic Calls across every tournament. Manual Calls stay independent in both cases.</p>
                </div>
              </>
            )}
          </div>

          {/* ── Advanced / Debug: Activity Guard Override ── */}
          {!isChallonge && <label className="flex items-center justify-between p-3 rounded-lg bg-red-950/20 border border-red-500/30 cursor-pointer">
            <div className="flex flex-col gap-0.5 pr-2">
              <span className="text-sm font-bold text-red-300">⚠ Override Activity Guard</span>
              <span className="text-[11px] text-textDim leading-snug">
                Load matches even if the tournament/phase isn't ACTIVE on start.gg.
                Off by default — Send/Call may still fail since start.gg refuses
                mutations on completed sets. Use for replaying or testing.
              </span>
            </div>
            <input
              type="checkbox"
              checked={ignoreActivityGuard}
              onChange={e => setIgnoreActivityGuard(e.target.checked)}
              className="w-4 h-4 accent-red-500 cursor-pointer rounded shrink-0"
            />
          </label>}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-white/10 px-5 py-3.5 bg-black/35">
          <button 
            onClick={handleSave}
            disabled={saving}
            className="px-5 py-2 rounded-md text-sm font-bold bg-accentYellow text-black hover:bg-yellow-400 hover:shadow-[0_0_12px_rgba(255,200,0,0.3)] transition-all disabled:opacity-50 disabled:pointer-events-none"
          >
            {saving ? "Saving..." : "Save Settings"}
          </button>
        </div>
      </section>
  );
}
