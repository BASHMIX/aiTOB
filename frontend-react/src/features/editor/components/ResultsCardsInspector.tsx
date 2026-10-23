import { useEditorStore, type OverlayElement } from '@/store/useEditorStore';
import { MOCK_DATASETS } from '@/features/results/mockData';

function placementLabel(placement: number, index: number, repeated: boolean) {
  const mod100 = placement % 100;
  const suffix = mod100 >= 11 && mod100 <= 13
    ? 'th'
    : placement % 10 === 1 ? 'st' : placement % 10 === 2 ? 'nd' : placement % 10 === 3 ? 'rd' : 'th';
  return `${placement}${suffix}${repeated ? ` · ${index + 1}` : ''}`;
}

export function ResultsCardsInspector() {
  const store = useEditorStore();
  const group = store.selectedId ? store.elements[store.selectedId] : null;
  if (!group || group.type !== 'results-cards') return null;

  const cards = (group.childIds || [])
    .map((id: string) => store.elements[id])
    .filter((element): element is OverlayElement => element?.type === 'result-card');
  const stage = cards.find((card) => card.id === group.autoSequence?.stageInstanceId) || cards[0];
  const schedule = group.schedule || {
    order: 'placement-desc',
    delayBetweenStartsMs: 500,
    trigger: 'with-previous',
    keepPreviousVisible: true,
    loop: false,
  };
  const auto = group.autoSequence || {
    enabled: false,
    stageInstanceId: stage?.id || '',
    range: 'top8',
    pageNumber: 1,
    pageSize: 16,
    order: schedule.order,
    delayBetweenStartsMs: schedule.delayBetweenStartsMs,
    endBehavior: 'card-exit',
  };

  const updateSchedule = (updates: Record<string, unknown>) => {
    store.takeSnapshot();
    const autoUpdates: Record<string, unknown> = {};
    if ('order' in updates) autoUpdates.order = updates.order;
    if ('delayBetweenStartsMs' in updates) autoUpdates.delayBetweenStartsMs = updates.delayBetweenStartsMs;
    store.updateElement(group.id, {
      schedule: { ...schedule, ...updates },
      autoSequence: { ...auto, ...autoUpdates },
    });
  };
  const updateAuto = (updates: Record<string, unknown>) => {
    store.takeSnapshot();
    store.updateElement(group.id, { autoSequence: { ...auto, ...updates } });
  };
  const updatePreviewDataset = (dataset: string) => {
    store.takeSnapshot();
    store.updateElement(group.id, {
      preview: { ...(group.preview || { count: auto.range, pageNumber: 1 }), dataset },
    });
  };
  const control = (action: 'play' | 'pause' | 'restart' | 'clear' | 'next' | 'previous') => {
    window.dispatchEvent(new CustomEvent('result-sequence-control', { detail: { groupId: group.id, action } }));
  };

  const insertCards = (count: 8 | 16) => {
    if (!stage?.definitionId) return;
    const dataset = MOCK_DATASETS[group.preview?.dataset || 'normal'] || MOCK_DATASETS.normal;
    const selected = dataset.filter((standing) => standing.placement <= count);
    const next = { ...store.elements };
    const childIds: string[] = [];
    const columns = count <= 8 ? 4 : 8;
    const cardWidth = count <= 8 ? 260 : 190;
    const cardHeight = Math.round(cardWidth * ((stage.height || 560) / Math.max(1, stage.width || 420)));

    selected.forEach((standing, index) => {
      const existing = cards.find((item) => item.standingOrdinal === standing.ordinal)
        || (index === 0 ? stage : null);
      const id = existing?.id || `${stage.id}_linked_${standing.ordinal}_${Date.now()}`;
      const samePlacementIndex = selected.slice(0, index + 1).filter((item) => item.placement === standing.placement).length - 1;
      const repeated = selected.filter((item) => item.placement === standing.placement).length > 1;
      next[id] = {
        ...(existing || stage),
        id,
        parentId: group.id,
        name: placementLabel(standing.placement, samePlacementIndex, repeated),
        type: 'result-card',
        instanceRole: index === 0 ? 'stage' : 'linked',
        standingOrdinal: standing.ordinal,
        x: 80 + (index % columns) * (cardWidth + 20),
        y: 110 + Math.floor(index / columns) * (cardHeight + 20),
        width: cardWidth,
        height: cardHeight,
        zIndex: (stage.zIndex || 10) + index,
      };
      childIds.push(id);
    });

    store.takeSnapshot();
    store.setElements({
      ...next,
      [group.id]: {
        ...group,
        childIds,
        autoSequence: { ...auto, stageInstanceId: childIds[0] || stage.id },
      },
    });
    store.setSelectedId(group.id);
  };

  return (
    <div className="mb-4 space-y-3 rounded-lg border border-cyan-500/20 bg-cyan-500/5 p-3">
      <div>
        <h3 className="text-xs font-black uppercase tracking-wider text-cyan-300">Results Cards</h3>
        <p className="mt-1 text-[10px] leading-relaxed text-white/55">
          This group controls which placements play and when. Each card keeps the same standard Animation panel used by every other canvas element.
        </p>
      </div>

      <div className="rounded border border-white/10 bg-black/10 p-2.5">
        <div className="mb-2 text-[10px] font-black uppercase tracking-wider text-white/70">Sequence content</div>
        <div className="grid grid-cols-2 gap-2">
          <label className="text-[10px] text-white/60">Placements
            <select value={auto.range} onChange={(event) => updateAuto({ range: event.target.value })} className="mt-1 w-full rounded border border-white/15 bg-[#191919] px-2 py-1.5 text-xs text-white">
              <option value="top8">Top 8</option>
              <option value="top16">Top 16</option>
              <option value="all">All</option>
            </select>
          </label>
          <label className="text-[10px] text-white/60">Order
            <select value={schedule.order} onChange={(event) => updateSchedule({ order: event.target.value })} className="mt-1 w-full rounded border border-white/15 bg-[#191919] px-2 py-1.5 text-xs text-white">
              <option value="placement-desc">Lowest place first</option>
              <option value="placement-asc">Champion first</option>
              <option value="custom">Layer/custom order</option>
            </select>
          </label>
        </div>
        <label className="mt-2 block text-[10px] text-white/60">Preview data
          <select value={group.preview?.dataset || 'normal'} onChange={(event) => updatePreviewDataset(event.target.value)} className="mt-1 w-full rounded border border-white/15 bg-[#191919] px-2 py-1.5 text-xs text-white">
            <option value="normal">Normal · Top 16</option>
            <option value="long_names">Long names</option>
            <option value="missing_media">Missing media</option>
            <option value="rtl">RTL / Arabic</option>
            <option value="tied_placements">Tied placements</option>
          </select>
        </label>
        {auto.range === 'all' && (
          <div className="mt-2 grid grid-cols-2 gap-2">
            <label className="text-[10px] text-white/60">Page
              <input type="number" min="1" value={auto.pageNumber || 1} onChange={(event) => updateAuto({ pageNumber: Math.max(1, Math.floor(Number(event.target.value) || 1)) })} className="mt-1 w-full rounded border border-white/15 bg-[#191919] px-2 py-1.5 text-xs text-white" />
            </label>
            <label className="text-[10px] text-white/60">Cards per page
              <input type="number" min="1" max="64" value={auto.pageSize || 16} onChange={(event) => updateAuto({ pageSize: Math.max(1, Math.min(64, Math.floor(Number(event.target.value) || 16))) })} className="mt-1 w-full rounded border border-white/15 bg-[#191919] px-2 py-1.5 text-xs text-white" />
            </label>
          </div>
        )}
        <button type="button" onClick={() => updateAuto({ enabled: !auto.enabled })} className={`mt-2 w-full rounded px-3 py-2 text-xs font-black ${auto.enabled ? 'bg-[#00ffcc] text-black' : 'border border-[#00ffcc]/30 bg-[#00ffcc]/10 text-[#00ffcc]'}`}>
          {auto.enabled ? 'One Card Sequence Enabled' : 'Enable One Card Sequence'}
        </button>
      </div>

      <div className="rounded border border-white/10 bg-black/10 p-2.5">
        <div className="mb-2 text-[10px] font-black uppercase tracking-wider text-white/70">Playback timing</div>
        <label className="block text-[10px] text-white/60">Delay / stagger (ms)
          <input type="number" min="0" step="50" value={schedule.delayBetweenStartsMs ?? 500} onChange={(event) => updateSchedule({ delayBetweenStartsMs: Math.max(0, Number(event.target.value)) })} className="mt-1 w-full rounded border border-white/15 bg-[#191919] px-2 py-1.5 text-xs text-white" />
          <span className="mt-1 block text-[9px] text-white/35">The next card may start before the previous animation finishes.</span>
        </label>
        <label className="mt-2 block text-[10px] text-white/60">Start next member
          <select value={schedule.trigger} onChange={(event) => updateSchedule({ trigger: event.target.value })} className="mt-1 w-full rounded border border-white/15 bg-[#191919] px-2 py-1.5 text-xs text-white">
            <option value="with-previous">After stagger (overlap allowed)</option>
            <option value="after-previous">After previous animation + stagger</option>
          </select>
        </label>
        <div className="mt-2 grid grid-cols-2 gap-2 text-[10px] text-white/65">
          <label className="flex items-center gap-2"><input type="checkbox" checked={Boolean(schedule.keepPreviousVisible)} onChange={(event) => updateSchedule({ keepPreviousVisible: event.target.checked })} />Keep previous visible</label>
          <label className="flex items-center gap-2"><input type="checkbox" checked={Boolean(schedule.loop)} onChange={(event) => updateSchedule({ loop: event.target.checked })} />Loop</label>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-1">
        <button type="button" onClick={() => control('play')} className="rounded bg-[#00ffcc] px-2 py-1.5 text-[10px] font-black text-black">▶ Preview</button>
        <button type="button" onClick={() => control('pause')} className="rounded border border-white/15 bg-white/5 px-2 py-1.5 text-[10px] font-bold">Ⅱ Hold</button>
        <button type="button" onClick={() => control('restart')} className="rounded border border-white/15 bg-white/5 px-2 py-1.5 text-[10px] font-bold">↺ Restart</button>
        <button type="button" onClick={() => control('previous')} className="rounded border border-white/15 bg-white/5 px-2 py-1.5 text-[10px] font-bold">← Previous</button>
        <button type="button" onClick={() => control('next')} className="rounded border border-white/15 bg-white/5 px-2 py-1.5 text-[10px] font-bold">Next →</button>
        <button type="button" onClick={() => control('clear')} className="rounded border border-red-400/20 bg-red-400/10 px-2 py-1.5 text-[10px] font-bold text-red-200">Clear</button>
      </div>

      <div className="border-t border-white/10 pt-3">
        <p className="mb-2 text-[9px] leading-relaxed text-white/40">Insert cards only when you want to arrange every placement manually on the canvas.</p>
        <div className="grid grid-cols-2 gap-2">
          <button type="button" onClick={() => insertCards(8)} className="rounded border border-white/15 bg-white/5 px-2 py-2 text-[10px] font-bold hover:bg-white/10">Insert Top 8 Cards</button>
          <button type="button" onClick={() => insertCards(16)} className="rounded border border-white/15 bg-white/5 px-2 py-2 text-[10px] font-bold hover:bg-white/10">Insert Top 16 Cards</button>
        </div>
      </div>
    </div>
  );
}
