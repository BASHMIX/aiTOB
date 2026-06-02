import { useEditorStore } from '@/store/useEditorStore';

export function SidebarAnimation() {
  const store = useEditorStore();
  const selId = store.selectedId;
  const selEl = selId ? store.elements[selId] : null;

  if (!selEl || !selId) {
    return null;
  }

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

  return (
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
  );
}
