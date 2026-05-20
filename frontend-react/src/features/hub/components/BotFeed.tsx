import { useState, useEffect, useRef } from 'react';
import axios from 'axios';

export function BotFeed() {
  const [feed, setFeed] = useState<any[]>([]);
  const [cmdInput, setCmdInput] = useState('');
  const [isCollapsed, setIsCollapsed] = useState(true);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const loadFeed = async () => {
    try {
      const res = await axios.get('/api/bot-feed');
      setFeed(res.data.feed || []);
    } catch (e) {
      console.error("Failed to load bot feed", e);
    }
  };

  // Poll logs every 3 seconds for a true "live logs" experience
  useEffect(() => {
    loadFeed();
    const interval = setInterval(loadFeed, 3000);
    return () => clearInterval(interval);
  }, []);

  // Auto-scroll logs to bottom when new items arrive
  useEffect(() => {
    if (!isCollapsed) {
      logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [feed, isCollapsed]);

  const sendBotCommand = async () => {
    const cmd = cmdInput.trim();
    if (!cmd) return;
    setCmdInput('');
    try {
      await axios.post('/api/bot-command', { command: cmd });
      loadFeed();
    } catch (e) {
      console.error("Failed to send bot command", e);
    }
  };

  const clearFeed = async (e: React.MouseEvent) => {
    e.stopPropagation(); // Don't trigger collapse/expand when clicking clear
    if (!confirm('Clear all bot logs permanently?')) return;
    try {
      await axios.delete('/api/bot-feed');
      setFeed([]);
    } catch (e) {
      console.error("Failed to clear feed", e);
    }
  };

  if (isCollapsed) {
    return (
      <div 
        onClick={() => setIsCollapsed(false)}
        className="fixed bottom-4 right-4 z-50 bg-[#161a21] border border-white/10 hover:border-accentYellow/40 rounded-full px-4 py-2.5 shadow-2xl flex items-center gap-2 cursor-pointer transition-all duration-200 hover:scale-[1.03] active:scale-95 group"
      >
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-statusGreen opacity-75"></span>
          <span className="relative inline-flex rounded-full h-2 w-2 bg-statusGreen"></span>
        </span>
        <span className="text-xs font-bold text-gray-200 group-hover:text-white tracking-wide flex items-center gap-1.5">
          🤖 Bot Feed & Logs
          {feed.length > 0 && (
            <span className="bg-accentYellow text-black text-[9px] font-black px-1.5 py-0.5 rounded-full">
              {feed.length}
            </span>
          )}
        </span>
      </div>
    );
  }

  return (
    <div className="fixed bottom-4 right-4 z-50 w-80 md:w-96 h-[460px] bg-cardDark border border-white/10 rounded-xl shadow-2xl flex flex-col overflow-hidden animate-slideUp">
      {/* Header */}
      <div className="p-3.5 border-b border-white/10 flex justify-between items-center bg-[#13171f] cursor-pointer select-none" onClick={() => setIsCollapsed(true)}>
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-statusGreen opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-statusGreen"></span>
          </span>
          <h2 className="text-accentYellow font-bold text-xs tracking-widest uppercase">Bot Feed & Live Logs</h2>
        </div>
        <div className="flex items-center gap-2.5">
          <button 
            onClick={clearFeed} 
            className="text-[10px] text-textDim hover:text-white transition-colors bg-white/5 hover:bg-white/10 px-2 py-0.5 rounded font-bold"
            title="Clear all logs permanently"
          >
            Clear
          </button>
          <button 
            onClick={() => setIsCollapsed(true)}
            className="text-textDim hover:text-white text-sm font-black transition-colors"
            title="Collapse panel"
          >
            ✕
          </button>
        </div>
      </div>

      {/* Logs View */}
      <div className="p-4 overflow-y-auto overflow-x-hidden font-mono text-xs text-textLight flex flex-col gap-2 leading-relaxed flex-1 break-words whitespace-pre-wrap bg-black/15 custom-scrollbar">
        {feed.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-textDim italic text-center gap-1">
            <span>🤖 Logs are clean</span>
            <span className="text-[10px] opacity-60">Awaiting bot events...</span>
          </div>
        ) : (
          [...feed].map((f: any) => (
            <p key={f.id} className="break-words border-b border-white/[0.02] pb-1">
              <span className="text-textDim text-[10px]">[{f.timestamp?.substring(11, 19) || '—'}]</span>{' '}
              <span className={`font-semibold ${
                f.level === 'warn' || f.level === 'error' 
                  ? 'text-statusRed font-bold' 
                  : f.level === 'success' 
                    ? 'text-statusGreen font-bold' 
                    : 'text-gray-300'
              }`}>
                {f.message}
              </span>
            </p>
          ))
        )}
        <div ref={logsEndRef} />
      </div>

      {/* Command Input footer */}
      <div className="p-3 border-t border-white/10 flex gap-2 mt-auto bg-[#13171f]">
        <input 
          className="flex-1 bg-black/45 border border-white/10 rounded px-2.5 py-1.5 text-xs text-white focus:border-accentYellow/50 focus:ring-1 focus:ring-accentYellow/20 outline-none transition-colors" 
          placeholder="Command the bot (e.g. status)..." 
          value={cmdInput}
          onChange={e => setCmdInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && sendBotCommand()}
        />
        <button 
          onClick={sendBotCommand}
          className="bg-accentYellow text-black px-3.5 py-1.5 rounded text-xs hover:bg-yellow-400 font-bold tracking-wider hover:shadow-[0_0_10px_rgba(234,179,8,0.25)] transition-all"
        >
          Send
        </button>
      </div>
    </div>
  );
}
