import React, { useState } from 'react';
import { AitobSettings } from '../types/telemetry';
import { RefreshCw, PowerOff, Radio, X } from 'lucide-react';

interface Props {
  settings: AitobSettings;
  onSettingsChange: (settings: AitobSettings) => void;
  onConnect: () => void;
  onDisconnect: () => void;
  onSync?: () => void;
  isSyncing?: boolean;
}

export const AitobConnectionPanel: React.FC<Props> = ({ 
  settings, 
  onSettingsChange, 
  onConnect, 
  onDisconnect,
  onSync,
  isSyncing = false,
}) => {
  const [localSyncing, setLocalSyncing] = useState(false);

  const handleSyncClick = () => {
    setLocalSyncing(true);
    if (onSync) onSync();
    else onConnect();
    setTimeout(() => setLocalSyncing(false), 800);
  };

  const isSpinning = isSyncing || localSyncing;

  return (
    <div className="glass-panel p-4 rounded-xl mb-4 border border-violet-900/40 shadow-[0_0_15px_rgba(124,58,237,0.1)] transition-all">
      <div className="flex items-center justify-between mb-3.5">
        <h2 className="text-xl font-rajdhani font-bold text-violet-400 flex items-center gap-2">
          <span className={`w-2.5 h-2.5 rounded-full ${settings.connected ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]' : 'bg-violet-500 animate-pulse'}`} />
          aiTOB Station Identity
        </h2>
        <div className={`px-3 py-0.5 rounded-full text-xs font-rajdhani font-bold uppercase tracking-wider border flex items-center gap-1.5 ${
          settings.connected 
            ? 'bg-emerald-950/40 text-emerald-300 border-emerald-500/40 shadow-[0_0_10px_rgba(16,185,129,0.15)]' 
            : 'bg-slate-800/60 text-slate-400 border-slate-700/80'
        }`}>
          <span className={`w-1.5 h-1.5 rounded-full ${settings.connected ? 'bg-emerald-400' : 'bg-slate-500'}`} />
          {settings.connected ? 'Connected' : 'Offline'}
        </div>
      </div>

      <div className="flex flex-col lg:flex-row lg:items-end gap-3.5">
        {/* Station ID input */}
        <div className="w-full lg:w-48 shrink-0 min-w-0">
          <label className="block text-[11px] uppercase tracking-wider text-slate-400 mb-1.5 font-rajdhani font-bold">
            Station ID
          </label>
          <input
            type="text"
            value={settings.stationId}
            onChange={(e) => onSettingsChange({ ...settings, stationId: e.target.value })}
            className="w-full bg-[#090d16] border border-slate-700/90 hover:border-slate-600 focus:border-violet-500 rounded-xl px-3.5 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none transition-colors"
            placeholder="e.g. station-01"
          />
        </div>

        {/* Pairing Token / OBS Link input */}
        <div className="flex-1 min-w-0">
          <label className="block text-[11px] uppercase tracking-wider text-slate-400 mb-1.5 font-rajdhani font-bold">
            Pairing Token / OBS Link
          </label>
          <div className="relative">
            <input
              type="text"
              value={settings.pairingToken}
              onChange={(e) => onSettingsChange({ ...settings, pairingToken: e.target.value })}
              className="w-full bg-[#090d16] border border-slate-700/90 hover:border-slate-600 focus:border-violet-500 rounded-xl px-3.5 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none transition-colors pr-9 font-mono text-xs"
              placeholder="Paste Token or full OBS Link..."
            />
            {settings.pairingToken && (
              <button
                type="button"
                onClick={() => onSettingsChange({ ...settings, pairingToken: '' })}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors p-1"
                title="Clear token"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2.5 shrink-0 pt-1 lg:pt-0">
          {settings.connected ? (
            <>
              <button 
                type="button"
                onClick={handleSyncClick}
                disabled={isSpinning}
                className="px-4 py-2 rounded-xl bg-violet-600/20 hover:bg-violet-600/35 text-violet-300 hover:text-violet-100 border border-violet-500/40 hover:border-violet-500/70 font-rajdhani font-bold text-xs tracking-wider uppercase flex items-center gap-2 transition active:scale-95 shadow-[0_0_12px_rgba(139,92,246,0.15)] whitespace-nowrap disabled:opacity-60"
                title="Force refresh match telemetry from aiTOB"
              >
                <RefreshCw className={`w-3.5 h-3.5 text-violet-400 ${isSpinning ? 'animate-spin' : ''}`} />
                <span>SYNC NOW</span>
              </button>
              <button 
                type="button"
                onClick={onDisconnect}
                className="px-4 py-2 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 hover:text-rose-300 border border-rose-500/30 hover:border-rose-500/50 font-rajdhani font-bold text-xs tracking-wider uppercase flex items-center gap-2 transition active:scale-95 whitespace-nowrap"
                title="Disconnect from aiTOB Station"
              >
                <PowerOff className="w-3.5 h-3.5 text-rose-400" />
                <span>DISCONNECT</span>
              </button>
            </>
          ) : (
            <button 
              type="button"
              onClick={onConnect}
              className="w-full lg:w-auto px-5 py-2 rounded-xl bg-gradient-to-r from-violet-600 via-purple-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-rajdhani font-bold text-xs tracking-wider uppercase flex items-center justify-center gap-2 transition active:scale-95 shadow-lg shadow-violet-600/30 whitespace-nowrap"
            >
              <Radio className="w-3.5 h-3.5 text-violet-200" />
              <span>CONNECT TO AITOB</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
