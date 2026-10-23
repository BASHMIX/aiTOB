import React, { useState, useEffect } from 'react';
import { ObsSettings, AitobSettings } from '../types/telemetry';
import { 
  X, Check, Gamepad2, Video, Globe2, FolderOpen, 
  Save, RefreshCw, KeyRound, Link2, Unlink, CheckCircle2, ChevronDown 
} from 'lucide-react';
import { obsService } from '../services/obsService';

export type SettingsTab = 'GAME' | 'OBS' | 'AITOB';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  defaultTab?: SettingsTab;

  // Game config
  gameConnectionConfig: { method: 'udp' | 'json'; port: number; gamePath: string };
  onSaveGameConfig: (config: { method: 'udp' | 'json'; port: number; gamePath: string }) => void;

  // OBS config
  obsSettings: ObsSettings;
  onSaveObsSettings: (settings: ObsSettings) => void;
  isObsConnected: boolean;
  isObsConnecting: boolean;
  onTestObsConnection: () => Promise<void>;

  // aiTOB config
  aitobSettings: AitobSettings;
  onSaveAitobSettings: (settings: AitobSettings) => void;
  onSyncAitob: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  defaultTab = 'GAME',
  gameConnectionConfig,
  onSaveGameConfig,
  obsSettings,
  onSaveObsSettings,
  isObsConnected,
  isObsConnecting,
  onTestObsConnection,
  aitobSettings,
  onSaveAitobSettings,
  onSyncAitob,
}) => {
  const [activeTab, setActiveTab] = useState<SettingsTab>(defaultTab || 'GAME');

  // Local state for forms with safe fallback defaults
  const [localGameConfig, setLocalGameConfig] = useState(
    gameConnectionConfig || { method: 'json', port: 8080, gamePath: '' }
  );
  const [installStatus, setInstallStatus] = useState<string | null>(null);

  const [localObsSettings, setLocalObsSettings] = useState<ObsSettings>(
    obsSettings || { ip: '127.0.0.1', port: 4455, password: '', scenePreMatch: '', sceneGameplay: '', sceneVictory: '', autoSwitch: true }
  );
  const [localAitobSettings, setLocalAitobSettings] = useState<AitobSettings>(
    aitobSettings || { serverUrl: 'http://localhost:8000', stationId: 'station-01', pairingToken: '', connected: false }
  );

  const [savedMessage, setSavedMessage] = useState(false);

  // Live OBS scenes list
  const [obsScenes, setObsScenes] = useState<string[]>([]);
  const [isLoadingScenes, setIsLoadingScenes] = useState(false);
  const [manualSceneMode, setManualSceneMode] = useState(false);

  const fetchScenes = async () => {
    if (obsService.getConnected() || isObsConnected) {
      setIsLoadingScenes(true);
      try {
        const scenes = await obsService.getSceneList();
        if (scenes && scenes.length > 0) {
          setObsScenes(scenes);
        }
      } catch (err) {
        console.error('Failed to get scenes list:', err);
      } finally {
        setIsLoadingScenes(false);
      }
    }
  };

  // Sync state ONLY when opening the modal, NOT on every keystroke or tab switch
  useEffect(() => {
    if (isOpen) {
      setActiveTab(defaultTab || 'GAME');
      setLocalGameConfig(gameConnectionConfig || { method: 'json', port: 8080, gamePath: '' });
      setLocalObsSettings(obsSettings || { ip: '127.0.0.1', port: 4455, password: '', scenePreMatch: '', sceneGameplay: '', sceneVictory: '', autoSwitch: true });
      setLocalAitobSettings(aitobSettings || { serverUrl: 'http://localhost:8000', stationId: 'station-01', pairingToken: '', connected: false });
      setInstallStatus(null);
      setSavedMessage(false);
    }
  }, [isOpen, defaultTab]);

  // Fetch OBS scenes when opening OBS tab while connected
  useEffect(() => {
    if (isOpen && activeTab === 'OBS' && (isObsConnected || obsService.getConnected())) {
      fetchScenes();
    }
  }, [isOpen, activeTab, isObsConnected]);

  if (!isOpen) return null;

  const handleSelectGameDir = async () => {
    if (typeof window !== 'undefined' && window.api?.selectDirectory) {
      try {
        const dir = await window.api.selectDirectory();
        if (dir) {
          setLocalGameConfig(prev => ({ ...prev, gamePath: dir }));
        }
      } catch (err) {
        console.error('Failed to select directory:', err);
      }
    }
  };

  const handleInstallMod = async () => {
    if (typeof window !== 'undefined' && window.api?.installMod) {
      setInstallStatus('Installing...');
      try {
        const res = await window.api.installMod(localGameConfig?.gamePath || '', localGameConfig?.port || 8080);
        if (res.success) {
          setInstallStatus('Mod Installed Successfully! Please click "Reset Scripts" in REFramework.');
        } else {
          setInstallStatus('Install failed: ' + res.error);
        }
      } catch (err: any) {
        setInstallStatus('Install failed: ' + (err?.message || err));
      }
    }
  };

  const handleTestAndFetch = async () => {
    await onTestObsConnection();
    setTimeout(() => {
      fetchScenes();
    }, 600);
  };

  const handleSaveAll = () => {
    if (localGameConfig) onSaveGameConfig(localGameConfig);
    if (localObsSettings) onSaveObsSettings(localObsSettings);
    if (localAitobSettings) onSaveAitobSettings(localAitobSettings);
    setSavedMessage(true);
    setTimeout(() => {
      onClose();
    }, 350);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-fadeIn">
      <div className="w-full max-w-3xl bg-[#0d111a] border border-gray-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800 bg-[#090d14]">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-white font-rajdhani tracking-wider">Preferences & Settings</h2>
            <span className="text-xs px-2 py-0.5 rounded bg-blue-500/10 text-cyan-400 border border-cyan-500/20">
              Station Config
            </span>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-gray-400 hover:text-white bg-gray-800/60 hover:bg-gray-800 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body (Sidebar Tabs + Content) */}
        <div className="flex flex-1 min-h-[460px] overflow-hidden">
          
          {/* Left Tabs Sidebar */}
          <div className="w-56 bg-[#080b12] border-r border-gray-800/80 p-3 flex flex-col gap-1.5 shrink-0">
            <button
              type="button"
              onClick={() => setActiveTab('GAME')}
              className={`flex items-center gap-3 px-3.5 py-3 rounded-xl text-xs font-semibold transition text-left ${
                activeTab === 'GAME'
                  ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/40 shadow-sm'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/40 border border-transparent'
              }`}
            >
              <Gamepad2 className={`w-4 h-4 ${activeTab === 'GAME' ? 'text-indigo-400' : 'text-gray-500'}`} />
              <div>
                <div className="font-bold">Game & Mod</div>
                <div className="text-[10px] text-gray-500">Street Fighter 6 / REFramework</div>
              </div>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('OBS')}
              className={`flex items-center gap-3 px-3.5 py-3 rounded-xl text-xs font-semibold transition text-left ${
                activeTab === 'OBS'
                  ? 'bg-purple-600/20 text-purple-300 border border-purple-500/40 shadow-sm'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/40 border border-transparent'
              }`}
            >
              <Video className={`w-4 h-4 ${activeTab === 'OBS' ? 'text-purple-400' : 'text-gray-500'}`} />
              <div>
                <div className="font-bold">OBS Studio</div>
                <div className="text-[10px] text-gray-500">WebSocket & Scenes</div>
              </div>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('AITOB')}
              className={`flex items-center gap-3 px-3.5 py-3 rounded-xl text-xs font-semibold transition text-left ${
                activeTab === 'AITOB'
                  ? 'bg-cyan-600/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/40 border border-transparent'
              }`}
            >
              <Globe2 className={`w-4 h-4 ${activeTab === 'AITOB' ? 'text-cyan-400' : 'text-gray-500'}`} />
              <div>
                <div className="font-bold">aiTOB Platform</div>
                <div className="text-[10px] text-gray-500">Hub & Bracket Sync</div>
              </div>
            </button>
          </div>

          {/* Right Content Panel */}
          <div className="flex-1 p-6 overflow-y-auto bg-[#0b0f19]">
            
            {/* TAB 1: GAME & MOD */}
            {activeTab === 'GAME' && (
              <div className="space-y-5 animate-fadeIn">
                <div>
                  <h3 className="font-bold text-white text-base">Game Telemetry Connection</h3>
                  <p className="text-xs text-gray-400">Configure how the Station Agent reads match states from Street Fighter 6.</p>
                </div>

                <div className="space-y-3">
                  <label className="text-xs font-semibold text-gray-300">Connection Method</label>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      type="button"
                      onClick={() => setLocalGameConfig(prev => ({ ...prev, method: 'json' }))}
                      className={`p-3 rounded-xl border text-left transition-all ${
                        localGameConfig?.method === 'json'
                          ? 'bg-indigo-500/10 border-indigo-500 text-indigo-300'
                          : 'bg-gray-900/40 border-gray-800 text-gray-400 hover:border-gray-700'
                      }`}
                    >
                      <div className="font-bold text-xs mb-0.5">JSON File (Recommended)</div>
                      <div className="text-[11px] opacity-75">Auto-reads telemetry file from game dir. Very stable.</div>
                    </button>
                    
                    <button
                      type="button"
                      onClick={() => setLocalGameConfig(prev => ({ ...prev, method: 'udp' }))}
                      className={`p-3 rounded-xl border text-left transition-all ${
                        localGameConfig?.method === 'udp'
                          ? 'bg-indigo-500/10 border-indigo-500 text-indigo-300'
                          : 'bg-gray-900/40 border-gray-800 text-gray-400 hover:border-gray-700'
                      }`}
                    >
                      <div className="font-bold text-xs mb-0.5">UDP Port Receiver</div>
                      <div className="text-[11px] opacity-75">Direct packet reception. Requires LuaSocket in game.</div>
                    </button>
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-gray-900/50 border border-gray-800/80 space-y-4">
                  <div>
                    <label className="block text-xs font-semibold text-gray-300 mb-1">UDP Port</label>
                    <input
                      type="number"
                      value={localGameConfig?.port ?? 8080}
                      onChange={(e) => setLocalGameConfig(prev => ({ ...prev, port: Number(e.target.value) }))}
                      className="w-full bg-[#070a10] border border-gray-700/80 rounded-lg px-3 py-2 text-xs font-mono text-white focus:border-indigo-500 focus:outline-none"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-gray-300 mb-1">
                      Street Fighter 6 Folder Path
                    </label>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={localGameConfig?.gamePath ?? ''}
                        onChange={(e) => setLocalGameConfig(prev => ({ ...prev, gamePath: e.target.value }))}
                        placeholder="e.g. C:\Program Files (x86)\Steam\steamapps\common\Street Fighter 6"
                        className="flex-1 bg-[#070a10] border border-gray-700/80 rounded-lg px-3 py-2 text-xs font-mono text-gray-200 focus:border-indigo-500 focus:outline-none"
                      />
                      <button
                        type="button"
                        onClick={handleSelectGameDir}
                        className="p-2 bg-gray-800 border border-gray-700 rounded-lg hover:bg-gray-700 transition text-gray-300"
                        title="Browse Folder"
                      >
                        <FolderOpen className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  <div className="pt-2 border-t border-gray-800">
                    <button
                      type="button"
                      onClick={handleInstallMod}
                      disabled={!localGameConfig?.gamePath}
                      className="w-full py-2 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 text-emerald-400 rounded-lg text-xs font-bold transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                      Install / Auto-Update Telemetry Mod to Game Folder
                    </button>
                    {installStatus && (
                      <div className="mt-2 text-xs text-center text-gray-300 bg-gray-900 border border-gray-800 p-2 rounded">
                        {installStatus}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* TAB 2: OBS STUDIO */}
            {activeTab === 'OBS' && (
              <div className="space-y-4 animate-fadeIn">
                <div>
                  <h3 className="font-bold text-white text-base">OBS Studio WebSocket v5</h3>
                  <p className="text-xs text-gray-400">Connect to OBS to switch scenes and control sources automatically.</p>
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <div className="col-span-2">
                    <label className="block text-gray-300 text-xs font-semibold mb-1">OBS Address (Host / IP)</label>
                    <input
                      type="text"
                      value={localObsSettings?.ip ?? '127.0.0.1'}
                      onChange={(e) => setLocalObsSettings(prev => ({ ...prev, ip: e.target.value }))}
                      className="w-full bg-[#070a10] border border-gray-700/80 rounded-lg p-2 text-xs font-mono text-white focus:border-purple-500 focus:outline-none"
                      placeholder="127.0.0.1"
                    />
                  </div>
                  <div>
                    <label className="block text-gray-300 text-xs font-semibold mb-1">Port</label>
                    <input
                      type="number"
                      value={localObsSettings?.port ?? 4455}
                      onChange={(e) => setLocalObsSettings(prev => ({ ...prev, port: Number(e.target.value) }))}
                      className="w-full bg-[#070a10] border border-gray-700/80 rounded-lg p-2 text-xs font-mono text-white focus:border-purple-500 focus:outline-none"
                      placeholder="4455"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-gray-300 text-xs font-semibold mb-1">WebSocket Password (Optional)</label>
                  <input
                    type="password"
                    value={localObsSettings?.password ?? ''}
                    onChange={(e) => setLocalObsSettings(prev => ({ ...prev, password: e.target.value }))}
                    className="w-full bg-[#070a10] border border-gray-700/80 rounded-lg p-2 text-xs font-mono text-white focus:border-purple-500 focus:outline-none"
                    placeholder="••••••••"
                  />
                </div>

                {/* AUTOMATED SCENE NAMES WITH LIVE OBS DROPDOWN SELECTION */}
                <div className="border-t border-gray-800 pt-3 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-gray-200 text-xs">Automated Scene Names</span>
                      {obsScenes.length > 0 && (
                        <span className="text-[10px] text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded-full border border-purple-500/20 font-mono">
                          {obsScenes.length} OBS scenes
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-3">
                      {obsScenes.length > 0 && (
                        <button
                          type="button"
                          onClick={() => setManualSceneMode(!manualSceneMode)}
                          className="text-[10px] text-purple-400 hover:text-purple-300 underline transition"
                        >
                          {manualSceneMode ? 'Pick from dropdown' : 'Enter custom names'}
                        </button>
                      )}
                      {(isObsConnected || obsService.getConnected()) && (
                        <button
                          type="button"
                          onClick={fetchScenes}
                          disabled={isLoadingScenes}
                          className="text-[10px] flex items-center gap-1 text-gray-400 hover:text-white transition"
                          title="Refresh scenes list from OBS"
                        >
                          <RefreshCw className={`w-3 h-3 ${isLoadingScenes ? 'animate-spin text-purple-400' : ''}`} />
                          <span>Refresh</span>
                        </button>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
                    {/* Scene 1: Pre-Match / Versus */}
                    <div>
                      <label className="block text-gray-400 text-[10px] mb-1 font-semibold">Versus / Pre-Match</label>
                      {obsScenes.length > 0 && !manualSceneMode ? (
                        <div className="relative">
                          <select
                            value={localObsSettings?.scenePreMatch ?? ''}
                            onChange={(e) => setLocalObsSettings(prev => ({ ...prev, scenePreMatch: e.target.value }))}
                            className="w-full bg-[#070a10] border border-gray-700/80 rounded-lg p-2 text-xs font-mono text-white focus:border-purple-500 focus:outline-none appearance-none pr-7"
                          >
                            <option value="">-- Select Scene --</option>
                            {localObsSettings?.scenePreMatch && !obsScenes.includes(localObsSettings.scenePreMatch) && (
                              <option value={localObsSettings.scenePreMatch}>{localObsSettings.scenePreMatch} (Current)</option>
                            )}
                            {obsScenes.map(scene => (
                              <option key={scene} value={scene}>{scene}</option>
                            ))}
                          </select>
                          <ChevronDown className="w-3.5 h-3.5 text-gray-500 absolute right-2.5 top-2.5 pointer-events-none" />
                        </div>
                      ) : (
                        <input
                          type="text"
                          value={localObsSettings?.scenePreMatch ?? ''}
                          onChange={(e) => setLocalObsSettings(prev => ({ ...prev, scenePreMatch: e.target.value }))}
                          className="w-full bg-[#070a10] border border-gray-700/80 rounded-lg p-2 text-xs font-mono text-white focus:border-purple-500 focus:outline-none"
                          placeholder="SF6 - Versus"
                        />
                      )}
                    </div>

                    {/* Scene 2: Gameplay / Live */}
                    <div>
                      <label className="block text-gray-400 text-[10px] mb-1 font-semibold">In-Game / Live</label>
                      {obsScenes.length > 0 && !manualSceneMode ? (
                        <div className="relative">
                          <select
                            value={localObsSettings?.sceneGameplay ?? ''}
                            onChange={(e) => setLocalObsSettings(prev => ({ ...prev, sceneGameplay: e.target.value }))}
                            className="w-full bg-[#070a10] border border-gray-700/80 rounded-lg p-2 text-xs font-mono text-white focus:border-purple-500 focus:outline-none appearance-none pr-7"
                          >
                            <option value="">-- Select Scene --</option>
                            {localObsSettings?.sceneGameplay && !obsScenes.includes(localObsSettings.sceneGameplay) && (
                              <option value={localObsSettings.sceneGameplay}>{localObsSettings.sceneGameplay} (Current)</option>
                            )}
                            {obsScenes.map(scene => (
                              <option key={scene} value={scene}>{scene}</option>
                            ))}
                          </select>
                          <ChevronDown className="w-3.5 h-3.5 text-gray-500 absolute right-2.5 top-2.5 pointer-events-none" />
                        </div>
                      ) : (
                        <input
                          type="text"
                          value={localObsSettings?.sceneGameplay ?? ''}
                          onChange={(e) => setLocalObsSettings(prev => ({ ...prev, sceneGameplay: e.target.value }))}
                          className="w-full bg-[#070a10] border border-gray-700/80 rounded-lg p-2 text-xs font-mono text-white focus:border-purple-500 focus:outline-none"
                          placeholder="SF6 - InGame"
                        />
                      )}
                    </div>

                    {/* Scene 3: Victory / Post-Match */}
                    <div>
                      <label className="block text-gray-400 text-[10px] mb-1 font-semibold">Post-Match / Victory</label>
                      {obsScenes.length > 0 && !manualSceneMode ? (
                        <div className="relative">
                          <select
                            value={localObsSettings?.sceneVictory ?? ''}
                            onChange={(e) => setLocalObsSettings(prev => ({ ...prev, sceneVictory: e.target.value }))}
                            className="w-full bg-[#070a10] border border-gray-700/80 rounded-lg p-2 text-xs font-mono text-white focus:border-purple-500 focus:outline-none appearance-none pr-7"
                          >
                            <option value="">-- Select Scene --</option>
                            {localObsSettings?.sceneVictory && !obsScenes.includes(localObsSettings.sceneVictory) && (
                              <option value={localObsSettings.sceneVictory}>{localObsSettings.sceneVictory} (Current)</option>
                            )}
                            {obsScenes.map(scene => (
                              <option key={scene} value={scene}>{scene}</option>
                            ))}
                          </select>
                          <ChevronDown className="w-3.5 h-3.5 text-gray-500 absolute right-2.5 top-2.5 pointer-events-none" />
                        </div>
                      ) : (
                        <input
                          type="text"
                          value={localObsSettings?.sceneVictory ?? ''}
                          onChange={(e) => setLocalObsSettings(prev => ({ ...prev, sceneVictory: e.target.value }))}
                          className="w-full bg-[#070a10] border border-gray-700/80 rounded-lg p-2 text-xs font-mono text-white focus:border-purple-500 focus:outline-none"
                          placeholder="SF6 - Victory"
                        />
                      )}
                    </div>
                  </div>

                  {obsScenes.length === 0 && (
                    <p className="text-[10px] text-gray-500 italic mt-1">
                      💡 Tip: Click "Test OBS Connection" to connect to OBS and automatically select from your live scenes.
                    </p>
                  )}
                </div>

                <div className="pt-2">
                  <button
                    type="button"
                    onClick={handleTestAndFetch}
                    disabled={isObsConnecting}
                    className="px-4 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-purple-300 border border-purple-500/30 text-xs font-bold flex items-center gap-2 transition disabled:opacity-50"
                  >
                    {isObsConnected ? <Unlink className="w-3.5 h-3.5" /> : <Link2 className="w-3.5 h-3.5" />}
                    <span>{isObsConnected ? 'Disconnect from OBS' : 'Test OBS Connection'}</span>
                  </button>
                </div>
              </div>
            )}

            {/* TAB 3: AITOB PLATFORM */}
            {activeTab === 'AITOB' && (
              <div className="space-y-4 animate-fadeIn">
                <div>
                  <h3 className="font-bold text-white text-base">aiTOB Platform Hub</h3>
                  <p className="text-xs text-gray-400">Sync match brackets, players, and auto-submit certified results.</p>
                </div>

                <div>
                  <label className="block text-gray-300 text-xs font-semibold mb-1">Platform Server (API URL)</label>
                  <input
                    type="text"
                    value={localAitobSettings?.serverUrl ?? ''}
                    onChange={(e) => setLocalAitobSettings(prev => ({ ...prev, serverUrl: e.target.value }))}
                    className="w-full bg-[#070a10] border border-gray-700/80 rounded-lg p-2 text-xs font-mono text-white focus:border-cyan-500 focus:outline-none"
                    placeholder="http://localhost:8000"
                  />
                </div>

                <div>
                  <label className="block text-gray-300 text-xs font-semibold mb-1">Station ID</label>
                  <input
                    type="text"
                    value={localAitobSettings?.stationId ?? ''}
                    onChange={(e) => setLocalAitobSettings(prev => ({ ...prev, stationId: e.target.value }))}
                    className="w-full bg-[#070a10] border border-gray-700/80 rounded-lg p-2 text-xs font-mono text-white focus:border-cyan-500 focus:outline-none"
                    placeholder="station-01"
                  />
                </div>

                <div>
                  <label className="block text-gray-300 text-xs font-semibold mb-1 flex items-center gap-1.5">
                    <KeyRound className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Pairing Token / OBS Link</span>
                  </label>
                  <input
                    type="text"
                    value={localAitobSettings?.pairingToken ?? ''}
                    onChange={(e) => setLocalAitobSettings(prev => ({ ...prev, pairingToken: e.target.value }))}
                    className="w-full bg-[#070a10] border border-gray-700/80 rounded-lg p-2 text-xs font-mono text-white focus:border-cyan-500 focus:outline-none"
                    placeholder="Paste Token or OBS Link from Hub"
                  />
                  <p className="text-[11px] text-gray-400 mt-1">
                    Paste the Station Token or OBS Link copied from the Station Card in the Admin Hub.
                  </p>
                </div>

                <div className="p-3 rounded-xl bg-gray-900/60 border border-gray-800 text-xs space-y-1">
                  <div className="flex justify-between items-center">
                    <span className="text-gray-400">Active Set ID:</span>
                    <span className="font-mono text-cyan-400 font-bold">{localAitobSettings?.activeSetId || 'None'}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-400">Sync Status:</span>
                    <span className={localAitobSettings?.connected ? 'text-emerald-400 font-bold' : 'text-amber-400'}>
                      {localAitobSettings?.connected ? 'Connected' : 'Offline / Local Mode'}
                    </span>
                  </div>
                </div>

                <div className="pt-2">
                  <button
                    type="button"
                    onClick={onSyncAitob}
                    className="px-4 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-cyan-300 border border-cyan-500/30 text-xs font-bold flex items-center gap-1.5 transition"
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                    <span>Sync With Server</span>
                  </button>
                </div>
              </div>
            )}

          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-gray-800 bg-[#090d14] flex items-center justify-between">
          <div className="text-xs text-gray-400">
            {savedMessage && (
              <span className="text-emerald-400 flex items-center gap-1.5 font-semibold">
                <CheckCircle2 className="w-4 h-4" /> Settings Saved!
              </span>
            )}
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-1.5 rounded-lg text-xs font-semibold text-gray-400 hover:text-white hover:bg-gray-800 transition"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSaveAll}
              className="px-5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold flex items-center gap-1.5 shadow-lg shadow-indigo-600/30 transition"
            >
              <Save className="w-3.5 h-3.5" />
              Save & Apply
            </button>
          </div>
        </div>

      </div>
    </div>
  );
};
