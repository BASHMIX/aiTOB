import React, { useState } from "react";
import axios from "axios";

interface MatchSettingsModalProps {
  currentSlug: string;
  initialAutoDqEnabled: boolean;
  initialDqTimerSeconds: number;
  onClose: () => void;
  onSave: () => void;
}

export function MatchSettingsModal({ currentSlug, initialAutoDqEnabled, initialDqTimerSeconds, onClose, onSave }: MatchSettingsModalProps) {
  const [autoDqEnabled, setAutoDqEnabled] = useState(initialAutoDqEnabled);
  const [dqTimerMinutes, setDqTimerMinutes] = useState(Math.floor(initialDqTimerSeconds / 60));
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      await axios.patch(`/api/tournaments/${currentSlug}/settings`, {
        auto_dq_enabled: autoDqEnabled,
        dq_timer_seconds: dqTimerMinutes * 60,
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
      <div className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className="fixed left-1/2 top-1/2 z-50 w-full max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-lg border border-white/10 bg-[#161a21] shadow-2xl">
        <div className="border-b border-white/10 px-4 py-3">
          <h2 className="text-lg font-bold text-white">Match Settings</h2>
        </div>
        
        <div className="p-4 flex flex-col gap-4">
          <label className="flex items-center justify-between cursor-pointer">
            <span className="text-sm font-semibold text-gray-200">Enable Auto DQ</span>
            <input 
              type="checkbox" 
              checked={autoDqEnabled} 
              onChange={e => setAutoDqEnabled(e.target.checked)}
              className="w-4 h-4 accent-accentYellow"
            />
          </label>

          <label className="flex items-center justify-between">
            <span className="text-sm font-semibold text-gray-200">DQ Timer (Minutes)</span>
            <input 
              type="number" 
              min={1} 
              max={60}
              value={dqTimerMinutes} 
              onChange={e => setDqTimerMinutes(Number(e.target.value))}
              className="w-20 bg-black/30 border border-white/10 rounded px-2 py-1 text-right text-sm text-white focus:outline-none focus:border-accentYellow/50"
            />
          </label>
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-white/10 px-4 py-3 bg-black/20">
          <button 
            onClick={onClose}
            className="px-4 py-1.5 rounded text-sm font-semibold text-gray-400 hover:bg-white/5 transition-colors"
          >
            Cancel
          </button>
          <button 
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-1.5 rounded text-sm font-semibold bg-accentYellow text-black hover:bg-yellow-400 transition-colors disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>
    </>
  );
}
