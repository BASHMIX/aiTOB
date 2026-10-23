import React, { useState } from 'react';
import { AitobSettings } from '../types/telemetry';
import { Globe2, X, Check, RefreshCw, KeyRound } from 'lucide-react';

interface AitobSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  settings: AitobSettings;
  onSave: (newSettings: AitobSettings) => void;
  onSync: () => void;
}

export const AitobSettingsModal: React.FC<AitobSettingsModalProps> = ({
  isOpen,
  onClose,
  settings,
  onSave,
  onSync,
}) => {
  const [formData, setFormData] = useState<AitobSettings>({ ...settings });

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave(formData);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fadeIn">
      <div className="w-full max-w-md glass-panel rounded-2xl p-6 border border-slate-700 shadow-2xl relative text-right">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-5 right-5 p-1.5 rounded-lg text-slate-400 hover:text-white bg-slate-800 hover:bg-slate-700 transition"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Modal Header */}
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-xl bg-blue-500/20 text-cyan-400 border border-cyan-500/30 flex items-center justify-center">
            <Globe2 className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-bold text-lg text-white">aiTOB Platform Settings</h3>
            <p className="text-xs text-slate-400">Sync players and automate result submission</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          {/* Server URL */}
          <div>
            <label className="block text-slate-300 font-semibold mb-1">aiTOB Server (API URL)</label>
            <input
              type="text"
              value={formData.serverUrl}
              onChange={(e) => setFormData({ ...formData, serverUrl: e.target.value })}
              className="w-full bg-[#090d16] border border-slate-700 rounded-lg p-2.5 text-white font-mono focus:border-cyan-500 focus:outline-none"
              placeholder="http://localhost:8000"
            />
          </div>

          {/* Station Identifier */}
          <div>
            <label className="block text-slate-300 font-semibold mb-1">Station ID</label>
            <input
              type="text"
              value={formData.stationId}
              onChange={(e) => setFormData({ ...formData, stationId: e.target.value })}
              className="w-full bg-[#090d16] border border-slate-700 rounded-lg p-2.5 text-white font-mono focus:border-cyan-500 focus:outline-none"
              placeholder="station-01"
            />
            <span className="text-[10px] text-slate-400 mt-1 block">
              Must match the Station ID registered in the aiTOB dashboard.
            </span>
          </div>

          {/* Pairing Key */}
          <div>
            <label className="block text-slate-300 font-semibold mb-1 flex items-center gap-1">
              <KeyRound className="w-3.5 h-3.5 text-cyan-400" />
              <span>Pairing Token (Optional)</span>
            </label>
            <input
              type="password"
              value={formData.pairingToken}
              onChange={(e) => setFormData({ ...formData, pairingToken: e.target.value })}
              className="w-full bg-[#090d16] border border-slate-700 rounded-lg p-2.5 text-white font-mono focus:border-cyan-500 focus:outline-none"
              placeholder="aitob_sec_••••••••"
            />
          </div>

          {/* Active Set ID info */}
          <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-800">
            <div className="flex justify-between items-center text-[11px] mb-1">
              <span className="text-slate-400">Active Set ID:</span>
              <span className="font-mono text-cyan-400 font-bold">{formData.activeSetId || 'None'}</span>
            </div>
            <div className="flex justify-between items-center text-[11px]">
              <span className="text-slate-400">Sync Status:</span>
              <span className={formData.connected ? 'text-emerald-400 font-bold' : 'text-amber-400'}>
                {formData.connected ? 'Connected' : 'Offline (Local Mode)'}
              </span>
            </div>
          </div>

          {/* Actions */}
          <div className="pt-2 flex items-center justify-between">
            <button
              type="button"
              onClick={onSync}
              className="px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-cyan-300 border border-cyan-500/30 font-bold flex items-center gap-1.5 transition"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Sync Now</span>
            </button>

            <button
              type="submit"
              className="px-5 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-bold flex items-center gap-1.5 shadow-lg shadow-blue-600/30 transition"
            >
              <Check className="w-4 h-4" />
              <span>Save Settings</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
