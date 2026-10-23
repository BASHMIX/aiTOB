import type { CSSProperties } from 'react';
import type {
  AnimationSettings,
  CardVariantOverride,
  SceneDocumentV2,
  StandingEntrySnapshot,
} from './types';
import { countryFlagUrl } from '@/utils/country';
import { FLAG_IMAGE_PLACEHOLDER, PLAYER_IMAGE_PLACEHOLDER } from '@/utils/overlayAssets';

interface CardTemplateNodeProps {
  scene: SceneDocumentV2;
  nodeId: string;
  standing: StandingEntrySnapshot;
  scaleX: number;
  scaleY: number;
  variantOverrides: Record<string, Partial<CardVariantOverride>>;
  cueVisible: boolean;
  fillParent?: boolean;
}

function resolveBindingValue(
  binding: string | undefined,
  standing: StandingEntrySnapshot,
  defaultText = '',
): string {
  const presentation = standing.presentation;
  if (!binding) return defaultText;
  switch (binding) {
    case 'placement': return standing.is_tied ? `T${standing.placement}` : String(standing.placement);
    case 'displayName': return presentation?.display_name?.value || standing.entrant_name;
    case 'prefix': return presentation?.prefix?.value || defaultText;
    case 'countryCode': return presentation?.country?.value || defaultText;
    case 'countryFlagUrl': return countryFlagUrl(presentation?.country?.value) || defaultText;
    case 'characterId': return presentation?.character?.value?.id || '';
    case 'characterImageUrl': return presentation?.character?.value?.image_url || defaultText;
    case 'characterName': return presentation?.character?.value?.name || defaultText;
    case 'avatarUrl': return presentation?.avatar_url?.value || defaultText;
    case 'entrantName': return standing.entrant_name;
    default: return defaultText;
  }
}

function hiddenTransform(animation?: AnimationSettings): string {
  if (!animation || animation.animationType === 'none') return 'none';
  const offsets: Record<string, string> = {
    bottom: 'translateY(40px)',
    'bottom-left': 'translate(-40px, 40px)',
    left: 'translateX(-40px)',
    'top-left': 'translate(-40px, -40px)',
    top: 'translateY(-40px)',
    'top-right': 'translate(40px, -40px)',
    right: 'translateX(40px)',
    'bottom-right': 'translate(40px, 40px)',
    'in-place': 'translate(0, 0)',
  };
  const offset = offsets[animation.direction] || 'translateY(40px)';
  return animation.animationType === 'float-in' ? `${offset} scale(0.96)` : offset;
}

export function resolveAnimatedVisibilityStyle(
  animation: AnimationSettings | undefined,
  visible: boolean,
  opacity = 1,
): CSSProperties {
  const duration = Math.max(0, Number(animation?.duration ?? 350));
  const delay = visible ? Math.max(0, Number(animation?.delay ?? 0)) : 0;
  const easing: Record<string, string> = {
    linear: 'linear',
    'ease-in': 'ease-in',
    'ease-out': 'ease-out',
    'ease-in-out': 'ease-in-out',
    bounce: 'cubic-bezier(0.175, 0.885, 0.32, 1.275)',
    'back-out': 'cubic-bezier(0.34, 1.56, 0.64, 1)',
    elastic: 'cubic-bezier(0.25, 1.36, 0.49, 1.16)',
  };
  return {
    opacity: visible ? opacity : 0,
    transform: visible ? 'none' : hiddenTransform(animation),
    transition: `opacity ${duration}ms ${easing[animation?.tweenType || 'ease-out'] || 'ease-out'}, transform ${duration}ms ${easing[animation?.tweenType || 'ease-out'] || 'ease-out'}`,
    transitionDelay: `${delay}ms`,
  };
}

export function CardTemplateNode({
  scene,
  nodeId,
  standing,
  scaleX,
  scaleY,
  variantOverrides,
  cueVisible,
  fillParent = false,
}: CardTemplateNodeProps) {
  const node = scene.nodes[nodeId];
  if (!node || !node.visible) return null;
  const override = variantOverrides[nodeId] || {};
  if (override.visible === false) return null;

  const isAbs = Boolean(override.isAbsolute);
  const unitScale = isAbs ? 1 : Math.min(scaleX, scaleY);
  const x = override.x !== undefined ? (isAbs ? override.x : override.x * scaleX) : (node.x ?? 0) * scaleX;
  const y = override.y !== undefined ? (isAbs ? override.y : override.y * scaleY) : (node.y ?? 0) * scaleY;
  const width = override.width !== undefined ? (isAbs ? override.width : override.width * scaleX) : (node.width ?? 0) * scaleX;
  const height = override.height !== undefined ? (isAbs ? override.height : override.height * scaleY) : (node.height ?? 0) * scaleY;
  const animated = resolveAnimatedVisibilityStyle(
    override.animation ?? node.animation,
    cueVisible,
    override.opacity ?? node.opacity ?? 1,
  );
  const positioned: CSSProperties = {
    position: 'absolute',
    left: fillParent ? 0 : x,
    top: fillParent ? 0 : y,
    width: fillParent ? '100%' : width,
    height: fillParent ? '100%' : height,
    zIndex: override.zIndex ?? node.zIndex,
    boxSizing: 'border-box', ...animated,
  };

  if (node.type === 'group') {
    return (
      <div key={nodeId} style={positioned}>
        {node.childIds.map((childId) => (
          <CardTemplateNode
            key={childId}
            scene={scene}
            nodeId={childId}
            standing={standing}
            scaleX={scaleX}
            scaleY={scaleY}
            variantOverrides={variantOverrides}
            cueVisible={cueVisible}
          />
        ))}
      </div>
    );
  }

  if (node.type === 'rect' || node.type === 'circle') {
    return (
      <div
        key={nodeId}
        style={{
          ...positioned,
          backgroundColor: override.color ?? node.color ?? 'transparent',
          borderRadius: node.type === 'circle' ? '50%' : `${(override.borderRadius ?? node.borderRadius ?? 0) * unitScale}px`,
          border: override.border || ((override.strokeColor ?? node.strokeColor)
            ? `${(override.strokeWidth ?? node.strokeWidth ?? 1) * unitScale}px solid ${override.strokeColor ?? node.strokeColor}`
            : 'none'),
        }}
      />
    );
  }

  if (node.type === 'text') {
    const text = resolveBindingValue(node.binding, standing, node.text || '');
    const textAlign = override.textAlign ?? node.textAlign ?? 'left';
    return (
      <div
        key={nodeId}
        data-testid={node.binding === 'placement' ? 'card-placement-text' : undefined}
        style={{
          ...positioned,
          fontSize: `${override.fontSize !== undefined ? (isAbs ? override.fontSize : override.fontSize * unitScale) : ((node.fontSize ?? 16) * unitScale)}px`,
          fontFamily: node.fontFamily || scene.canvas.globalFontFamily || 'sans-serif',
          fontWeight: override.fontWeight ?? node.fontWeight ?? 'normal',
          color: override.color ?? node.color ?? '#ffffff',
          textAlign,
          display: 'flex', alignItems: 'center',
          justifyContent: textAlign === 'center' ? 'center' : textAlign === 'right' ? 'flex-end' : 'flex-start',
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', lineHeight: 1.1,
        }}
      >
        {text}
      </div>
    );
  }

  if (node.type === 'image') {
    const binding = override.binding ?? node.binding;
    const src = resolveBindingValue(binding, standing, override.src ?? node.src ?? '');
    const borderRadius = `${(override.borderRadius ?? node.borderRadius ?? 0) * unitScale}px`;
    const objectFit = override.objectFit ?? node.objectFit ?? 'cover';
    const objectPosition = override.objectPosition ?? 'top center';
    const border = override.border;
    const backgroundColor = override.backgroundColor;
    const maskImage = override.maskImage;
    const fallbackSrc = binding === 'countryFlagUrl'
      ? FLAG_IMAGE_PLACEHOLDER
      : PLAYER_IMAGE_PLACEHOLDER;
    if (!src) {
      return (
        <img
          key={nodeId}
          data-testid="image-fallback-placeholder"
          src={fallbackSrc}
          alt={node.name || 'card-placeholder'}
          style={{
            ...positioned, borderRadius, objectFit, objectPosition, border,
            backgroundColor: backgroundColor || 'rgba(255,255,255,0.05)',
            maskImage,
            WebkitMaskImage: maskImage,
            pointerEvents: 'none',
          }}
        />
      );
    }
    return (
      <img
        key={nodeId}
        data-testid="card-bound-image"
        src={src}
        alt={node.name || 'card-asset'}
        crossOrigin="anonymous"
        onError={(event) => {
          if (!event.currentTarget.src.endsWith(fallbackSrc)) {
            event.currentTarget.crossOrigin = '';
            event.currentTarget.src = fallbackSrc;
          }
        }}
        style={{
          ...positioned,
          objectFit,
          objectPosition,
          borderRadius,
          border,
          backgroundColor,
          maskImage,
          WebkitMaskImage: maskImage,
          pointerEvents: 'none',
        }}
      />
    );
  }

  return null;
}
