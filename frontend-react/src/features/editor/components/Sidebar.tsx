import { useState, useEffect } from 'react';
import { useEditorStore } from '@/store/useEditorStore';
import { AssetManager } from './AssetManager';

export function Sidebar({ onPush }: { onPush: () => void }) {
  const store = useEditorStore();
  const [addId, setAddId] = useState('');
  const [isCollapsed, setIsCollapsed] = useState(false);

  const selId = store.selectedId;
  const selEl = selId ? store.elements[selId] : null;

  // Animation configuration fallback & helper
  const anim = selEl?.animation || {
    animationType: 'none',
    direction: 'bottom',
    duration: 500,
    delay: 0,
    loop: 0,
    tweenType: 'ease-out',
    playOn: 'IN',
    trigger: 'on-load',
    revealStyle: 'all',
    scoreGlitch: false,
    idleAnimation: 'none',
    idleIntensity: 1.0
  };

  const updateAnim = (updates: Partial<typeof anim>) => {
    if (!selId) return;
    store.updateElement(selId, {
      animation: { ...anim, ...updates }
    });
  };

  const triggerPreview = () => {
    if (!selId) return;
    const event = new CustomEvent('play-element-preview', { detail: { id: selId } });
    window.dispatchEvent(event);
  };

  // Handle global keydown for delete
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return;
      if ((e.key === 'Delete' || e.key === 'Backspace') && store.selectedId) {
        store.deleteElement(store.selectedId);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [store.selectedId]);

  const handleWheel = (e: React.WheelEvent<HTMLInputElement>, field: string, currentValue: any) => {
    if (!selId) return;
    const current = parseFloat(currentValue) || 0;
    const delta = e.deltaY < 0 ? 1 : -1;
    const step = e.shiftKey ? 10 : 1;
    store.updateElement(selId, { [field]: current + (delta * step) });
  };

  const addGenericElement = (type: 'text' | 'image' | 'rect' | 'circle') => {
    const id = `${type}_${Date.now()}`;
    const base = { id, x: 960, y: 540, visible: true, zIndex: 10 };
    
    if (type === 'text') {
      store.addElement({ ...base, type: 'text', text: 'New Text', fontSize: 48, color: '#ffffff' });
    } else if (type === 'image') {
      store.addElement({ ...base, type: 'image', width: 300, height: 300, src: '/static/player_placeholder.jpg' });
    } else if (type === 'rect') {
      store.addElement({ ...base, type: 'rect', width: 400, height: 200, color: 'rgba(0,0,0,0.5)', borderRadius: 0 });
    } else if (type === 'circle') {
      store.addElement({ ...base, type: 'circle', width: 200, height: 200, color: 'rgba(0,255,255,0.5)', borderRadius: 100 });
    }
  };

  return (
    <div 
      className={`bg-[#2b2b2b] flex flex-col h-screen text-white text-[13px] transition-all duration-300 ease-in-out relative ${
        isCollapsed ? 'w-[64px] min-w-[64px] items-center px-2' : 'w-[360px] min-w-[360px] p-4'
      } overflow-y-auto overflow-x-hidden`}
    >
      <button 
        className={`absolute top-4 right-4 text-[#00ffcc] hover:text-white transition-transform duration-300 z-10 flex items-center justify-center w-8 h-8 rounded bg-[#333] hover:bg-[#444]`}
        style={{ transform: isCollapsed ? 'rotate(180deg)' : 'rotate(0deg)' }}
        onClick={() => setIsCollapsed(!isCollapsed)}
        title="Toggle Sidebar"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M15 18l-6-6 6-6" />
        </svg>
      </button>

      {/* COLLAPSED VIEW: Only Icons */}
      {isCollapsed && (
        <div className="flex flex-col gap-8 mt-16 items-center w-full">
          <button title="Design Elements" onClick={() => setIsCollapsed(false)} className="text-2xl hover:scale-110 transition-transform">🎨</button>
          <button title="Add Logic Elements" onClick={() => setIsCollapsed(false)} className="text-2xl hover:scale-110 transition-transform">➕</button>
          <button title="Element Settings" onClick={() => setIsCollapsed(false)} className="text-2xl hover:scale-110 transition-transform">✏️</button>
          <div className="flex-grow"></div>
          <button title="Push to OBS" onClick={onPush} className="text-2xl hover:scale-110 transition-transform mb-4">⬆️</button>
        </div>
      )}

      {/* EXPANDED VIEW: Full Form */}
      <div className={`flex flex-col w-full transition-opacity duration-300 ${isCollapsed ? 'opacity-0 hidden' : 'opacity-100'}`}>
        
        <h2 className="text-[#00ffcc] uppercase tracking-wide mb-3 font-bold mt-10">Add Elements</h2>
        <div className="grid grid-cols-2 gap-2 mb-3">
          <button onClick={() => addGenericElement('text')} className="bg-[#3a3a3a] hover:bg-[#444] border border-[#555] rounded py-2 text-center text-xs font-bold">📄 Add Text</button>
          <button onClick={() => addGenericElement('image')} className="bg-[#3a3a3a] hover:bg-[#444] border border-[#555] rounded py-2 text-center text-xs font-bold">🖼️ Add Image</button>
          <button onClick={() => addGenericElement('rect')} className="bg-[#3a3a3a] hover:bg-[#444] border border-[#555] rounded py-2 text-center text-xs font-bold">⬛ Add Rect</button>
          <button onClick={() => addGenericElement('circle')} className="bg-[#3a3a3a] hover:bg-[#444] border border-[#555] rounded py-2 text-center text-xs font-bold">⚪ Add Circle</button>
        </div>
        <hr className="border-[#3a3a3a] my-3" />

        <h2 className="text-[#00ffcc] uppercase tracking-wide mb-3 font-bold">Live Data Hooks</h2>
        <div className="flex gap-2 mb-3">
          <select className="flex-1 bg-[#3a3a3a] border border-[#555] rounded px-2 py-1.5 focus:border-[#00ffcc] outline-none" value={addId} onChange={e => setAddId(e.target.value)}>
            <option value="">-- Select Data Field --</option>
            {['p1_name', 'p2_name', 'p1_score', 'p2_score', 'p1_team', 'p2_team', 'tournament_round', 'tournament_name', 'p1_avatar', 'p2_avatar', 'p1_flag', 'p2_flag']
              .filter(id => !store.elements[id] || !store.elements[id].visible)
              .map((id) => (
                <option key={id} value={id}>{id}</option>
            ))}
          </select>
          <button 
            className="bg-[#00ffcc] text-[#111] font-bold px-3 rounded hover:bg-[#00d4aa]" 
            onClick={() => { if (addId) store.restoreElement(addId); }}
          >+ Add</button>
        </div>
        <hr className="border-[#3a3a3a] my-3" />

        <h2 className="text-[#00ffcc] uppercase tracking-wide mb-3 font-bold">Element Properties</h2>
        {!selEl || !selId ? (
          <p className="text-[#666] text-[12px]">Click an element on the canvas to edit properties.</p>
        ) : (
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

            {/* Element Animation Controls */}
            <div className="mb-3 p-2 bg-[#333] rounded border border-[#444]">
              <div className="flex justify-between items-center mb-2">
                <h4 className="text-[11px] text-[#00ffcc] uppercase tracking-wider font-bold">Animation</h4>
                <button
                  onClick={triggerPreview}
                  className="bg-[#00ffcc] text-[#111] hover:bg-[#00d4aa] px-2 py-0.5 rounded text-[10px] font-bold flex items-center gap-1 transition-all"
                  title="Play preview in canvas"
                >
                  ▶ Play Preview
                </button>
              </div>

              {/* Row 1: Animation type & Direction */}
              <div className="grid grid-cols-2 gap-2 mb-2">
                <div>
                  <label className="text-[10px] text-[#999] block mb-1">Animation</label>
                  <select
                    className="w-full bg-[#222] border border-[#555] rounded px-2 py-1 text-xs text-white outline-none focus:border-[#00ffcc]"
                    value={anim.animationType}
                    onChange={(e) => updateAnim({ animationType: e.target.value as any })}
                  >
                    <option value="none">None</option>
                    <option value="fly-in">Fly In</option>
                    <option value="float-in">Float In</option>
                    <option value="fade-in">Fade In</option>
                  </select>
                </div>
                <div>
                  <label className="text-[10px] text-[#999] block mb-1">Direction</label>
                  <select
                    className="w-full bg-[#222] border border-[#555] rounded px-2 py-1 text-xs text-white outline-none focus:border-[#00ffcc]"
                    value={anim.direction}
                    onChange={(e) => updateAnim({ direction: e.target.value as any })}
                  >
                    <option value="bottom">⬇ Bottom</option>
                    <option value="bottom-left">⬃ Bottom-Left</option>
                    <option value="left">⬅ Left</option>
                    <option value="top-left">⬁ Top-Left</option>
                    <option value="top">⬆ Top</option>
                    <option value="top-right">⬀ Top-Right</option>
                    <option value="right">➡ Right</option>
                    <option value="bottom-right">⬂ Bottom-Right</option>
                    <option value="in-place">● In Place</option>
                  </select>
                </div>
              </div>

              {/* Row 2: Duration & Idle Animation */}
              <div className="grid grid-cols-2 gap-2 mb-2">
                <div>
                  <label className="text-[10px] text-[#999] block mb-1">Duration (ms)</label>
                  <input
                    type="number"
                    min="0"
                    step="50"
                    className="w-full bg-[#222] border border-[#555] rounded px-2 py-1 text-xs text-white outline-none focus:border-[#00ffcc]"
                    value={anim.duration}
                    onChange={(e) => updateAnim({ duration: Math.max(0, parseInt(e.target.value) || 0) })}
                  />
                </div>
                <div>
                  <label className="text-[10px] text-[#999] block mb-1">Idle Animation</label>
                  <select
                    className="w-full bg-[#222] border border-[#555] rounded px-2 py-1 text-xs text-white outline-none focus:border-[#00ffcc]"
                    value={anim.idleAnimation || 'none'}
                    onChange={(e) => {
                      const val = e.target.value as any;
                      updateAnim({
                        idleAnimation: val,
                        loop: val !== 'none' ? -1 : 0
                      });
                    }}
                  >
                    <option value="none">None</option>
                    <option value="bobbing">Bobbing</option>
                    <option value="pulsing">Pulsing</option>
                    <option value="hovering">Hovering</option>
                    <option value="spinning">Spinning</option>
                  </select>
                </div>
              </div>

              {/* Row 2.5: Idle Animation Intensity Slider */}
              {anim.idleAnimation && anim.idleAnimation !== 'none' && (
                <div className="mb-3 px-1">
                  <div className="flex justify-between items-center mb-1">
                    <label className="text-[10px] text-[#999]">Idle Intensity</label>
                    <span className="text-[10px] text-[#00ffcc] font-mono">{(anim.idleIntensity ?? 1.0).toFixed(2)}x</span>
                  </div>
                  <input
                    type="range"
                    min="0.1"
                    max="3.0"
                    step="0.1"
                    className="w-full accent-[#00ffcc] h-1 bg-[#333] rounded-lg appearance-none cursor-pointer"
                    value={anim.idleIntensity ?? 1.0}
                    onChange={(e) => updateAnim({ idleIntensity: parseFloat(e.target.value) })}
                  />
                </div>
              )}

              {/* Row 3: Delay & Tween (Easing) */}
              <div className="grid grid-cols-2 gap-2 mb-2">
                <div>
                  <label className="text-[10px] text-[#999] block mb-1">Delay (ms)</label>
                  <input
                    type="number"
                    min="0"
                    step="50"
                    className="w-full bg-[#222] border border-[#555] rounded px-2 py-1 text-xs text-white outline-none focus:border-[#00ffcc]"
                    value={anim.delay}
                    onChange={(e) => updateAnim({ delay: Math.max(0, parseInt(e.target.value) || 0) })}
                  />
                </div>
                <div>
                  <label className="text-[10px] text-[#999] block mb-1">Tween Type</label>
                  <select
                    className="w-full bg-[#222] border border-[#555] rounded px-2 py-1 text-xs text-white outline-none focus:border-[#00ffcc]"
                    value={anim.tweenType}
                    onChange={(e) => updateAnim({ tweenType: e.target.value as any })}
                  >
                    <option value="linear">Linear</option>
                    <option value="ease-in">Ease In</option>
                    <option value="ease-out">Ease Out</option>
                    <option value="ease-in-out">Ease In-Out</option>
                    <option value="bounce">Bounce</option>
                    <option value="back-out">Back Out</option>
                    <option value="elastic">Elastic</option>
                  </select>
                </div>
              </div>

              {/* Row 4: Trigger */}
              <div className="mb-2">
                <label className="text-[10px] text-[#999] block mb-1">Trigger Sequence</label>
                <select
                  className="w-full bg-[#222] border border-[#555] rounded px-2 py-1 text-xs text-white outline-none focus:border-[#00ffcc]"
                  value={anim.trigger}
                  onChange={(e) => updateAnim({ trigger: e.target.value as any })}
                >
                  <option value="on-load">On Load</option>
                  <option value="with-prev">With Previous</option>
                  <option value="after-prev">After Previous</option>
                </select>
              </div>

              {/* Text Specific: Reveal Style */}
              {selEl.type === 'text' && (
                <>
                  <div className="mb-2">
                    <label className="text-[10px] text-[#999] block mb-1">Text Reveal Style</label>
                    <select
                      className="w-full bg-[#222] border border-[#555] rounded px-2 py-1 text-xs text-white outline-none focus:border-[#00ffcc]"
                      value={anim.revealStyle || 'all'}
                      onChange={(e) => updateAnim({ revealStyle: e.target.value as any })}
                    >
                      <option value="all">All at once</option>
                      <option value="word">Word by Word</option>
                      <option value="letter">Letter by Letter</option>
                    </select>
                  </div>
                  {anim.revealStyle && anim.revealStyle !== 'all' && (
                    <div className="mb-2">
                      <div className="flex justify-between text-[10px] text-[#999] mb-1">
                        <span>Reveal Scale (Start)</span>
                        <span className="text-[#00ffcc] font-bold">{(anim.revealScale ?? 0.3).toFixed(2)}x</span>
                      </div>
                      <input
                        type="range"
                        min="0.0"
                        max="1.0"
                        step="0.05"
                        className="w-full h-1 bg-[#222] rounded-lg appearance-none cursor-pointer accent-[#00ffcc]"
                        value={anim.revealScale ?? 0.3}
                        onChange={(e) => updateAnim({ revealScale: parseFloat(e.target.value) })}
                      />
                    </div>
                  )}
                </>
              )}

              {/* Score Specific: Glitch Update Toggle */}
              {selEl.id?.includes('score') && (
                <>
                  <div className="flex items-center justify-between mb-2 p-1 bg-[#2b2b2b] rounded border border-[#444]">
                    <label className="text-[10px] text-[#999] cursor-pointer" htmlFor="score-glitch-toggle">Score Glitch Effect</label>
                    <input
                      id="score-glitch-toggle"
                      type="checkbox"
                      className="w-4 h-4 cursor-pointer accent-[#00ffcc]"
                      checked={anim.scoreGlitch || false}
                      onChange={(e) => updateAnim({ scoreGlitch: e.target.checked })}
                    />
                  </div>
                  {anim.scoreGlitch && (
                    <div className="mb-2 p-1 bg-[#2b2b2b] rounded border border-[#444] mt-[-4px]">
                      <div className="flex justify-between text-[10px] text-[#999] mb-1">
                        <span>Glitch Intensity (Scale)</span>
                        <span className="text-[#00ffcc] font-bold">{(anim.glitchScale ?? 1.15).toFixed(2)}x</span>
                      </div>
                      <input
                        type="range"
                        min="1.0"
                        max="2.0"
                        step="0.05"
                        className="w-full h-1 bg-[#222] rounded-lg appearance-none cursor-pointer accent-[#00ffcc]"
                        value={anim.glitchScale ?? 1.15}
                        onChange={(e) => updateAnim({ glitchScale: parseFloat(e.target.value) })}
                      />
                    </div>
                  )}
                </>
              )}

              {/* Play On Toggles */}
              <div>
                <label className="text-[10px] text-[#999] block mb-1">Play On</label>
                <div className="flex rounded border border-[#555] overflow-hidden">
                  {(['IN', 'BOTH', 'OUT'] as const).map((tab) => (
                    <button
                      key={tab}
                      onClick={() => updateAnim({ playOn: tab })}
                      className={`flex-1 py-1 text-[11px] font-bold transition-all ${
                        anim.playOn === tab
                          ? 'bg-[#00ffcc] text-[#111]'
                          : 'bg-[#3a3a3a] text-white hover:bg-[#444]'
                      }`}
                    >
                      {tab}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <button className="bg-[#ff4444] text-white font-bold py-2 rounded hover:bg-[#cc2222]" onClick={() => store.deleteElement(selId)}>🗑️ Remove Element</button>
          </div>
        )}
        <hr className="border-[#3a3a3a] my-4" />

        <button className="bg-[#00ffcc] text-[#111] font-bold py-3 rounded hover:bg-[#00d4aa] text-[14px]" onClick={onPush}>⬆ Push to OBS</button>
        <p className="text-[11px] text-[#888] text-center mt-3">{store.statusMsg}</p>
      </div>
    </div>
  );
}
