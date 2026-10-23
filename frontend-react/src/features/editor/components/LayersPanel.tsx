import { useState } from 'react';
import { useEditorStore, type OverlayElement } from '@/store/useEditorStore';
import { Eye, EyeOff, Trash2, GripVertical, Layers, CopyPlus, ChevronDown, ChevronRight } from 'lucide-react';

export function getStructuralParentId(elements: Record<string, OverlayElement>, layer: OverlayElement) {
  return Object.values(elements).find((candidate) => (
    (candidate.type === 'group' || candidate.type === 'results-cards') && candidate.childIds?.includes(layer.id)
  ))?.id
    || Object.values(elements).find((candidate) => candidate.type === 'results-group' && (candidate.cardDefinitionId === layer.id || candidate.templateId === layer.id))?.id
    || Object.values(elements).find((candidate) => candidate.type === 'result-card' && candidate.definitionId === layer.id)?.id
    || null;
}

export function LayersPanel() {
  const store = useEditorStore();
  const { elements, selectedId, selectedIds, setSelectedId, toggleSelectedId, updateElement, setElements, deleteElement, takeSnapshot } = store;
  const [draggedId, setDraggedId] = useState<string | null>(null);
  const [collapsedIds, setCollapsedIds] = useState<Set<string>>(new Set());

  // Sort elements by zIndex descending so top layers appear at the top of the list
  const sortedLayers = Object.values(elements)
    .sort((a, b) => (b.zIndex || 0) - (a.zIndex || 0));

  const structuralParentId = (layer: OverlayElement) => {
    // The owner's structural references are authoritative. A stale parentId on
    // an ordinary text/image/shape must never create an accidental tree.
    return getStructuralParentId(elements, layer);
  };

  const handleToggleVisibility = (id: string, currentVal: boolean) => {
    takeSnapshot();
    updateElement(id, { visible: !currentVal });
  };

  const handleDrop = (targetId: string) => {
    if (!draggedId || draggedId === targetId) return;
    const dragged = elements[draggedId];
    const target = elements[targetId];
    if (!dragged || !target || structuralParentId(dragged) !== structuralParentId(target)) return;
    const siblings = sortedLayers.filter((layer) => structuralParentId(layer) === structuralParentId(target));
    const from = siblings.findIndex(layer => layer.id === draggedId);
    const to = siblings.findIndex(layer => layer.id === targetId);
    if (from < 0 || to < 0) return;
    const reordered = [...siblings];
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

  const getElementBadge = (layer: typeof sortedLayers[number]) => {
    switch (layer.type) {
      case 'text':
        return <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-blue-500/10 text-blue-400 border border-blue-500/20 uppercase">Text</span>;
      case 'image':
        return <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-purple-500/10 text-purple-400 border border-purple-500/20 uppercase">Img</span>;
      case 'rect':
        return <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-green-500/10 text-green-400 border border-green-500/20 uppercase">Rect</span>;
      case 'circle':
        return <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-orange-500/10 text-orange-400 border border-orange-500/20 uppercase">Circ</span>;
      case 'group':
        if (layer.definitionRole === 'result-card' || layer.templateRole === 'player-card') {
          return <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20 uppercase">Design</span>;
        }
        return <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-yellow-500/10 text-yellow-400 border border-yellow-500/20 uppercase">Group</span>;
      case 'results-group':
        return <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 uppercase">Results</span>;
      case 'results-cards':
        return <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-cyan-500/10 text-cyan-300 border border-cyan-500/20 uppercase">Cards</span>;
      case 'result-card':
        return <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-sky-500/10 text-sky-300 border border-sky-500/20 uppercase">Card</span>;
      default:
        return null;
    }
  };

  // Build the authored hierarchy recursively. Generated player cards are renderer
  // values and intentionally never become layer rows.
  const childrenFor = (parent: OverlayElement) => Object.values(elements)
    .filter((child) => structuralParentId(child) === parent.id)
    .filter((child) => parent.type !== 'result-card'
      || child.id !== parent.definitionId
      || store.editingResultCardDefinitionId === child.id)
    .filter((child, index, list) => list.findIndex((item) => item.id === child.id) === index)
    .sort((a, b) => (b.zIndex || 0) - (a.zIndex || 0));

  const rootLayers = Object.values(elements)
    .filter((el) => {
      const parentId = structuralParentId(el);
      return !parentId || !elements[parentId];
    })
    .sort((a, b) => (b.zIndex || 0) - (a.zIndex || 0));

  const flatHierarchicalLayers: Array<{ layer: OverlayElement; depth: number; hasChildren: boolean }> = [];
  const visited = new Set<string>();
  const appendWithChildren = (layer: OverlayElement, depth = 0) => {
    if (visited.has(layer.id)) return;
    visited.add(layer.id);
    const children = childrenFor(layer);
    flatHierarchicalLayers.push({ layer, depth, hasChildren: children.length > 0 });
    if (!collapsedIds.has(layer.id)) children.forEach((child) => appendWithChildren(child, depth + 1));
  };
  rootLayers.forEach((layer) => appendWithChildren(layer, 0));

  const displayLayers = flatHierarchicalLayers;

  return (
    <div className="w-[280px] min-w-[280px] bg-[#2b2b2b] border-l border-white/10 flex flex-col h-screen text-white text-[13px] select-none">
      <div className="p-4 border-b border-white/10 flex items-center gap-2">
        <Layers size={16} className="text-[#00ffcc]" />
        <h2 className="text-[#00ffcc] uppercase tracking-wider font-bold text-sm">Layers Panel</h2>
      </div>

      <div className="flex-grow overflow-y-auto p-3 flex flex-col gap-2">
        {Object.values(elements).some((element) => element.type === 'results-group' || element.type === 'result-card') && (
          <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 text-[10px] leading-relaxed text-emerald-100/75">
            Result Cards are atomic here. Use Edit Card Design to open their internal layers. Only deliberately inserted linked cards appear as separate rows.
          </div>
        )}
        {displayLayers.length === 0 ? (
          <p className="text-[#666] text-xs italic text-center py-8">No elements in this overlay.</p>
        ) : (
          displayLayers.map(({ layer, depth, hasChildren }) => {
            const isSelected = selectedIds.includes(layer.id) || selectedId === layer.id;
            const isVisible = layer.visible !== false;
            const isNested = depth > 0;
            const canCreateInstance = depth === 0
              && !['group', 'result-card', 'results-cards', 'results-group'].includes(layer.type);

            return (
              <div
                key={layer.id}
                data-testid={`layer-row-${layer.id}`}
                data-nested={isNested ? 'true' : 'false'}
                data-depth={depth}
                data-selected={isSelected ? 'true' : 'false'}
                aria-current={isSelected ? 'true' : undefined}
                onClick={(event) => event.ctrlKey || event.metaKey || event.shiftKey ? toggleSelectedId(layer.id) : setSelectedId(layer.id)}
                draggable
                onDragStart={() => setDraggedId(layer.id)}
                onDragOver={(event) => event.preventDefault()}
                onDrop={() => handleDrop(layer.id)}
                onDragEnd={() => setDraggedId(null)}
                style={{ marginLeft: `${Math.min(depth, 4) * 14}px` }}
                className={`group flex flex-col gap-1.5 p-2.5 rounded-lg border transition-all cursor-pointer ${
                  isSelected
                    ? 'bg-[#064e3b] border-[#00ffcc] ring-2 ring-[#00ffcc]/60 shadow-[0_0_16px_rgba(0,255,204,0.16)]'
                    : isNested
                      ? 'bg-[#2f2f2f]/60 border-white/5 hover:bg-[#3d3d3d] hover:border-white/10'
                      : 'bg-[#333]/50 border-transparent hover:bg-[#3d3d3d] hover:border-white/5'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <GripVertical size={15} className="shrink-0 text-white/35 cursor-grab active:cursor-grabbing" aria-label="Drag to reorder layer" />
                    {hasChildren ? (
                      <button
                        type="button"
                        aria-label={`${collapsedIds.has(layer.id) ? 'Expand' : 'Collapse'} ${layer.name || layer.id}`}
                        onClick={(event) => {
                          event.stopPropagation();
                          setCollapsedIds((current) => {
                            const next = new Set(current);
                            if (next.has(layer.id)) next.delete(layer.id);
                            else next.add(layer.id);
                            return next;
                          });
                        }}
                        className="rounded p-0.5 text-white/55 hover:bg-white/10 hover:text-white"
                      >
                        {collapsedIds.has(layer.id) ? <ChevronRight size={13} /> : <ChevronDown size={13} />}
                      </button>
                    ) : <span className="w-[17px] shrink-0" />}
                    {getElementBadge(layer)}
                    <span className="font-semibold truncate text-[12px] text-white/95" title={layer.name || layer.id}>
                      {layer.name || layer.id}
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

                    {canCreateInstance && (
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
                      </button>
                    )}

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
                  {layer.type === 'results-group' && `${layer.mode === 'sequence' ? 'Animated sequence' : 'Static board'} · ${layer.cutoff || 'top8'}`}
                  {layer.type === 'results-cards' && `Freeform schedule · ${layer.autoSequence?.range || 'top8'}`}
                  {layer.type === 'result-card' && `${layer.instanceRole === 'linked' ? 'Linked' : 'Stage'} · ${layer.standingOrdinal || 1}`}
                  {layer.type === 'group' && (layer.definitionRole === 'result-card' || layer.templateRole === 'player-card') && 'Shared Result Card design'}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
