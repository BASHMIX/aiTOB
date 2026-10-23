import React from 'react';
import { 
  Gamepad2, 
  Video, 
  Globe2, 
  Settings, 
  Radio, 
  PlayCircle,
  SlidersHorizontal 
} from 'lucide-react';

interface NavbarProps {
  stationId: string;
  isGameConnected: boolean;
  gamePacketCount: number;
  gamePort?: number;
  gameMethod?: 'udp' | 'json';
  isObsConnected: boolean;
  obsPort?: number;
  isAitobConnected: boolean;
  onOpenGameSettings: () => void;
  onOpenObsSettings: () => void;
  onOpenAitobSettings: () => void;
  onSimulateFight: () => void;
  onSimulateFinish: () => void;
  compactMode?: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  stationId,
  isGameConnected,
  gamePacketCount,
  gamePort = 8080,
  gameMethod = 'json',
  isObsConnected,
  obsPort = 4455,
  isAitobConnected,
  onOpenGameSettings,
  onOpenObsSettings,
  onOpenAitobSettings,
  onSimulateFight,
  onSimulateFinish,
  compactMode = false,
}) => {
  // COMPACT MODE NAVBAR
  if (compactMode) {
    return (
      <header className="h-11 px-4 glass-panel border-b border-slate-800/80 flex items-center justify-between sticky top-9 z-40 bg-[#080b12]/95 backdrop-blur-md">
        {/* Brand & Station */}
        <div className="flex items-center gap-2">
          <Radio className="w-4 h-4 text-cyan-400" />
          <span className="font-extrabold text-xs tracking-wider text-white font-rajdhani uppercase">
            Station: <span className="text-cyan-400 font-mono">{stationId}</span>
          </span>
          <span className="text-[10px] px-1.5 py-0.2 rounded bg-blue-500/10 text-cyan-400 border border-cyan-500/20 font-semibold uppercase">
            SF6
          </span>
        </div>

        {/* Compact Status Pills (Game, OBS, Platform) */}
        <div className="flex items-center gap-1.5">
          {/* Game Telemetry Mini Pill with actual Port/Method */}
          <button
            onClick={onOpenGameSettings}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-[11px] font-mono transition hover:opacity-90 ${
              isGameConnected 
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' 
                : 'bg-rose-500/10 text-rose-400 border-rose-500/30'
            }`}
            title={`SF6 Telemetry (${gameMethod === 'json' ? 'JSON File Mode' : `UDP Port ${gamePort}`}) - Click to configure`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${isGameConnected ? 'bg-emerald-400 animate-ping' : 'bg-rose-500'}`} />
            <Gamepad2 className="w-3.5 h-3.5" />
            <span className="font-bold">
              {isGameConnected 
                ? `Game: On (${gameMethod === 'json' ? 'JSON' : `:${gamePort}`})` 
                : `Game: Off (${gameMethod === 'json' ? 'JSON' : `:${gamePort}`})`}
            </span>
          </button>

          {/* OBS Studio Mini Pill with actual Port */}
          <button
            onClick={onOpenObsSettings}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-[11px] font-mono transition hover:bg-slate-800 ${
              isObsConnected 
                ? 'bg-purple-500/10 text-purple-400 border-purple-500/30' 
                : 'bg-slate-800/80 text-slate-400 border-slate-700'
            }`}
            title={`OBS WebSocket (Port ${obsPort}) - Click to configure`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${isObsConnected ? 'bg-purple-400' : 'bg-slate-500'}`} />
            <Video className="w-3.5 h-3.5" />
            <span className="font-bold">{isObsConnected ? `OBS: :${obsPort}` : 'OBS: Off'}</span>
          </button>

          {/* aiTOB Platform Mini Pill */}
          <button
            onClick={onOpenAitobSettings}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-[11px] font-mono transition hover:bg-slate-800 ${
              isAitobConnected 
                ? 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30' 
                : 'bg-amber-500/10 text-amber-400 border-amber-500/30'
            }`}
            title="aiTOB Platform Hub (Click to configure)"
          >
            <span className={`w-1.5 h-1.5 rounded-full ${isAitobConnected ? 'bg-cyan-400' : 'bg-amber-500'}`} />
            <Globe2 className="w-3.5 h-3.5" />
            <span className="font-bold">{isAitobConnected ? 'aiTOB: Sync' : 'aiTOB: Local'}</span>
          </button>
        </div>

        {/* Note: Simulation buttons are completely hidden in Compact Mode! */}
      </header>
    );
  }

  // STANDARD FULL NAVBAR
  return (
    <header className="h-16 px-6 glass-panel border-b border-slate-800/80 flex items-center justify-between sticky top-9 z-40 bg-[#0a0d14]/90 backdrop-blur-md">
      {/* Brand & Station Identifier */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-cyan-400 p-[2px] shadow-lg shadow-blue-500/20">
          <div className="w-full h-full bg-[#0a0d14] rounded-[10px] flex items-center justify-center">
            <Radio className="w-5 h-5 text-cyan-400 animate-pulse" />
          </div>
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-extrabold text-base tracking-wide bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
              aiTOB Station Agent
            </h1>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-500/10 text-cyan-400 border border-cyan-500/30 font-semibold uppercase tracking-wider">
              Street Fighter 6
            </span>
          </div>
          <p className="text-xs text-slate-400 flex items-center gap-1.5 font-mono">
            <span>Station:</span>
            <span className="text-white font-bold">{stationId}</span>
          </p>
        </div>
      </div>

      {/* Connectivity Status Badges */}
      <div className="flex items-center gap-2">
        {/* Game Telemetry Badge with Dynamic Port/Method */}
        <button 
          onClick={onOpenGameSettings}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs transition-all hover:bg-opacity-80 ${
            isGameConnected 
              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' 
              : 'bg-rose-500/10 text-rose-400 border-rose-500/30'
          }`}
          title="Click to configure Game Connection Settings"
        >
          <Gamepad2 className="w-4 h-4" />
          <div className="flex flex-col text-right">
            <span className="font-bold leading-none">
              {isGameConnected ? 'Game Connected' : 'Waiting for Game...'}
            </span>
            <span className="text-[10px] font-mono text-slate-400 leading-none mt-0.5">
              {gameMethod === 'json' ? 'JSON Mode' : `UDP ${gamePort}`} {isGameConnected ? `(${gamePacketCount} pkts)` : ''}
            </span>
          </div>
          <span className={`w-2 h-2 rounded-full ${isGameConnected ? 'bg-emerald-400 animate-ping' : 'bg-rose-500'}`} />
        </button>

        {/* OBS Studio WebSocket with Dynamic Port */}
        <button
          onClick={onOpenObsSettings}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs transition-all hover:bg-slate-800 ${
            isObsConnected 
              ? 'bg-purple-500/10 text-purple-400 border-purple-500/30' 
              : 'bg-slate-800/60 text-slate-400 border-slate-700'
          }`}
          title={`OBS Studio WebSocket (${obsPort})`}
        >
          <Video className="w-4 h-4" />
          <div className="flex flex-col text-right">
            <span className="font-bold leading-none">
              {isObsConnected ? 'OBS Connected' : 'OBS Disconnected'}
            </span>
            <span className="text-[10px] font-mono text-slate-400 leading-none mt-0.5">
              Port {obsPort}
            </span>
          </div>
          <SlidersHorizontal className="w-3 h-3 text-slate-500 hover:text-white" />
        </button>

        {/* aiTOB Platform Bridge */}
        <button
          onClick={onOpenAitobSettings}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs transition-all hover:bg-slate-800 ${
            isAitobConnected 
              ? 'bg-blue-500/10 text-cyan-400 border-cyan-500/30' 
              : 'bg-amber-500/10 text-amber-400 border-amber-500/30'
          }`}
          title="aiTOB Platform Hub"
        >
          <Globe2 className="w-4 h-4" />
          <div className="flex flex-col text-right">
            <span className="font-bold leading-none">
              {isAitobConnected ? 'aiTOB Connected' : 'Standalone Mode'}
            </span>
            <span className="text-[10px] font-mono text-slate-400 leading-none mt-0.5">
              Live Sync
            </span>
          </div>
          <Settings className="w-3 h-3 text-slate-500 hover:text-white" />
        </button>
      </div>

      {/* Simulator Test Tools (Visible in standard mode) */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-slate-500 hidden md:inline">Simulation:</span>
        <button
          onClick={onSimulateFight}
          className="px-2.5 py-1 text-xs rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 flex items-center gap-1.5 transition-colors"
          title="Simulate Hit Exchange"
        >
          <PlayCircle className="w-3.5 h-3.5 text-cyan-400" />
          <span>Simulate Hits</span>
        </button>
        <button
          onClick={onSimulateFinish}
          className="px-2.5 py-1 text-xs rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 flex items-center gap-1.5 transition-colors"
          title="Simulate Round End (K.O.)"
        >
          <PlayCircle className="w-3.5 h-3.5 text-rose-400" />
          <span>Final K.O.</span>
        </button>
      </div>
    </header>
  );
};
