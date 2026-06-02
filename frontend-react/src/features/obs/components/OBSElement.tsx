import React from 'react';
import { getAnimationStyles } from '../utils';

interface OBSElementProps {
  id: string;
  el: any;
  cascadeDelay: number;
  transitionState: 'none' | 'in' | 'out' | 'run' | 'idle';
  isGlitched: boolean;
}

export const OBSElement: React.FC<OBSElementProps> = ({
  id,
  el,
  cascadeDelay,
  transitionState,
  isGlitched
}) => {
  if (!el.visible) return null;

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
    content = (
      <img
        src={el.src}
        className={glitchClass}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'contain',
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
