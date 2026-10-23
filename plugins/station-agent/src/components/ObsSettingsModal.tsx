import React, { useState } from 'react';
import { ObsSettings } from '../types/telemetry';
import { Video, X, Check, Link2, Unlink } from 'lucide-react';

interface ObsSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  settings: ObsSettings;
  onSave: (newSettings: ObsSettings) => void;
  isConnecting: boolean;
  onTestConnection: () => Promise<void>;
  isConnected: boolean;
}

export const ObsSettingsModal: React.FC<ObsSettingsModalProps> = ({
  isOpen,
  onClose,
  settings,
  onSave,
  isConnecting,
  onTestConnection,
  isConnected,
}) => {
  const [formData, setFormData] = useState<ObsSettings>({ ...settings });

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
          <div className="w-10 h-10 rounded-xl bg-purple-500/20 text-purple-400 border border-purple-500/30 flex items-center justify-center">
            <Video className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-bold text-lg text-white">OBS Studio Connection</h3>
            <p className="text-xs text-slate-400">Automate scene switching via WebSocket v5</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          {/* Host & Port */}
          <div className="grid grid-cols-3 gap-2">
            <div className="col-span-2">
              <label className="block text-slate-300 font-semibold mb-1">OBS Address (Host/IP)</label>
              <input
                type="text"
                value={formData.ip}
                onChange={(e) => setFormData({ ...formData, ip: e.target.value })}
                className="w-full bg-[#090d16] border border-slate-700 rounded-lg p-2.5 text-white font-mono focus:border-purple-500 focus:outline-none"
                placeholder="127.0.0.1"
              />
            </div>
            <div>
              <label className="block text-slate-300 font-semibold mb-1">Port</label>
              <input
                type="number"
                value={formData.port}
                onChange={(e) => setFormData({ ...formData, port: Number(e.target.value) })}
                className="w-full bg-[#090d16] border border-slate-700 rounded-lg p-2.5 text-white font-mono focus:border-purple-500 focus:outline-none"
                placeholder="4455"
              />
            </div>
          </div>

          {/* Password */}
          <div>
            <label className="block text-slate-300 font-semibold mb-1">WebSocket Password (Optional)</label>
            <input
              type="password"
              value={formData.password || ''}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              className="w-full bg-[#090d16] border border-slate-700 rounded-lg p-2.5 text-white font-mono focus:border-purple-500 focus:outline-none"
              placeholder="••••••••"
            />
          </div>

          {/* Scene Names */}
          <div className="border-t border-slate-800 pt-3">
            <span className="font-bold text-slate-200 block mb-2">Matching OBS Scene Names:</span>
            <div className="space-y-2">
              <div>
                <label className="block text-slate-400 text-[11px] mb-0.5">Versus / Pre-Match Scene</label>
                <input
                  type="text"
                  value={formData.scenePreMatch}
                  onChange={(e) => setFormData({ ...formData, scenePreMatch: e.target.value })}
                  className="w-full bg-[#090d16] border border-slate-700 rounded-lg p-2 text-white font-mono"
                  placeholder="SF6 - Versus"
                />
              </div>
              <div>
                <label className="block text-slate-400 text-[11px] mb-0.5">Gameplay / Live Scene</label>
                <input
                  type="text"
                  value={formData.sceneGameplay}
                  onChange={(e) => setFormData({ ...formData, sceneGameplay: e.target.value })}
                  className="w-full bg-[#090d16] border border-slate-700 rounded-lg p-2 text-white font-mono"
                  placeholder="SF6 - InGame"
                />
              </div>
              <div>
                <label className="block text-slate-400 text-[11px] mb-0.5">Victory / Post-Match Scene</label>
                <input
                  type="text"
                  value={formData.sceneVictory}
                  onChange={(e) => setFormData({ ...formData, sceneVictory: e.target.value })}
                  className="w-full bg-[#090d16] border border-slate-700 rounded-lg p-2 text-white font-mono"
                  placeholder="SF6 - PostMatch"
                />
              </div>
            </div>
          </div>

          {/* Connection Actions */}
          <div className="pt-2 flex items-center justify-between">
            <button
              type="button"
              onClick={onTestConnection}
              disabled={isConnecting}
              className="px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-purple-300 border border-purple-500/30 font-bold flex items-center gap-1.5 transition disabled:opacity-50"
            >
              {isConnected ? <Unlink className="w-3.5 h-3.5" /> : <Link2 className="w-3.5 h-3.5" />}
              <span>{isConnected ? 'Disconnect' : 'Test OBS Connection'}</span>
            </button>

            <button
              type="submit"
              className="px-5 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-white font-bold flex items-center gap-1.5 shadow-lg shadow-purple-600/30 transition"
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
