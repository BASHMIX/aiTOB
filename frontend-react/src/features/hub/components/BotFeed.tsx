import { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import { useHubSocket } from '@/hooks/useHubSocket';

export function BotFeed() {
  const [feed, setFeed] = useState<any[]>([]);
  const [cmdInput, setCmdInput] = useState('');
  const [isCollapsed, setIsCollapsed] = useState(true);
  const [activeTab, setActiveTab] = useState<'chat' | 'logs'>('chat');
  const [isAgentTyping, setIsAgentTyping] = useState(false);

  // Chat message history loaded from localStorage
  const [chatMessages, setChatMessages] = useState<any[]>(() => {
    const saved = localStorage.getItem('hub_agent_chat');
    return saved ? JSON.parse(saved) : [
      { 
        id: 'welcome', 
        sender: 'agent', 
        text: 'Hello! I am your AI Hub Assistant. I can help you coordinate matches, disqualify players, force scores, reopen matches, or make public announcements. What would you like to do?', 
        timestamp: new Date().toISOString() 
      }
    ];
  });

  const logsEndRef = useRef<HTMLDivElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const loadFeed = async () => {
    try {
      const res = await axios.get('/api/bot-feed');
      setFeed(res.data.feed || []);
    } catch (e) {
      console.error("Failed to load bot feed", e);
    }
  };

  // Save chat to localStorage whenever it changes
  useEffect(() => {
    localStorage.setItem('hub_agent_chat', JSON.stringify(chatMessages));
  }, [chatMessages]);

  // Initial load
  useEffect(() => {
    loadFeed();
  }, []);

  // Listen to WebSocket events in real-time
  useHubSocket(useCallback((evt) => {
    if (evt.type === 'bot_feed_update') {
      loadFeed();
    } else if (evt.type === 'agent_response') {
      const responseText = evt.response;
      
      setChatMessages((curr) => {
        // Prevent duplicate appending from multiple clients
        const exists = curr.some(
          (msg) => msg.text === responseText && 
          msg.sender === 'agent' && 
          Math.abs(new Date(msg.timestamp).getTime() - Date.now()) < 3000
        );
        if (exists) return curr;

        return [
          ...curr,
          {
            id: `agent_${Date.now()}`,
            sender: 'agent',
            text: responseText,
            timestamp: new Date().toISOString()
          }
        ];
      });
      setIsAgentTyping(false);
    }
  }, []));

  // Auto-scroll to bottom on new updates
  useEffect(() => {
    if (!isCollapsed) {
      if (activeTab === 'logs') {
        logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      } else {
        chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      }
    }
  }, [feed, chatMessages, activeTab, isCollapsed, isAgentTyping]);

  const sendBotCommand = async () => {
    const cmd = cmdInput.trim();
    if (!cmd) return;
    setCmdInput('');

    if (activeTab === 'chat') {
      // Append User message
      const userMsg = {
        id: `user_${Date.now()}`,
        sender: 'user',
        text: cmd,
        timestamp: new Date().toISOString()
      };
      setChatMessages((curr) => [...curr, userMsg]);
      setIsAgentTyping(true);

      try {
        await axios.post('/api/hub/command', { command: cmd });
      } catch (e) {
        console.error("Failed to send command to agent", e);
        setChatMessages((curr) => [
          ...curr,
          {
            id: `err_${Date.now()}`,
            sender: 'agent',
            text: '⚠️ I encountered an error communicating with the bot client. Make sure the Discord Bot service is online.',
            timestamp: new Date().toISOString()
          }
        ]);
        setIsAgentTyping(false);
      }
    } else {
      // Logs tab raw command sending
      try {
        await axios.post('/api/bot-command', { command: cmd });
        loadFeed();
      } catch (e) {
        console.error("Failed to send bot command", e);
      }
    }
  };

  const handleQuickCommand = (cmdText: string) => {
    setCmdInput(cmdText);
  };

  const clearChat = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Clear AI Assistant conversation history?')) return;
    setChatMessages([
      { 
        id: 'welcome', 
        sender: 'agent', 
        text: 'Hello! Conversation reset. What would you like to do next?', 
        timestamp: new Date().toISOString() 
      }
    ]);
  };

  const clearFeed = async (e: React.MouseEvent) => {
    e.stopPropagation();
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
          🤖 AI Assistant & Logs
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
    <div className="fixed bottom-4 right-4 z-50 w-80 md:w-[420px] h-[520px] bg-cardDark border border-white/10 rounded-xl shadow-2xl flex flex-col overflow-hidden animate-slideUp">
      
      {/* Header with Sub-Tabs */}
      <div className="border-b border-white/10 flex flex-col bg-[#13171f] shrink-0">
        
        {/* Title Bar */}
        <div className="p-3.5 pb-2.5 flex justify-between items-center select-none">
          <div onClick={() => setIsCollapsed(true)} className="cursor-pointer flex items-center gap-2 flex-grow">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-statusGreen opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-statusGreen"></span>
            </span>
            <h2 className="text-accentYellow font-bold text-xs tracking-widest uppercase">AI Organizer Console</h2>
          </div>
          
          <div className="flex items-center gap-2">
            {activeTab === 'chat' ? (
              <button 
                onClick={clearChat} 
                className="text-[9px] text-textDim hover:text-white transition-colors bg-white/5 hover:bg-white/10 px-2 py-0.5 rounded font-mono uppercase tracking-wider"
                title="Reset Chat History"
              >
                Reset Chat
              </button>
            ) : (
              <button 
                onClick={clearFeed} 
                className="text-[9px] text-textDim hover:text-white transition-colors bg-white/5 hover:bg-white/10 px-2 py-0.5 rounded font-mono uppercase tracking-wider"
                title="Wipe Logs Permanently"
              >
                Clear Logs
              </button>
            )}
            <button 
              onClick={() => setIsCollapsed(true)}
              className="text-textDim hover:text-white text-sm font-black transition-colors px-1"
              title="Minimize panel"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Tab Selector */}
        <div className="flex px-3 pb-2 gap-2">
          <button
            onClick={() => setActiveTab('chat')}
            className={`flex-1 py-1 px-3 text-[10px] font-bold tracking-widest uppercase rounded transition-all border ${
              activeTab === 'chat'
                ? 'bg-accentYellow/10 border-accentYellow/30 text-accentYellow shadow-sm shadow-accentYellow/5'
                : 'bg-transparent border-transparent text-textDim hover:text-white'
            }`}
          >
            💬 AI Assistant
          </button>
          <button
            onClick={() => setActiveTab('logs')}
            className={`flex-1 py-1 px-3 text-[10px] font-bold tracking-widest uppercase rounded transition-all border ${
              activeTab === 'logs'
                ? 'bg-accentYellow/10 border-accentYellow/30 text-accentYellow shadow-sm shadow-accentYellow/5'
                : 'bg-transparent border-transparent text-textDim hover:text-white'
            }`}
          >
            📋 Live Logs
          </button>
        </div>
      </div>

      {/* Content Container */}
      <div className="flex-1 overflow-hidden bg-black/10 flex flex-col">
        
        {/* 1. AI Assistant Chat View */}
        {activeTab === 'chat' && (
          <div className="flex-grow overflow-y-auto p-4 flex flex-col gap-3 custom-scrollbar">
            {chatMessages.map((msg) => (
              <div 
                key={msg.id}
                className={`flex flex-col max-w-[85%] ${
                  msg.sender === 'user' ? 'self-end items-end' : 'self-start items-start'
                }`}
              >
                <div 
                  className={`p-3 rounded-xl text-xs leading-relaxed whitespace-pre-wrap ${
                    msg.sender === 'user'
                      ? 'bg-accentYellow/15 border border-accentYellow/30 text-white rounded-br-none'
                      : 'bg-cardLight border border-white/5 text-gray-200 rounded-bl-none'
                  }`}
                >
                  {msg.text}
                </div>
                <span className="text-[9px] text-textDim mt-1 px-1 font-mono">
                  {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </span>
              </div>
            ))}
            
            {/* Thinking / Typing Animation */}
            {isAgentTyping && (
              <div className="self-start flex flex-col items-start max-w-[85%]">
                <div className="bg-cardLight border border-white/5 p-3.5 rounded-xl rounded-bl-none flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-accentYellow animate-bounce" style={{ animationDelay: '0ms' }}></span>
                  <span className="w-1.5 h-1.5 rounded-full bg-accentYellow animate-bounce" style={{ animationDelay: '150ms' }}></span>
                  <span className="w-1.5 h-1.5 rounded-full bg-accentYellow animate-bounce" style={{ animationDelay: '300ms' }}></span>
                </div>
                <span className="text-[8px] text-accentYellow/60 mt-1 font-mono uppercase tracking-widest">Hub Agent is working...</span>
              </div>
            )}
            
            {/* Quick Command Suggestions (When chat history has only welcome message) */}
            {chatMessages.length === 1 && !isAgentTyping && (
              <div className="mt-4 flex flex-col gap-2 shrink-0 animate-fadeIn">
                <span className="text-[10px] text-textDim uppercase tracking-wider font-bold">Try asking:</span>
                <div className="flex flex-wrap gap-1.5">
                  <button 
                    onClick={() => handleQuickCommand('Who is currently playing?')}
                    className="text-[10px] bg-white/5 border border-white/10 hover:border-accentYellow/30 rounded px-2.5 py-1 text-left text-gray-300 hover:text-white transition-colors"
                  >
                    🔍 Who is currently playing?
                  </button>
                  <button 
                    onClick={() => handleQuickCommand('Announce that top 8 begins in 10 minutes')}
                    className="text-[10px] bg-white/5 border border-white/10 hover:border-accentYellow/30 rounded px-2.5 py-1 text-left text-gray-300 hover:text-white transition-colors"
                  >
                    📢 Announce top 8 starts in 10m
                  </button>
                  <button 
                    onClick={() => handleQuickCommand('reopen match 12345')}
                    className="text-[10px] bg-white/5 border border-white/10 hover:border-accentYellow/30 rounded px-2.5 py-1 text-left text-gray-300 hover:text-white transition-colors"
                  >
                    ⚙️ Reopen match [ID]
                  </button>
                  <button 
                    onClick={() => handleQuickCommand('disqualify p1 in match 12345')}
                    className="text-[10px] bg-white/5 border border-white/10 hover:border-accentYellow/30 rounded px-2.5 py-1 text-left text-gray-300 hover:text-white transition-colors"
                  >
                    🚫 Disqualify p1 in match [ID]
                  </button>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
        )}

        {/* 2. Live Logs View */}
        {activeTab === 'logs' && (
          <div className="flex-grow overflow-y-auto p-4 font-mono text-xs text-textLight flex flex-col gap-2 leading-relaxed break-words whitespace-pre-wrap custom-scrollbar">
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
        )}
      </div>

      {/* Unified Footer */}
      <div className="p-3 border-t border-white/10 flex gap-2 shrink-0 bg-[#13171f]">
        <input 
          className="flex-1 bg-black/45 border border-white/10 rounded px-2.5 py-1.5 text-xs text-white focus:border-accentYellow/50 focus:ring-1 focus:ring-accentYellow/20 outline-none transition-colors" 
          placeholder={
            activeTab === 'chat'
              ? "Command the AI organizer (e.g. reopen set 123)..."
              : "Command the bot (e.g. call_match 10299)..."
          }
          value={cmdInput}
          onChange={e => setCmdInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && sendBotCommand()}
        />
        <button 
          onClick={sendBotCommand}
          className="bg-accentYellow text-black px-4 py-1.5 rounded text-xs hover:bg-yellow-400 font-bold tracking-wider hover:shadow-[0_0_10px_rgba(234,179,8,0.25)] transition-all"
        >
          Send
        </button>
      </div>
    </div>
  );
}
