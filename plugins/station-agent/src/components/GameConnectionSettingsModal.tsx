import React, { useState } from 'react';
import { X, Save, FolderOpen, Gamepad2, Info } from 'lucide-react';

interface GameConnectionSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentMethod: 'udp' | 'json';
  currentPort: number;
  currentGamePath: string;
  onSave: (config: { method: 'udp' | 'json', port: number, gamePath: string }) => void;
}

export const GameConnectionSettingsModal: React.FC<GameConnectionSettingsModalProps> = ({
  isOpen,
  onClose,
  currentMethod,
  currentPort,
  currentGamePath,
  onSave,
}) => {
  const [method, setMethod] = useState<'udp' | 'json'>(currentMethod);
  const [port, setPort] = useState(currentPort);
  const [gamePath, setGamePath] = useState(currentGamePath);
  const [installStatus, setInstallStatus] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSelectDir = async () => {
    if (typeof window !== 'undefined' && window.api?.selectDirectory) {
      const dir = await window.api.selectDirectory();
      if (dir) {
        setGamePath(dir);
      }
    }
  };

  const handleInstallMod = async () => {
    if (typeof window !== 'undefined' && window.api?.installMod) {
      setInstallStatus('Installing...');
      const res = await window.api.installMod(gamePath, port);
      if (res.success) {
        setInstallStatus('Mod Installed Successfully! Please click "Reset Scripts" in REFramework.');
      } else {
        setInstallStatus('Install failed: ' + res.error);
      }
    }
  };

  const handleSave = () => {
    onSave({ method, port, gamePath });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-700/50 rounded-2xl p-6 w-full max-w-lg shadow-2xl">
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center gap-2">
            <Gamepad2 className="w-5 h-5 text-indigo-400" />
            <h2 className="text-xl font-bold font-rajdhani">Game Connection Settings</h2>
          </div>
          <button onClick={onClose} className="p-1 hover:bg-slate-800 rounded-lg text-slate-400 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-6">
          {/* Method Selection */}
          <div className="space-y-3">
            <label className="text-sm font-semibold text-slate-300">Connection Method</label>
            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={() => setMethod('json')}
                className={`p-3 rounded-lg border text-left transition-all ${
                  method === 'json'
                    ? 'bg-indigo-500/10 border-indigo-500 text-indigo-400'
                    : 'bg-slate-800/50 border-slate-700 text-slate-400 hover:border-slate-600'
                }`}
              >
                <div className="font-bold mb-1">JSON File (Auto)</div>
                <div className="text-xs opacity-70">Reads telemetry file automatically. Extremely stable.</div>
              </button>
              
              <button
                onClick={() => setMethod('udp')}
                className={`p-3 rounded-lg border text-left transition-all ${
                  method === 'udp'
                    ? 'bg-indigo-500/10 border-indigo-500 text-indigo-400'
                    : 'bg-slate-800/50 border-slate-700 text-slate-400 hover:border-slate-600'
                }`}
              >
                <div className="font-bold mb-1">UDP Port</div>
                <div className="text-xs opacity-70">Direct packet reception. Requires LuaSocket plugin in game.</div>
              </button>
            </div>
          </div>

          {/* Connection Details */}
          <div className="bg-slate-800/30 rounded-xl p-4 border border-slate-700/30 space-y-4">
            
            <div>
              <label className="block text-xs font-semibold text-slate-400 mb-1">UDP Port</label>
              <input
                type="number"
                value={port}
                onChange={(e) => setPort(Number(e.target.value))}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-400 mb-1">Street Fighter 6 Path (For JSON Mode or Mod Install)</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={gamePath}
                  onChange={(e) => setGamePath(e.target.value)}
                  placeholder="Auto-detected if game is running..."
                  className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none text-slate-300"
                />
                <button
                  onClick={handleSelectDir}
                  className="p-2 bg-slate-800 border border-slate-700 rounded-lg hover:bg-slate-700 transition-colors text-slate-300"
                  title="Browse Folder"
                >
                  <FolderOpen className="w-5 h-5" />
                </button>
              </div>
            </div>

            <div className="pt-2 border-t border-slate-700/50">
              <button
                onClick={handleInstallMod}
                disabled={!gamePath}
                className="w-full py-2.5 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 text-emerald-400 rounded-lg text-sm font-bold transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                Install / Update Mod to Game
              </button>
              {installStatus && (
                <div className="mt-2 text-xs text-center text-slate-300 bg-slate-800 p-2 rounded">
                  {installStatus}
                </div>
              )}
            </div>

          </div>
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm font-semibold text-slate-300 hover:bg-slate-800 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="px-4 py-2 rounded-lg text-sm font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition-colors flex items-center gap-2"
          >
            <Save className="w-4 h-4" />
            Save & Restart Connection
          </button>
        </div>
      </div>
    </div>
  );
};
