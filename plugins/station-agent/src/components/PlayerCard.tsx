import React from 'react';
import { PlayerState } from '../types/telemetry';
import { Shield, Zap, Plus, Minus, UserCheck } from 'lucide-react';

interface PlayerCardProps {
  playerNumber: 1 | 2;
  player: PlayerState;
  onScoreChange: (newScore: number) => void;
  onNameChange: (newName: string) => void;
  bestOf: number;
}

export const PlayerCard: React.FC<PlayerCardProps> = ({
  playerNumber,
  player,
  onScoreChange,
  onNameChange,
  bestOf,
}) => {
  const isP1 = playerNumber === 1;
  const hpPercentage = Math.max(0, Math.min(100, (player.currentHp / (player.maxHp || 10000)) * 100));

  // Determine health color threshold
  let hpColorClass = isP1 
    ? 'bg-gradient-to-r from-cyan-500 to-blue-600 shadow-[0_0_15px_rgba(6,182,212,0.5)]'
    : 'bg-gradient-to-r from-rose-500 to-red-600 shadow-[0_0_15px_rgba(244,63,94,0.5)]';

  if (hpPercentage < 25) {
    hpColorClass = 'bg-gradient-to-r from-red-600 to-amber-500 animate-pulse shadow-[0_0_20px_rgba(239,68,68,0.8)]';
  } else if (hpPercentage < 50) {
    hpColorClass = 'bg-gradient-to-r from-amber-500 to-orange-500';
  }

  // Drive gauge blocks (6 blocks)
  const driveBars = 6;
  const currentDrive = Math.max(0, Math.min(6, player.driveGauge || 0));
  const isBurnout = player.isBurnout;

  // Rounds needed to win a single game (normally 2)
  const maxGameRounds = 2;

  return (
    <div
      className={`relative rounded-2xl p-5 glass-panel transition-all overflow-hidden ${
        isP1 ? 'glass-panel-glow-cyan' : 'glass-panel-glow-pink'
      }`}
    >
      {/* Background Ambient Glow */}
      <div 
        className={`absolute -top-24 ${isP1 ? '-left-24 bg-cyan-500/10' : '-right-24 bg-rose-500/10'} w-56 h-56 rounded-full blur-3xl pointer-events-none`} 
      />

      {/* Header: Player Tag & Score in Set */}
      <div className={`flex items-center justify-between gap-4 mb-4 ${isP1 ? 'flex-row' : 'flex-row-reverse'}`}>
        <div className={`flex items-center gap-3 ${isP1 ? 'text-right' : 'text-left'}`}>
          <div className="relative">
            <div 
              className={`w-14 h-14 rounded-xl flex flex-col items-center justify-center font-rajdhani font-black text-xl shadow-lg overflow-hidden ${
                isP1 
                  ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/40' 
                  : 'bg-rose-500/20 text-rose-400 border border-rose-500/40'
              }`}
            >
              {player.characterName && !['none', 'unselected', 'unknown', ''].includes(player.characterName.toLowerCase()) ? (
                <img 
                  src={`https://res.cloudinary.com/dvgtmykxp/image/upload/aitob/characters/sf6/${player.characterName.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '')}.png`}
                  alt={player.characterName}
                  className="w-full h-full object-cover bg-slate-900"
                  onError={(e) => {
                    // Fallback to stylized initials if image fails
                    (e.target as HTMLElement).style.display = 'none';
                  }}
                />
              ) : (
                <span className="font-bold text-sm tracking-wider uppercase opacity-70">P{playerNumber}</span>
              )}
              <span className="absolute bottom-0 text-[10px] bg-black/70 w-full text-center tracking-widest backdrop-blur-sm font-bold">P{playerNumber}</span>
            </div>
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <input
                type="text"
                value={player.displayName}
                onChange={(e) => onNameChange(e.target.value)}
                placeholder={isP1 ? 'Player 1' : 'Player 2'}
                className="font-black text-xl bg-transparent border-b border-transparent hover:border-slate-600 focus:border-cyan-400 focus:outline-none transition-colors w-44 tracking-wide text-white"
              />
            </div>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-xs font-semibold px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 font-mono">
                {player.characterName || 'Unselected'}
              </span>
              {player.characterId > 0 && (
                <span className="text-[10px] text-slate-500 font-mono">
                  ID: {player.characterId}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Set Score Stepper */}
        <div className="flex flex-col items-center">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1">
            Set Score
          </span>
          <div className="flex items-center gap-2 bg-[#090d16] p-1.5 rounded-xl border border-slate-800">
            <button
              onClick={() => onScoreChange(Math.max(0, player.scoreInSet - 1))}
              className="w-7 h-7 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 flex items-center justify-center transition"
            >
              <Minus className="w-3.5 h-3.5" />
            </button>
            <span className="font-rajdhani font-black text-2xl px-2 text-white w-7 text-center">
              {player.scoreInSet}
            </span>
            <button
              onClick={() => onScoreChange(player.scoreInSet + 1)}
              className="w-7 h-7 rounded-lg bg-slate-800 hover:bg-slate-700 text-white flex items-center justify-center transition"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Health Bar Section */}
      <div className="mb-4">
        <div className="flex justify-between items-center text-xs mb-1.5 font-mono">
          <span className="font-bold text-slate-300 flex items-center gap-1">
            <span>Health (HP)</span>
            {hpPercentage < 20 && (
              <span className="text-[10px] px-1.5 py-0.2 rounded bg-rose-500/20 text-rose-400 font-bold animate-pulse">
                DANGER
              </span>
            )}
          </span>
          <span className="font-rajdhani font-bold text-sm text-slate-200">
            <span className={hpPercentage < 25 ? 'text-rose-400' : 'text-emerald-400'}>
              {player.currentHp.toLocaleString()}
            </span>
            <span className="text-slate-500"> / {player.maxHp.toLocaleString()}</span>
            <span className="text-slate-400 text-xs ml-1 font-mono">({hpPercentage.toFixed(1)}%)</span>
          </span>
        </div>

        {/* Outer Bar Frame */}
        <div className="h-6 w-full bg-[#06080d] rounded-lg p-0.5 border border-slate-800 overflow-hidden relative shadow-inner mb-2">
          <div
            className={`h-full rounded-md hp-bar-fill ${hpColorClass} ${isP1 ? '' : 'ml-auto'}`}
            style={{ width: `${hpPercentage}%` }}
          />
        </div>

        {/* Max Combo & Damage Tags */}
        <div className={`flex items-center gap-3 text-[11px] font-mono ${isP1 ? 'justify-start' : 'justify-end'}`}>
          <span className="bg-slate-800/80 text-slate-300 border border-slate-700/50 px-2 py-0.5 rounded shadow-sm">
            Max Combo: <span className="font-bold text-white">{player.maxCombo || 0}</span>
          </span>
          <span className="bg-slate-800/80 text-slate-300 border border-slate-700/50 px-2 py-0.5 rounded shadow-sm">
            Max DMG: <span className="font-bold text-white">{player.maxDamage || 0}</span>
          </span>
        </div>
      </div>

      {/* Drive Gauge (SF6 Specific Mechanic - 6 bars) */}
      <div className="mb-4">
        <div className="flex justify-between items-center text-[11px] mb-1 font-mono">
          <span className="text-slate-400 flex items-center gap-1">
            <Shield className="w-3 h-3 text-emerald-400" />
            <span>Drive Gauge</span>
          </span>
          {isBurnout ? (
            <span className="text-slate-500 font-bold animate-pulse text-[10px]">
              BURNOUT! (RECOVERING)
            </span>
          ) : (
            <span className="text-slate-300 font-rajdhani font-bold">
              {currentDrive.toFixed(1)} / 6.0
            </span>
          )}
        </div>
        <div className="grid grid-cols-6 gap-1 h-2.5">
          {Array.from({ length: driveBars }).map((_, idx) => {
            const isFilled = currentDrive >= idx + 1;
            const isPartial = currentDrive > idx && currentDrive < idx + 1;
            return (
              <div 
                key={idx} 
                className="bg-[#06080d] rounded-sm overflow-hidden border border-slate-800 h-full relative"
              >
                <div 
                  className={`h-full transition-all ${
                    isBurnout 
                      ? 'bg-slate-500/40 shadow-[0_0_5px_rgba(100,116,139,0.3)]' 
                      : isFilled 
                        ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.5)]' 
                        : isPartial 
                          ? 'bg-emerald-500/60' 
                          : 'bg-transparent'
                  }`}
                  style={{ width: isFilled ? '100%' : isPartial ? `${(currentDrive - idx) * 100}%` : '0%' }}
                />
              </div>
            );
          })}
        </div>
      </div>

      {/* Sub-Footer: Super Art & Round Win Dots */}
      <div className="flex items-center justify-between pt-2 border-t border-slate-800/80 text-xs">
        {/* Super Art Gauge */}
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-slate-400 flex items-center gap-1">
            <Zap className="w-3.5 h-3.5 text-amber-400" />
            <span>Super Art:</span>
          </span>
          <div className="flex items-center gap-1">
            {[1, 2, 3].map((lvl) => (
              <span
                key={lvl}
                className={`w-5 h-5 rounded flex items-center justify-center font-rajdhani font-bold text-xs ${
                  (player.superArt || 0) >= lvl
                    ? 'bg-gradient-to-tr from-amber-500 to-yellow-300 text-black shadow-[0_0_10px_rgba(245,158,11,0.6)]'
                    : 'bg-slate-800 text-slate-500 border border-slate-700'
                }`}
              >
                {lvl}
              </span>
            ))}
          </div>
        </div>

        {/* Round Win Dots */}
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-slate-400">Match Rounds:</span>
          <div className="flex items-center gap-1.5">
            {Array.from({ length: maxGameRounds }).map((_, idx) => {
              const won = (player.roundsWon || 0) > idx;
              return (
                <div
                  key={idx}
                  className={`w-3.5 h-3.5 rounded-full border transition-all ${
                    won
                      ? isP1
                        ? 'bg-cyan-400 border-cyan-300 shadow-[0_0_10px_rgba(6,182,212,0.8)]'
                        : 'bg-rose-500 border-rose-300 shadow-[0_0_10px_rgba(244,63,94,0.8)]'
                      : 'bg-slate-900 border-slate-700'
                  }`}
                  title={won ? 'Round Won' : 'Undecided'}
                />
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
