import React, { useState } from 'react';
import { TelemetryLogEntry } from '../types/telemetry';
import { Terminal, ChevronUp, ChevronDown, Trash2 } from 'lucide-react';

interface TelemetryConsoleProps {
  logs: TelemetryLogEntry[];
  onClear: () => void;
  lastRawPacket: any;
}

export const TelemetryConsole: React.FC<TelemetryConsoleProps> = ({
  logs,
  onClear,
  lastRawPacket,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState<'LOGS' | 'RAW'>('LOGS');

  return (
    <div className="mx-6 mb-4 glass-panel rounded-2xl border border-slate-800/80 overflow-hidden transition-all text-xs">
      {/* Console Header Bar */}
      <div 
        onClick={() => setIsExpanded(!isExpanded)}
        className="px-4 py-2.5 bg-[#090d16] flex items-center justify-between cursor-pointer hover:bg-slate-900/90 transition"
      >
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-cyan-400" />
          <span className="font-bold text-slate-200">Live Telemetry & Event Log</span>
          <span className="text-[10px] px-2 py-0.2 rounded-full bg-slate-800 text-slate-400 font-mono">
            {logs.length} events
          </span>
        </div>

        <div className="flex items-center gap-3">
          {isExpanded ? (
            <ChevronDown className="w-4 h-4 text-slate-400" />
          ) : (
            <ChevronUp className="w-4 h-4 text-slate-400" />
          )}
        </div>
      </div>

      {/* Expandable Body */}
      {isExpanded && (
        <div className="p-4 bg-[#06080d]/90 border-t border-slate-800 animate-fadeIn">
          {/* Sub Header / Tabs */}
          <div className="flex items-center justify-between mb-3 border-b border-slate-800 pb-2">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setActiveTab('LOGS')}
                className={`px-3 py-1 rounded-lg font-semibold transition ${
                  activeTab === 'LOGS'
                    ? 'bg-slate-800 text-cyan-400 border border-cyan-500/30'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Events Stream
              </button>
              <button
                onClick={() => setActiveTab('RAW')}
                className={`px-3 py-1 rounded-lg font-semibold transition ${
                  activeTab === 'RAW'
                    ? 'bg-slate-800 text-cyan-400 border border-cyan-500/30'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Raw JSON Packet
              </button>
            </div>

            <button
              onClick={onClear}
              className="text-slate-500 hover:text-rose-400 flex items-center gap-1 transition text-[11px]"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Clear Log</span>
            </button>
          </div>

          {/* Logs Tab */}
          {activeTab === 'LOGS' ? (
            <div className="space-y-1.5 max-h-48 overflow-y-auto font-mono text-[11px] pr-1">
              {logs.length === 0 ? (
                <div className="text-slate-600 text-center py-4">No incoming packets yet...</div>
              ) : (
                logs.slice().reverse().map((entry) => {
                  let badgeColor = 'bg-slate-800 text-slate-400 border-slate-700';
                  if (entry.type === 'PACKET') badgeColor = 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30';
                  if (entry.type === 'OBS') badgeColor = 'bg-purple-500/10 text-purple-400 border-purple-500/30';
                  if (entry.type === 'AITOB') badgeColor = 'bg-blue-500/10 text-blue-400 border-blue-500/30';

                  return (
                    <div key={entry.id} className="flex items-center gap-2 py-0.5 border-b border-slate-900">
                      <span className="text-slate-500 text-[10px]">{entry.timestamp}</span>
                      <span className={`px-1.5 py-0.2 rounded border text-[9px] font-bold ${badgeColor}`}>
                        {entry.type}
                      </span>
                      <span className="text-slate-300 truncate">{entry.message}</span>
                    </div>
                  );
                })
              )}
            </div>
          ) : (
            /* Raw JSON Tab */
            <div className="bg-[#040508] p-3 rounded-lg border border-slate-800 max-h-48 overflow-auto font-mono text-[11px] text-emerald-400">
              <pre>{JSON.stringify(lastRawPacket || { status: 'No packet received yet' }, null, 2)}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
