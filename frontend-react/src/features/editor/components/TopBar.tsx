import { useState } from 'react';
import { Save, Edit3, Check, X, Image as ImageIcon, Type, Link as LinkIcon, Undo, Redo } from 'lucide-react';
import { useEditorStore } from '@/store/useEditorStore';

interface TopBarProps {
  slot: string;
  stationId: string;
  onRename: (newName: string) => void;
  onSave: () => void;
  onLoadClick: () => void;
  status: string;
}

export function TopBar({ slot, stationId, onRename, onSave, onLoadClick, status }: TopBarProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [newName, setNewName] = useState(slot);
  const store = useEditorStore();

  const handleRename = () => {
    onRename(newName);
    setIsEditing(false);
  };

  const copyOBSLink = () => {
    const obsUrl = `${window.location.origin}/obs?slot=${stationId}`;
    navigator.clipboard.writeText(obsUrl);
    alert(`Station OBS URL copied successfully!\n${obsUrl}`);
  };

  return (
    <div className="h-16 bg-[#2a2a2a] border-b border-white/10 flex items-center justify-between px-6 z-50">
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          {isEditing ? (
            <div className="flex items-center gap-1">
              <input 
                value={newName}
                onChange={e => setNewName(e.target.value)}
                className="bg-[#111] border border-accentYellow/50 rounded px-2 py-1 text-sm text-white focus:outline-none"
                autoFocus
              />
              <button onClick={handleRename} className="p-1 hover:text-statusGreen"><Check size={16} /></button>
              <button onClick={() => { setIsEditing(false); setNewName(slot); }} className="p-1 hover:text-red-400"><X size={16} /></button>
            </div>
          ) : (
            <div className="flex items-center gap-2 group min-w-[200px]">
              <h1 className="text-lg font-bold tracking-tight text-white/90">
                Overlay: <span className="text-accentYellow">{slot}</span>
              </h1>
              <button 
                onClick={() => setIsEditing(true)}
                className="opacity-0 group-hover:opacity-100 p-1 text-white/40 hover:text-white transition-all"
              >
                <Edit3 size={14} />
              </button>
            </div>
          )}
        </div>
        
        <div className="h-6 w-px bg-white/10" />
        
        {/* Global Settings */}
        <div className="flex items-center gap-3 text-xs">
          <div className="flex items-center gap-2 bg-[#1a1a1a] rounded px-3 py-1.5 border border-white/5 focus-within:border-accentYellow/50 transition-colors" title="Background Image URL">
            <ImageIcon size={14} className="text-white/40" />
            <input 
              className="bg-transparent border-none outline-none w-48 placeholder-white/30 text-white" 
              placeholder="Background URL..." 
              value={store.background_url} 
              onChange={e => store.setGlobalSettings(e.target.value, store.global_font_url, store.global_font_family)} 
            />
          </div>

          <div className="flex items-center gap-2 bg-[#1a1a1a] rounded px-3 py-1.5 border border-white/5 focus-within:border-accentYellow/50 transition-colors" title="Google Font URL">
            <LinkIcon size={14} className="text-white/40" />
            <input 
              className="bg-transparent border-none outline-none w-48 placeholder-white/30 text-white" 
              placeholder="Google Font URL..." 
              value={store.global_font_url} 
              onChange={e => store.setGlobalSettings(store.background_url, e.target.value, store.global_font_family)} 
            />
          </div>

          <div className="flex items-center gap-2 bg-[#1a1a1a] rounded px-3 py-1.5 border border-white/5 focus-within:border-accentYellow/50 transition-colors" title="Global Font Family">
            <Type size={14} className="text-white/40" />
            <input 
              className="bg-transparent border-none outline-none w-32 placeholder-white/30 text-white" 
              placeholder="'Inter', sans-serif" 
              value={store.global_font_family} 
              onChange={e => store.setGlobalSettings(store.background_url, store.global_font_url, e.target.value)} 
            />
          </div>
        </div>
      </div>

      <div className="flex items-center gap-4 flex-shrink-0">
        <span className="text-xs text-textDim font-medium animate-pulse">{status}</span>
        
        {/* Undo / Redo controls */}
        <div className="flex items-center gap-1 bg-[#1a1a1a] rounded-full p-1 border border-white/5">
          <button 
            onClick={() => store.undo()} 
            disabled={store.past.length === 0}
            className={`p-1.5 rounded-full hover:bg-white/10 transition-colors ${store.past.length === 0 ? 'text-white/20 cursor-not-allowed' : 'text-[#00ffcc] hover:text-white'}`}
            title="Undo"
          >
            <Undo size={14} />
          </button>
          <button 
            onClick={() => store.redo()} 
            disabled={store.future.length === 0}
            className={`p-1.5 rounded-full hover:bg-white/10 transition-colors ${store.future.length === 0 ? 'text-white/20 cursor-not-allowed' : 'text-[#00ffcc] hover:text-white'}`}
            title="Redo"
          >
            <Redo size={14} />
          </button>
        </div>

        <button 
          onClick={() => window.dispatchEvent(new Event('play-slide-preview'))}
          className="flex items-center gap-2 bg-[#00ffcc]/20 hover:bg-[#00ffcc]/30 text-[#00ffcc] border border-[#00ffcc]/40 px-4 py-1.5 rounded-full text-sm font-bold transition-all hover:scale-105 active:scale-95"
          title="Play PowerPoint slide animation sequence for all elements"
        >
          ▶ Play Slide
        </button>

        <button 
          onClick={copyOBSLink}
          className="flex items-center gap-2 bg-accentYellow/20 hover:bg-accentYellow/30 text-accentYellow border border-accentYellow/40 px-4 py-1.5 rounded-full text-sm font-bold transition-all hover:scale-105 active:scale-95"
          title="Copy static OBS link for this station"
        >
          <LinkIcon size={16} />
          Copy OBS Link
        </button>

        <button 
          onClick={onLoadClick}
          className="flex items-center gap-2 bg-[#333] hover:bg-[#444] text-white border border-white/20 px-4 py-1.5 rounded-full text-sm font-bold transition-all hover:scale-105 active:scale-95"
          title="Load a saved overlay template onto this station"
        >
          <ImageIcon size={16} />
          Load Slide
        </button>

        <button 
          onClick={onSave}
          className="flex items-center gap-2 bg-statusGreen/20 hover:bg-statusGreen/30 text-statusGreen border border-statusGreen/40 px-4 py-1.5 rounded-full text-sm font-bold transition-all hover:scale-105 active:scale-95"
        >
          <Save size={16} />
          Save Overlay
        </button>
      </div>
    </div>
  );
}
