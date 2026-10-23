import { useState, useEffect, useRef } from 'react';
import { Rnd } from 'react-rnd';
import { useEditorStore } from '@/store/useEditorStore';
import { countryFlagUrl } from '@/utils/country';
import { overlayImageLayout, overlayImagePlaceholder, resolveOverlayImageSource } from '@/utils/overlayAssets';
import type { OverlayElement } from '@/store/useEditorStore';
import { useDraggable } from '../hooks/useDraggable';
import { ResultsGroupRenderer } from '@/scene/ResultsGroupRenderer';
import { ResultCardRenderer } from '@/scene/ResultCardRenderer';
import { MatchMatrixRenderer } from './MatchMatrixRenderer';
import { BracketTreeRenderer } from './BracketTreeRenderer';
import { VictoryPathRenderer } from './VictoryPathRenderer';
import { useHubStore } from '@/store/useHubStore';
import { useLiveStandings } from '@/features/results/useLiveStandings';
import type { SceneDocumentV2 } from '@/scene/types';

function resolveCascadeDelays(elements: Record<string, any>) {
  const sorted = Object.entries(elements).sort(
    (a, b) => (a[1].zIndex || 0) - (b[1].zIndex || 0)
  );

  const resolvedDelays: Record<string, number> = {};
  let lastDuration = 0;

  for (let i = 0; i < sorted.length; i++) {
    const [id, el] = sorted[i];
    const anim = el.animation;
    if (!anim || anim.animationType === 'none') {
      resolvedDelays[id] = 0;
      continue;
    }

    const selfDelay = anim.delay || 0;
    const selfDuration = anim.duration || 500;

    if (anim.trigger === 'after-prev' && i > 0) {
      const prevId = sorted[i - 1][0];
      const start = (resolvedDelays[prevId] || 0) + lastDuration + selfDelay;
      resolvedDelays[id] = start;
    } else if (anim.trigger === 'with-prev' && i > 0) {
      const prevId = sorted[i - 1][0];
      const start = (resolvedDelays[prevId] || 0) + selfDelay;
      resolvedDelays[id] = start;
    } else {
      resolvedDelays[id] = selfDelay;
    }

    lastDuration = selfDuration;
  }

  return resolvedDelays;
}

interface Props {
  id: string;
  element: OverlayElement;
  scale: number;
  onContextMenu?: (e: React.MouseEvent) => void;
}

export function DraggableElement({ id, element, scale, onContextMenu }: Props) {
  const store = useEditorStore();
  const { updateElement, selectedId, selectedIds, setSelectedId, toggleSelectedId, activeMatch } = store;

  const { onResize, onResizeStop } = useDraggable(id, updateElement);

  const [isPlaying, setIsPlaying] = useState(false);
  const [isLooping, setIsLooping] = useState(false);
  const [useCascade, setUseCascade] = useState(false);
  const [hiddenForAutoSequence, setHiddenForAutoSequence] = useState(false);
  const groupDragOrigin = useRef<Record<string, { x: number; y: number }> | null>(null);

  const currentSlug = useHubStore((s) => s.currentSlug);
  const currentEventId = useHubStore((s) => s.currentEventId);
  const tournaments = useHubStore((s) => s.tournaments);
  const activeTournament = tournaments.find((t) => t.slug === currentSlug) || tournaments[0] || null;
  const tournamentSlug = activeTournament?.slug || currentSlug || undefined;
  const eventId = activeTournament?.event_id || currentEventId || undefined;

  const datasetKey = element.type === 'results-group'
    ? (element.preview?.dataset || 'normal')
    : element.type === 'result-card'
    ? (store.elements[element.parentId || '']?.preview?.dataset || 'normal')
    : 'normal';

  const isTestMode = element.bracketTestMode ?? false;
  const { standings: liveStandings } = useLiveStandings(
    tournamentSlug,
    eventId,
    isTestMode,
    datasetKey
  );

  const beginGroupDrag = () => {
    if (!selectedIds.includes(id)) setSelectedId(id);
    const ids = selectedIds.includes(id) ? selectedIds : [id];
    groupDragOrigin.current = Object.fromEntries(ids.map((selected) => {
      const item = store.elements[selected];
      return [selected, { x: item?.x || 0, y: item?.y || 0 }];
    }));
    store.takeSnapshot();
  };

  const dragGroup = (_event: any, data: any) => {
    const origin = groupDragOrigin.current;
    if (!origin || !origin[id]) return;
    const dx = Math.round(data.x) - origin[id].x;
    const dy = Math.round(data.y) - origin[id].y;
    Object.entries(origin).forEach(([selected, position]) => {
      updateElement(selected, { x: position.x + dx, y: position.y + dy });
    });
  };

  const finishGroupDrag = (_event: any, data: any) => {
    dragGroup(_event, data);
    groupDragOrigin.current = null;
  };

  // Play preview event listener
  useEffect(() => {
    const handlePreview = (e: Event) => {
      const isGlobal = e.type === 'play-slide-preview';
      const customEvent = e as CustomEvent;
      
      if (isGlobal || customEvent.detail?.id === id) {
        setIsLooping(false);
        setIsPlaying(true);
        setUseCascade(isGlobal);
        
        const timer1 = setTimeout(() => {
          setIsPlaying(false);
        }, 30);
        
        // Solve cascade sequence delays
        const delays = resolveCascadeDelays(store.elements || {});
        const cascadeDelay = delays[id] || 0;
        
        const duration = element.animation?.duration || 500;
        const selfDelay = element.animation?.delay || 0;
        const totalDelay = isGlobal ? cascadeDelay : selfDelay;
        
        const timer2 = setTimeout(() => {
          if (element.animation?.loop === -1) {
            setIsLooping(true);
          }
          setUseCascade(false);
        }, totalDelay + duration + 50);




        return () => {
          clearTimeout(timer1);
          clearTimeout(timer2);
        };
      }
    };
    
    window.addEventListener('play-element-preview', handlePreview);
    window.addEventListener('play-slide-preview', handlePreview);
    
    return () => {
      window.removeEventListener('play-element-preview', handlePreview);
      window.removeEventListener('play-slide-preview', handlePreview);
    };
  }, [id, element.animation, store.elements]);

  useEffect(() => {
    if (element.type !== 'result-card' || !element.parentId) return;
    const handleSequenceControl = (event: Event) => {
      const detail = (event as CustomEvent).detail;
      if (detail?.groupId !== element.parentId) return;
      if (detail.action === 'play' || detail.action === 'restart' || detail.action === 'next' || detail.action === 'previous') {
        setHiddenForAutoSequence(true);
      } else if (detail.action === 'clear') {
        setHiddenForAutoSequence(false);
      }
    };
    const handleSequenceEnded = (event: Event) => {
      const detail = (event as CustomEvent).detail;
      if (detail?.groupId === element.parentId) setHiddenForAutoSequence(false);
    };
    window.addEventListener('result-sequence-control', handleSequenceControl);
    window.addEventListener('result-sequence-preview-ended', handleSequenceEnded);
    return () => {
      window.removeEventListener('result-sequence-control', handleSequenceControl);
      window.removeEventListener('result-sequence-preview-ended', handleSequenceEnded);
    };
  }, [element.type, element.parentId]);

  const belongsToCardDefinition = (() => {
    let currentId: string | undefined = id;
    const visited = new Set<string>();
    while (currentId && !visited.has(currentId)) {
      visited.add(currentId);
      const current = store.elements[currentId];
      if (current?.type === 'group' && (current.definitionRole === 'result-card' || current.templateRole === 'player-card')) return true;
      currentId = store.elements[currentId]?.parentId || undefined;
    }
    return false;
  })();

  // Player Card templates are authored through the Layers tree but rendered
  // only through their Results Group. Drawing them independently duplicates
  // the master and its children on top of the generated preview cards.
  if (belongsToCardDefinition || element.type === 'results-cards') return null;
  if (!element.visible) return null;

  const isImg = element.type === 'image';
  const isShape = element.type === 'rect' || element.type === 'circle';
  const isSelected = selectedIds.includes(id) || selectedId === id;

  // Substitute active match data into telemetry data hooks dynamically for preview
  let textToRender = element.text;
  let srcToRender = element.src;

  const hookKey = element.sourceId || id;

  if (activeMatch) {
    const isSwapped = activeMatch.swapped === true || activeMatch.swapped === 1 || activeMatch.swapped === '1';

    // Swap players' data temporarily if swap toggle is active
    const p1Name = isSwapped ? activeMatch.p2_name : activeMatch.p1_name;
    const p2Name = isSwapped ? activeMatch.p1_name : activeMatch.p2_name;
    const p1Score = isSwapped ? activeMatch.p2_score : activeMatch.p1_score;
    const p2Score = isSwapped ? activeMatch.p1_score : activeMatch.p2_score;
    const p1Prefix = isSwapped
      ? (activeMatch.p2_prefix ?? activeMatch.p2_team)
      : (activeMatch.p1_prefix ?? activeMatch.p1_team);
    const p2Prefix = isSwapped
      ? (activeMatch.p1_prefix ?? activeMatch.p1_team)
      : (activeMatch.p2_prefix ?? activeMatch.p2_team);
    const p1Character = isSwapped ? activeMatch.p2_character : activeMatch.p1_character;
    const p2Character = isSwapped ? activeMatch.p1_character : activeMatch.p2_character;
    const p1CharacterImage = isSwapped ? activeMatch.p2_character_image : activeMatch.p1_character_image;
    const p2CharacterImage = isSwapped ? activeMatch.p1_character_image : activeMatch.p2_character_image;
    const p1Avatar = isSwapped ? activeMatch.p2_avatar : activeMatch.p1_avatar;
    const p2Avatar = isSwapped ? activeMatch.p1_avatar : activeMatch.p2_avatar;
    const p1Country = isSwapped ? activeMatch.p2_country : activeMatch.p1_country;
    const p2Country = isSwapped ? activeMatch.p1_country : activeMatch.p2_country;
    const p1Cfn = isSwapped ? activeMatch.p2_cfn : activeMatch.p1_cfn;
    const p2Cfn = isSwapped ? activeMatch.p1_cfn : activeMatch.p2_cfn;

    if (hookKey === 'p1_name') textToRender = p1Name || 'Player 1';
    else if (hookKey === 'p2_name') textToRender = p2Name || 'Player 2';
    else if (hookKey === 'p1_score') textToRender = String(p1Score ?? '0');
    else if (hookKey === 'p2_score') textToRender = String(p2Score ?? '0');
    else if (hookKey === 'p1_prefix' || hookKey === 'p1_team') textToRender = p1Prefix || '';
    else if (hookKey === 'p2_prefix' || hookKey === 'p2_team') textToRender = p2Prefix || '';
    else if (hookKey === 'p1_country') textToRender = p1Country || '';
    else if (hookKey === 'p2_country') textToRender = p2Country || '';
    else if (hookKey === 'p1_cfn') textToRender = p1Cfn || '';
    else if (hookKey === 'p2_cfn') textToRender = p2Cfn || '';
    else if (hookKey === 'p1_character') textToRender = p1Character || '';
    else if (hookKey === 'p2_character') textToRender = p2Character || '';
    else if (hookKey === 'game_name') textToRender = activeMatch.game_name || '';
    else if (hookKey === 'tournament_round') textToRender = activeMatch.round_name || '';
    else if (hookKey === 'match_format_badge') {
      const bestOf = Number(activeMatch.best_of) || 9;
      const targetWins = Math.floor(bestOf / 2) + 1;
      textToRender = `FIRST TO ${targetWins} GAMES`;
    }
    else if (hookKey === 'p1_avatar') srcToRender = p1Avatar || '/static/player_placeholder.jpg';
    else if (hookKey === 'p2_avatar') srcToRender = p2Avatar || '/static/player_placeholder.jpg';
    else if (hookKey === 'p1_character_image') srcToRender = p1CharacterImage || '/static/player_placeholder.jpg';
    else if (hookKey === 'p2_character_image') srcToRender = p2CharacterImage || '/static/player_placeholder.jpg';
    else if (hookKey === 'p1_flag') {
      srcToRender = countryFlagUrl(p1Country) || '/static/flag_placeholder.png';
    }
    else if (hookKey === 'p2_flag') {
      srcToRender = countryFlagUrl(p2Country) || '/static/flag_placeholder.png';
    }

    const nextMatch = activeMatch.next_match;
    if (nextMatch) {
      if (hookKey === 'next_p1_name') textToRender = nextMatch.p1_name || element.text || 'Next Player 1';
      else if (hookKey === 'next_p2_name') textToRender = nextMatch.p2_name || element.text || 'Next Player 2';
      else if (hookKey === 'next_p1_score') textToRender = String(nextMatch.p1_score ?? element.text ?? '0');
      else if (hookKey === 'next_p2_score') textToRender = String(nextMatch.p2_score ?? element.text ?? '0');
      else if (hookKey === 'next_p1_prefix') textToRender = nextMatch.p1_prefix || nextMatch.p1_team || element.text || '';
      else if (hookKey === 'next_p2_prefix') textToRender = nextMatch.p2_prefix || nextMatch.p2_team || element.text || '';
      else if (hookKey === 'next_p1_country') textToRender = nextMatch.p1_country || element.text || '';
      else if (hookKey === 'next_p2_country') textToRender = nextMatch.p2_country || element.text || '';
      else if (hookKey === 'next_p1_character') textToRender = nextMatch.p1_character || element.text || '';
      else if (hookKey === 'next_p2_character') textToRender = nextMatch.p2_character || element.text || '';
      else if (hookKey === 'next_round_name') textToRender = nextMatch.round_name || element.text || 'Next Round';
      else if (hookKey === 'next_match_number') textToRender = nextMatch.match_number ? `Match #${nextMatch.match_number}` : (element.text || '');
      else if (hookKey === 'next_match_status') textToRender = nextMatch.match_status || nextMatch.status || element.text || 'Up Next';
      else if (hookKey === 'next_p1_avatar') srcToRender = nextMatch.p1_avatar || element.src || '/static/player_placeholder.jpg';
      else if (hookKey === 'next_p2_avatar') srcToRender = nextMatch.p2_avatar || element.src || '/static/player_placeholder.jpg';
      else if (hookKey === 'next_p1_flag') srcToRender = countryFlagUrl(nextMatch.p1_country) || element.src || '/static/flag_placeholder.png';
      else if (hookKey === 'next_p2_flag') srcToRender = countryFlagUrl(nextMatch.p2_country) || element.src || '/static/flag_placeholder.png';
    }
  }

  // Render content
  let content = null;
  if (isImg) {
    const imgShadow = element.shadowColor 
      ? `drop-shadow(${element.shadowOffsetX || 0}px ${element.shadowOffsetY || 0}px ${element.shadowBlur || 0}px ${element.shadowColor})`
      : 'none';
    const imageLayout = overlayImageLayout(hookKey, element.width, element.height);
    content = (
      <img 
        src={resolveOverlayImageSource(hookKey, srcToRender)}
        alt="" 
        onError={(event) => {
          const fallback = overlayImagePlaceholder(hookKey);
          if (event.currentTarget.getAttribute('src') !== fallback) {
            event.currentTarget.src = fallback;
          }
        }}
        className="block pointer-events-none"
        style={{ ...imageLayout, filter: imgShadow }}
      />
    );
  } else if (element.type === 'result-card') {
    const sceneDoc: SceneDocumentV2 = {
      schemaVersion: 2,
      canvas: { width: 1920, height: 1080 },
      dataSource: { kind: 'tournament-results' },
      rootIds: [element.id],
      nodes: store.elements as any,
    };
    const standing = liveStandings.find((entry) => entry.ordinal === (element.standingOrdinal || 1))
      || liveStandings[Math.max(0, (element.standingOrdinal || 1) - 1)]
      || liveStandings[0];
    content = standing ? (
      <ResultCardRenderer
        scene={sceneDoc}
        definitionId={element.definitionId || ''}
        standing={standing}
        width={element.width || 420}
        height={element.height || 560}
        variant={element.variant}
        largeImageSource={element.largeImageSource}
        showSmallImage={element.showSmallImage}
        smallImageSource={element.smallImageSource}
      />
    ) : null;
  } else if (element.type === 'results-group') {
    const sceneDoc: SceneDocumentV2 = {
      schemaVersion: 2,
      canvas: { width: 1920, height: 1080 },
      dataSource: { kind: 'tournament-results' },
      rootIds: [element.id],
      nodes: store.elements as any,
    };
    const previewNode = {
      ...element,
      x: 0,
      y: 0,
      customSlots: element.customSlots?.map((slot) => ({
        ...slot,
        x: slot.x - (element.x || 0),
        y: slot.y - (element.y || 0),
      })),
    };
    content = (
      <div className="w-full h-full border border-dashed border-[#00ffcc]/40 relative pointer-events-none select-none">
        <ResultsGroupRenderer
          scene={sceneDoc}
          node={previewNode as any}
          standings={liveStandings}
          activeCueIndex={store.resultsPreviewCueIndex[element.id]}
        />
      </div>
    );
  } else if (element.type === 'match-grid') {
    content = (
      <MatchMatrixRenderer
        element={element}
        activeMatch={activeMatch}
        interactive={true}
        onUpdateHistory={(newHistory) => {
          store.updateElement(id, { gamesHistoryOverride: newHistory });
        }}
      />
    );
  } else if (element.type === 'bracket-tree') {
    content = (
      <BracketTreeRenderer
        element={element}
        activeMatch={activeMatch}
      />
    );
  } else if (element.type === 'victory-path') {
    content = (
      <VictoryPathRenderer
        element={element}
        activeMatch={activeMatch}
      />
    );
  } else if (element.type === 'group') {
    content = (
      <div className="w-full h-full border-2 border-dashed border-amber-400/50 rounded bg-amber-500/5 p-2 pointer-events-none select-none">
        <span className="text-[10px] font-bold text-amber-300 uppercase tracking-wider bg-black/60 px-1.5 py-0.5 rounded border border-amber-500/30">
          {element.definitionRole === 'result-card' || element.templateRole === 'player-card' ? 'Result Card Design' : 'Group'}
        </span>
      </div>
    );
  } else if (isShape) {
    const shapeShadow = element.shadowColor
      ? `${element.shadowOffsetX || 0}px ${element.shadowOffsetY || 0}px ${element.shadowBlur || 0}px ${element.shadowColor}`
      : 'none';
    const borderStyle = element.strokeWidth && element.strokeColor
      ? `${element.strokeWidth}px solid ${element.strokeColor}`
      : 'none';
    content = (
      <div 
        className="w-full h-full"
        style={{ 
          backgroundColor: element.color || 'rgba(255,255,255,0.5)', 
          borderRadius: element.type === 'circle' ? '50%' : `${element.borderRadius || 0}px`,
          boxShadow: shapeShadow,
          border: borderStyle,
          boxSizing: 'border-box'
        }} 
      />
    );
  } else {
    // Text elements: Support alignment, fonts, strokes, text wrap, and text shadow
    const strokeStyle = element.strokeWidth && element.strokeColor
      ? `${element.strokeWidth}px ${element.strokeColor}`
      : 'initial';

    const textShadowStyle = element.shadowColor
      ? `${element.shadowOffsetX || 0}px ${element.shadowOffsetY || 0}px ${element.shadowBlur || 0}px ${element.shadowColor}`
      : 'none';

    const hasReveal = element.animation && element.animation.animationType !== 'none' && element.animation.revealStyle && element.animation.revealStyle !== 'all';
    
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
    const easing = easings[element.animation?.tweenType || 'ease-out'] || 'ease-out';
    const duration = element.animation?.duration || 500;
    const delay = element.animation?.delay || 0;

    let textContentToRender = null;
    if (hasReveal && element.animation?.revealStyle === 'letter') {
      const chars = String(textToRender || '').split('');
      textContentToRender = (
        <span className="inline-flex flex-wrap w-full items-center justify-inherit" style={{ justifyContent: 'inherit' }}>
          {chars.map((char, i) => (
            <span
              key={i}
              style={{
                display: 'inline-block',
                whiteSpace: char === ' ' ? 'pre' : 'normal',
                transition: isPlaying ? 'none' : `transform ${duration}ms ${easing}, opacity ${duration}ms ${easing}`,
                transitionDelay: isPlaying ? '0ms' : `${delay + (i * 20)}ms`,
                transform: isPlaying ? `translateY(35px) scale(${element.animation?.revealScale ?? 0.3}) rotate(-8deg)` : 'none',
                opacity: isPlaying ? 0 : 1,
              }}
            >
              {char}
            </span>
          ))}
        </span>
      );
    } else if (hasReveal && element.animation?.revealStyle === 'word') {
      const words = String(textToRender || '').split(' ');
      textContentToRender = (
        <span className="inline-flex flex-wrap w-full items-center justify-inherit" style={{ justifyContent: 'inherit' }}>
          {words.map((word, i) => (
            <span
              key={i}
              style={{
                display: 'inline-block',
                marginRight: '0.25em',
                transition: isPlaying ? 'none' : `transform ${duration}ms ${easing}, opacity ${duration}ms ${easing}`,
                transitionDelay: isPlaying ? '0ms' : `${delay + (i * 80)}ms`,
                transform: isPlaying ? `translateY(45px) scale(${element.animation?.revealScale ?? 0.3}) rotate(-12deg)` : 'none',
                opacity: isPlaying ? 0 : 1,
              }}
            >
              {word}
            </span>
          ))}
        </span>
      );
    } else {
      textContentToRender = textToRender;
    }

    content = (
      <div 
        style={{ 
          fontSize: `${element.fontSize || 24}px`, 
          fontFamily: element.fontFamily || undefined,
          color: element.color || '#ffffff',
          fontWeight: element.fontWeight || 'normal',
          fontStyle: element.fontStyle || 'normal',
          textAlign: element.textAlign || 'left',
          WebkitTextStroke: strokeStyle,
          textShadow: textShadowStyle,
          paintOrder: 'stroke fill',
          width: '100%',
          height: '100%',
          whiteSpace: 'pre-wrap', // Support multi-line layout wrapping
          display: 'flex',
          alignItems: 'center',
          justifyContent: element.textAlign === 'center' ? 'center' : element.textAlign === 'right' ? 'flex-end' : 'flex-start'
        }} 
        className="w-full h-full select-none"
      >
        {textContentToRender}
      </div>
    );
  }

  // Text elements should also have width and height resizability for align-alignment bounding box
  const hasFixedSize = true; 

  const getAnimationStyles = () => {
    if (!element.animation || element.animation.animationType === 'none') return {};

    const { animationType, direction, duration, delay, tweenType } = element.animation;

    const easings: Record<string, string> = {
      'linear': 'linear',
      'ease-in': 'ease-in',
      'ease-out': 'ease-out',
      'ease-in-out': 'ease-in-out',
      'bounce': 'cubic-bezier(0.175, 0.885, 0.32, 1.275)',
      'back-out': 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      'elastic': 'cubic-bezier(0.25, 1.36, 0.49, 1.16)'
    };
    const easing = easings[tweenType] || 'ease-out';

    let startX = 0;
    let startY = 0;
    let startOpacity = 1;

    const w = element.width || 250;
    const h = element.height || 60;
    const x = element.x || 0;
    const y = element.y || 0;

    // Nominal canvas dimensions
    const canvasWidth = 1920;
    const canvasHeight = 1080;

    if (animationType === 'fly-in') {
      if (direction === 'bottom') startY = canvasHeight - y;
      else if (direction === 'top') startY = -y - h;
      else if (direction === 'left') startX = -x - w;
      else if (direction === 'right') startX = canvasWidth - x;
      else if (direction === 'bottom-left') { startX = -x - w; startY = canvasHeight - y; }
      else if (direction === 'bottom-right') { startX = canvasWidth - x; startY = canvasHeight - y; }
      else if (direction === 'top-left') { startX = -x - w; startY = -y - h; }
      else if (direction === 'top-right') { startX = canvasWidth - x; startY = -y - h; }
    } else if (animationType === 'float-in') {
      startOpacity = 0;
      if (direction === 'bottom') startY = 50;
      else if (direction === 'top') startY = -50;
      else if (direction === 'left') startX = -50;
      else if (direction === 'right') startX = 50;
      else if (direction === 'bottom-left') { startX = -35; startY = 35; }
      else if (direction === 'bottom-right') { startX = 35; startY = 35; }
      else if (direction === 'top-left') { startX = -35; startY = -35; }
      else if (direction === 'top-right') { startX = 35; startY = -35; }
    } else if (animationType === 'fade-in') {
      startOpacity = 0;
    }

    // Solve delays for global cascades preview
    const delays = resolveCascadeDelays(store.elements || {});
    const cascadeDelay = delays[id] || 0;
    const resolvedDelay = useCascade ? cascadeDelay : delay;

    if (isLooping && element.animation && ((element.animation.idleAnimation && element.animation.idleAnimation !== 'none') || element.animation.loop === -1)) {
      return {
        transition: 'none',
      };
    }

    return {
      transition: isPlaying ? 'none' : `transform ${duration}ms ${easing} ${resolvedDelay}ms, opacity ${duration}ms ${easing} ${resolvedDelay}ms`,
      transform: isPlaying ? `translate(${startX}px, ${startY}px)` : 'translate(0, 0)',
      opacity: isPlaying ? startOpacity : 1,
    };
  };

  const animStyles = getAnimationStyles();
  
  // Decide loop animations
  let loopClass = '';
  if (isLooping && element.animation) {
    const idleType = element.animation.idleAnimation || 'none';
    if (idleType !== 'none') {
      loopClass = `idle-animation-${idleType}`;
    } else if (Number(element.animation.loop) === -1) {
      if (element.animation.animationType === 'fade-in') loopClass = 'continuous-loop-pulse';
      else loopClass = 'continuous-loop-bob';
    }
  }

  return (
    <Rnd
      key={id}
      scale={scale}
      position={{ x: Math.round(element.x), y: Math.round(element.y) }}
      size={hasFixedSize ? { width: Math.round(element.width || 250), height: Math.round(element.height || 60) } : undefined}
      onDrag={dragGroup}
      onDragStop={finishGroupDrag}
      onDragStart={beginGroupDrag}
      onResize={hasFixedSize ? onResize : undefined}
      onResizeStop={hasFixedSize ? onResizeStop : undefined}
      onResizeStart={() => { store.takeSnapshot(); setSelectedId(id); }}
      disableDragging={false}
      enableResizing={hasFixedSize}
      style={{ zIndex: isSelected ? 100 : (element.zIndex || 1) }}
      data-overlay-element="true"
      data-overlay-element-id={id}
      onMouseDown={(event) => {
        if (event.ctrlKey || event.metaKey || event.shiftKey) toggleSelectedId(id);
        else setSelectedId(id);
      }}
      className={`select-none text-center box-border ${isSelected ? 'outline-dashed outline-2 outline-[#00ffcc]' : ''}`}
      bounds={element.type === 'result-card' ? undefined : 'parent'}
      dragGrid={[1, 1]}
      resizeGrid={[1, 1]}
    >
      <div 
        className={`w-full h-full ${loopClass}`} 
        style={{
          ...animStyles,
          visibility: hiddenForAutoSequence ? 'hidden' : 'visible',
          opacity: (animStyles as any).opacity ?? element.opacity ?? 1,
          rotate: element.rotation ? `${element.rotation}deg` : undefined,
          ['--idle-intensity' as any]: element.animation?.idleIntensity ?? 1.0,
        }} 
        onContextMenu={onContextMenu}
      >
        {content}
      </div>
    </Rnd>
  );
}
