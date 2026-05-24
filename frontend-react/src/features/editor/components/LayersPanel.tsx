import { useEditorStore } from '@/store/useEditorStore';
import { Eye, EyeOff, Trash2, ChevronUp, ChevronDown, Layers } from 'lucide-react';

export function LayersPanel() {
  const store = useEditorStore();
  const { elements, selectedId, setSelectedId, updateElement, deleteElement, takeSnapshot } = store;

  // Sort elements by zIndex descending so top layers appear at the top of the list
  const sortedLayers = Object.values(elements)
    .sort((a, b) => (b.zIndex || 0) - (a.zIndex || 0));

  const handleToggleVisibility = (id: string, currentVal: boolean) => {
    takeSnapshot();
    updateElement(id, { visible: !currentVal });
  };

  const handleZIndexChange = (id: string, delta: number, currentZ: number) => {
    takeSnapshot();
    updateElement(id, { zIndex: currentZ + delta });
  };

  const handleDelete = (id: string) => {
    if (confirm(`Delete element '${id}'?`)) {
      deleteElement(id);
    }
  };

  const getElementBadge = (type: string) => {
    switch (type) {
      case 'text':
        return <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-blue-500/10 text-blue-400 border border-blue-500/20 uppercase">Text</span>;
      case 'image':
        return <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-purple-500/10 text-purple-400 border border-purple-500/20 uppercase">Img</span>;
      case 'rect':
        return <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-green-500/10 text-green-400 border border-green-500/20 uppercase">Rect</span>;
      case 'circle':
        return <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-orange-500/10 text-orange-400 border border-orange-500/20 uppercase">Circ</span>;
      default:
        return null;
    }
  };

  return (
    <div className="w-[280px] min-w-[280px] bg-[#2b2b2b] border-l border-white/10 flex flex-col h-screen text-white text-[13px]">
      <div className="p-4 border-b border-white/10 flex items-center gap-2">
        <Layers size={16} className="text-[#00ffcc]" />
        <h2 className="text-[#00ffcc] uppercase tracking-wider font-bold text-sm">Layers Panel</h2>
      </div>

      <div className="flex-grow overflow-y-auto p-3 flex flex-col gap-2">
        {sortedLayers.length === 0 ? (
          <p className="text-[#666] text-xs italic text-center py-8">No elements in this overlay.</p>
        ) : (
          sortedLayers.map((layer) => {
            const isSelected = selectedId === layer.id;
            const currentZ = layer.zIndex || 0;
            const isVisible = layer.visible !== false;

            return (
              <div
                key={layer.id}
                onClick={() => setSelectedId(layer.id)}
                className={`group flex flex-col gap-1.5 p-2.5 rounded-lg border transition-all cursor-pointer ${
                  isSelected
                    ? 'bg-[#00ffcc]/10 border-[#00ffcc]/40 shadow-[0_0_10px_rgba(0,255,204,0.05)]'
                    : 'bg-[#333]/50 border-transparent hover:bg-[#3d3d3d] hover:border-white/5'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 min-w-0">
                    {getElementBadge(layer.type)}
                    <span className="font-semibold truncate text-[12px] text-white/95" title={layer.id}>
                      {layer.id}
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5 opacity-65 group-hover:opacity-100 transition-opacity">
                    {/* Visibility Toggle */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleToggleVisibility(layer.id, isVisible);
                      }}
                      className={`p-1 rounded hover:bg-white/10 ${isVisible ? 'text-white/80' : 'text-white/20'}`}
                      title={isVisible ? 'Hide Layer' : 'Show Layer'}
                    >
                      {isVisible ? <Eye size={14} /> : <EyeOff size={14} />}
                    </button>

                    {/* Z-Index Controls */}
                    <div className="flex items-center rounded bg-[#222] border border-white/5 overflow-hidden">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleZIndexChange(layer.id, 1, currentZ);
                        }}
                        className="p-0.5 hover:bg-white/15 text-white/60 hover:text-white"
                        title="Bring Forward"
                      >
                        <ChevronUp size={12} />
                      </button>
                      <span className="text-[10px] px-1 text-white/40 select-none font-bold">
                        {currentZ}
                      </span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleZIndexChange(layer.id, -1, currentZ);
                        }}
                        className="p-0.5 hover:bg-white/15 text-white/60 hover:text-white"
                        title="Send Backward"
                      >
                        <ChevronDown size={12} />
                      </button>
                    </div>

                    {/* Delete button */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(layer.id);
                      }}
                      className="p-1 rounded hover:bg-red-500/20 text-white/30 hover:text-red-400 transition-colors"
                      title="Delete Layer"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>

                {/* Snippet of content / info */}
                <div className="text-[10px] text-textDim italic truncate pl-1 border-l border-white/10">
                  {layer.type === 'text' && (layer.text || '[Empty Text]')}
                  {layer.type === 'image' && (layer.src?.split('/').pop() || 'placeholder')}
                  {(layer.type === 'rect' || layer.type === 'circle') && `Color: ${layer.color || 'default'}`}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
