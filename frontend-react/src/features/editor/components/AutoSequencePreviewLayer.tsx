import { useEffect, useMemo, useRef, useState } from 'react';
import { useEditorStore } from '@/store/useEditorStore';
import { MOCK_DATASETS } from '@/features/results/mockData';
import { resolveAutoSequence } from '@/scene/resolveAutoSequence';
import { ResultCardRenderer } from '@/scene/ResultCardRenderer';
import { resolveLinkedResultCards } from '@/scene/resolveLinkedResultCards';
import { resolveResultCardLifecycle } from '@/scene/resolveResultCardAnimation';
import type { ResultCardNode, SceneDocumentV2 } from '@/scene/types';

type PreviewState = { elapsedMs: number; running: boolean };

export function AutoSequencePreviewLayer() {
  const store = useEditorStore();
  const [states, setStates] = useState<Record<string, PreviewState>>({});
  const lastFrame = useRef<number | null>(null);

  const groups = useMemo(
    // Disabled means "do not auto-play live". Manual editor preview must still work.
    () => Object.values(store.elements).filter((element) => element.type === 'results-cards'),
    [store.elements],
  );

  useEffect(() => {
    const handleControl = (event: Event) => {
      const detail = (event as CustomEvent<{ groupId: string; action: string }>).detail;
      if (!detail?.groupId) return;
      setStates((current) => {
        const previous = current[detail.groupId] || { elapsedMs: -1, running: false };
        if (detail.action === 'play') return { ...current, [detail.groupId]: { elapsedMs: Math.max(0, previous.elapsedMs), running: true } };
        if (detail.action === 'pause') return { ...current, [detail.groupId]: { ...previous, running: false } };
        if (detail.action === 'restart') return { ...current, [detail.groupId]: { elapsedMs: 0, running: true } };
        if (detail.action === 'clear') return { ...current, [detail.groupId]: { elapsedMs: -1, running: false } };
        const group = store.elements[detail.groupId];
        const delay = Math.max(1, group?.autoSequence?.delayBetweenStartsMs || 500);
        const delta = detail.action === 'previous' ? -delay : delay;
        return { ...current, [detail.groupId]: { elapsedMs: Math.max(0, previous.elapsedMs + delta), running: false } };
      });
    };
    window.addEventListener('result-sequence-control', handleControl);
    return () => window.removeEventListener('result-sequence-control', handleControl);
  }, [store.elements]);

  useEffect(() => {
    const anyRunning = Object.values(states).some((state) => state.running);
    if (!anyRunning) {
      lastFrame.current = null;
      return;
    }
    let frame = 0;
    const tick = (now: number) => {
      const previous = lastFrame.current ?? now;
      const delta = Math.min(100, now - previous);
      lastFrame.current = now;
      setStates((current) => Object.fromEntries(Object.entries(current).map(([id, state]) => [
        id,
        state.running ? { ...state, elapsedMs: state.elapsedMs + delta } : state,
      ])));
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [Object.values(states).some((state) => state.running)]);

  useEffect(() => {
    const finished: string[] = [];
    groups.forEach((group) => {
      const state = states[group.id];
      if (!state?.running || group.schedule?.loop) return;
      const standings = MOCK_DATASETS[group.preview?.dataset || 'normal'] || MOCK_DATASETS.normal;
      const linkedCards = (group.childIds || [])
        .map((id: string) => store.elements[id])
        .filter((item): item is ResultCardNode => item?.type === 'result-card');
      let duration = 0;
      if (linkedCards.length > 1 && group.schedule) {
        duration = resolveLinkedResultCards(linkedCards, standings, group.schedule, 0)
          .reduce((maximum, instance) => Math.max(maximum, instance.endTimeMs), 0);
      } else {
        const settings = group.autoSequence;
        const stage = settings?.stageInstanceId ? store.elements[settings.stageInstanceId] : null;
        if (settings && stage?.type === 'result-card') {
          duration = resolveAutoSequence(
            group.id,
            standings,
            resolveResultCardLifecycle(stage as ResultCardNode),
            settings,
            0,
          ).reduce((maximum, instance) => Math.max(maximum, instance.endTimeMs), 0);
        }
      }
      if (state.elapsedMs >= duration) finished.push(group.id);
    });
    if (!finished.length) return;
    setStates((current) => {
      const next = { ...current };
      finished.forEach((groupId) => { next[groupId] = { elapsedMs: -1, running: false }; });
      return next;
    });
    finished.forEach((groupId) => window.dispatchEvent(new CustomEvent('result-sequence-preview-ended', {
      detail: { groupId },
    })));
  }, [groups, states, store.elements]);

  const scene: SceneDocumentV2 = {
    schemaVersion: 2,
    canvas: { width: 1920, height: 1080 },
    dataSource: { kind: 'tournament-results' },
    rootIds: [],
    nodes: store.elements as any,
  };

  return (
    <div className="pointer-events-none absolute inset-0 z-[450] overflow-visible" data-testid="auto-sequence-preview-layer">
      {groups.flatMap((group) => {
        const state = states[group.id];
        if (!state || state.elapsedMs < 0) return [];
        const settings = group.autoSequence;
        const stage = settings?.stageInstanceId ? store.elements[settings.stageInstanceId] : null;
        const standings = MOCK_DATASETS[group.preview?.dataset || 'normal'] || MOCK_DATASETS.normal;
        const linkedCards = (group.childIds || [])
          .map((id: string) => store.elements[id])
          .filter((item): item is any => item?.type === 'result-card');

        if (linkedCards.length > 1 && group.schedule) {
          const linkedRuntime = resolveLinkedResultCards(
            linkedCards as unknown as ResultCardNode[],
            standings,
            group.schedule,
            state.elapsedMs,
          );
          return linkedRuntime.filter((instance) => instance.animation.visible).map((instance, index) => (
            <div
              key={`${group.id}-linked-preview-${instance.card.id}`}
              data-testid={`${group.id}-linked-preview-${instance.card.id}`}
              style={{
                position: 'absolute',
                left: instance.animation.transform.x,
                top: instance.animation.transform.y,
                width: instance.card.width || 420,
                height: instance.card.height || 560,
                opacity: instance.animation.transform.opacity,
                transform: `scale(${instance.animation.transform.scale}) rotate(${instance.animation.transform.rotation}deg)`,
                transformOrigin: 'center',
                zIndex: (instance.card.zIndex || 10) + index,
              }}
            >
              <ResultCardRenderer
                scene={scene}
                definitionId={instance.card.definitionId}
                standing={instance.standing}
                width={instance.card.width || 420}
                height={instance.card.height || 560}
                variant={instance.card.variant}
              />
            </div>
          ));
        }

        if (!settings || !stage || stage.type !== 'result-card' || !stage.definitionId) return [];
        const definitionId = stage.definitionId;
        const runtime = resolveAutoSequence(
          group.id,
          standings,
          resolveResultCardLifecycle(stage as ResultCardNode),
          settings,
          state.elapsedMs,
        );
        return runtime.filter((instance) => instance.visible).map((instance) => (
          <div
            key={instance.runtimeId}
            data-testid={instance.runtimeId}
            style={{
              position: 'absolute',
              left: instance.transform.x,
              top: instance.transform.y,
              width: stage.width || 420,
              height: stage.height || 560,
              opacity: instance.transform.opacity,
              transform: `scale(${instance.transform.scale}) rotate(${instance.transform.rotation}deg)`,
              transformOrigin: 'center',
              zIndex: (stage.zIndex || 10) + instance.ordinalIndex,
            }}
          >
            <ResultCardRenderer scene={scene} definitionId={definitionId} standing={instance.standing} width={stage.width || 420} height={stage.height || 560} />
          </div>
        ));
      })}
    </div>
  );
}
