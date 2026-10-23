import { useState } from 'react';
import { useEditorStore } from '@/store/useEditorStore';
import { getResultsLayoutPresetSlots } from '@/features/results/templates';
import { ResultsSequenceControls } from './ResultsSequenceControls';
import { MOCK_DATASETS } from '@/features/results/mockData';
import { resolveResultsGroup } from '@/scene/resolveResultsGroup';
import { createDefaultResultCardAnimation } from '@/scene/defaultResultCard';
import { exportSceneToPng } from '@/utils/resultsExport';
import type { GroupNode, ResultsGroupNode } from '@/scene/types';

const THEME_PRESETS = [
  { id: 'crimson', label: 'Crimson', icon: '🔴', accent: '#ef4444', cardBg: '#18181b', border: 'rgba(239, 68, 68, 0.45)', badge: '#ef4444', prefix: '#f87171' },
  { id: 'royal-blue', label: 'Royal', icon: '🔵', accent: '#3b82f6', cardBg: '#0f172a', border: 'rgba(59, 130, 246, 0.45)', badge: '#3b82f6', prefix: '#60a5fa' },
  { id: 'cyber-gold', label: 'Gold', icon: '🟡', accent: '#f59e0b', cardBg: '#18140e', border: 'rgba(245, 158, 11, 0.45)', badge: '#f59e0b', prefix: '#fbbf24' },
  { id: 'emerald', label: 'Emerald', icon: '🟢', accent: '#10b981', cardBg: '#061e18', border: 'rgba(16, 185, 129, 0.45)', badge: '#10b981', prefix: '#34d399' },
  { id: 'monochrome', label: 'Mono', icon: '⚪', accent: '#ffffff', cardBg: '#121214', border: 'rgba(255, 255, 255, 0.35)', badge: '#e4e4e7', prefix: '#ffffff' },
];

const CARD_ANIMATIONS = [
  { id: 'deal', label: 'Deal', icon: '🃏', type: 'fly-in', dir: 'left', dur: 450, tween: 'ease-out' },
  { id: 'slam', label: 'Slam', icon: '💥', type: 'fly-in', dir: 'top', dur: 380, tween: 'bounce' },
  { id: 'flip', label: 'Flip', icon: '🔄', type: 'fly-in', dir: 'bottom', dur: 480, tween: 'back-out' },
  { id: 'float', label: 'Float', icon: '☁️', type: 'float-in', dir: 'bottom', dur: 500, tween: 'ease-out' },
  { id: 'hologram', label: 'Holo', icon: '⚡', type: 'fade-in', dir: 'in-place', dur: 400, tween: 'linear' },
  { id: 'energy', label: 'Energy', icon: '🔮', type: 'fly-in', dir: 'bottom-left', dur: 600, tween: 'elastic' },
  { id: 'none', label: 'Static', icon: '⏸️', type: 'none', dir: 'in-place', dur: 0, tween: 'linear' },
];

export function ResultsGroupInspector() {
  const store = useEditorStore();
  const selId = store.selectedId;
  const element = selId ? store.elements[selId] : null;
  const [isExporting, setIsExporting] = useState(false);

  if (!element || element.type !== 'results-group') {
    return null;
  }

  const updateProp = (key: string, val: any) => {
    store.takeSnapshot();
    store.updateElement(element.id, { [key]: val });
  };

  const updatePreview = (key: string, val: any) => {
    store.takeSnapshot();
    const currentPrev = element.preview || { dataset: 'normal', count: 'top8', pageNumber: 1 };
    store.updateElement(element.id, {
      preview: { ...currentPrev, [key]: val },
    });
  };

  const updateSequence = (key: string, val: any) => {
    store.takeSnapshot();
    const currentSeq = element.sequence || {
      order: 'champion-last',
      startDelayMs: 300,
      intervalMs: 800,
      holdMs: 4000,
      exit: 'none',
      loop: false,
      manualCue: false,
    };
    store.updateElement(element.id, {
      sequence: { ...currentSeq, [key]: val },
    });
  };

  const updateCutoff = (cutoff: 'top8' | 'top16' | 'all') => {
    store.takeSnapshot();
    store.updateElement(element.id, {
      cutoff,
      pageSize: cutoff === 'top8' ? 8 : cutoff === 'top16' ? 16 : 64,
      preview: { ...(element.preview || { count: 'top8', pageNumber: 1 }), count: cutoff, pageNumber: 1 },
      pageNumber: 1,
    });
  };

  const applyLayoutPreset = (layoutPresetId: string) => {
    store.takeSnapshot();
    store.updateElement(element.id, {
      layoutPresetId,
      customSlots: getResultsLayoutPresetSlots(layoutPresetId, element as any),
    });
  };

  const swapImages = () => {
    store.takeSnapshot();
    const currentLarge = element.largeImageSource || 'character';
    const currentSmall = element.smallImageSource || 'player';
    store.updateElement(element.id, {
      largeImageSource: currentSmall,
      smallImageSource: currentLarge,
    });
  };

  const applyThemePreset = (theme: typeof THEME_PRESETS[0]) => {
    store.takeSnapshot();
    updateProp('themePreset', theme.id);
    updateProp('bracketAccentColor', theme.accent);

    const definitionId = element.cardDefinitionId || element.templateId;
    if (!definitionId || !store.elements[definitionId]) return;

    const def = store.elements[definitionId];
    const next = { ...store.elements };

    // Update definition's children (bg, badge, prefix)
    (def.childIds || []).forEach((childId) => {
      const child = next[childId];
      if (!child) return;

      if (child.type === 'rect' && (child.name?.toLowerCase().includes('background') || child.id.includes('_bg_') || child.id === 'mc-bg')) {
        next[childId] = {
          ...child,
          color: theme.cardBg,
          strokeColor: theme.border,
        };
      } else if (child.type === 'rect' && (child.name?.toLowerCase().includes('badge') || child.id.includes('_badge_') || child.id === 'mc-placement-badge')) {
        next[childId] = {
          ...child,
          color: theme.badge,
        };
      } else if (child.type === 'text' && (child.binding === 'prefix' || child.id.includes('_prefix_') || child.id === 'mc-prefix-text')) {
        next[childId] = {
          ...child,
          color: theme.prefix,
        };
      }
    });

    store.setElements(next);
    store.setStatusMsg(`Applied ${theme.label} theme to Results Group.`);
  };

  const applyCardAnimation = (anim: typeof CARD_ANIMATIONS[0]) => {
    const definitionId = element.cardDefinitionId || element.templateId;
    if (!definitionId || !store.elements[definitionId]) return;

    store.takeSnapshot();
    updateProp('cardAnimationPreset', anim.id);

    store.updateElement(definitionId, {
      animation: {
        animationType: anim.type as any,
        direction: anim.dir as any,
        duration: anim.dur,
        tweenType: anim.tween as any,
        delay: 0,
        loop: 0,
        playOn: 'IN',
        trigger: 'on-load',
      },
    });

    window.dispatchEvent(new CustomEvent('play-slide-preview', { detail: { id: element.id } }));
    store.setStatusMsg(`Set card animation to ${anim.label}.`);
  };

  const handleExportTop8Png = async () => {
    setIsExporting(true);
    try {
      const canvas = document.querySelector<HTMLElement>('[data-overlay-canvas="true"]')
        || (document.querySelector(`[data-testid="results-group-${element.id}"]`) as HTMLElement);
      if (!canvas) {
        throw new Error('Canvas element not found in DOM.');
      }
      await exportSceneToPng(canvas, {
        width: 1920,
        height: 1080,
        filename: `Top8_Results_${Date.now()}.png`,
      });
      store.setStatusMsg('✓ Top 8 social graphic (Top8er style) exported as PNG!');
    } catch (err: any) {
      console.error('Export failed', err);
      store.setStatusMsg(`Export failed: ${err.message || 'unknown error'}`);
    } finally {
      setIsExporting(false);
    }
  };

  const replayStreamSequence = () => {
    window.dispatchEvent(new CustomEvent('play-slide-preview', { detail: { id: element.id } }));
  };

  const materializeLinkedCards = () => {
    const definitionId = element.cardDefinitionId || element.templateId;
    const definition = definitionId ? store.elements[definitionId] : null;
    if (!definition || definition.type !== 'group') return;
    const dataset = MOCK_DATASETS[element.preview?.dataset || 'normal'] || MOCK_DATASETS.normal;
    const instances = resolveResultsGroup(
      element as unknown as ResultsGroupNode,
      definition as unknown as GroupNode,
      dataset,
    );
    if (!instances.length) return;

    const suffix = Date.now();
    const schedulerId = `results_cards_from_${element.id}_${suffix}`;
    const cardIds: string[] = [];
    const next = { ...store.elements };
    instances.forEach((instance, index) => {
      const cardId = `result_card_from_${element.id}_${instance.standing.ordinal}_${suffix}`;
      cardIds.push(cardId);
      next[cardId] = {
        id: cardId,
        parentId: schedulerId,
        name: `${instance.standing.is_tied ? 'T' : ''}${instance.standing.placement} · ${instance.standing.presentation.display_name.value}`,
        type: 'result-card',
        definitionId,
        instanceRole: index === 0 ? 'stage' : 'linked',
        standingOrdinal: instance.standing.ordinal,
        variant: instance.variant,
        visible: true,
        x: instance.transform.x,
        y: instance.transform.y,
        width: instance.transform.width,
        height: instance.transform.height,
        rotation: 0,
        opacity: 1,
        zIndex: (element.zIndex || 1) + index + 1,
        animation: createDefaultResultCardAnimation(),
      };
    });
    next[schedulerId] = {
      id: schedulerId,
      name: `${element.name || 'Results Group'} · Editable Cards`,
      type: 'results-cards',
      visible: true,
      x: 0,
      y: 0,
      width: 1920,
      height: 1080,
      childIds: cardIds,
      schedule: {
        order: 'placement-desc', delayBetweenStartsMs: 500,
        trigger: 'with-previous', keepPreviousVisible: true, loop: false,
      },
      autoSequence: {
        enabled: false,
        stageInstanceId: cardIds[0],
        range: element.cutoff || 'top8',
        pageNumber: element.pageNumber || 1,
        pageSize: element.pageSize || 8,
        order: 'placement-desc',
        delayBetweenStartsMs: 500,
        endBehavior: 'card-exit',
      },
      preview: { ...(element.preview || { dataset: 'normal', count: element.cutoff || 'top8', pageNumber: 1 }) },
      zIndex: element.zIndex || 1,
    };
    store.takeSnapshot();
    store.setElements(next);
    store.setSelectedId(schedulerId);
    store.setStatusMsg(`${instances.length} linked Result Cards created from the template layout.`);
  };

  const mode = element.mode || 'board';
  const cutoff = element.cutoff || 'top8';
  const preview = element.preview || { dataset: 'normal', count: 'top8', pageNumber: 1 };
  const sequence = element.sequence || {
    order: 'champion-last',
    startDelayMs: 300,
    intervalMs: 800,
    holdMs: 4000,
    exit: 'none',
    loop: false,
    manualCue: false,
  };

  return (
    <div className="bg-[#242424] border border-[#3a3a3a] rounded-lg p-3 space-y-4 mb-4">
      <div className="border-b border-[#3a3a3a] pb-2">
        <h3 className="text-xs font-bold uppercase tracking-wider text-[#00ffcc] flex items-center gap-1.5">
          <span>🏆</span> Results Group Settings
        </h3>
        <p className="mt-1 text-[10px] leading-relaxed text-gray-400">
          Complete Top 8 / Standings board with instant Top8er social image export and sequential broadcast reveal.
        </p>
      </div>

      {/* Top8er Social Image Export Box */}
      <div className="rounded-lg border border-amber-500/40 bg-gradient-to-r from-amber-500/15 via-amber-500/5 to-transparent p-2.5 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-black text-amber-300 flex items-center gap-1.5 uppercase tracking-wide">
            <span>📸</span> Top8er Social Graphic
          </span>
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-400/20 text-amber-200 font-bold font-mono">
            1920×1080 PNG
          </span>
        </div>
        <p className="text-[10px] text-gray-300 leading-relaxed">
          Export verified Top 8 graphic for Twitter/X, Instagram, and Discord in classic Top8er format.
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleExportTop8Png}
            disabled={isExporting}
            className="flex-1 py-1.5 px-3 rounded bg-amber-500 hover:bg-amber-400 active:scale-95 text-slate-950 font-black text-xs transition-all shadow flex items-center justify-center gap-1.5 disabled:opacity-50"
          >
            <span>{isExporting ? '⏳ Exporting...' : '💾 Export Top 8 Image (PNG)'}</span>
          </button>
          <a
            href="/admin/results"
            target="_blank"
            rel="noreferrer"
            className="py-1.5 px-2.5 rounded border border-white/20 bg-white/10 hover:bg-white/20 text-white text-xs font-bold transition-all flex items-center justify-center gap-1"
            title="Open Full Results Studio with Multi-ratio export"
          >
            <span>🎨 Studio</span>
          </a>
        </div>
      </div>

      {/* 1-Click Unified Themes */}
      <div className="space-y-1.5">
        <label className="block text-[11px] font-semibold text-gray-300">
          Color Theme (1-Click Presets)
        </label>
        <div className="grid grid-cols-5 gap-1">
          {THEME_PRESETS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => applyThemePreset(t)}
              className={`py-1 px-1.5 rounded text-[10px] font-bold border transition-all text-center flex flex-col items-center gap-0.5 ${
                element.themePreset === t.id
                  ? 'border-white text-white shadow-md bg-white/20'
                  : 'border-white/10 bg-[#1b1b1b] text-white/70 hover:text-white hover:bg-white/10'
              }`}
            >
              <span className="text-sm">{t.icon}</span>
              <span>{t.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Card Entrance Animation */}
      <div className="space-y-1.5">
        <label className="block text-[11px] font-semibold text-gray-300">
          Card Entrance Animation
        </label>
        <div className="grid grid-cols-4 gap-1">
          {CARD_ANIMATIONS.map((a) => (
            <button
              key={a.id}
              type="button"
              onClick={() => applyCardAnimation(a)}
              className={`py-1 px-1.5 rounded text-[10px] font-bold border transition-all text-center flex items-center justify-center gap-1 ${
                element.cardAnimationPreset === a.id
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

      {/* Image Roles & Layout (توزيع ومصادر الصور) */}
      <div className="space-y-2 pt-1 border-t border-[#3a3a3a]">
        <div className="flex items-center justify-between">
          <label className="block text-[11px] font-semibold text-gray-300">
            🖼️ Image Roles & Layout (توزيع ومصادر الصور)
          </label>
          <button
            type="button"
            onClick={swapImages}
            title="تبديل الصورتين بين الكبيرة والصغيرة"
            className="px-2 py-0.5 rounded bg-sky-600 hover:bg-sky-500 text-white text-[10px] font-bold flex items-center gap-1 transition-all shadow-sm"
          >
            <span>⇄</span> Swap Images
          </button>
        </div>

        {/* Large Image Source */}
        <div className="space-y-1">
          <span className="text-[10px] font-medium text-gray-400">
            Hero / Large Image (الصورة الكبيرة)
          </span>
          <div className="grid grid-cols-2 gap-1.5">
            <button
              type="button"
              onClick={() => {
                store.takeSnapshot();
                store.updateElement(element.id, {
                  largeImageSource: 'character',
                  smallImageSource: 'player',
                });
              }}
              className={`py-1.5 px-2 rounded text-xs font-bold border transition-all text-center flex items-center justify-center gap-1.5 ${
                (element.largeImageSource || 'character') === 'character'
                  ? 'border-sky-400 bg-sky-500/20 text-sky-300 font-black'
                  : 'border-white/10 bg-[#1b1b1b] text-white/60 hover:text-white'
              }`}
            >
              <span>🎮</span> Character Art
            </button>
            <button
              type="button"
              onClick={() => {
                store.takeSnapshot();
                store.updateElement(element.id, {
                  largeImageSource: 'player',
                  smallImageSource: 'character',
                });
              }}
              className={`py-1.5 px-2 rounded text-xs font-bold border transition-all text-center flex items-center justify-center gap-1.5 ${
                element.largeImageSource === 'player'
                  ? 'border-sky-400 bg-sky-500/20 text-sky-300 font-black'
                  : 'border-white/10 bg-[#1b1b1b] text-white/60 hover:text-white'
              }`}
            >
              <span>👤</span> Player Photo
            </button>
          </div>
        </div>

        {/* Small Image Controls */}
        <div className="rounded-lg border border-white/10 bg-black/20 p-2 space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-[10px] font-semibold text-gray-300 flex items-center gap-1.5 cursor-pointer">
              <input
                type="checkbox"
                checked={element.showSmallImage !== false}
                onChange={(e) => updateProp('showSmallImage', e.target.checked)}
                className="rounded accent-sky-400 cursor-pointer"
              />
              <span>Small Image (إظهار الصورة الصغيرة)</span>
            </label>
            <span className="text-[9px] font-medium text-gray-400">
              {element.showSmallImage === false ? '❌ معطلة (الكبيرة فقط)' : '✔️ مفعلة'}
            </span>
          </div>

          {element.showSmallImage !== false && (
            <div className="space-y-1 pt-1 border-t border-white/5">
              <span className="text-[10px] font-medium text-gray-400">
                Small Image Content (محتوى الصورة الصغيرة)
              </span>
              <div className="grid grid-cols-2 gap-1.5">
                <button
                  type="button"
                  onClick={() => {
                    store.takeSnapshot();
                    store.updateElement(element.id, {
                      smallImageSource: 'player',
                      largeImageSource: 'character',
                    });
                  }}
                  className={`py-1 px-2 rounded text-xs font-bold border transition-all text-center flex items-center justify-center gap-1.5 ${
                    (element.smallImageSource || 'player') === 'player'
                      ? 'border-emerald-400 bg-emerald-500/20 text-emerald-300 font-black'
                      : 'border-white/10 bg-[#1b1b1b] text-white/60 hover:text-white'
                  }`}
                >
                  <span>👤</span> Player Photo
                </button>
                <button
                  type="button"
                  onClick={() => {
                    store.takeSnapshot();
                    store.updateElement(element.id, {
                      smallImageSource: 'character',
                      largeImageSource: 'player',
                    });
                  }}
                  className={`py-1 px-2 rounded text-xs font-bold border transition-all text-center flex items-center justify-center gap-1.5 ${
                    element.smallImageSource === 'character'
                      ? 'border-emerald-400 bg-emerald-500/20 text-emerald-300 font-black'
                      : 'border-white/10 bg-[#1b1b1b] text-white/60 hover:text-white'
                  }`}
                >
                  <span>🎮</span> Character Art
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Render Mode Selector */}
      <div className="space-y-1.5 pt-1 border-t border-[#3a3a3a]">
        <label className="block text-[11px] font-semibold text-gray-300">
          Display Mode
        </label>
        <div className="grid grid-cols-2 gap-1.5">
          <button
            type="button"
            onClick={() => updateProp('mode', 'board')}
            className={`py-2 px-2.5 rounded text-xs font-bold border transition-all text-left flex flex-col gap-0.5 ${
              mode === 'board'
                ? 'border-[#00ffcc] bg-[#00ffcc]/15 text-[#00ffcc] font-black'
                : 'border-white/10 bg-[#1b1b1b] text-white/70 hover:text-white hover:bg-white/5'
            }`}
          >
            <span className="flex items-center gap-1.5">
              <span>📋</span> Static Board
            </span>
            <span className="text-[9px] font-normal opacity-80">Full poster (Top8er style)</span>
          </button>
          <button
            type="button"
            onClick={() => updateProp('mode', 'sequence')}
            className={`py-2 px-2.5 rounded text-xs font-bold border transition-all text-left flex flex-col gap-0.5 ${
              mode === 'sequence'
                ? 'border-amber-400 bg-amber-400/15 text-amber-300 font-black'
                : 'border-white/10 bg-[#1b1b1b] text-white/70 hover:text-white hover:bg-white/5'
            }`}
          >
            <span className="flex items-center gap-1.5">
              <span>🎬</span> Stream Reveal
            </span>
            <span className="text-[9px] font-normal opacity-80">Cards reveal one after another</span>
          </button>
        </div>
      </div>

      {/* Sequence Mode Settings */}
      {mode === 'sequence' && (
        <div className="rounded-lg border border-amber-500/30 bg-black/30 p-2.5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-amber-400 uppercase tracking-wide flex items-center gap-1.5">
              <span>🎬</span> Stream Reveal Settings
            </span>
            <button
              type="button"
              onClick={replayStreamSequence}
              className="px-2 py-0.5 rounded bg-amber-500 hover:bg-amber-400 text-slate-950 text-[10px] font-bold flex items-center gap-1"
            >
              <span>▶️</span> Replay Reveal
            </button>
          </div>

          <div className="space-y-1">
            <label htmlFor="seq-exit-select" className="block text-[10px] font-semibold text-gray-300">
              Reveal Style (طريقة الظهور)
            </label>
            <select
              id="seq-exit-select"
              aria-label="Reveal Style"
              value={sequence.exit || 'none'}
              onChange={(e) => updateSequence('exit', e.target.value)}
              className="w-full bg-[#1b1b1b] border border-[#444] rounded px-2.5 py-1.5 text-xs text-white focus:border-amber-400 outline-none"
            >
              <option value="none">Accumulate (تراكمي - كارت وراء كارت حتى يكتمل البورد)</option>
              <option value="sequential">Spotlight (كارت تلو الآخر - واحد في كل مرة)</option>
            </select>
          </div>

          <div className="space-y-1">
            <label htmlFor="seq-order-select" className="block text-[10px] font-semibold text-gray-300">
              Reveal Order (ترتيب الظهور)
            </label>
            <select
              id="seq-order-select"
              aria-label="Sequence Order"
              value={sequence.order || 'champion-last'}
              onChange={(e) => updateSequence('order', e.target.value)}
              className="w-full bg-[#1b1b1b] border border-[#444] rounded px-2.5 py-1.5 text-xs text-white focus:border-amber-400 outline-none"
            >
              <option value="champion-last">Champion Last (8th → 1st — الأكثر حماساً)</option>
              <option value="podium-first">Podium First (1st → 3rd → البقية)</option>
              <option value="placement-asc">Placement Ascending (1st → 8th)</option>
              <option value="placement-desc">Placement Descending (8th → 1st)</option>
            </select>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label htmlFor="seq-start-delay-input" className="block text-[10px] font-semibold text-gray-300">
                Start Delay (ms)
              </label>
              <input
                id="seq-start-delay-input"
                aria-label="Start Delay (ms)"
                type="number"
                min="0"
                step="100"
                value={sequence.startDelayMs ?? 300}
                onChange={(e) => updateSequence('startDelayMs', Math.max(0, Number(e.target.value)))}
                className="w-full bg-[#1b1b1b] border border-[#444] rounded px-2 py-1 text-xs text-white focus:border-amber-400 outline-none"
              />
            </div>
            <div>
              <label htmlFor="seq-interval-input" className="block text-[10px] font-semibold text-gray-300">
                Step Interval (ms)
              </label>
              <input
                id="seq-interval-input"
                aria-label="Step Interval (ms)"
                type="number"
                min="100"
                step="100"
                value={sequence.intervalMs ?? 800}
                onChange={(e) => updateSequence('intervalMs', Math.max(100, Number(e.target.value)))}
                className="w-full bg-[#1b1b1b] border border-[#444] rounded px-2 py-1 text-xs text-white focus:border-amber-400 outline-none"
              />
            </div>
          </div>
          <ResultsSequenceControls />
        </div>
      )}

      {/* Standings Cutoff */}
      <div className="space-y-1">
        <label htmlFor="results-cutoff-select" className="block text-[11px] font-semibold text-gray-300">
          Standings Cutoff
        </label>
        <select
          id="results-cutoff-select"
          aria-label="Standings Cutoff"
          value={cutoff}
          onChange={(e) => updateCutoff(e.target.value as 'top8' | 'top16' | 'all')}
          className="w-full bg-[#1b1b1b] border border-[#444] rounded px-2.5 py-1.5 text-xs text-white focus:border-[#00ffcc] focus:outline-none"
        >
          <option value="top8">Top 8 Standings</option>
          <option value="top16">Top 16 Standings</option>
          <option value="all">All Entrants</option>
        </select>
      </div>

      {/* Layout Preset */}
      <div className="space-y-1">
        <label htmlFor="results-preset-select" className="block text-[11px] font-semibold text-gray-300">
          Layout Preset (تصميم وتوزيع الكروت)
        </label>
        <select
          id="results-preset-select"
          aria-label="Layout Preset"
          value={element.layoutPresetId || 'champion-focus'}
          onChange={(e) => applyLayoutPreset(e.target.value)}
          className="w-full bg-[#1b1b1b] border border-[#444] rounded px-2.5 py-1.5 text-xs text-white focus:border-[#00ffcc] focus:outline-none"
        >
          <option value="champion-focus">Champion Focus (Top8er Style — البطل بارز على اليسار)</option>
          <option value="podium-remaining">Podium + Remaining (منصة التتويج 1-2-3 في الأعلى)</option>
          <option value="equal-grid">Equal Grid (شبكة متساوية 4×2)</option>
          <option value="ranked-list">Ranked List (قائمة أفقية مرتبة)</option>
        </select>
        <button
          type="button"
          onClick={() => applyLayoutPreset(element.layoutPresetId || 'champion-focus')}
          className="w-full rounded border border-[#00ffcc]/25 bg-[#00ffcc]/5 px-2 py-1.5 text-[10px] font-bold text-[#00ffcc] hover:bg-[#00ffcc]/10"
        >
          Apply Selected Layout to Canvas
        </button>
      </div>

      {/* Dataset / Live Tournament Selector */}
      <div className="space-y-1">
        <label htmlFor="results-dataset-select" className="block text-[11px] font-semibold text-gray-300">
          Standings Source & Dataset
        </label>
        <select
          id="results-dataset-select"
          aria-label="Standings Source"
          value={preview.dataset || 'normal'}
          onChange={(e) => updatePreview('dataset', e.target.value)}
          className="w-full bg-[#1b1b1b] border border-[#444] rounded px-2.5 py-1.5 text-xs text-white focus:border-[#00ffcc] focus:outline-none"
        >
          <option value="normal">Live Tournament Standings (بيانات البطولة الحقيقية فقط)</option>
          <option value="demo_preview">Demo: Full Top 8 Preview (معاينة تجريبية كاملة - 8 كروت)</option>
          <option value="long_names">Demo: Long Names & Sponsors</option>
          <option value="missing_media">Demo: Missing Media & Avatars</option>
          <option value="rtl">Demo: RTL (Arabic / Middle East)</option>
          <option value="tied_placements">Demo: Tied Placements (T-3rd/5th/7th)</option>
        </select>
      </div>

      {/* Advanced Tools */}
      <div className="rounded border border-white/10 bg-black/20 p-2 text-[10px] space-y-2">
        <div className="text-gray-400 font-semibold uppercase tracking-wider text-[9px]">
          Card Design & Layers
        </div>
        {(element.cardDefinitionId || element.templateId) && store.elements[element.cardDefinitionId || element.templateId || ''] && (
          <button
            type="button"
            onClick={() => store.enterResultCardDesign(element.cardDefinitionId || element.templateId || '')}
            className="block w-full rounded border border-amber-400/30 bg-amber-400/10 px-2 py-1.5 font-bold text-amber-200 hover:bg-amber-400/20 text-center"
          >
            ✏️ Deep Edit Master Card Design
          </button>
        )}
        <button
          type="button"
          onClick={materializeLinkedCards}
          disabled={!element.cardDefinitionId && !element.templateId}
          className="block w-full rounded border border-sky-400/30 bg-sky-400/10 px-2 py-1.5 font-bold text-sky-200 hover:bg-sky-400/20 disabled:cursor-not-allowed disabled:opacity-40 text-center"
        >
          🧩 Materialize Individual Freeform Cards
        </button>
      </div>
    </div>
  );
}
