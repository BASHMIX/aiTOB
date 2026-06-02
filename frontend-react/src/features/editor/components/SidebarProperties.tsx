import { useEditorStore } from '@/store/useEditorStore';
import { AssetManager } from './AssetManager';

export function SidebarProperties() {
  const store = useEditorStore();
  const selId = store.selectedId;
  const selEl = selId ? store.elements[selId] : null;

  if (!selEl || !selId) {
    return null;
  }

  const handleWheel = (e: React.WheelEvent<HTMLInputElement>, field: string, currentValue: any) => {
    if (!selId) return;
    const current = parseFloat(currentValue) || 0;
    const delta = e.deltaY < 0 ? 1 : -1;
    const step = e.shiftKey ? 10 : 1;
    store.updateElement(selId, { [field]: current + (delta * step) });
  };

  return (
    <div className="flex flex-col">
      <label className="text-[11px] text-[#999] uppercase tracking-wide mb-1 block">ID</label>
      <input className="w-full bg-[#222] border border-[#555] rounded px-2 py-1.5 mb-3 text-[#aaa]" readOnly value={selId} />

      {selEl.type === 'text' && (
        <>
          <label className="text-[11px] text-[#999] uppercase tracking-wide mb-1 block">Text</label>
          <textarea
            className="w-full bg-[#3a3a3a] border border-[#555] rounded px-2 py-1.5 mb-3 text-xs h-20 resize-y"
            value={selEl.text || ''}
            onChange={e => store.updateElement(selId, { text: e.target.value })}
          />

          <div className="flex gap-2 mb-3">
            <button
              onClick={() => store.updateElement(selId, { fontWeight: selEl.fontWeight === 'bold' ? 'normal' : 'bold' })}
              className={`flex-1 py-1 px-2 border rounded font-bold text-xs ${selEl.fontWeight === 'bold' ? 'bg-[#00ffcc] text-[#111] border-[#00ffcc]' : 'bg-[#3a3a3a] border-[#555] text-white'}`}
            >
              Bold
            </button>
            <button
              onClick={() => store.updateElement(selId, { fontStyle: selEl.fontStyle === 'italic' ? 'normal' : 'italic' })}
              className={`flex-1 py-1 px-2 border rounded italic text-xs ${selEl.fontStyle === 'italic' ? 'bg-[#00ffcc] text-[#111] border-[#00ffcc]' : 'bg-[#3a3a3a] border-[#555] text-white'}`}
            >
              Italic
            </button>
          </div>

          <label className="text-[11px] text-[#999] uppercase tracking-wide mb-1 block">Alignment</label>
          <div className="flex rounded border border-[#555] overflow-hidden mb-3">
            {(['left', 'center', 'right'] as const).map((align) => (
              <button
                key={align}
                onClick={() => store.updateElement(selId, { textAlign: align })}
                className={`flex-1 py-1 text-xs capitalize ${selEl.textAlign === align ? 'bg-[#00ffcc] text-[#111]' : 'bg-[#3a3a3a] text-white hover:bg-[#444]'}`}
              >
                {align}
              </button>
            ))}
          </div>

          <label className="text-[11px] text-[#999] uppercase tracking-wide mb-1 block">Font Size (px)</label>
          <input type="number" className="w-full bg-[#3a3a3a] border border-[#555] rounded px-2 py-1.5 mb-3" value={selEl.fontSize} onChange={e => store.updateElement(selId, { fontSize: parseFloat(e.target.value) })} onWheel={e => handleWheel(e, 'fontSize', selEl.fontSize)} />

          <label className="text-[11px] text-[#999] uppercase tracking-wide mb-1 block">Color</label>
          <input type="color" className="w-full h-[38px] p-1 bg-[#3a3a3a] border border-[#555] rounded mb-3 cursor-pointer" value={selEl.color || '#ffffff'} onChange={e => store.updateElement(selId, { color: e.target.value })} />
        </>
      )}

      {(selEl.type === 'image' || selEl.type === 'rect' || selEl.type === 'circle') && (
        <>
          {selEl.type === 'image' && (
            <>
              <label className="text-[11px] text-[#999] uppercase tracking-wide mb-1 block">Image Selection</label>
              <div className="mb-3">
                <AssetManager onSelect={(url) => store.updateElement(selId, { src: url })} />
              </div>
              <label className="text-[11px] text-[#999] uppercase tracking-wide mb-1 block">Custom URL</label>
              <input className="w-full bg-[#3a3a3a] border border-[#555] rounded px-2 py-1.5 mb-3" value={selEl.src} onChange={e => store.updateElement(selId, { src: e.target.value })} />
            </>
          )}
          {(selEl.type === 'rect' || selEl.type === 'circle') && (
            <>
              <label className="text-[11px] text-[#999] uppercase tracking-wide mb-1 block">Fill Color</label>
              <div className="flex gap-2 mb-3">
                <input type="color" className="w-16 h-[38px] p-1 bg-[#3a3a3a] border border-[#555] rounded cursor-pointer" value={selEl.color?.startsWith('#') ? selEl.color : '#000000'} onChange={e => store.updateElement(selId, { color: e.target.value })} />
                <input className="flex-1 bg-[#3a3a3a] border border-[#555] rounded px-2 py-1.5 text-xs" value={selEl.color} onChange={e => store.updateElement(selId, { color: e.target.value })} placeholder="rgba(0,0,0,0.5)" />
              </div>
              <label className="text-[11px] text-[#999] uppercase tracking-wide mb-1 block">Corner Radius (px)</label>
              <input type="number" className="w-full bg-[#3a3a3a] border border-[#555] rounded px-2 py-1.5 mb-3" value={selEl.borderRadius || 0} onChange={e => store.updateElement(selId, { borderRadius: parseFloat(e.target.value) })} onWheel={e => handleWheel(e, 'borderRadius', selEl.borderRadius)} />
            </>
          )}

          <div className="flex gap-2 mb-3">
            <div className="flex-1">
              <label className="text-[11px] text-[#999] uppercase tracking-wide mb-1 block">Width (px)</label>
              <input type="number" className="w-full bg-[#3a3a3a] border border-[#555] rounded px-2 py-1.5" value={selEl.width} onChange={e => store.updateElement(selId, { width: parseFloat(e.target.value) })} onWheel={e => handleWheel(e, 'width', selEl.width)} />
            </div>
            <div className="flex-1">
              <label className="text-[11px] text-[#999] uppercase tracking-wide mb-1 block">Height (px)</label>
              <input type="number" className="w-full bg-[#3a3a3a] border border-[#555] rounded px-2 py-1.5" value={selEl.height} onChange={e => store.updateElement(selId, { height: parseFloat(e.target.value) })} onWheel={e => handleWheel(e, 'height', selEl.height)} />
            </div>
          </div>
        </>
      )}

      <div className="flex gap-2 mb-4">
        <div className="flex-1">
          <label className="text-[11px] text-[#999] uppercase tracking-wide mb-1 block">X Position</label>
          <input type="number" className="w-full bg-[#3a3a3a] border border-[#555] rounded px-2 py-1.5" value={Math.round(selEl.x)} onChange={e => store.updateElement(selId, { x: parseFloat(e.target.value) })} onWheel={e => handleWheel(e, 'x', selEl.x)} />
        </div>
        <div className="flex-1">
          <label className="text-[11px] text-[#999] uppercase tracking-wide mb-1 block">Y Position</label>
          <input type="number" className="w-full bg-[#3a3a3a] border border-[#555] rounded px-2 py-1.5" value={Math.round(selEl.y)} onChange={e => store.updateElement(selId, { y: parseFloat(e.target.value) })} onWheel={e => handleWheel(e, 'y', selEl.y)} />
        </div>
      </div>

      {/* Stroke Controls for Text & Shapes */}
      {(selEl.type === 'text' || selEl.type === 'rect' || selEl.type === 'circle') && (
        <div className="mb-3 p-2 bg-[#333] rounded border border-[#444]">
          <h4 className="text-[11px] text-[#00ffcc] uppercase tracking-wider mb-2 font-bold">Stroke / Border</h4>
          <div className="flex gap-2">
            <div className="flex-1">
              <label className="text-[10px] text-[#999] block mb-1">Thickness (px)</label>
              <input
                type="number"
                min="0"
                className="w-full bg-[#222] border border-[#555] rounded px-2 py-1 text-xs text-white"
                value={selEl.strokeWidth || 0}
                onChange={e => store.updateElement(selId, { strokeWidth: Math.max(0, parseFloat(e.target.value) || 0) })}
              />
            </div>
            <div className="flex-1">
              <label className="text-[10px] text-[#999] block mb-1">Color</label>
              <div className="flex gap-1">
                <input
                  type="color"
                  className="w-8 h-7 p-0.5 bg-[#222] border border-[#555] rounded cursor-pointer"
                  value={selEl.strokeColor?.startsWith('#') ? selEl.strokeColor : '#000000'}
                  onChange={e => store.updateElement(selId, { strokeColor: e.target.value })}
                />
                <input
                  className="flex-1 min-w-0 bg-[#222] border border-[#555] rounded px-1 text-[10px] text-white"
                  value={selEl.strokeColor || ''}
                  placeholder="#000000"
                  onChange={e => store.updateElement(selId, { strokeColor: e.target.value })}
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Drop Shadow Controls */}
      <div className="mb-3 p-2 bg-[#333] rounded border border-[#444]">
        <h4 className="text-[11px] text-[#00ffcc] uppercase tracking-wider mb-2 font-bold">Drop Shadow</h4>
        <div className="grid grid-cols-2 gap-2 mb-2">
          <div>
            <label className="text-[10px] text-[#999] block mb-1">Color</label>
            <div className="flex gap-1">
              <input
                type="color"
                className="w-8 h-7 p-0.5 bg-[#222] border border-[#555] rounded cursor-pointer"
                value={selEl.shadowColor?.startsWith('#') ? selEl.shadowColor : '#000000'}
                onChange={e => store.updateElement(selId, { shadowColor: e.target.value })}
              />
              <input
                className="flex-1 min-w-0 bg-[#222] border border-[#555] rounded px-1 text-[10px] text-white"
                value={selEl.shadowColor || ''}
                placeholder="#000000"
                onChange={e => store.updateElement(selId, { shadowColor: e.target.value })}
              />
            </div>
          </div>
          <div>
            <label className="text-[10px] text-[#999] block mb-1">Blur (px)</label>
            <input
              type="number"
              min="0"
              className="w-full bg-[#222] border border-[#555] rounded px-2 py-1 text-xs text-white"
              value={selEl.shadowBlur || 0}
              onChange={e => store.updateElement(selId, { shadowBlur: Math.max(0, parseFloat(e.target.value) || 0) })}
            />
          </div>
        </div>
        <div className="flex gap-2">
          <div className="flex-1">
            <label className="text-[10px] text-[#999] block mb-1">Offset X (px)</label>
            <input
              type="number"
              className="w-full bg-[#222] border border-[#555] rounded px-2 py-1 text-xs text-white"
              value={selEl.shadowOffsetX || 0}
              onChange={e => store.updateElement(selId, { shadowOffsetX: parseFloat(e.target.value) || 0 })}
            />
          </div>
          <div className="flex-1">
            <label className="text-[10px] text-[#999] block mb-1">Offset Y (px)</label>
            <input
              type="number"
              className="w-full bg-[#222] border border-[#555] rounded px-2 py-1 text-xs text-white"
              value={selEl.shadowOffsetY || 0}
              onChange={e => store.updateElement(selId, { shadowOffsetY: parseFloat(e.target.value) || 0 })}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
