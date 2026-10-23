import { useEffect, useState, type CSSProperties } from 'react';
import type { ResultCardNode, SceneDocumentV2, StandingEntrySnapshot } from './types';
import { ResultsGroupRenderer } from './ResultsGroupRenderer';
import { ResultCardRenderer } from './ResultCardRenderer';
import { resolveAutoSequence } from './resolveAutoSequence';
import { resolveLinkedResultCards } from './resolveLinkedResultCards';
import { resolveResultCardLifecycle } from './resolveResultCardAnimation';

interface SceneRendererProps {
  scene: SceneDocumentV2;
  standings?: StandingEntrySnapshot[];
  scale?: number;
  className?: string;
  style?: React.CSSProperties;
  activeCueId?: string | null;
  activeCueIndex?: number;
  playbackState?: string;
  playbackUpdatedAt?: string;
  id?: string;
}

interface SceneNodeViewProps {
  scene: SceneDocumentV2;
  nodeId: string;
  standings: StandingEntrySnapshot[];
  activeCueId?: string | null;
  activeCueIndex?: number;
  playbackElapsedMs?: number;
}

function SceneNodeView({
  scene,
  nodeId,
  standings,
  activeCueId,
  activeCueIndex,
  playbackElapsedMs = 0,
}: SceneNodeViewProps) {
  const node = scene.nodes[nodeId];
  if (!node || !node.visible) return null;

  if (node.type === 'results-group') {
    return (
      <ResultsGroupRenderer
        scene={scene}
        node={node}
        standings={standings}
        activeCueId={activeCueId}
        activeCueIndex={activeCueIndex}
      />
    );
  }

  if (node.type === 'results-cards') {
    const settings = node.autoSequence;
    const stage = settings?.stageInstanceId ? scene.nodes[settings.stageInstanceId] : null;
    const playbackActive = activeCueIndex !== undefined;
    if (playbackActive && (activeCueIndex ?? -1) < 0) {
      return <div key={node.id} data-testid={`results-cards-${node.id}`} />;
    }
    if (
      settings?.enabled
      && stage?.type === 'result-card'
      && activeCueIndex !== undefined
      && activeCueIndex >= 0
    ) {
      const elapsedMs = (activeCueIndex * Math.max(0, settings.delayBetweenStartsMs))
        + Math.max(0, playbackElapsedMs);
      const runtime = resolveAutoSequence(
        node.id,
        standings,
        resolveResultCardLifecycle(stage),
        settings,
        elapsedMs,
      );
      return (
        <div key={node.id} data-testid={`results-cards-${node.id}`}>
          {runtime.filter((instance) => instance.visible).map((instance) => (
            <div
              key={instance.runtimeId}
              style={{
                position: 'absolute', left: instance.transform.x, top: instance.transform.y,
                width: stage.width, height: stage.height, opacity: instance.transform.opacity,
                transform: `scale(${instance.transform.scale}) rotate(${instance.transform.rotation}deg)`,
                transformOrigin: 'center', zIndex: (stage.zIndex || 1) + instance.ordinalIndex,
              }}
            >
              <ResultCardRenderer scene={scene} definitionId={stage.definitionId} standing={instance.standing} width={stage.width} height={stage.height} />
            </div>
          ))}
        </div>
      );
    }
    if (playbackActive) {
      const linkedCards = node.childIds
        .map((childId) => scene.nodes[childId])
        .filter((child): child is ResultCardNode => child?.type === 'result-card');
      const scheduleShape = resolveLinkedResultCards(linkedCards, standings, node.schedule, 0);
      const currentStart = scheduleShape[Math.min(Math.max(0, activeCueIndex || 0), Math.max(0, scheduleShape.length - 1))]?.startTimeMs || 0;
      const runtime = resolveLinkedResultCards(
        linkedCards,
        standings,
        node.schedule,
        currentStart + Math.max(0, playbackElapsedMs),
      );
      return (
        <div key={node.id} data-testid={`results-cards-${node.id}`}>
          {runtime.filter((instance) => instance.animation.visible).map((instance) => (
            <div
              key={`${node.id}-linked-runtime-${instance.card.id}`}
              style={{
                position: 'absolute',
                left: instance.animation.transform.x,
                top: instance.animation.transform.y,
                width: instance.card.width,
                height: instance.card.height,
                opacity: instance.animation.transform.opacity,
                transform: `scale(${instance.animation.transform.scale}) rotate(${instance.animation.transform.rotation}deg)`,
                transformOrigin: 'center',
                zIndex: instance.card.zIndex,
              }}
            >
              <ResultCardRenderer
                scene={scene}
                definitionId={instance.card.definitionId}
                standing={instance.standing}
                width={instance.card.width}
                height={instance.card.height}
                variant={instance.card.variant}
              />
            </div>
          ))}
        </div>
      );
    }
    return (
      <div key={node.id} data-testid={`results-cards-${node.id}`}>
        {node.childIds.map((childId) => (
          <SceneNodeView
            key={childId}
            scene={scene}
            nodeId={childId}
            standings={standings}
            activeCueId={activeCueId}
            activeCueIndex={activeCueIndex}
            playbackElapsedMs={playbackElapsedMs}
          />
        ))}
      </div>
    );
  }

  if (node.type === 'result-card') {
    const standing = standings.find((entry) => entry.ordinal === node.standingOrdinal)
      || standings[Math.max(0, node.standingOrdinal - 1)];
    if (!standing) return null;
    return (
      <div
        key={node.id}
        data-testid={`scene-result-card-${node.id}`}
        style={{
          position: 'absolute', left: node.x, top: node.y,
          width: node.width, height: node.height,
          opacity: node.opacity ?? 1,
          transform: node.rotation ? `rotate(${node.rotation}deg)` : undefined,
          transformOrigin: 'center', zIndex: node.zIndex,
        }}
      >
        <ResultCardRenderer
          scene={scene}
          definitionId={node.definitionId}
          standing={standing}
          width={node.width}
          height={node.height}
          variant={node.variant}
        />
      </div>
    );
  }

  const positioned: CSSProperties = {
    position: 'absolute',
    left: node.x,
    top: node.y,
    width: node.width,
    height: node.height,
    opacity: node.opacity ?? 1,
    transform: node.rotation ? `rotate(${node.rotation}deg)` : undefined,
    transformOrigin: 'center',
    zIndex: node.zIndex,
    boxSizing: 'border-box',
  };

  if (node.type === 'group') {
    if (node.definitionRole === 'result-card' || node.templateRole === 'player-card') return null;
    return (
      <div key={node.id} data-testid={`scene-group-${node.id}`} style={positioned}>
        {node.childIds.map((childId) => (
          <SceneNodeView
            key={childId}
            scene={scene}
            nodeId={childId}
            standings={standings}
            activeCueId={activeCueId}
            activeCueIndex={activeCueIndex}
            playbackElapsedMs={playbackElapsedMs}
          />
        ))}
      </div>
    );
  }

  if (node.type === 'text') {
    const textAlign = node.textAlign || 'left';
    return (
      <div
        key={node.id}
        data-testid={`scene-text-${node.id}`}
        style={{
          ...positioned,
          fontSize: node.fontSize || 24,
          fontFamily: node.fontFamily || scene.canvas.globalFontFamily || 'sans-serif',
          fontWeight: node.fontWeight || 'normal',
          fontStyle: node.fontStyle || 'normal',
          color: node.color || '#ffffff',
          textAlign,
          display: 'flex', alignItems: 'center',
          justifyContent: textAlign === 'center' ? 'center' : textAlign === 'right' ? 'flex-end' : 'flex-start',
          lineHeight: 1.2, userSelect: 'none',
        }}
      >
        {node.text || ''}
      </div>
    );
  }

  if (node.type === 'rect' || node.type === 'circle') {
    return (
      <div
        key={node.id}
        data-testid={`scene-${node.type}-${node.id}`}
        style={{
          ...positioned,
          backgroundColor: node.color || 'transparent',
          borderRadius: node.type === 'circle' ? '50%' : `${node.borderRadius || 0}px`,
          border: node.strokeColor ? `${node.strokeWidth || 1}px solid ${node.strokeColor}` : 'none',
        }}
      />
    );
  }

  if (node.type === 'image' && node.src) {
    return (
      <img
        key={node.id}
        data-testid={`scene-image-${node.id}`}
        src={node.src}
        alt={node.name || 'scene-image'}
        crossOrigin="anonymous"
        style={{
          ...positioned,
          objectFit: node.objectFit || 'cover',
          borderRadius: node.borderRadius || 0,
          pointerEvents: 'none',
        }}
      />
    );
  }

  return null;
}

export const SceneRenderer: React.FC<SceneRendererProps> = ({
  scene,
  standings = [],
  scale = 1,
  className = '',
  style = {},
  activeCueId,
  activeCueIndex,
  playbackState,
  playbackUpdatedAt,
  id,
}) => {
  const width = scene.canvas.width || 1920;
  const height = scene.canvas.height || 1080;
  const [playbackElapsedMs, setPlaybackElapsedMs] = useState(0);

  useEffect(() => {
    const shouldRun = playbackState === 'live' || playbackState === 'complete';
    const updatedAtMs = playbackUpdatedAt ? Date.parse(playbackUpdatedAt) : Number.NaN;
    if (!shouldRun || !Number.isFinite(updatedAtMs)) {
      setPlaybackElapsedMs(0);
      return;
    }
    let frame = 0;
    const tick = () => {
      setPlaybackElapsedMs(Math.max(0, Date.now() - updatedAtMs));
      frame = requestAnimationFrame(tick);
    };
    tick();
    return () => cancelAnimationFrame(frame);
  }, [playbackState, playbackUpdatedAt, activeCueIndex]);
  return (
    <div
      id={id}
      data-testid="scene-renderer-canvas"
      className={className}
      style={{
        position: 'relative', width, height,
        backgroundColor: scene.canvas.backgroundUrl ? undefined : '#0d1117',
        backgroundImage: scene.canvas.backgroundUrl ? `url(${scene.canvas.backgroundUrl})` : undefined,
        backgroundSize: 'cover', backgroundPosition: 'center', overflow: 'hidden',
        transform: scale !== 1 ? `scale(${scale})` : undefined,
        transformOrigin: 'top left',
        ...style,
      }}
    >
      {scene.rootIds.map((rootId) => (
        <SceneNodeView
          key={rootId}
          scene={scene}
          nodeId={rootId}
          standings={standings}
          activeCueId={activeCueId}
          activeCueIndex={activeCueIndex}
          playbackElapsedMs={playbackElapsedMs}
        />
      ))}
    </div>
  );
};
