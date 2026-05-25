import { useState, useEffect } from 'react';
import { Rnd } from 'react-rnd';
import { useEditorStore } from '@/store/useEditorStore';
import type { OverlayElement } from '@/store/useEditorStore';

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
  const { updateElement, selectedId, setSelectedId, activeMatch } = store;

  const [isPlaying, setIsPlaying] = useState(false);
  const [isLooping, setIsLooping] = useState(false);
  const [useCascade, setUseCascade] = useState(false);

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

  if (!element.visible) return null;

  const isImg = element.type === 'image';
  const isShape = element.type === 'rect' || element.type === 'circle';
  const isSelected = selectedId === id;

  // Substitute active match data into telemetry data hooks dynamically for preview
  let textToRender = element.text;
  let srcToRender = element.src;

  if (activeMatch) {
    const isSwapped = activeMatch.swapped === true || activeMatch.swapped === 1 || activeMatch.swapped === '1';

    // Swap players' data temporarily if swap toggle is active
    const p1Name = isSwapped ? activeMatch.p2_name : activeMatch.p1_name;
    const p2Name = isSwapped ? activeMatch.p1_name : activeMatch.p2_name;
    const p1Score = isSwapped ? activeMatch.p2_score : activeMatch.p1_score;
    const p2Score = isSwapped ? activeMatch.p1_score : activeMatch.p2_score;
    const p1Team = isSwapped ? activeMatch.p2_team : activeMatch.p1_team;
    const p2Team = isSwapped ? activeMatch.p1_team : activeMatch.p2_team;
    const p1Avatar = isSwapped ? activeMatch.p2_avatar : activeMatch.p1_avatar;
    const p2Avatar = isSwapped ? activeMatch.p1_avatar : activeMatch.p2_avatar;
    const p1Country = isSwapped ? activeMatch.p2_country : activeMatch.p1_country;
    const p2Country = isSwapped ? activeMatch.p1_country : activeMatch.p2_country;

    if (id === 'p1_name') textToRender = p1Name || 'Player 1';
    else if (id === 'p2_name') textToRender = p2Name || 'Player 2';
    else if (id === 'p1_score') textToRender = String(p1Score ?? '0');
    else if (id === 'p2_score') textToRender = String(p2Score ?? '0');
    else if (id === 'p1_team') textToRender = p1Team || '';
    else if (id === 'p2_team') textToRender = p2Team || '';
    else if (id === 'tournament_round') textToRender = activeMatch.round_name || '';
    else if (id === 'p1_avatar') srcToRender = p1Avatar || '/static/player_placeholder.jpg';
    else if (id === 'p2_avatar') srcToRender = p2Avatar || '/static/player_placeholder.jpg';
    else if (id === 'p1_flag') {
      srcToRender = p1Country 
        ? `https://flagcdn.com/160x120/${p1Country.toLowerCase()}.png` 
        : '/static/flag_placeholder.png';
    }
    else if (id === 'p2_flag') {
      srcToRender = p2Country 
        ? `https://flagcdn.com/160x120/${p2Country.toLowerCase()}.png` 
        : '/static/flag_placeholder.png';
    }
  }

  // Render content
  let content = null;
  if (isImg) {
    const imgShadow = element.shadowColor 
      ? `drop-shadow(${element.shadowOffsetX || 0}px ${element.shadowOffsetY || 0}px ${element.shadowBlur || 0}px ${element.shadowColor})`
      : 'none';
    content = (
      <img 
        src={srcToRender} 
        alt="" 
        className="w-full h-full object-contain block pointer-events-none" 
        style={{ filter: imgShadow }}
      />
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

  // Snap dragging stop to precise integers to prevent CSS fractional shift
  const onDragStop = (_e: any, d: any) => {
    updateElement(id, { x: Math.round(d.x), y: Math.round(d.y) });
  };

  // Update store coordinates in real-time while dragging to prevent controlled input snapback on re-renders
  const onDrag = (_e: any, d: any) => {
    updateElement(id, { x: Math.round(d.x), y: Math.round(d.y) });
  };

  // Snap resizing to precise integers to prevent coordinate drift
  const onResizeStop = (_e: any, _direction: any, ref: any, _delta: any, position: any) => {
    updateElement(id, {
      width: Math.round(parseInt(ref.style.width, 10)),
      height: Math.round(parseInt(ref.style.height, 10)),
      x: Math.round(position.x),
      y: Math.round(position.y)
    });
  };

  // Update store width/height/coordinates in real-time while resizing to keep inputs and bounding box in sync
  const onResize = (_e: any, _direction: any, ref: any, _delta: any, position: any) => {
    updateElement(id, {
      width: Math.round(parseInt(ref.style.width, 10)),
      height: Math.round(parseInt(ref.style.height, 10)),
      x: Math.round(position.x),
      y: Math.round(position.y)
    });
  };

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
      onDrag={onDrag}
      onDragStop={onDragStop}
      onDragStart={() => { store.takeSnapshot(); setSelectedId(id); }}
      onResize={hasFixedSize ? onResize : undefined}
      onResizeStop={hasFixedSize ? onResizeStop : undefined}
      onResizeStart={() => { store.takeSnapshot(); setSelectedId(id); }}
      disableDragging={false}
      enableResizing={hasFixedSize}
      style={{ zIndex: isSelected ? 100 : (element.zIndex || 1) }}
      onMouseDown={() => {
        setSelectedId(id);
      }}
      className={`select-none text-center box-border ${isSelected ? 'outline-dashed outline-2 outline-[#00ffcc]' : ''}`}
      bounds="parent"
      dragGrid={[1, 1]}
      resizeGrid={[1, 1]}
    >
      <div 
        className={`w-full h-full ${loopClass}`} 
        style={{
          ...animStyles,
          ['--idle-intensity' as any]: element.animation?.idleIntensity ?? 1.0,
        }} 
        onContextMenu={onContextMenu}
      >
        {content}
      </div>
    </Rnd>
  );
}
