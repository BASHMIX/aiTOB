import { useEditorStore } from '@/store/useEditorStore';
import { AssetManager } from './AssetManager';

export function SidebarProperties() {
  const store = useEditorStore();
  const selId = store.selectedId;
  const selEl = selId ? store.elements[selId] : null;
  const selectedIds = store.selectedIds.length ? store.selectedIds : (selId ? [selId] : []);

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

  const updatePosition = (field: 'x' | 'y', value: number) => {
    if (!selectedIds.length || !selEl) return;
    const delta = value - (selEl[field] || 0);
    selectedIds.forEach((id) => {
      const element = store.elements[id];
      if (element) store.updateElement(id, { [field]: Math.round((element[field] || 0) + delta) });
    });
  };

  return (
    <div className="flex flex-col">
      <label className="text-[11px] text-[#999] uppercase tracking-wide mb-1 block">ID</label>
      <input className="w-full bg-[#222] border border-[#555] rounded px-2 py-1.5 mb-3 text-[#aaa]" readOnly value={selId} />

      {selEl.binding && (
        <div className="mb-3 rounded border border-[#00ffcc]/20 bg-[#00ffcc]/5 px-2.5 py-2">
          <div className="text-[9px] font-bold uppercase tracking-wider text-[#00ffcc]">Player Data Binding</div>
          <div className="mt-1 font-mono text-[11px] text-white/80">{selEl.binding}</div>
          <div className="mt-1 text-[9px] leading-relaxed text-white/45">Preview text or image below is used only when player data is unavailable.</div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-2 mb-3">
        {(['x', 'y'] as const).map((field) => (
          <label key={field} className="text-[11px] text-[#999] uppercase tracking-wide">
            {field} position
            <input
              type="number"
              className="w-full mt-1 bg-[#3a3a3a] border border-[#555] rounded px-2 py-1.5 text-xs text-white"
              value={Math.round(selEl[field] || 0)}
              onChange={(event) => updatePosition(field, parseFloat(event.target.value) || 0)}
              onWheel={(event) => {
                event.preventDefault();
                updatePosition(field, (selEl[field] || 0) + (event.deltaY < 0 ? (event.shiftKey ? 10 : 1) : -(event.shiftKey ? 10 : 1)));
              }}
            />
          </label>
        ))}
      </div>

      {selEl.type === 'result-card' && (
        <div className="mb-4 p-2.5 rounded border border-[#00ffcc]/30 bg-[#00ffcc]/5 space-y-3">
          <div className="text-[10px] font-bold uppercase tracking-wider text-[#00ffcc] flex items-center justify-between">
            <span className="flex items-center gap-1.5">🪪 Player Result Card</span>
            <span className="text-[9px] px-1.5 py-0.5 rounded bg-[#00ffcc]/20 text-[#00ffcc] font-mono">
              Placement #{selEl.standingOrdinal || 1}
            </span>
          </div>

          <button
            type="button"
            onClick={() => selEl.definitionId && store.enterResultCardDesign(selEl.definitionId)}
            className="w-full rounded border border-[#00ffcc]/40 bg-[#00ffcc]/15 px-3 py-2 text-xs font-black text-[#00ffcc] hover:bg-[#00ffcc]/25 transition-all text-center flex items-center justify-center gap-1.5"
          >
            <span>✏️</span> Edit Card Design &amp; Layout
          </button>

          {/* Placement Selector */}
          <div>
            <label className="text-[10px] text-white/70 uppercase tracking-wide block mb-1">
              Standing Placement (المركز)
            </label>
            <select
              value={selEl.standingOrdinal || 1}
              onChange={(e) => store.updateElement(selId, { standingOrdinal: Number(e.target.value) })}
              className="w-full bg-[#252525] border border-white/15 rounded px-2 py-1 text-xs text-white font-bold"
            >
              <option value={1}>1st Place (Champion / البطل)</option>
              <option value={2}>2nd Place (Runner-up / الوصيف)</option>
              <option value={3}>3rd Place (المركز الثالث)</option>
              <option value={4}>4th Place (المركز الرابع)</option>
              <option value={5}>5th Place · Tie 1 (الخامس)</option>
              <option value={6}>5th Place · Tie 2 (الخامس مكرر)</option>
              <option value={7}>7th Place · Tie 1 (السابع)</option>
              <option value={8}>7th Place · Tie 2 (السابع مكرر)</option>
            </select>
          </div>

          {/* 1-Click Themes */}
          <div>
            <label className="text-[10px] text-white/70 uppercase tracking-wide block mb-1">
              Card Color Theme
            </label>
            <div className="grid grid-cols-5 gap-1">
              {[
                { id: 'crimson', label: 'Crimson', icon: '🔴', accent: '#ef4444', cardBg: '#18181b', border: 'rgba(239, 68, 68, 0.45)', badge: '#ef4444', prefix: '#f87171' },
                { id: 'royal-blue', label: 'Royal', icon: '🔵', accent: '#3b82f6', cardBg: '#0f172a', border: 'rgba(59, 130, 246, 0.45)', badge: '#3b82f6', prefix: '#60a5fa' },
                { id: 'cyber-gold', label: 'Gold', icon: '🟡', accent: '#f59e0b', cardBg: '#18140e', border: 'rgba(245, 158, 11, 0.45)', badge: '#f59e0b', prefix: '#fbbf24' },
                { id: 'emerald', label: 'Emerald', icon: '🟢', accent: '#10b981', cardBg: '#061e18', border: 'rgba(16, 185, 129, 0.45)', badge: '#10b981', prefix: '#34d399' },
                { id: 'monochrome', label: 'Mono', icon: '⚪', accent: '#ffffff', cardBg: '#121214', border: 'rgba(255, 255, 255, 0.35)', badge: '#e4e4e7', prefix: '#ffffff' },
              ].map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => {
                    store.takeSnapshot();
                    store.updateElement(selId, { themePreset: t.id, accentColor: t.accent });
                    const defId = selEl.definitionId;
                    if (defId && store.elements[defId]) {
                      const def = store.elements[defId];
                      const next = { ...store.elements };
                      (def.childIds || []).forEach((cId) => {
                        const child = next[cId];
                        if (!child) return;
                        if (child.type === 'rect' && (child.name?.toLowerCase().includes('background') || child.id.includes('_bg_') || child.id === 'mc-bg')) {
                          next[cId] = { ...child, color: t.cardBg, strokeColor: t.border };
                        } else if (child.type === 'rect' && (child.name?.toLowerCase().includes('badge') || child.id.includes('_badge_') || child.id === 'mc-placement-badge')) {
                          next[cId] = { ...child, color: t.badge };
                        } else if (child.type === 'text' && (child.binding === 'prefix' || child.id.includes('_prefix_') || child.id === 'mc-prefix-text')) {
                          next[cId] = { ...child, color: t.prefix };
                        }
                      });
                      store.setElements(next);
                    }
                  }}
                  className={`py-1 px-1 rounded text-[10px] font-bold border transition-all text-center flex flex-col items-center gap-0.5 ${
                    selEl.themePreset === t.id
                      ? 'border-white text-white shadow-md bg-white/20'
                      : 'border-white/10 bg-[#1b1b1b] text-white/70 hover:text-white hover:bg-white/10'
                  }`}
                >
                  <span className="text-xs">{t.icon}</span>
                  <span className="text-[9px]">{t.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Card Animation */}
          <div>
            <label className="text-[10px] text-white/70 uppercase tracking-wide block mb-1">
              Card Animation (حركة الدخول)
            </label>
            <div className="grid grid-cols-4 gap-1">
              {[
                { id: 'deal', label: 'Deal', icon: '🃏', type: 'fly-in', dir: 'left', dur: 450, tween: 'ease-out' },
                { id: 'slam', label: 'Slam', icon: '💥', type: 'fly-in', dir: 'top', dur: 380, tween: 'bounce' },
                { id: 'flip', label: 'Flip', icon: '🔄', type: 'fly-in', dir: 'bottom', dur: 480, tween: 'back-out' },
                { id: 'float', label: 'Float', icon: '☁️', type: 'float-in', dir: 'bottom', dur: 500, tween: 'ease-out' },
                { id: 'hologram', label: 'Holo', icon: '⚡', type: 'fade-in', dir: 'in-place', dur: 400, tween: 'linear' },
                { id: 'energy', label: 'Energy', icon: '🔮', type: 'fly-in', dir: 'bottom-left', dur: 600, tween: 'elastic' },
                { id: 'none', label: 'Static', icon: '⏸️', type: 'none', dir: 'in-place', dur: 0, tween: 'linear' },
              ].map((a) => (
                <button
                  key={a.id}
                  type="button"
                  onClick={() => {
                    store.takeSnapshot();
                    const animPayload = {
                      animationType: a.type as any,
                      direction: a.dir as any,
                      duration: a.dur,
                      tweenType: a.tween as any,
                      delay: 0,
                      loop: 0,
                      playOn: 'IN' as const,
                      trigger: 'on-load' as const,
                    };
                    store.updateElement(selId, { animation: animPayload, cardAnimationPreset: a.id });
                    if (selEl.definitionId) {
                      store.updateElement(selEl.definitionId, { animation: animPayload });
                    }
                    window.dispatchEvent(new CustomEvent('play-slide-preview', { detail: { id: selId } }));
                  }}
                  className={`py-1 px-1 rounded text-[9px] font-bold border transition-all text-center flex items-center justify-center gap-1 ${
                    selEl.cardAnimationPreset === a.id
                      ? 'border-[#00ffcc] text-[#00ffcc] bg-[#00ffcc]/15 shadow-sm font-black'
                      : 'border-white/10 bg-[#1b1b1b] text-white/70 hover:text-white hover:bg-white/10'
                  }`}
                >
                  <span>{a.icon}</span>
                  <span>{a.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Image Roles & Layout */}
          <div className="space-y-2 pt-2 border-t border-white/10 mb-3">
            <div className="flex items-center justify-between">
              <label className="text-[10px] text-white/70 uppercase tracking-wide">
                🖼️ Image Roles (توزيع الصور)
              </label>
              <button
                type="button"
                onClick={() => {
                  store.takeSnapshot();
                  const curLarge = selEl.largeImageSource || 'character';
                  const curSmall = selEl.smallImageSource || 'player';
                  store.updateElement(selId, {
                    largeImageSource: curSmall,
                    smallImageSource: curLarge,
                  });
                }}
                className="px-2 py-0.5 rounded bg-sky-600 hover:bg-sky-500 text-white text-[10px] font-bold flex items-center gap-1 transition-all shadow-sm"
              >
                <span>⇄</span> Swap
              </button>
            </div>

            <div className="space-y-1">
              <span className="text-[9px] text-white/60">Large Image (الكبيرة)</span>
              <div className="grid grid-cols-2 gap-1">
                <button
                  type="button"
                  onClick={() => store.updateElement(selId, { largeImageSource: 'character' })}
                  className={`py-1 px-1.5 rounded text-[10px] font-bold border transition-all ${
                    (selEl.largeImageSource || 'character') === 'character'
                      ? 'border-sky-400 bg-sky-500/20 text-sky-300 font-black'
                      : 'border-white/10 bg-[#252525] text-white/60 hover:text-white'
                  }`}
                >
                  🎮 Character
                </button>
                <button
                  type="button"
                  onClick={() => store.updateElement(selId, { largeImageSource: 'player' })}
                  className={`py-1 px-1.5 rounded text-[10px] font-bold border transition-all ${
                    selEl.largeImageSource === 'player'
                      ? 'border-sky-400 bg-sky-500/20 text-sky-300 font-black'
                      : 'border-white/10 bg-[#252525] text-white/60 hover:text-white'
                  }`}
                >
                  👤 Player
                </button>
              </div>
            </div>

            <div className="rounded border border-white/10 bg-black/20 p-1.5 space-y-1.5">
              <label className="flex items-center justify-between cursor-pointer text-[10px] text-white/80">
                <span className="flex items-center gap-1.5">
                  <input
                    type="checkbox"
                    checked={selEl.showSmallImage !== false}
                    onChange={(e) => store.updateElement(selId, { showSmallImage: e.target.checked })}
                    className="rounded accent-sky-400 cursor-pointer"
                  />
                  <span>Show Small Image</span>
                </span>
                <span className="text-[9px] text-gray-400">
                  {selEl.showSmallImage === false ? '❌ معطلة' : '✔️ مفعلة'}
                </span>
              </label>

              {selEl.showSmallImage !== false && (
                <div className="grid grid-cols-2 gap-1 pt-1 border-t border-white/5">
                  <button
                    type="button"
                    onClick={() => store.updateElement(selId, { smallImageSource: 'player' })}
                    className={`py-1 px-1 rounded text-[9px] font-bold border transition-all ${
                      (selEl.smallImageSource || 'player') === 'player'
                        ? 'border-emerald-400 bg-emerald-500/20 text-emerald-300 font-black'
                        : 'border-white/10 bg-[#252525] text-white/60 hover:text-white'
                    }`}
                  >
                    👤 Player
                  </button>
                  <button
                    type="button"
                    onClick={() => store.updateElement(selId, { smallImageSource: 'character' })}
                    className={`py-1 px-1 rounded text-[9px] font-bold border transition-all ${
                      selEl.smallImageSource === 'character'
                        ? 'border-emerald-400 bg-emerald-500/20 text-emerald-300 font-black'
                        : 'border-white/10 bg-[#252525] text-white/60 hover:text-white'
                    }`}
                  >
                    🎮 Character
                  </button>
                </div>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 pt-2 border-t border-white/10">
            <label className="text-[10px] text-white/55">Width
              <input type="number" min="1" value={Math.round(selEl.width || 420)} onChange={(event) => store.updateElement(selId, { width: Math.max(1, Number(event.target.value)) })} className="mt-1 w-full rounded border border-white/15 bg-[#252525] px-2 py-1.5 text-xs text-white" />
            </label>
            <label className="text-[10px] text-white/55">Height
              <input type="number" min="1" value={Math.round(selEl.height || 560)} onChange={(event) => store.updateElement(selId, { height: Math.max(1, Number(event.target.value)) })} className="mt-1 w-full rounded border border-white/15 bg-[#252525] px-2 py-1.5 text-xs text-white" />
            </label>
            <label className="text-[10px] text-white/55">Rotation
              <input type="number" step="1" value={selEl.rotation || 0} onChange={(event) => store.updateElement(selId, { rotation: Number(event.target.value) })} className="mt-1 w-full rounded border border-white/15 bg-[#252525] px-2 py-1.5 text-xs text-white" />
            </label>
            <label className="text-[10px] text-white/55">Opacity
              <input type="number" min="0" max="1" step="0.05" value={selEl.opacity ?? 1} onChange={(event) => store.updateElement(selId, { opacity: Math.max(0, Math.min(1, Number(event.target.value))) })} className="mt-1 w-full rounded border border-white/15 bg-[#252525] px-2 py-1.5 text-xs text-white" />
            </label>
          </div>
        </div>
      )}

      {selEl.type === 'match-grid' && (
        <div className="mb-4 p-2.5 rounded border border-[#00ffcc]/30 bg-[#00ffcc]/5">
          <div className="text-[10px] font-bold uppercase tracking-wider text-[#00ffcc] mb-2 flex items-center gap-1.5">
            <span>🎮</span> Match Matrix Settings
          </div>

          {/* Card / Box Animation (حركة وتأثيرات المربعات) */}
          <div className="mb-3">
            <div className="flex items-center justify-between mb-1">
              <label className="text-[10px] text-white/70 uppercase tracking-wide">
                Box Animation (حركة المربعات)
              </label>
              <span className="text-[9px] font-mono text-[#00ffcc] font-bold">
                {selEl.matrixCardAnimation || 'deal'}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-1">
              {[
                { id: 'deal', label: '🃏 Deal (سحب الكروت)' },
                { id: 'slam', label: '💥 Slam (ضربة قتالية)' },
                { id: 'flip', label: '🔄 3D Flip (انقلاب)' },
                { id: 'float', label: '✨ 3D Float (طوفان)' },
                { id: 'hologram', label: '⚡ Hologram (سايبر)' },
                { id: 'glow-pulse', label: '🔥 Energy (طاقة)' },
                { id: 'none', label: '⏸️ Static (ثابت)' },
              ].map((anim) => (
                <button
                  key={anim.id}
                  type="button"
                  onClick={() => store.updateElement(selId, { matrixCardAnimation: anim.id as any })}
                  className={`py-1 px-1.5 rounded text-[10px] font-bold transition-all text-center ${
                    (selEl.matrixCardAnimation || 'deal') === anim.id
                      ? 'bg-[#00ffcc] text-slate-950 shadow-sm font-black'
                      : 'bg-[#252525] text-white/70 hover:bg-[#333]'
                  }`}
                >
                  {anim.label}
                </button>
              ))}
            </div>
          </div>

          {/* 1-Click Unified Theme Presets for Match Matrix */}
          <label className="text-[10px] text-white/70 uppercase tracking-wide block mb-1">Theme Presets</label>
          <div className="grid grid-cols-5 gap-1 mb-3">
            {[
              { id: 'crimson', label: 'Crimson', icon: '🔴', accent: '#ef4444', wonBg: 'rgba(239, 68, 68, 0.22)', border: 'rgba(239, 68, 68, 0.45)', bg: 'rgba(24, 24, 27, 0.88)', highlight: '#f87171' },
              { id: 'royal-blue', label: 'Royal', icon: '🔵', accent: '#3b82f6', wonBg: 'rgba(59, 130, 246, 0.22)', border: 'rgba(59, 130, 246, 0.45)', bg: 'rgba(15, 23, 42, 0.88)', highlight: '#60a5fa' },
              { id: 'cyber-gold', label: 'Gold', icon: '🟡', accent: '#f59e0b', wonBg: 'rgba(245, 158, 11, 0.22)', border: 'rgba(245, 158, 11, 0.45)', bg: 'rgba(24, 20, 14, 0.88)', highlight: '#fbbf24' },
              { id: 'emerald', label: 'Emerald', icon: '🟢', accent: '#10b981', wonBg: 'rgba(16, 185, 129, 0.22)', border: 'rgba(16, 185, 129, 0.45)', bg: 'rgba(6, 30, 24, 0.88)', highlight: '#34d399' },
              { id: 'monochrome', label: 'Mono', icon: '⚪', accent: '#ffffff', wonBg: 'rgba(255, 255, 255, 0.22)', border: 'rgba(255, 255, 255, 0.35)', bg: 'rgba(18, 18, 20, 0.88)', highlight: '#ffffff' },
            ].map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() =>
                  store.updateElement(selId, {
                    matrixThemePreset: t.id as any,
                    wonColor: t.accent,
                    wonBgColor: t.wonBg,
                    boxBorderColor: t.border,
                    boxBgColor: t.bg,
                    currentHighlightColor: t.highlight,
                  })
                }
                className={`py-1.5 px-1 rounded text-[10px] font-bold transition-all text-center flex flex-col items-center justify-center gap-0.5 border ${
                  selEl.matrixThemePreset === t.id
                    ? 'border-white text-white shadow-md bg-white/10'
                    : 'border-transparent bg-[#252525] text-white/60 hover:text-white hover:bg-[#333]'
                }`}
                title={t.label}
              >
                <span>{t.icon}</span>
                <span className="text-[9px] truncate">{t.label}</span>
              </button>
            ))}
          </div>

          <label className="text-[10px] text-white/70 uppercase tracking-wide block mb-1">Format / Games Mode</label>
          <div className="grid grid-cols-3 gap-1 mb-3">
            {[
              { id: 'auto', label: 'Auto (Live)' },
              { id: 'ft2', label: 'FT2 (3)' },
              { id: 'ft3', label: 'FT3 (5)' },
              { id: 'ft5', label: 'FT5 (9)' },
              { id: 'ft7', label: 'FT7 (13)' },
            ].map((fmt) => (
              <button
                key={fmt.id}
                type="button"
                onClick={() => store.updateElement(selId, { formatMode: fmt.id as any })}
                className={`py-1 px-1.5 rounded text-[10px] font-bold transition-all ${
                  (selEl.formatMode || 'auto') === fmt.id
                    ? 'bg-[#00ffcc] text-black shadow-[0_0_8px_rgba(0,255,204,0.5)]'
                    : 'bg-[#252525] text-white/70 hover:bg-[#333] border border-white/10'
                }`}
              >
                {fmt.label}
              </button>
            ))}
          </div>

          <label className="text-[10px] text-white/70 uppercase tracking-wide block mb-1">Win Marker Style</label>
          <div className="grid grid-cols-4 gap-1 mb-3">
            {[
              { id: 'check', label: '✓ Check' },
              { id: 'solid', label: '█ Solid' },
              { id: 'dot', label: '⬤ Dot' },
              { id: 'image', label: '🖼️ Icon' },
            ].map((st) => (
              <button
                key={st.id}
                type="button"
                onClick={() => store.updateElement(selId, { winMarkerStyle: st.id as any })}
                className={`py-1 px-1 rounded text-[10px] font-bold transition-all ${
                  (selEl.winMarkerStyle || 'check') === st.id
                    ? 'bg-amber-400 text-black shadow-[0_0_8px_rgba(245,158,11,0.5)]'
                    : 'bg-[#252525] text-white/70 hover:bg-[#333] border border-white/10'
                }`}
              >
                {st.label}
              </button>
            ))}
          </div>

          {selEl.winMarkerStyle === 'image' && (
            <div className="mb-3 p-2 bg-[#1a233a] rounded border border-amber-400/40">
              <div className="text-[10px] font-bold uppercase tracking-wider text-amber-300 mb-1.5">
                🖼️ Custom Icon Image & Offset
              </div>

              <label className="text-[9px] text-white/70 uppercase tracking-wide block mb-1">Choose Asset</label>
              <div className="mb-2">
                <AssetManager onSelect={(url) => store.updateElement(selId, { customMarkerUrl: url })} />
              </div>

              <label className="text-[9px] text-white/70 uppercase tracking-wide block mb-1">Image URL / Path</label>
              <input
                type="text"
                className="w-full bg-[#111827] border border-white/15 rounded px-2 py-1 text-xs text-white font-mono mb-2"
                value={selEl.customMarkerUrl || ''}
                onChange={(e) => store.updateElement(selId, { customMarkerUrl: e.target.value })}
                placeholder="https://... or /static/... or data:image/..."
              />

              <div className="grid grid-cols-2 gap-2 mb-2">
                <label className="text-[9px] text-white/70">
                  Icon Width (px)
                  <input
                    type="number"
                    min="8"
                    max="120"
                    className="w-full mt-0.5 bg-[#111827] border border-white/15 rounded px-2 py-1 text-xs text-white"
                    value={selEl.markerWidth || 32}
                    onChange={(e) => store.updateElement(selId, { markerWidth: parseFloat(e.target.value) || 32 })}
                  />
                </label>
                <label className="text-[9px] text-white/70">
                  Icon Height (px)
                  <input
                    type="number"
                    min="8"
                    max="120"
                    className="w-full mt-0.5 bg-[#111827] border border-white/15 rounded px-2 py-1 text-xs text-white"
                    value={selEl.markerHeight || 32}
                    onChange={(e) => store.updateElement(selId, { markerHeight: parseFloat(e.target.value) || 32 })}
                  />
                </label>
              </div>

              <div className="grid grid-cols-2 gap-2 mb-1">
                <label className="text-[10px] text-amber-300 font-bold">
                  Offset X (px)
                  <input
                    type="number"
                    className="w-full mt-0.5 bg-[#111827] border border-amber-400/50 rounded px-2 py-1 text-xs text-white font-mono"
                    value={selEl.markerOffsetX || 0}
                    onChange={(e) => store.updateElement(selId, { markerOffsetX: parseFloat(e.target.value) || 0 })}
                  />
                </label>
                <label className="text-[10px] text-amber-300 font-bold">
                  Offset Y (px)
                  <input
                    type="number"
                    className="w-full mt-0.5 bg-[#111827] border border-amber-400/50 rounded px-2 py-1 text-xs text-white font-mono"
                    value={selEl.markerOffsetY || 0}
                    onChange={(e) => store.updateElement(selId, { markerOffsetY: parseFloat(e.target.value) || 0 })}
                  />
                </label>
              </div>
              <p className="mt-1 text-[9px] text-white/45 leading-tight">
                Adjust Offset X & Y to position the icon perfectly over the cell!
              </p>
            </div>
          )}

          <label className="text-[10px] text-white/70 uppercase tracking-wide block mb-1">Checkmark / Won Color</label>
          <div className="flex gap-2 mb-3 items-center">
            <input
              type="color"
              className="w-10 h-8 p-0.5 bg-[#252525] border border-white/20 rounded cursor-pointer"
              value={selEl.wonColor?.startsWith('#') ? selEl.wonColor : '#f59e0b'}
              onChange={(e) => store.updateElement(selId, { wonColor: e.target.value })}
            />
            <input
              type="text"
              className="flex-1 bg-[#252525] border border-white/15 rounded px-2 py-1 text-xs text-white font-mono"
              value={selEl.wonColor || '#f59e0b'}
              onChange={(e) => store.updateElement(selId, { wonColor: e.target.value })}
            />
          </div>

          <label className="text-[10px] text-white/70 uppercase tracking-wide block mb-1">Box Border Color</label>
          <input
            type="text"
            className="w-full bg-[#252525] border border-white/15 rounded px-2 py-1 text-xs text-white font-mono mb-3"
            value={selEl.boxBorderColor || 'rgba(56, 189, 248, 0.35)'}
            onChange={(e) => store.updateElement(selId, { boxBorderColor: e.target.value })}
            placeholder="rgba(56, 189, 248, 0.35)"
          />

          <label className="text-[10px] text-white/70 uppercase tracking-wide block mb-1">Box Background Color</label>
          <input
            type="text"
            className="w-full bg-[#252525] border border-white/15 rounded px-2 py-1 text-xs text-white font-mono mb-3"
            value={selEl.boxBgColor || 'rgba(12, 20, 44, 0.85)'}
            onChange={(e) => store.updateElement(selId, { boxBgColor: e.target.value })}
            placeholder="rgba(12, 20, 44, 0.85)"
          />

          <div className="pt-2 border-t border-white/10 flex gap-2">
            <button
              type="button"
              onClick={() => store.updateElement(selId, { gamesHistoryOverride: ['p1', 'p2', 'p2', 'p2', 'p1', 'p2', null, null, null] })}
              className="flex-1 bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 rounded py-1 text-[10px] font-bold"
              title="Apply 2 - 4 sample result"
            >
              ⭐ Sample (2-4)
            </button>
            <button
              type="button"
              onClick={() => store.updateElement(selId, { gamesHistoryOverride: Array(13).fill(null) })}
              className="flex-1 bg-white/10 hover:bg-white/20 text-white/80 border border-white/15 rounded py-1 text-[10px] font-bold"
            >
              🔄 Reset
            </button>
          </div>
          <p className="mt-1.5 text-[9px] text-white/45 leading-tight">
            Tip: Click directly on any box on the canvas to toggle P1 / P2 win!
          </p>
        </div>
      )}

      {selEl.type === 'bracket-tree' && (
        <div className="mb-4 p-2.5 rounded border border-amber-500/40 bg-amber-500/5">
          <div className="text-[10px] font-bold uppercase tracking-wider text-amber-400 mb-2 flex items-center justify-between">
            <span className="flex items-center gap-1.5">👑 Bracket Tree Settings</span>
            <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 font-mono">
              {selEl.bracketLayoutVariant || 'top8-double-elim'}
            </span>
          </div>

          <label className="text-[10px] text-white/70 uppercase tracking-wide block mb-1">Layout Presentation</label>
          <div className="grid grid-cols-2 gap-1 mb-3">
            {[
              { id: 'top8-double-elim', label: 'Top 8 Double-Elim' },
              { id: 'top4-showcase', label: 'Dynamic Top 8' },
            ].map((v) => (
              <button
                key={v.id}
                type="button"
                onClick={() => store.updateElement(selId, { bracketLayoutVariant: v.id as any })}
                className={`py-1.5 px-2 rounded text-[11px] font-bold transition-all text-center ${
                  (selEl.bracketLayoutVariant || 'top8-double-elim') === v.id
                    ? 'bg-amber-500 text-slate-950 shadow-sm'
                    : 'bg-[#252525] text-white/70 hover:bg-[#333]'
                }`}
              >
                {v.label}
              </button>
            ))}
          </div>

          {/* Card Animation (حركة وتأثيرات كروت اللاعبين) */}
          <div className="mb-3">
            <div className="flex items-center justify-between mb-1">
              <label className="text-[10px] text-white/70 uppercase tracking-wide">
                Card Animation (حركة الكروت)
              </label>
              <span className="text-[9px] font-mono text-amber-300 font-bold">
                {selEl.bracketCardAnimation || 'deal'}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-1">
              {[
                { id: 'deal', label: '🃏 Deal (سحب الكروت)' },
                { id: 'slam', label: '💥 Slam (ضربة قتالية)' },
                { id: 'flip', label: '🔄 3D Flip (انقلاب)' },
                { id: 'float', label: '✨ 3D Float (طوفان)' },
                { id: 'hologram', label: '⚡ Hologram (سايبر)' },
                { id: 'glow-pulse', label: '🔥 Energy (طاقة)' },
                { id: 'none', label: '⏸️ Static (ثابت)' },
              ].map((anim) => (
                <button
                  key={anim.id}
                  type="button"
                  onClick={() => store.updateElement(selId, { bracketCardAnimation: anim.id as any })}
                  className={`py-1 px-1.5 rounded text-[10px] font-bold transition-all text-center ${
                    (selEl.bracketCardAnimation || 'deal') === anim.id
                      ? 'bg-amber-500 text-slate-950 shadow-sm font-black'
                      : 'bg-[#252525] text-white/70 hover:bg-[#333]'
                  }`}
                >
                  {anim.label}
                </button>
              ))}
            </div>
          </div>

          {selEl.bracketLayoutVariant === 'top4-showcase' && (
            <div className="mb-3">
              <label className="text-[10px] text-white/70 uppercase tracking-wide block mb-1">
                Showcase Stage Mode (طور العرض)
              </label>
              <div className="grid grid-cols-2 gap-1">
                {[
                  { id: 'auto', label: '⚡ Auto (تلقائي)' },
                  { id: 'opening_top8', label: '🥊 Top 8 (4 ضد 4)' },
                  { id: 'final4', label: '🔥 Final 4 (الأربعة)' },
                  { id: 'grand_finals', label: '👑 Grand Finals' },
                ].map((st) => (
                  <button
                    key={st.id}
                    type="button"
                    onClick={() => store.updateElement(selId, { top4StageMode: st.id as any })}
                    className={`py-1 px-1.5 rounded text-[10px] font-bold transition-all text-center ${
                      (selEl.top4StageMode || 'auto') === st.id
                        ? 'bg-amber-500 text-slate-950 shadow-sm'
                        : 'bg-[#252525] text-white/70 hover:bg-[#333]'
                    }`}
                  >
                    {st.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* 1-Click Unified Theme Presets */}
          <label className="text-[10px] text-white/70 uppercase tracking-wide block mb-1">Theme Presets</label>
          <div className="grid grid-cols-5 gap-1 mb-3">
            {[
              { id: 'crimson', label: 'Crimson', icon: '🔴', accent: '#ef4444', cardBg: '#18181b', border: 'rgba(239, 68, 68, 0.4)', line: '#ef4444', header: '#991b1b' },
              { id: 'royal-blue', label: 'Royal', icon: '🔵', accent: '#3b82f6', cardBg: '#0f172a', border: 'rgba(59, 130, 246, 0.4)', line: '#60a5fa', header: '#1e40af' },
              { id: 'cyber-gold', label: 'Gold', icon: '🟡', accent: '#f59e0b', cardBg: '#18140e', border: 'rgba(245, 158, 11, 0.4)', line: '#f59e0b', header: '#b45309' },
              { id: 'emerald', label: 'Emerald', icon: '🟢', accent: '#10b981', cardBg: '#061e18', border: 'rgba(16, 185, 129, 0.4)', line: '#34d399', header: '#065f46' },
              { id: 'monochrome', label: 'Mono', icon: '⚪', accent: '#ffffff', cardBg: '#121214', border: 'rgba(255, 255, 255, 0.25)', line: '#a1a1aa', header: '#27272a' },
            ].map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() =>
                  store.updateElement(selId, {
                    bracketThemePreset: t.id as any,
                    bracketAccentColor: t.accent,
                    bracketCardBgColor: t.cardBg,
                    bracketCardBorderColor: t.border,
                    bracketConnectorColor: t.line,
                    bracketHeaderColor: t.header,
                  })
                }
                className={`py-1.5 px-1 rounded text-[10px] font-bold transition-all text-center flex flex-col items-center justify-center gap-0.5 border ${
                  selEl.bracketThemePreset === t.id
                    ? 'border-white text-white shadow-md bg-white/10'
                    : 'border-transparent bg-[#252525] text-white/60 hover:text-white hover:bg-[#333]'
                }`}
                title={t.label}
              >
                <span>{t.icon}</span>
                <span className="text-[9px] truncate">{t.label}</span>
              </button>
            ))}
          </div>

          <label className="text-[10px] text-white/70 uppercase tracking-wide block mb-1">Grand Finals (W) / (L) Badge Style</label>
          <div className="grid grid-cols-2 gap-1 mb-3">
            {[
              { id: 'pill', label: 'Pill [W] / [L]' },
              { id: 'text', label: 'Text [W] / [L]' },
            ].map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => store.updateElement(selId, { bracketBadgeStyle: s.id as any })}
                className={`py-1 px-2 rounded text-[10px] font-bold transition-all ${
                  (selEl.bracketBadgeStyle || 'pill') === s.id
                    ? 'bg-amber-500 text-slate-950 shadow-sm'
                    : 'bg-[#252525] text-white/70 hover:bg-[#333]'
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>

          <div className="mb-3 space-y-2 pt-1 border-t border-white/10">
            <div>
              <label className="text-[10px] text-white/70 uppercase tracking-wide block mb-1">Game Name</label>
              <input
                type="text"
                className="w-full bg-[#252525] border border-white/15 rounded px-2 py-1 text-xs text-white uppercase font-bold"
                value={selEl.bracketGameName || ''}
                onChange={(e) => store.updateElement(selId, { bracketGameName: e.target.value })}
                placeholder="STREET FIGHTER 6 (or auto)"
              />
            </div>

            <div>
              <label className="text-[10px] text-white/70 uppercase tracking-wide block mb-1">Tournament Name</label>
              <input
                type="text"
                className="w-full bg-[#252525] border border-white/15 rounded px-2 py-1 text-xs text-white uppercase font-bold"
                value={selEl.bracketTournamentName || ''}
                onChange={(e) => store.updateElement(selId, { bracketTournamentName: e.target.value })}
                placeholder="TOURNAMENT NAME (or auto)"
              />
            </div>

            <div>
              <label className="text-[10px] text-white/70 uppercase tracking-wide block mb-1">Round Format (Header Badge)</label>
              <input
                type="text"
                className="w-full bg-[#252525] border border-white/15 rounded px-2 py-1 text-xs text-white uppercase font-bold"
                value={selEl.bracketRoundBestOf || 'BO5'}
                onChange={(e) => store.updateElement(selId, { bracketRoundBestOf: e.target.value })}
                placeholder="BO5"
              />
            </div>

            <label className="flex items-center gap-2 cursor-pointer text-xs text-white/90">
              <input
                type="checkbox"
                checked={selEl.bracketShowBackground ?? true}
                onChange={(e) => store.updateElement(selId, { bracketShowBackground: e.target.checked })}
                className="accent-blue-500 rounded"
              />
              <span>Show Esports Frame &amp; Background</span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer text-xs text-white/90">
              <input
                type="checkbox"
                checked={selEl.bracketShowSponsors ?? true}
                onChange={(e) => store.updateElement(selId, { bracketShowSponsors: e.target.checked })}
                className="accent-blue-500 rounded"
              />
              <span>Show Bottom Sponsor / Broadcast Bar</span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer text-xs text-white/90">
              <input
                type="checkbox"
                checked={selEl.bracketShowAvatars ?? false}
                onChange={(e) => store.updateElement(selId, { bracketShowAvatars: e.target.checked })}
                className="accent-blue-500 rounded"
              />
              <span>Show Player Avatars</span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer text-xs text-sky-300 font-bold">
              <input
                type="checkbox"
                checked={selEl.bracketTestMode ?? false}
                onChange={(e) => store.updateElement(selId, { bracketTestMode: e.target.checked })}
                className="accent-blue-500 rounded"
              />
              <span>Preview Test Data (Top 8 Demo)</span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer text-xs text-amber-300 font-bold">
              <input
                type="checkbox"
                checked={selEl.bracketSimulateReset ?? false}
                onChange={(e) => store.updateElement(selId, { bracketSimulateReset: e.target.checked })}
                className="accent-amber-500 rounded"
              />
              <span>⚡ Simulate Grand Finals Reset (Set 2)</span>
            </label>
          </div>

          {/* Color Customization & Pickers */}
          <div className="pt-2 border-t border-white/10 space-y-2">
            <div>
              <label className="text-[10px] text-white/70 uppercase tracking-wide block mb-1">Primary Accent Color</label>
              <div className="flex gap-2">
                <input
                  type="color"
                  className="w-10 h-8 p-0.5 bg-[#252525] border border-white/20 rounded cursor-pointer shrink-0"
                  value={selEl.bracketAccentColor?.startsWith('#') ? selEl.bracketAccentColor : '#ef4444'}
                  onChange={(e) => store.updateElement(selId, { bracketAccentColor: e.target.value })}
                />
                <input
                  type="text"
                  className="flex-1 bg-[#252525] border border-white/15 rounded px-2 py-1 text-xs text-white font-mono"
                  value={selEl.bracketAccentColor || '#ef4444'}
                  onChange={(e) => store.updateElement(selId, { bracketAccentColor: e.target.value })}
                />
              </div>
            </div>

            <div>
              <label className="text-[10px] text-white/70 uppercase tracking-wide block mb-1">Card Background Color</label>
              <div className="flex gap-2">
                <input
                  type="color"
                  className="w-10 h-8 p-0.5 bg-[#252525] border border-white/20 rounded cursor-pointer shrink-0"
                  value={selEl.bracketCardBgColor?.startsWith('#') ? selEl.bracketCardBgColor : '#18181b'}
                  onChange={(e) => store.updateElement(selId, { bracketCardBgColor: e.target.value })}
                />
                <input
                  type="text"
                  className="flex-1 bg-[#252525] border border-white/15 rounded px-2 py-1 text-xs text-white font-mono"
                  value={selEl.bracketCardBgColor || '#18181b'}
                  onChange={(e) => store.updateElement(selId, { bracketCardBgColor: e.target.value })}
                />
              </div>
            </div>

            <div>
              <label className="text-[10px] text-white/70 uppercase tracking-wide block mb-1">Card Border Color</label>
              <input
                type="text"
                className="w-full bg-[#252525] border border-white/15 rounded px-2 py-1 text-xs text-white font-mono"
                value={selEl.bracketCardBorderColor || 'rgba(239, 68, 68, 0.4)'}
                onChange={(e) => store.updateElement(selId, { bracketCardBorderColor: e.target.value })}
              />
            </div>

            <div>
              <label className="text-[10px] text-white/70 uppercase tracking-wide block mb-1">Connector Line Color</label>
              <div className="flex gap-2">
                <input
                  type="color"
                  className="w-10 h-8 p-0.5 bg-[#252525] border border-white/20 rounded cursor-pointer shrink-0"
                  value={selEl.bracketConnectorColor?.startsWith('#') ? selEl.bracketConnectorColor : '#ef4444'}
                  onChange={(e) => store.updateElement(selId, { bracketConnectorColor: e.target.value })}
                />
                <input
                  type="text"
                  className="flex-1 bg-[#252525] border border-white/15 rounded px-2 py-1 text-xs text-white font-mono"
                  value={selEl.bracketConnectorColor || '#ef4444'}
                  onChange={(e) => store.updateElement(selId, { bracketConnectorColor: e.target.value })}
                />
              </div>
            </div>

            <div>
              <label className="text-[10px] text-white/70 uppercase tracking-wide block mb-1">Bottom Sponsor / Footer Text</label>
              <input
                type="text"
                className="w-full bg-[#252525] border border-white/15 rounded px-2 py-1 text-xs text-white font-mono"
                value={selEl.bracketSponsorText || ''}
                onChange={(e) => store.updateElement(selId, { bracketSponsorText: e.target.value })}
                placeholder="POWERED BY AITOB BROADCAST ENGINE"
              />
            </div>
          </div>
        </div>
      )}

      {selEl.type === 'victory-path' && (
        <div className="mb-4 p-2.5 rounded border border-blue-500/40 bg-blue-500/5">
          <div className="text-[10px] font-bold uppercase tracking-wider text-sky-400 mb-2 flex items-center justify-between">
            <span className="flex items-center gap-1.5">🏆 Victory Path Settings</span>
            <span className="text-[9px] px-1.5 py-0.5 rounded bg-blue-500/20 text-sky-300 font-mono">
              {selEl.vpTargetPlayer || 'p1'}
            </span>
          </div>

          {/* Quick Switch: P1 vs P2 Victory Path */}
          <div className="flex flex-col gap-1.5 mb-2.5">
            <label className="text-[10px] text-white/80 uppercase tracking-wide block font-semibold">Target Player (Victory Path)</label>
            <div className="grid grid-cols-2 gap-1.5 bg-black/40 p-1 rounded-lg border border-white/10">
              <button
                type="button"
                onClick={() => store.updateElement(selId, { vpTargetPlayer: 'p1' })}
                className={`py-1.5 px-2 rounded text-xs font-bold transition-all text-center flex items-center justify-center gap-1.5 ${
                  (selEl.vpTargetPlayer || 'p1') === 'p1'
                    ? 'bg-emerald-500 text-slate-950 shadow-md font-black'
                    : 'text-white/70 hover:text-white hover:bg-white/5'
                }`}
              >
                <span>👤</span>
                <span>P1 Victory Path</span>
              </button>
              <button
                type="button"
                onClick={() => store.updateElement(selId, { vpTargetPlayer: 'p2' })}
                className={`py-1.5 px-2 rounded text-xs font-bold transition-all text-center flex items-center justify-center gap-1.5 ${
                  selEl.vpTargetPlayer === 'p2'
                    ? 'bg-emerald-500 text-slate-950 shadow-md font-black'
                    : 'text-white/70 hover:text-white hover:bg-white/5'
                }`}
              >
                <span>👤</span>
                <span>P2 Victory Path</span>
              </button>
            </div>
            <div className="flex justify-end">
              <button
                type="button"
                onClick={() => store.updateElement(selId, { vpTargetPlayer: 'custom' })}
                className={`text-[10px] px-2 py-0.5 rounded font-mono ${
                  selEl.vpTargetPlayer === 'custom'
                    ? 'bg-sky-500/30 text-sky-300 border border-sky-400/50'
                    : 'text-white/40 hover:text-white/70'
                }`}
              >
                Manual / Custom Mode
              </button>
            </div>
          </div>

          {/* 1-Click Unified Theme Presets for Victory Path */}
          <label className="text-[10px] text-white/70 uppercase tracking-wide block mb-1">Theme Presets</label>
          <div className="grid grid-cols-5 gap-1 mb-3">
            {[
              { id: 'crimson', label: 'Crimson', icon: '🔴', accent: '#ef4444', bg: 'linear-gradient(180deg, #7f1d1d 0%, #450a0a 50%, #1c0505 100%)', cardBg: '#18181b', border: 'rgba(239, 68, 68, 0.45)' },
              { id: 'royal-blue', label: 'Royal', icon: '🔵', accent: '#3b82f6', bg: 'linear-gradient(180deg, #0d34a4 0%, #072173 50%, #04144d 100%)', cardBg: '#0f172a', border: 'rgba(59, 130, 246, 0.45)' },
              { id: 'cyber-gold', label: 'Gold', icon: '🟡', accent: '#f59e0b', bg: 'linear-gradient(180deg, #78350f 0%, #451a03 50%, #1c0b02 100%)', cardBg: '#18140e', border: 'rgba(245, 158, 11, 0.45)' },
              { id: 'emerald', label: 'Emerald', icon: '🟢', accent: '#10b981', bg: 'linear-gradient(180deg, #064e3b 0%, #022c22 50%, #021a14 100%)', cardBg: '#061e18', border: 'rgba(16, 185, 129, 0.45)' },
              { id: 'monochrome', label: 'Mono', icon: '⚪', accent: '#ffffff', bg: 'linear-gradient(180deg, #27272a 0%, #18181b 50%, #09090b 100%)', cardBg: '#121214', border: 'rgba(255, 255, 255, 0.35)' },
            ].map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() =>
                  store.updateElement(selId, {
                    vpThemePreset: t.id as any,
                    vpAccentColor: t.accent,
                    vpBgColor: t.bg,
                    vpCardBgColor: t.cardBg,
                    vpBorderColor: t.border,
                  })
                }
                className={`py-1.5 px-1 rounded text-[10px] font-bold transition-all text-center flex flex-col items-center justify-center gap-0.5 border ${
                  selEl.vpThemePreset === t.id
                    ? 'border-white text-white shadow-md bg-white/10'
                    : 'border-transparent bg-[#252525] text-white/60 hover:text-white hover:bg-[#333]'
                }`}
                title={t.label}
              >
                <span>{t.icon}</span>
                <span className="text-[9px] truncate">{t.label}</span>
              </button>
            ))}
          </div>

          {/* Card Animation (حركة وتأثيرات الكروت) */}
          <div className="mb-3">
            <div className="flex items-center justify-between mb-1">
              <label className="text-[10px] text-white/70 uppercase tracking-wide">
                Card Animation (حركة الكروت)
              </label>
              <span className="text-[9px] font-mono text-sky-300 font-bold">
                {selEl.vpCardAnimation || 'deal'}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-1">
              {[
                { id: 'deal', label: '🃏 Deal (سحب الكروت)' },
                { id: 'slam', label: '💥 Slam (ضربة قتالية)' },
                { id: 'flip', label: '🔄 3D Flip (انقلاب)' },
                { id: 'float', label: '✨ 3D Float (طوفان)' },
                { id: 'hologram', label: '⚡ Hologram (سايبر)' },
                { id: 'glow-pulse', label: '🔥 Energy (طاقة)' },
                { id: 'none', label: '⏸️ Static (ثابت)' },
              ].map((anim) => (
                <button
                  key={anim.id}
                  type="button"
                  onClick={() => store.updateElement(selId, { vpCardAnimation: anim.id as any })}
                  className={`py-1 px-1.5 rounded text-[10px] font-bold transition-all text-center ${
                    (selEl.vpCardAnimation || 'deal') === anim.id
                      ? 'bg-blue-500 text-slate-950 shadow-sm font-black'
                      : 'bg-[#252525] text-white/70 hover:bg-[#333]'
                  }`}
                >
                  {anim.label}
                </button>
              ))}
            </div>
          </div>

          <div className="mb-3 space-y-2 pt-1 border-t border-white/10">
            <label className="flex items-center gap-2 cursor-pointer text-xs text-sky-300 font-bold">
              <input
                type="checkbox"
                checked={selEl.vpTestMode ?? false}
                onChange={(e) => store.updateElement(selId, { vpTestMode: e.target.checked })}
                className="accent-blue-500 rounded"
              />
              <span>Preview Test Data (Victory Path Demo)</span>
            </label>

            <div>
              <label className="text-[10px] text-white/70 uppercase tracking-wide block mb-1">Custom Player Name</label>
              <input
                type="text"
                className="w-full bg-[#252525] border border-white/15 rounded px-2 py-1 text-xs text-white uppercase font-bold"
                value={selEl.vpCustomPlayerName || ''}
                onChange={(e) => store.updateElement(selId, { vpCustomPlayerName: e.target.value })}
                placeholder="e.g. PUNK"
              />
            </div>

            <div>
              <label className="text-[10px] text-white/70 uppercase tracking-wide block mb-1">Footer Title</label>
              <input
                type="text"
                className="w-full bg-[#252525] border border-white/15 rounded px-2 py-1 text-xs text-white uppercase font-bold"
                value={selEl.vpFooterText || 'VICTORY PATH'}
                onChange={(e) => store.updateElement(selId, { vpFooterText: e.target.value })}
                placeholder="VICTORY PATH"
              />
            </div>

            <div>
              <label className="text-[10px] text-white/70 uppercase tracking-wide block mb-1">Accent Color</label>
              <div className="flex gap-2">
                <input
                  type="color"
                  className="w-10 h-8 p-0.5 bg-[#252525] border border-white/20 rounded cursor-pointer shrink-0"
                  value={selEl.vpAccentColor?.startsWith('#') ? selEl.vpAccentColor : '#10b981'}
                  onChange={(e) => store.updateElement(selId, { vpAccentColor: e.target.value })}
                />
                <input
                  type="text"
                  className="flex-1 bg-[#252525] border border-white/15 rounded px-2 py-1 text-xs text-white font-mono"
                  value={selEl.vpAccentColor || '#10b981'}
                  onChange={(e) => store.updateElement(selId, { vpAccentColor: e.target.value })}
                />
              </div>
            </div>
          </div>
        </div>
      )}

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

          <label className="text-[11px] text-[#999] uppercase tracking-wide mb-1 block">Font Family</label>
          <select
            className="w-full bg-[#3a3a3a] border border-[#555] rounded px-2 py-1.5 mb-1 text-xs"
            value={selEl.fontFamily || ''}
            onChange={e => store.updateElement(selId, { fontFamily: e.target.value || undefined })}
          >
            <option className="bg-white text-black" value="">Global Default</option>
            {store.font_library.map(font => <option className="bg-white text-black" key={font.family} value={font.family}>{font.family}</option>)}
          </select>
          <input
            className="w-full bg-[#3a3a3a] border border-[#555] rounded px-2 py-1.5 mb-3 text-xs"
            value={selEl.fontFamily || ''}
            onChange={e => store.updateElement(selId, { fontFamily: e.target.value || undefined })}
            placeholder="Custom CSS family, e.g. Arial, sans-serif"
          />

          <label className="text-[11px] text-[#999] uppercase tracking-wide mb-1 block">Color</label>
          <input type="color" className="w-full h-[38px] p-1 bg-[#3a3a3a] border border-[#555] rounded mb-3 cursor-pointer" value={selEl.color || '#ffffff'} onChange={e => store.updateElement(selId, { color: e.target.value })} />
        </>
      )}

      {(selEl.type === 'image' || selEl.type === 'rect' || selEl.type === 'circle') && (
        <>
          {selEl.type === 'image' && (
            <>
              <label className="text-[11px] text-[#999] uppercase tracking-wide mb-1 block">{selEl.binding ? 'Fallback Image' : 'Image Selection'}</label>
              <div className="mb-3">
                <AssetManager onSelect={(url) => store.updateElement(selId, { src: url })} />
              </div>
              <label className="text-[11px] text-[#999] uppercase tracking-wide mb-1 block">{selEl.binding ? 'Fallback URL' : 'Custom URL'}</label>
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
