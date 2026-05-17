import { useState } from 'react';
import { Save, Edit3, Check, X, Image as ImageIcon, Type, Link as LinkIcon } from 'lucide-react';
import { useEditorStore } from '@/store/useEditorStore';

interface TopBarProps {
  slot: string;
  onRename: (newName: string) => void;
  onSave: () => void;
  status: string;
}

export function TopBar({ slot, onRename, onSave, status }: TopBarProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [newName, setNewName] = useState(slot);
  const store = useEditorStore();

  const handleRename = () => {
    onRename(newName);
    setIsEditing(false);
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
