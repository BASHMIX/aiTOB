import { useState } from "react";
import axios from "axios";

interface MatchSettingsModalProps {
  currentSlug: string;
  initialAutoDqEnabled: boolean;
  initialDqTimerSeconds: number;
  initialBotManageLimit?: string;
  initialBotManageFinish?: string;
  initialAutoDispatchEnabled?: boolean;
  initialAutoDispatchConcurrency?: number;
  initialAutoDispatchStopAt?: number;
  initialIgnoreActivityGuard?: boolean;
  phaseGroups: string[];
  onClose: () => void;
  onSave: () => void;
}

export function MatchSettingsModal({
  currentSlug,
  initialAutoDqEnabled,
  initialDqTimerSeconds,
  initialBotManageLimit = "off",
  initialBotManageFinish = "off",
  initialAutoDispatchEnabled = false,
  initialAutoDispatchConcurrency = 1,
  initialAutoDispatchStopAt = 8,
  initialIgnoreActivityGuard = false,
  phaseGroups,
  onClose,
  onSave,
}: MatchSettingsModalProps) {
  const [autoDqEnabled, setAutoDqEnabled] = useState(initialAutoDqEnabled);
  const [dqTimerMinutes, setDqTimerMinutes] = useState(Math.floor(initialDqTimerSeconds / 60));
  const [botManageLimit, setBotManageLimit] = useState(initialBotManageLimit);
  const [botManageFinish, setBotManageFinish] = useState(initialBotManageFinish);
  const [autoDispatchEnabled, setAutoDispatchEnabled] = useState(initialAutoDispatchEnabled);
  const [autoDispatchConcurrency, setAutoDispatchConcurrency] = useState(initialAutoDispatchConcurrency);
  const [autoDispatchStopAt, setAutoDispatchStopAt] = useState(initialAutoDispatchStopAt);
  const [ignoreActivityGuard, setIgnoreActivityGuard] = useState(initialIgnoreActivityGuard);
  const [saving, setSaving] = useState(false);

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
        ignore_activity_guard: ignoreActivityGuard,
      });
      onSave();
      onClose();
    } catch (e) {
      console.error("Failed to save match settings", e);
      alert("Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      {/* Absolute Backdrop relative to MatchDashboard container */}
      <div 
        className="absolute inset-0 z-20 bg-black/60 backdrop-blur-sm rounded-lg" 
        onClick={onClose} 
      />
      {/* Absolute Modal Panel centered relative to MatchDashboard */}
      <div className="absolute left-1/2 top-1/2 z-30 w-[95%] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-xl border border-white/10 bg-cardDark shadow-2xl flex flex-col max-h-[90%] overflow-hidden animate-fadeIn">
        <div className="border-b border-white/10 px-5 py-4 flex items-center justify-between">
          <h2 className="text-base font-bold text-white tracking-wide">Tournament Bot Settings</h2>
          <button 
            onClick={onClose}
            className="text-textDim hover:text-white transition-colors"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>
        
        <div className="p-5 flex flex-col gap-4 overflow-y-auto custom-scrollbar">
          {/* Auto DQ Toggle */}
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

          {/* DQ Timer */}
          <div className="flex flex-col gap-2 p-3 rounded-lg bg-black/25 border border-white/5">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-gray-200">DQ Timer (Minutes)</span>
              <input 
                type="number" 
                min={1} 
                max={60}
                value={dqTimerMinutes} 
                onChange={e => setDqTimerMinutes(Number(e.target.value))}
                className="w-20 bg-black/40 border border-white/10 rounded px-2.5 py-1 text-center text-sm font-medium text-white focus:outline-none focus:border-accentYellow/50"
              />
            </div>
            <span className="text-xs text-textDim">Grace period before auto-DQ after match is called</span>
          </div>

          {/* Bot Manage Limit (Till) */}
          <div className="flex flex-col gap-2 p-3 rounded-lg bg-black/25 border border-white/5">
            <span className="text-sm font-semibold text-gray-200">Bot Manage Limit (Round/Pool)</span>
            <select
              value={botManageLimit}
              onChange={e => setBotManageLimit(e.target.value)}
              className="w-full bg-black/40 border border-white/10 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-accentYellow/50"
            >
              <option value="off" className="text-black">Disable Bot (Manual Call)</option>
              <option value="all" className="text-black">All Rounds (No Limit)</option>
              <option value="top8" className="text-black">Pools up to Top 8 (Auto till Top 8)</option>
              <option value="top16" className="text-black">Pools up to Top 16 (Auto till Top 16)</option>
              {phaseGroups.map(pg => (
                <option key={pg} value={pg} className="text-black">
                  Only manage Pool: {pg}
                </option>
              ))}
            </select>
            <span className="text-xs text-textDim">Define up to what stage the bot automatically manages matches</span>
          </div>

          {/* Bot Manage Finish */}
          <div className="flex flex-col gap-2 p-3 rounded-lg bg-black/25 border border-white/5">
            <span className="text-sm font-semibold text-gray-200">Bot manage finish matches</span>
            <select
              value={botManageFinish}
              onChange={e => setBotManageFinish(e.target.value)}
              className="w-full bg-black/40 border border-white/10 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-accentYellow/50"
            >
              <option value="off" className="text-black">Off (Admins report manually)</option>
              <option value="on" className="text-black">On (DM Players to report & verify scores)</option>
              <option value="auto" className="text-black">Auto (Finish immediately on report)</option>
            </select>
            <span className="text-xs text-textDim">Let the Discord bot DM players to collect and submit scores</span>
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

                <div className="text-[11px] text-amber-300/70 bg-amber-500/5 border border-amber-500/20 rounded p-2 leading-relaxed">
                  Skips planned-stream matches and matches with TBD entrants. Logs every action to the bot feed. Flip the master switch off at any time to take over.
                </div>
              </>
            )}
          </div>

          {/* ── Advanced / Debug: Activity Guard Override ── */}
          <label className="flex items-center justify-between p-3 rounded-lg bg-red-950/20 border border-red-500/30 cursor-pointer">
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
          </label>
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-white/10 px-5 py-3.5 bg-black/35 mt-auto">
          <button 
            onClick={onClose}
            className="px-4 py-2 rounded-md text-sm font-semibold text-gray-400 hover:bg-white/5 hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button 
            onClick={handleSave}
            disabled={saving}
            className="px-5 py-2 rounded-md text-sm font-bold bg-accentYellow text-black hover:bg-yellow-400 hover:shadow-[0_0_12px_rgba(255,200,0,0.3)] transition-all disabled:opacity-50 disabled:pointer-events-none"
          >
            {saving ? "Saving..." : "Save Settings"}
          </button>
        </div>
      </div>
    </>
  );
}
