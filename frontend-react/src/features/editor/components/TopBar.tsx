import { useState } from 'react';
import { Save, Edit3, Check, X } from 'lucide-react';

interface TopBarProps {
  slot: string;
  onRename: (newName: string) => void;
  onSave: () => void;
  status: string;
}

export function TopBar({ slot, onRename, onSave, status }: TopBarProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [newName, setNewName] = useState(slot);

  const handleRename = () => {
    onRename(newName);
    setIsEditing(false);
  };

  return (
    <div className="h-14 bg-[#2a2a2a] border-b border-white/10 flex items-center justify-between px-6 z-50">
      <div className="flex items-center gap-4">
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
            <div className="flex items-center gap-2 group">
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
        <div className="h-4 w-px bg-white/10 mx-2" />
        <span className="text-xs text-textDim font-medium animate-pulse">{status}</span>
      </div>

      <button 
        onClick={onSave}
        className="flex items-center gap-2 bg-statusGreen/20 hover:bg-statusGreen/30 text-statusGreen border border-statusGreen/40 px-4 py-1.5 rounded-full text-sm font-bold transition-all hover:scale-105 active:scale-95"
      >
        <Save size={16} />
        Save Overlay
      </button>
    </div>
  );
}
