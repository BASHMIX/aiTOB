import React from 'react';
import { MatchStateEnum } from '../types/telemetry';

interface Props {
  roomId?: string;
  matchState: MatchStateEnum;
  p1GameWins: number;
  p2GameWins: number;
}

export const RoomContext: React.FC<Props> = ({ roomId, matchState, p1GameWins, p2GameWins }) => {
  const getStatusColor = (state: MatchStateEnum) => {
    switch (state) {
      case 'FIGHTING': return 'text-red-400';
      case 'CUSTOM_ROOM_LOBBY': return 'text-violet-400';
      case 'CHARACTER_SELECT': 
      case 'CHARACTER_SELECT_OR_MENU': return 'text-blue-400';
      case 'MATCH_RESULTS': return 'text-green-400';
      default: return 'text-gray-400';
    }
  };

  return (
    <div className="glass-panel p-3 rounded-xl mb-4 border border-sf-border shadow-lg flex justify-between items-center">
      <div className="flex flex-col">
        <span className="text-[10px] uppercase text-gray-500 font-bold tracking-widest">Network Room</span>
        <div className="flex items-center gap-2">
          {roomId ? (
            <>
              <span className="w-2 h-2 rounded-full bg-violet-400 animate-pulse shadow-[0_0_8px_rgba(167,139,250,0.8)]"></span>
              <span className="text-sm font-bold text-violet-300 drop-shadow-[0_0_5px_rgba(167,139,250,0.5)]">Custom Room</span>
            </>
          ) : (
            <>
              <span className="w-2 h-2 rounded-full bg-gray-600"></span>
              <span className="text-sm text-gray-500 italic">Not in a Custom Room</span>
            </>
          )}
        </div>
      </div>

      <div className="flex flex-col items-center border-x border-gray-700/50 px-8">
        <span className="text-[10px] uppercase text-gray-500 font-bold tracking-widest">Match State</span>
        <span className={`text-sm font-bold tracking-wider ${getStatusColor(matchState)}`}>
          {matchState.replace(/_/g, ' ')}
        </span>
      </div>

      <div className="flex flex-col text-right">
        <span className="text-[10px] uppercase text-gray-500 font-bold tracking-widest">Game Win Streak</span>
        <div className="flex items-center justify-end gap-3 text-sm">
          <span className="text-sf-p1">P1: {p1GameWins}</span>
          <span className="text-gray-600">|</span>
          <span className="text-sf-p2">P2: {p2GameWins}</span>
        </div>
      </div>
    </div>
  );
};
