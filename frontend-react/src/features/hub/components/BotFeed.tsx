import { useState, useEffect } from 'react';
import axios from 'axios';

export function BotFeed() {
  const [feed, setFeed] = useState([]);
  const [cmdInput, setCmdInput] = useState('');

  const loadFeed = async () => {
    const res = await axios.get('/api/bot-feed');
    setFeed(res.data.feed || []);
  };

  useEffect(() => {
    loadFeed();
  }, []);

  const sendBotCommand = async () => {
    const cmd = cmdInput.trim();
    if (!cmd) return;
    setCmdInput('');
    await axios.post('/api/bot-command', { command: cmd });
    loadFeed();
  };

  const clearFeed = async () => {
    if (!confirm('Clear all bot logs permanently?')) return;
    try {
      await axios.delete('/api/bot-feed');
      setFeed([]);
    } catch (e) {
      console.error("Failed to clear feed", e);
    }
  };

  return (
    <div className="bg-cardDark rounded-lg shadow-md flex-1 flex flex-col border border-white/5 min-h-[400px]">
      <div className="p-4 border-b border-white/10 flex justify-between items-center relative">
        <h2 className="text-accentYellow font-bold text-lg tracking-wide uppercase text-center w-full">Bot Feed & Live Logs</h2>
        <button 
          onClick={clearFeed} 
          className="absolute right-4 text-textDim hover:text-white transition-colors text-xs font-bold bg-white/5 px-2 py-1 rounded"
          title="Clear all logs permanently"
        >
          Clear
        </button>
      </div>
      <div className="p-4 overflow-y-auto overflow-x-hidden font-mono text-sm text-textLight flex flex-col gap-1.5 leading-relaxed flex-1 break-words whitespace-pre-wrap">
        {[...feed].reverse().map((f: any) => (
          <p key={f.id} className="break-words">
            <span className="text-textDim">[{f.timestamp?.substring(11,16) || '—'}] </span>
            <span className={f.level === 'warn' ? 'text-statusRed' : ''}>{f.message}</span>
          </p>
        ))}
      </div>
      <div className="p-4 border-t border-white/10 flex gap-2 mt-auto">
        <input 
          className="flex-1 bg-appDark border border-white/10 rounded px-3 py-2 text-sm text-white focus:border-accentYellow focus:ring-1 focus:ring-accentYellow outline-none" 
          placeholder="Command the bot..." 
          value={cmdInput}
          onChange={e => setCmdInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && sendBotCommand()}
        />
        <button 
          onClick={sendBotCommand}
          className="bg-btnActive text-white px-4 py-2 rounded text-sm hover:bg-white/20 transition-colors font-bold"
        >
          Send
        </button>
      </div>
    </div>
  );
}
