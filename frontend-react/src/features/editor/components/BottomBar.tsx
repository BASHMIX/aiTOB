import { ZoomIn, ZoomOut, PlusCircle, Trash2 } from 'lucide-react';
import { OverlayThumbnail } from './OverlayThumbnail';
import { useEditorStore } from '@/store/useEditorStore';

interface BottomBarProps {
  scale: number;
  onScaleChange: (scale: number) => void;
  presets: { name: string, config: any }[];
  currentSlot: string;
  onSelectPreset: (name: string) => void;
  onNewPreset: () => void;
  onDeletePreset: (name: string) => void;
}

export function BottomBar({ scale, onScaleChange, presets, currentSlot, onSelectPreset, onNewPreset, onDeletePreset }: BottomBarProps) {
  const store = useEditorStore();

  return (
    <div className="h-32 bg-[#2a2a2a] border-t border-white/10 flex items-center px-6 gap-8 z-50">
      {/* Zoom Controls */}
      <div className="flex flex-col items-center gap-2 min-w-[120px]">
        <div className="flex items-center gap-3 text-white/60">
          <button onClick={() => onScaleChange(Math.max(0.1, scale - 0.1))} className="hover:text-accentYellow transition-colors"><ZoomOut size={18} /></button>
          <input 
            type="range" 
            min="0.1" 
            max="1.5" 
            step="0.05" 
            value={scale}
            onChange={(e) => onScaleChange(parseFloat(e.target.value))}
            className="w-24 h-1 bg-white/10 rounded-lg appearance-none cursor-pointer accent-accentYellow"
          />
          <button onClick={() => onScaleChange(Math.min(1.5, scale + 0.1))} className="hover:text-accentYellow transition-colors"><ZoomIn size={18} /></button>
        </div>
        <span className="text-[10px] font-bold text-textDim uppercase tracking-widest">
          Scale: {Math.round(scale * 100)}%
        </span>
      </div>

      <div className="h-12 w-px bg-white/10" />

      {/* Presets List */}
      <div className="flex-grow flex items-center gap-3 overflow-x-auto py-2 no-scrollbar h-full">
        <button 
          onClick={onNewPreset}
          className="flex-shrink-0 w-32 h-[86px] rounded border-2 border-dashed border-white/10 hover:border-accentYellow/50 hover:bg-white/5 flex flex-col items-center justify-center gap-1 text-white/40 hover:text-accentYellow transition-all group"
        >
          <PlusCircle size={20} />
          <span className="text-[8px] font-bold uppercase mt-1">New Preset</span>
        </button>

        {Array.isArray(presets) && presets.map((p) => {
          const isSelected = p.name === currentSlot;
          const configToUse = isSelected ? {
            elements: store.elements,
            background_url: store.background_url,
            global_font_url: store.global_font_url,
            global_font_family: store.global_font_family
          } : p.config;

          return (
            <div key={p.name} className="relative group flex-shrink-0">
              <OverlayThumbnail 
                name={p.name}
                config={configToUse}
                isSelected={isSelected}
                onClick={() => onSelectPreset(p.name)}
              />
              <button 
                onClick={(e) => { e.stopPropagation(); onDeletePreset(p.name); }}
                className="absolute -top-2 -right-2 w-6 h-6 bg-red-500/90 text-white rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity shadow-lg z-20 hover:bg-red-600 hover:scale-110"
                title="Delete Preset"
              >
                <Trash2 size={12} />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
