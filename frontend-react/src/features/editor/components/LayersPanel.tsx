import { useState } from 'react';
import { useEditorStore } from '@/store/useEditorStore';
import { Eye, EyeOff, Trash2, GripVertical, Layers, CopyPlus } from 'lucide-react';

export function LayersPanel() {
  const store = useEditorStore();
  const { elements, selectedId, selectedIds, setSelectedId, toggleSelectedId, updateElement, setElements, deleteElement, takeSnapshot } = store;
  const [draggedId, setDraggedId] = useState<string | null>(null);

  // Sort elements by zIndex descending so top layers appear at the top of the list
  const sortedLayers = Object.values(elements)
    .sort((a, b) => (b.zIndex || 0) - (a.zIndex || 0));

  const handleToggleVisibility = (id: string, currentVal: boolean) => {
    takeSnapshot();
    updateElement(id, { visible: !currentVal });
  };

  const handleDrop = (targetId: string) => {
    if (!draggedId || draggedId === targetId) return;
    const from = sortedLayers.findIndex(layer => layer.id === draggedId);
    const to = sortedLayers.findIndex(layer => layer.id === targetId);
    if (from < 0 || to < 0) return;
    const reordered = [...sortedLayers];
    const [moved] = reordered.splice(from, 1);
    reordered.splice(to, 0, moved);
    takeSnapshot();
    const next = { ...elements };
    reordered.forEach((layer, index) => { next[layer.id] = { ...layer, zIndex: reordered.length - index }; });
    setElements(next);
    setDraggedId(null);
  };

  const handleDelete = (id: string) => {
    if (confirm(`Delete element '${id}'?`)) {
      deleteElement(id);
    }
  };

  const handleCreateInstance = (source: typeof sortedLayers[number]) => {
    const now = Date.now();
    let id = `${source.id}_instance_${now}`;
    let suffix = 2;
    while (elements[id]) id = `${source.id}_instance_${now}_${suffix++}`;
    const maxZ = Math.max(0, ...Object.values(elements).map(element => element.zIndex || 0));
    store.addElement({
      ...JSON.parse(JSON.stringify(source)),
      id,
      sourceId: source.sourceId || source.id,
      x: source.x + 32,
      y: source.y + 32,
      zIndex: maxZ + 1,
    });
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
    <div className="w-[280px] min-w-[280px] bg-[#2b2b2b] border-l border-white/10 flex flex-col h-screen text-white text-[13px] select-none">
      <div className="p-4 border-b border-white/10 flex items-center gap-2">
        <Layers size={16} className="text-[#00ffcc]" />
        <h2 className="text-[#00ffcc] uppercase tracking-wider font-bold text-sm">Layers Panel</h2>
      </div>

      <div className="flex-grow overflow-y-auto p-3 flex flex-col gap-2">
        {sortedLayers.length === 0 ? (
          <p className="text-[#666] text-xs italic text-center py-8">No elements in this overlay.</p>
        ) : (
          sortedLayers.map((layer) => {
            const isSelected = selectedIds.includes(layer.id) || selectedId === layer.id;
            const isVisible = layer.visible !== false;

            return (
              <div
                key={layer.id}
                onClick={(event) => event.ctrlKey || event.metaKey || event.shiftKey ? toggleSelectedId(layer.id) : setSelectedId(layer.id)}
                draggable
                onDragStart={() => setDraggedId(layer.id)}
                onDragOver={(event) => event.preventDefault()}
                onDrop={() => handleDrop(layer.id)}
                onDragEnd={() => setDraggedId(null)}
                className={`group flex flex-col gap-1.5 p-2.5 rounded-lg border transition-all cursor-pointer ${
                  isSelected
                    ? 'bg-[#00ffcc]/10 border-[#00ffcc]/40 shadow-[0_0_10px_rgba(0,255,204,0.05)]'
                    : 'bg-[#333]/50 border-transparent hover:bg-[#3d3d3d] hover:border-white/5'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <GripVertical size={15} className="shrink-0 text-white/35 cursor-grab active:cursor-grabbing" aria-label="Drag to reorder layer" />
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

                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleCreateInstance(layer);
                      }}
                      className="p-1 rounded hover:bg-[#00ffcc]/15 text-white/45 hover:text-[#00ffcc] transition-colors"
                      title="Create instance (mirrors this live-data source)"
                      aria-label={`Create instance of ${layer.id}`}
                    >
                      <CopyPlus size={14} />
                      <span className="text-[9px] font-bold uppercase">Instance</span>
                    </button>

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
