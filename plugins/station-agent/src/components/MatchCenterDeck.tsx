import React from 'react';
import { MatchStateEnum } from '../types/telemetry';
import { Swords, Trophy, Clock } from 'lucide-react';

interface MatchCenterDeckProps {
  matchState: MatchStateEnum;
  roundTimer: number;
  roundNumber: number;
  matchTitle: string;
  bestOf: number;
  onResetSet: () => void;
  onChangeBestOf: (bestOf: number) => void;
}

export const MatchCenterDeck: React.FC<MatchCenterDeckProps> = ({
  matchState,
  roundTimer,
  roundNumber,
  matchTitle,
  bestOf,
  onResetSet,
  onChangeBestOf,
}) => {
  const getStatusBadge = () => {
    switch (matchState) {
      case 'FIGHTING':
        return (
          <span className="px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 text-xs font-bold uppercase tracking-wider animate-pulse flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            Live
          </span>
        );
      case 'ROUND_OVER':
        return (
          <span className="px-3 py-1 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/40 text-xs font-bold uppercase tracking-wider">
            Round Over
          </span>
        );
      case 'MATCH_OVER':
        return (
          <span className="px-3 py-1 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/40 text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 shadow-[0_0_15px_rgba(168,85,247,0.5)]">
            <Trophy className="w-3.5 h-3.5 text-yellow-400" />
            Match Over (K.O.)
          </span>
        );
      case 'CHARACTER_SELECT':
        return (
          <span className="px-3 py-1 rounded-full bg-blue-500/20 text-cyan-400 border border-cyan-500/40 text-xs font-bold uppercase tracking-wider">
            Character Select
          </span>
        );
      default:
        return (
          <span className="px-3 py-1 rounded-full bg-slate-800 text-slate-400 border border-slate-700 text-xs font-bold uppercase tracking-wider">
            Waiting to Start
          </span>
        );
    }
  };

  return (
    <div className="flex flex-col items-center justify-center px-4">
      {/* Set Title & Format */}
      <div className="text-center mb-2">
        <h2 className="text-sm font-bold text-slate-300 tracking-wide mb-1">
          {matchTitle}
        </h2>
        <div className="flex items-center justify-center gap-1">
          {[2, 3, 5, 7].map(ft => (
            <button
              key={ft}
              onClick={() => onChangeBestOf((ft * 2) - 1)}
              className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono transition-colors border ${Math.ceil(bestOf / 2) === ft ? 'bg-cyan-500/20 text-cyan-400 border-cyan-500/40 shadow-[0_0_10px_rgba(34,211,238,0.2)]' : 'bg-slate-800/50 text-slate-500 border-slate-700/50 hover:bg-slate-800 hover:text-slate-300'}`}
            >
              FT{ft}
            </button>
          ))}
        </div>
      </div>

      {/* VS Emblem & Timer */}
      <div className="relative flex flex-col items-center my-2">
        {/* Glow behind timer */}
        <div className="absolute w-24 h-24 bg-blue-500/10 rounded-full blur-2xl pointer-events-none" />

        {/* Round Timer Dial */}
        <div className="w-20 h-20 rounded-2xl bg-[#090d16] border-2 border-slate-700/80 shadow-2xl flex flex-col items-center justify-center p-2 relative group hover:border-cyan-500/50 transition-colors">
          <span className="text-[10px] font-mono text-slate-400 uppercase tracking-widest flex items-center gap-0.5">
            <Clock className="w-2.5 h-2.5" />
            Time
          </span>
          <span className="font-rajdhani font-black text-3xl text-white tracking-wider">
            {roundTimer <= 0 ? 'K.O.' : roundTimer}
          </span>
          <span className="text-[9px] font-bold text-slate-400 uppercase tracking-wider">
            Round {roundNumber}
          </span>
        </div>

        {/* VS Badge */}
        <div className="mt-2 flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-slate-800/80 border border-slate-700 font-rajdhani font-black text-xs text-slate-300">
          <Swords className="w-3 h-3 text-cyan-400" />
          <span>V S</span>
        </div>
      </div>

      {/* Current Match State */}
      <div className="mt-2">
        {getStatusBadge()}
      </div>

      <button
        onClick={onResetSet}
        className="mt-4 px-3 py-1 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 text-rose-400 rounded text-[10px] font-bold uppercase tracking-wider transition-colors flex items-center gap-1"
        title="Reset Set Scores to 0"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>
        Reset Set
      </button>
    </div>
  );
};
