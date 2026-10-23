import { useState, useEffect, useMemo } from 'react';
import type { GroupNode, ResultsGroupNode, SceneDocumentV2, StandingEntrySnapshot } from './types';
import { resolveResultsGroup } from './resolveResultsGroup';
import { resolveSequence, getCueVisibility } from './resolveSequence';
import { resolveAnimatedVisibilityStyle } from './CardTemplateNode';
import { ResultCardRenderer } from './ResultCardRenderer';

interface ResultsGroupRendererProps {
  scene: SceneDocumentV2;
  node: ResultsGroupNode;
  standings?: StandingEntrySnapshot[];
  pageOverride?: number;
  activeCueId?: string | null;
  activeCueIndex?: number;
}

export const ResultsGroupRenderer: React.FC<ResultsGroupRendererProps> = ({
  scene,
  node,
  standings = [],
  pageOverride,
  activeCueId,
  activeCueIndex: externalCueIndex,
}) => {
  const definitionId = node.cardDefinitionId || node.templateId;
  const templateGroup = scene.nodes[definitionId] as GroupNode | undefined;
  if (!templateGroup || templateGroup.type !== 'group') return null;

  const [internalCueIndex, setInternalCueIndex] = useState<number>(-1);
  const [animKey, setAnimKey] = useState<number>(0);

  const isSequence = node.mode === 'sequence';
  const instances = resolveResultsGroup(node, templateGroup, standings, pageOverride);

  // Sync with Slide preview & element preview events
  useEffect(() => {
    const handleReplay = (e: Event) => {
      const isGlobal = e.type === 'play-slide-preview';
      const customEvent = e as CustomEvent;
      if (isGlobal || customEvent.detail?.id === node.id || customEvent.detail?.groupId === node.id) {
        setAnimKey((prev) => prev + 1);
        setInternalCueIndex(-1);
      }
    };

    window.addEventListener('play-slide-preview', handleReplay);
    window.addEventListener('play-element-preview', handleReplay);
    return () => {
      window.removeEventListener('play-slide-preview', handleReplay);
      window.removeEventListener('play-element-preview', handleReplay);
    };
  }, [node.id]);

  const allCues = useMemo(() => {
    return isSequence && templateGroup ? resolveSequence(node, templateGroup, standings, pageOverride) : [];
  }, [isSequence, templateGroup, node, standings, pageOverride]);

  const seq = node.sequence || {
    startDelayMs: 300,
    intervalMs: 800,
    holdMs: 4000,
    exit: 'none',
    loop: false,
  };
  const seqKey = `${seq.startDelayMs ?? 300}_${seq.intervalMs ?? 800}_${seq.holdMs ?? 4000}_${seq.exit ?? 'none'}_${seq.loop ?? false}`;

  // Automatic sequence playback when no external cue index is provided (e.g. OBS viewer or slide preview)
  useEffect(() => {
    if (!isSequence || externalCueIndex !== undefined || allCues.length === 0) return;

    let isCancelled = false;
    const timeouts: ReturnType<typeof setTimeout>[] = [];
    const startDelay = Math.max(0, seq.startDelayMs ?? 300);
    const interval = Math.max(100, seq.intervalMs ?? 800);
    const hold = Math.max(500, seq.holdMs ?? 4000);

    const tStart = setTimeout(() => {
      if (isCancelled) return;
      setInternalCueIndex(0);
      for (let i = 1; i < allCues.length; i++) {
        const t = setTimeout(() => {
          if (!isCancelled) {
            setInternalCueIndex(i);
          }
        }, i * interval);
        timeouts.push(t);
      }

      if (seq.loop) {
        const totalDuration = (allCues.length - 1) * interval + hold;
        const tLoop = setTimeout(() => {
          if (!isCancelled) {
            setAnimKey((k) => k + 1);
            setInternalCueIndex(-1);
          }
        }, totalDuration);
        timeouts.push(tLoop);
      }
    }, startDelay);
    timeouts.push(tStart);

    return () => {
      isCancelled = true;
      timeouts.forEach(clearTimeout);
    };
  }, [isSequence, externalCueIndex, allCues.length, animKey, seqKey]);

  const activeCueIndex = externalCueIndex !== undefined
    ? externalCueIndex
    : (isSequence ? internalCueIndex : undefined);

  const cues = isSequence && activeCueIndex !== undefined ? allCues : [];
  const cueVisibility = cues.length > 0 && activeCueIndex !== undefined
    ? getCueVisibility(cues, activeCueIndex, node.sequence?.exit || 'none')
    : null;

  return (
    <div
      key={animKey}
      data-testid={`results-group-${node.id}`}
      style={{
        position: 'absolute', left: node.x, top: node.y,
        width: node.width, height: node.height, pointerEvents: 'none',
      }}
    >
      {instances.map((instance) => {
        let cueVisible = true;
        if (isSequence) {
          if (activeCueId) {
            cueVisible = activeCueId === instance.instanceId;
          } else if (cueVisibility) {
            const cue = cues.find((item) => item.standing.entrant_id === instance.standing.entrant_id);
            cueVisible = cue ? Boolean(cueVisibility[cue.cueId]) : false;
          }
        }

        const variantOverrides = templateGroup.variants?.[instance.variant] || {};
        return (
          <div
            key={`${instance.instanceId}-${animKey}`}
            data-testid={`card-instance-${instance.standing.entrant_id}`}
            style={{
              position: 'absolute',
              left: instance.slot.x - node.x,
              top: instance.slot.y - node.y,
              width: instance.slot.width,
              height: instance.slot.height,
              overflow: 'hidden',
              boxSizing: 'border-box',
              ...resolveAnimatedVisibilityStyle(
                templateGroup.animation,
                cueVisible,
                templateGroup.opacity ?? 1,
              ),
            }}
          >
            <ResultCardRenderer
              scene={scene}
              definitionId={definitionId}
              standing={instance.standing}
              width={instance.slot.width}
              height={instance.slot.height}
              variantOverrides={variantOverrides}
              cueVisible={cueVisible}
              largeImageSource={node.largeImageSource}
              showSmallImage={node.showSmallImage}
              smallImageSource={node.smallImageSource}
            />
          </div>
        );
      })}
    </div>
  );
};
