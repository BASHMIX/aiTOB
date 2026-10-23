import React from 'react';
import { getAnimationStyles } from '../utils';
import { overlayImageLayout, overlayImagePlaceholder, resolveOverlayImageSource } from '@/utils/overlayAssets';
import { MatchMatrixRenderer } from '@/features/editor/components/MatchMatrixRenderer';
import { BracketTreeRenderer } from '@/features/editor/components/BracketTreeRenderer';
import { VictoryPathRenderer } from '@/features/editor/components/VictoryPathRenderer';
import { ResultsGroupRenderer } from '@/scene/ResultsGroupRenderer';
import { ResultCardRenderer } from '@/scene/ResultCardRenderer';
import { useLiveStandings } from '@/features/results/useLiveStandings';
import type { SceneDocumentV2 } from '@/scene/types';

interface OBSElementProps {
  id: string;
  el: any;
  activeMatch?: any;
  cascadeDelay: number;
  transitionState: 'none' | 'in' | 'out' | 'run' | 'idle';
  isGlitched: boolean;
  allElements?: Record<string, any>;
}

export const OBSElement: React.FC<OBSElementProps> = ({
  id,
  el,
  activeMatch,
  cascadeDelay,
  transitionState,
  isGlitched,
  allElements,
}) => {
  if (!el.visible) return null;

  const tournamentSlug = activeMatch?.tournament_slug || undefined;
  const eventId = activeMatch?.event_id || undefined;
  const { standings: liveStandings } = useLiveStandings(
    tournamentSlug,
    eventId,
    el.bracketTestMode ?? false,
    el.preview?.dataset || 'normal'
  );

  const animStyles = getAnimationStyles(el, cascadeDelay, transitionState);

  // Continuous loop / Idle animations
  let loopClass = '';
  if ((transitionState === 'none' || transitionState === 'idle') && el.animation) {
    const idleType = el.animation.idleAnimation || 'none';
    if (idleType !== 'none') {
      loopClass = `idle-animation-${idleType}`;
    } else if (Number(el.animation.loop) === -1) {
      // Legacy fallback
      if (el.animation.animationType === 'fade-in') loopClass = 'continuous-loop-pulse';
      else loopClass = 'continuous-loop-bob';
    }
  }

  // Score changes Glitch class
  const glitchClass = isGlitched ? (el.type === 'text' ? 'esports-glitch-text' : 'esports-glitch') : '';

  let content = null;
  if (el.type === 'text') {
    const strokeStyle = el.strokeWidth && el.strokeColor
      ? `${el.strokeWidth}px ${el.strokeColor}`
      : 'initial';

    const textShadowStyle = isGlitched
      ? undefined
      : (el.shadowColor
        ? `${el.shadowOffsetX || 0}px ${el.shadowOffsetY || 0}px ${el.shadowBlur || 0}px ${el.shadowColor}`
        : 'none');

    const hasReveal = el.animation && el.animation.animationType !== 'none' && el.animation.revealStyle && el.animation.revealStyle !== 'all';

    // Easing curves matching custom easing utilities
    const easings: Record<string, string> = {
      'linear': 'linear',
      'ease-in': 'ease-in',
      'ease-out': 'ease-out',
      'ease-in-out': 'ease-in-out',
      'bounce': 'cubic-bezier(0.175, 0.885, 0.32, 1.275)',
      'back-out': 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      'elastic': 'cubic-bezier(0.25, 1.36, 0.49, 1.16)'
    };
    const easing = easings[el.animation?.tweenType || 'ease-out'] || 'ease-out';
    const duration = el.animation?.duration || 500;
    const isEntrance = transitionState === 'in' && (el.animation?.playOn === 'IN' || el.animation?.playOn === 'BOTH');
    const isExit = transitionState === 'out' && (el.animation?.playOn === 'OUT' || el.animation?.playOn === 'BOTH');

    let textContentToRender = null;
    if (hasReveal && el.animation.revealStyle === 'letter') {
      const chars = String(el.text || '').split('');
      textContentToRender = (
        <span className="inline-flex flex-wrap w-full items-center justify-inherit" style={{ justifyContent: 'inherit' }}>
          {chars.map((char, i) => (
            <span
              key={i}
              style={{
                display: 'inline-block',
                whiteSpace: char === ' ' ? 'pre' : 'normal',
                transition: isEntrance ? 'none' : `transform ${duration}ms ${easing}, opacity ${duration}ms ${easing}`,
                transitionDelay: isEntrance ? '0ms' : `${cascadeDelay + (i * 20)}ms`,
                transform: isEntrance || isExit ? `translateY(35px) scale(${el.animation?.revealScale ?? 0.3}) rotate(-8deg)` : 'none',
                opacity: isEntrance || isExit ? 0 : 1,
              }}
            >
              {char}
            </span>
          ))}
        </span>
      );
    } else if (hasReveal && el.animation.revealStyle === 'word') {
      const words = String(el.text || '').split(' ');
      textContentToRender = (
        <span className="inline-flex flex-wrap w-full items-center justify-inherit" style={{ justifyContent: 'inherit' }}>
          {words.map((word, i) => (
            <span
              key={i}
              style={{
                display: 'inline-block',
                marginRight: '0.25em',
                transition: isEntrance ? 'none' : `transform ${duration}ms ${easing}, opacity ${duration}ms ${easing}`,
                transitionDelay: isEntrance ? '0ms' : `${cascadeDelay + (i * 80)}ms`,
                transform: isEntrance || isExit ? `translateY(45px) scale(${el.animation?.revealScale ?? 0.3}) rotate(-12deg)` : 'none',
                opacity: isEntrance || isExit ? 0 : 1,
              }}
            >
              {word}
            </span>
          ))}
        </span>
      );
    } else {
      textContentToRender = el.text;
    }

    content = (
      <div
        style={{
          color: el.color || '#fff',
          fontSize: `${el.fontSize || 24}px`,
          fontFamily: el.fontFamily || undefined,
          fontWeight: el.fontWeight || 'normal',
          fontStyle: el.fontStyle || 'normal',
          textAlign: el.textAlign || 'left',
          WebkitTextStroke: strokeStyle,
          textShadow: textShadowStyle,
          paintOrder: 'stroke fill',
          width: '100%',
          height: '100%',
          whiteSpace: 'pre-wrap', // Support wrap
          display: 'flex',
          alignItems: 'center',
          justifyContent: el.textAlign === 'center' ? 'center' : el.textAlign === 'right' ? 'flex-end' : 'flex-start'
        }}
        className={glitchClass}
        data-text={el.text}
      >
        {textContentToRender}
      </div>
    );
  } else if (el.type === 'image') {
    const imgShadow = el.shadowColor
      ? `drop-shadow(${el.shadowOffsetX || 0}px ${el.shadowOffsetY || 0}px ${el.shadowBlur || 0}px ${el.shadowColor})`
      : 'none';
    const imageLayout = overlayImageLayout(id, el.width, el.height);
    content = (
      <img
        src={resolveOverlayImageSource(id, el.src)}
        alt=""
        data-overlay-element-id={id}
        onError={(event) => {
          const fallback = overlayImagePlaceholder(id);
          if (event.currentTarget.getAttribute('src') !== fallback) {
            event.currentTarget.src = fallback;
          }
        }}
        className={glitchClass}
        style={{
          ...imageLayout,
          filter: imgShadow
        }}
      />
    );
  } else if (el.type === 'rect' || el.type === 'circle') {
    const shapeShadow = el.shadowColor
      ? `${el.shadowOffsetX || 0}px ${el.shadowOffsetY || 0}px ${el.shadowBlur || 0}px ${el.shadowColor}`
      : 'none';
    const borderStyle = el.strokeWidth && el.strokeColor
      ? `${el.strokeWidth}px solid ${el.strokeColor}`
      : 'none';
    content = (
      <div
        className={glitchClass}
        style={{
          width: '100%',
          height: '100%',
          backgroundColor: el.color || 'rgba(0,0,0,0.5)',
          borderRadius: el.type === 'circle' ? '50%' : `${el.borderRadius || 0}px`,
          boxShadow: shapeShadow,
          border: borderStyle,
          boxSizing: 'border-box'
        }}
      />
    );
  } else if (el.type === 'match-grid') {
    content = (
      <MatchMatrixRenderer
        element={el}
        activeMatch={activeMatch}
        interactive={false}
      />
    );
  } else if (el.type === 'bracket-tree') {
    content = (
      <BracketTreeRenderer
        element={el}
        activeMatch={activeMatch}
      />
    );
  } else if (el.type === 'victory-path') {
    content = (
      <VictoryPathRenderer
        element={el}
        activeMatch={activeMatch}
      />
    );
  } else if (el.type === 'results-group') {
    const sceneDoc: SceneDocumentV2 = {
      schemaVersion: 2,
      canvas: { width: 1920, height: 1080 },
      dataSource: { kind: 'tournament-results' },
      rootIds: [el.id],
      nodes: (allElements || {}) as any,
    };
    const normalizedNode = {
      ...el,
      x: 0,
      y: 0,
      customSlots: el.customSlots?.map((slot: any) => ({
        ...slot,
        x: slot.x - (el.x || 0),
        y: slot.y - (el.y || 0),
      })),
    };
    content = (
      <ResultsGroupRenderer
        scene={sceneDoc}
        node={normalizedNode as any}
        standings={liveStandings}
      />
    );
  } else if (el.type === 'result-card') {
    const sceneDoc: SceneDocumentV2 = {
      schemaVersion: 2,
      canvas: { width: 1920, height: 1080 },
      dataSource: { kind: 'tournament-results' },
      rootIds: [el.id],
      nodes: (allElements || {}) as any,
    };
    const standing = liveStandings.find((entry) => entry.ordinal === (el.standingOrdinal || 1))
      || liveStandings[Math.max(0, (el.standingOrdinal || 1) - 1)]
      || liveStandings[0];
    content = standing ? (
      <ResultCardRenderer
        scene={sceneDoc}
        definitionId={el.definitionId || ''}
        standing={standing}
        width={el.width || 420}
        height={el.height || 560}
        variant={el.variant}
        largeImageSource={el.largeImageSource}
        showSmallImage={el.showSmallImage}
        smallImageSource={el.smallImageSource}
      />
    ) : null;
  }

  return (
    <div
      key={id}
      style={{
        position: 'absolute',
        left: el.x,
        top: el.y,
        width: el.width || 'auto',
        height: el.height || 'auto',
        zIndex: el.zIndex || 1,
        ['--glitch-scale' as any]: el.animation?.glitchScale ?? 1.15,
      }}
    >
      <div
        className={`w-full h-full ${loopClass}`}
        style={{
          ...animStyles,
          ['--idle-intensity' as any]: el.animation?.idleIntensity ?? 1.0,
        }}
      >
        {content}
      </div>
    </div>
  );
};
