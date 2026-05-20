import { useState } from "react";
import axios from "axios";

interface MatchSettingsModalProps {
  currentSlug: string;
  initialAutoDqEnabled: boolean;
  initialDqTimerSeconds: number;
  initialBotManageLimit?: string;
  initialBotManageFinish?: string;
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
  phaseGroups,
  onClose,
  onSave,
}: MatchSettingsModalProps) {
  const [autoDqEnabled, setAutoDqEnabled] = useState(initialAutoDqEnabled);
  const [dqTimerMinutes, setDqTimerMinutes] = useState(Math.floor(initialDqTimerSeconds / 60));
  const [botManageLimit, setBotManageLimit] = useState(initialBotManageLimit);
  const [botManageFinish, setBotManageFinish] = useState(initialBotManageFinish);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      await axios.patch(`/api/tournaments/${currentSlug}/settings`, {
        auto_dq_enabled: autoDqEnabled,
        dq_timer_seconds: dqTimerMinutes * 60,
        bot_manage_limit: botManageLimit,
        bot_manage_finish: botManageFinish,
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
