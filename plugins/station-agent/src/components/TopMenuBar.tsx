import React, { useRef, useState } from 'react';
import { 
  Menu, FileJson, Settings2, ShieldCheck, Gamepad2, XCircle, 
  LayoutGrid, Eye, EyeOff, Download, Upload, HelpCircle, 
  MonitorPlay, Save, Check, LogOut, SlidersHorizontal, Info, Minimize2, Maximize2
} from 'lucide-react';
import { TriggerRule } from '../services/automationEngine';
import { ObsSettings } from '../services/obsService';
import { AitobSettings } from '../services/aitobBridge';

interface TopMenuBarProps {
  onOpenSettings: (tab?: 'GAME' | 'OBS' | 'AITOB') => void;
  rules: TriggerRule[];
  setRules: React.Dispatch<React.SetStateAction<TriggerRule[]>>;
  obsSettings: ObsSettings;
  setObsSettings: React.Dispatch<React.SetStateAction<ObsSettings>>;
  aitobSettings: AitobSettings;
  setAitobSettings: React.Dispatch<React.SetStateAction<AitobSettings>>;
  gameConnectionConfig: any;
  setGameConnectionConfig: React.Dispatch<React.SetStateAction<any>>;
  onClearLogs: () => void;
  onResetMatch: () => void;
  showLogs: boolean;
  onToggleLogs: () => void;
  compactMode: boolean;
  onToggleCompactMode: () => void;
  onOpenHelp: () => void;
}

export const TopMenuBar: React.FC<TopMenuBarProps> = ({
  onOpenSettings,
  rules, setRules,
  obsSettings, setObsSettings,
  aitobSettings, setAitobSettings,
  gameConnectionConfig, setGameConnectionConfig,
  onClearLogs, onResetMatch,
  showLogs, onToggleLogs,
  compactMode, onToggleCompactMode,
  onOpenHelp
}) => {
  const [activeMenu, setActiveMenu] = useState<'FILE' | 'EDIT' | 'VIEW' | 'HELP' | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const toggleMenu = (menu: 'FILE' | 'EDIT' | 'VIEW' | 'HELP') => {
    setActiveMenu(prev => prev === menu ? null : menu);
  };

  const handleExportProfile = () => {
    const profile = {
      rules,
      obsSettings,
      aitobSettings,
      gameConnectionConfig
    };
    
    const blob = new Blob([JSON.stringify(profile, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = `station_agent_profile_${new Date().getTime()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    setActiveMenu(null);
  };

  const handleImportProfile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const content = event.target?.result as string;
        const profile = JSON.parse(content);
        
        if (profile.rules) setRules(profile.rules);
        if (profile.obsSettings) setObsSettings(profile.obsSettings);
        if (profile.aitobSettings) setAitobSettings(profile.aitobSettings);
        if (profile.gameConnectionConfig) setGameConnectionConfig(profile.gameConnectionConfig);
        
        alert('Profile imported successfully!');
      } catch (err) {
        alert('Failed to parse profile JSON. Make sure the file is valid.');
      }
    };
    reader.readAsText(file);
    setActiveMenu(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleExitApp = () => {
    if (typeof window !== 'undefined' && (window as any).electron?.ipcRenderer) {
      (window as any).electron.ipcRenderer.send('app:quit');
    } else {
      window.close();
    }
  };

  const closeMenu = () => setActiveMenu(null);

  return (
    <div className="bg-[#080b12] border-b border-gray-800 text-gray-300 text-xs flex items-center px-4 relative z-50 h-9 shadow-md select-none">
      <div className="flex items-center gap-2 pr-5 border-r border-gray-800 py-1">
        <MonitorPlay className="w-4 h-4 text-cyan-400" />
        <span className="font-rajdhani font-bold text-white tracking-widest uppercase text-xs">Station Agent</span>
      </div>

      <div className="flex px-1 h-full" onMouseLeave={closeMenu}>
        
        {/* FILE MENU */}
        <div className="relative h-full flex items-center">
          <button 
            className={`px-3 h-full flex items-center hover:bg-gray-800/80 transition rounded-none ${activeMenu === 'FILE' ? 'bg-gray-800 text-white' : ''}`}
            onClick={() => toggleMenu('FILE')}
            onMouseEnter={() => activeMenu && setActiveMenu('FILE')}
          >
            File
          </button>
          
          {activeMenu === 'FILE' && (
            <div className="absolute left-0 top-full mt-0 w-64 bg-[#0d111a] border border-gray-700/80 shadow-2xl rounded-b-lg py-1.5 z-50">
              <button 
                onClick={() => { onOpenSettings(); closeMenu(); }} 
                className="w-full text-left px-3.5 py-1.5 hover:bg-gray-800 flex items-center justify-between text-xs text-gray-200"
              >
                <div className="flex items-center gap-2.5">
                  <SlidersHorizontal className="w-3.5 h-3.5 text-indigo-400" /> 
                  <span>Settings & Preferences...</span>
                </div>
                <span className="text-[10px] text-gray-500 font-mono">Ctrl+,</span>
              </button>

              <div className="h-px bg-gray-800 my-1 mx-2" />

              <button 
                onClick={() => { fileInputRef.current?.click(); closeMenu(); }} 
                className="w-full text-left px-3.5 py-1.5 hover:bg-gray-800 flex items-center gap-2.5 text-xs text-gray-200"
              >
                <Upload className="w-3.5 h-3.5 text-emerald-400" /> 
                <span>Import Profile...</span>
              </button>
              
              <button 
                onClick={handleExportProfile} 
                className="w-full text-left px-3.5 py-1.5 hover:bg-gray-800 flex items-center gap-2.5 text-xs text-gray-200"
              >
                <Download className="w-3.5 h-3.5 text-cyan-400" /> 
                <span>Export Profile...</span>
              </button>
              
              <div className="h-px bg-gray-800 my-1 mx-2" />
              
              <button 
                onClick={handleExitApp} 
                className="w-full text-left px-3.5 py-1.5 hover:bg-rose-950/40 text-rose-300 flex items-center gap-2.5 text-xs"
              >
                <LogOut className="w-3.5 h-3.5 text-rose-400" /> 
                <span>Exit Application</span>
              </button>
            </div>
          )}
        </div>

        {/* EDIT MENU */}
        <div className="relative h-full flex items-center">
          <button 
            className={`px-3 h-full flex items-center hover:bg-gray-800/80 transition rounded-none ${activeMenu === 'EDIT' ? 'bg-gray-800 text-white' : ''}`}
            onClick={() => toggleMenu('EDIT')}
            onMouseEnter={() => activeMenu && setActiveMenu('EDIT')}
          >
            Edit
          </button>
          
          {activeMenu === 'EDIT' && (
            <div className="absolute left-0 top-full mt-0 w-56 bg-[#0d111a] border border-gray-700/80 shadow-2xl rounded-b-lg py-1.5 z-50">
              <button 
                onClick={() => { onResetMatch(); closeMenu(); }} 
                className="w-full text-left px-3.5 py-1.5 hover:bg-gray-800 flex items-center gap-2.5 text-rose-400 text-xs"
              >
                <XCircle className="w-3.5 h-3.5" /> 
                <span>Reset Match State</span>
              </button>
              <button 
                onClick={() => { onClearLogs(); closeMenu(); }} 
                className="w-full text-left px-3.5 py-1.5 hover:bg-gray-800 flex items-center gap-2.5 text-xs text-gray-200"
              >
                <FileJson className="w-3.5 h-3.5 text-amber-400" /> 
                <span>Clear Event Logs</span>
              </button>
            </div>
          )}
        </div>

        {/* VIEW MENU */}
        <div className="relative h-full flex items-center">
          <button 
            className={`px-3 h-full flex items-center hover:bg-gray-800/80 transition rounded-none ${activeMenu === 'VIEW' ? 'bg-gray-800 text-white' : ''}`}
            onClick={() => toggleMenu('VIEW')}
            onMouseEnter={() => activeMenu && setActiveMenu('VIEW')}
          >
            View
          </button>
          
          {activeMenu === 'VIEW' && (
            <div className="absolute left-0 top-full mt-0 w-60 bg-[#0d111a] border border-gray-700/80 shadow-2xl rounded-b-lg py-1.5 z-50">
              <button 
                onClick={() => { onToggleLogs(); closeMenu(); }} 
                className="w-full text-left px-3.5 py-1.5 hover:bg-gray-800 flex items-center justify-between text-xs text-gray-200"
              >
                <div className="flex items-center gap-2.5">
                  {showLogs ? <Eye className="w-3.5 h-3.5 text-cyan-400" /> : <EyeOff className="w-3.5 h-3.5 text-gray-500" />}
                  <span>Telemetry Event Logs</span>
                </div>
                {showLogs && <Check className="w-3.5 h-3.5 text-cyan-400" />}
              </button>

              <button 
                onClick={() => { onToggleCompactMode(); closeMenu(); }} 
                className="w-full text-left px-3.5 py-1.5 hover:bg-gray-800 flex items-center justify-between text-xs text-gray-200"
              >
                <div className="flex items-center gap-2.5">
                  {compactMode ? <Minimize2 className="w-3.5 h-3.5 text-indigo-400" /> : <Maximize2 className="w-3.5 h-3.5 text-gray-500" />}
                  <span>Compact Layout Mode</span>
                </div>
                {compactMode && <Check className="w-3.5 h-3.5 text-indigo-400" />}
              </button>
            </div>
          )}
        </div>

        {/* HELP MENU */}
        <div className="relative h-full flex items-center">
          <button 
            className={`px-3 h-full flex items-center hover:bg-gray-800/80 transition rounded-none ${activeMenu === 'HELP' ? 'bg-gray-800 text-white' : ''}`}
            onClick={() => toggleMenu('HELP')}
            onMouseEnter={() => activeMenu && setActiveMenu('HELP')}
          >
            Help
          </button>
          
          {activeMenu === 'HELP' && (
            <div className="absolute left-0 top-full mt-0 w-60 bg-[#0d111a] border border-gray-700/80 shadow-2xl rounded-b-lg py-1.5 z-50">
              <button 
                onClick={() => { onOpenHelp(); closeMenu(); }} 
                className="w-full text-left px-3.5 py-1.5 hover:bg-gray-800 flex items-center gap-2.5 text-xs text-cyan-300"
              >
                <HelpCircle className="w-3.5 h-3.5 text-cyan-400" /> 
                <span>Quick Setup Guide...</span>
              </button>
              
              <div className="h-px bg-gray-800 my-1 mx-2" />

              <a 
                href="https://aitob.bashtech.xyz/terms" 
                target="_blank" 
                rel="noopener noreferrer"
                onClick={closeMenu}
                className="w-full text-left px-3.5 py-1.5 hover:bg-gray-800 flex items-center justify-between text-xs text-gray-300 transition-colors"
              >
                <span>Terms of Service & EULA</span>
                <span className="text-[10px] text-gray-500">↗</span>
              </a>

              <a 
                href="https://aitob.bashtech.xyz/privacy" 
                target="_blank" 
                rel="noopener noreferrer"
                onClick={closeMenu}
                className="w-full text-left px-3.5 py-1.5 hover:bg-gray-800 flex items-center justify-between text-xs text-gray-300 transition-colors"
              >
                <span>Privacy Policy</span>
                <span className="text-[10px] text-gray-500">↗</span>
              </a>

              <div className="h-px bg-gray-800 my-1 mx-2" />

              <div className="px-3.5 py-2 text-[11px] text-gray-400 leading-normal">
                <span className="font-semibold text-gray-200 block">aiTOB Station Agent</span>
                Version 1.0.0
                <span className="block text-[10px] text-gray-500 mt-0.5">Automated Broadcast & Match Engine</span>
              </div>
            </div>
          )}
        </div>

      </div>
      
      <input type="file" ref={fileInputRef} className="hidden" accept=".json" onChange={handleImportProfile} />
    </div>
  );
};
