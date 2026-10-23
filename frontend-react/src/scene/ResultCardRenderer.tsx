import type { CardVariantKind, CardVariantOverride, GroupNode, SceneDocumentV2, StandingEntrySnapshot } from './types';
import { CardTemplateNode } from './CardTemplateNode';
import { PLAYER_IMAGE_PLACEHOLDER } from '@/utils/overlayAssets';

interface ResultCardRendererProps {
  scene: SceneDocumentV2;
  definitionId: string;
  standing: StandingEntrySnapshot;
  width: number;
  height: number;
  cueVisible?: boolean;
  variantOverrides?: Record<string, Partial<CardVariantOverride>>;
  variant?: CardVariantKind;
  className?: string;
  largeImageSource?: 'character' | 'player';
  showSmallImage?: boolean;
  smallImageSource?: 'player' | 'character';
}

function computeAdaptiveCardOverrides(
  scene: SceneDocumentV2,
  definition: GroupNode,
  width: number,
  height: number,
  placement: number,
  largeImageSource: 'character' | 'player' = 'character',
  showSmallImage = true,
  smallImageSource: 'player' | 'character' = 'player',
): Record<string, Partial<CardVariantOverride>> {
  const childNodes = definition.childIds.map((id) => scene.nodes[id]).filter(Boolean) as any[];

  const bgNode = childNodes.find(
    (n) => (n.type === 'rect' || n.type === 'circle') &&
      (n.name?.toLowerCase().includes('background') || (n.width || 0) > 200)
  );
  const badgeNode = childNodes.find(
    (n) => (n.type === 'rect' || n.type === 'circle') &&
      (n.name?.toLowerCase().includes('badge') || (n.id !== bgNode?.id && !n.name?.toLowerCase().includes('background')))
  );
  const placementNode = childNodes.find(
    (n) => n.type === 'text' && (
      n.binding === 'placement' ||
      n.name?.toLowerCase().includes('placement') ||
      n.name?.toLowerCase().includes('rank') ||
      (n.text && /^[T]?\d+$/.test(n.text.trim()))
    )
  ) || childNodes.find((n) => n.binding === 'placement');
  const prefixNode = childNodes.find(
    (n) => n.type === 'text' && (n.binding === 'prefix' || n.name?.toLowerCase().includes('prefix'))
  );
  const nameNode = childNodes.find(
    (n) => n.type === 'text' && (
      n.binding === 'displayName' ||
      n.name?.toLowerCase().includes('name') ||
      n.name?.toLowerCase().includes('player')
    )
  );
  const flagNode = childNodes.find(
    (n) => n.binding === 'countryFlagUrl' || n.name?.toLowerCase().includes('flag')
  );
  const charNameNode = childNodes.find(
    (n) => n.type === 'text' && (n.binding === 'characterName' || n.name?.toLowerCase().includes('character'))
  );

  const largeImgNode = childNodes.find(
    (n) => n.type === 'image' && (
      n.binding === 'characterImageUrl' ||
      n.name?.toLowerCase().includes('character art') ||
      n.name?.toLowerCase().includes('hero') ||
      (!n.name?.toLowerCase().includes('flag') && !n.name?.toLowerCase().includes('avatar') && !n.name?.toLowerCase().includes('photo'))
    )
  );
  const smallImgNode = childNodes.find(
    (n) => n.type === 'image' && (
      n.binding === 'avatarUrl' ||
      n.name?.toLowerCase().includes('player photo') ||
      n.name?.toLowerCase().includes('avatar') ||
      (n.id !== largeImgNode?.id && !n.name?.toLowerCase().includes('flag'))
    )
  );

  const overrides: Record<string, Partial<CardVariantOverride>> = {};
  const isHorizontal = width > height * 1.25;

  let badgeColor = '#2563eb';
  let badgeTextColor = '#ffffff';
  let badgeBorder = 'none';

  if (placement === 1) {
    badgeColor = '#f59e0b';
    badgeTextColor = '#000000';
    badgeBorder = '2px solid rgba(255, 255, 255, 0.7)';
  } else if (placement === 2) {
    badgeColor = '#94a3b8';
    badgeTextColor = '#000000';
    badgeBorder = '2px solid rgba(255, 255, 255, 0.6)';
  } else if (placement === 3) {
    badgeColor = '#d97706';
    badgeTextColor = '#ffffff';
    badgeBorder = '2px solid rgba(255, 255, 255, 0.5)';
  } else {
    badgeColor = '#1e293b';
    badgeBorder = '1.5px solid rgba(255, 255, 255, 0.3)';
    badgeTextColor = '#ffffff';
  }

  if (isHorizontal) {
    const isBar = height <= 130 || width > height * 3.2;

    const badgeSize = isBar
      ? Math.max(38, Math.min(54, height - 20))
      : Math.max(48, Math.min(56, Math.floor(height * 0.28)));
    const badgeX = isBar ? 16 : 14;
    const badgeY = isBar ? Math.floor((height - badgeSize) / 2) : 14;

    const smallImgSize = isBar
      ? Math.max(42, Math.min(58, height - 20))
      : Math.max(74, Math.min(88, Math.floor(height * 0.38)));
    const smallImgX = isBar ? (badgeX + badgeSize + 14) : 14;
    const smallImgY = isBar ? Math.floor((height - smallImgSize) / 2) : (badgeY + badgeSize + 10);

    const largeImgW = isBar
      ? Math.min(850, Math.floor(width * 0.48))
      : Math.floor(width * 0.60);
    const largeImgX = width - largeImgW;

    const leftColWidth = showSmallImage ? Math.max(badgeSize, smallImgSize) : badgeSize;
    const infoStartX = isBar
      ? (showSmallImage ? (smallImgX + smallImgSize + 16) : (badgeX + badgeSize + 16))
      : (14 + leftColWidth + 14);
    const infoWidth = isBar
      ? Math.max(140, largeImgX - infoStartX - 20)
      : Math.max(120, largeImgX - infoStartX + 20);

    if (bgNode) {
      overrides[bgNode.id] = { isAbsolute: true, x: 0, y: 0, width, height, borderRadius: isBar ? 12 : 16, zIndex: 1 };
    }
    if (badgeNode) {
      overrides[badgeNode.id] = {
        isAbsolute: true,
        x: badgeX,
        y: badgeY,
        width: badgeSize,
        height: badgeSize,
        borderRadius: isBar ? 10 : 12,
        color: badgeColor,
        border: badgeBorder,
        zIndex: 10,
      };
    }
    if (placementNode) {
      overrides[placementNode.id] = {
        isAbsolute: true,
        x: badgeX,
        y: badgeY,
        width: badgeSize,
        height: badgeSize,
        fontSize: Math.floor(badgeSize * 0.60),
        fontWeight: 'bold',
        color: badgeTextColor,
        textAlign: 'center',
        zIndex: 25,
      };
    }

    if (smallImgNode) {
      if (!showSmallImage) {
        overrides[smallImgNode.id] = { visible: false };
      } else {
        overrides[smallImgNode.id] = {
          isAbsolute: true,
          visible: true,
          binding: smallImageSource === 'character' ? 'characterImageUrl' : 'avatarUrl',
          x: smallImgX,
          y: smallImgY,
          width: smallImgSize,
          height: smallImgSize,
          objectFit: 'contain',
          borderRadius: 12,
          border: '2px solid rgba(255, 255, 255, 0.25)',
          backgroundColor: 'rgba(0, 0, 0, 0.45)',
          zIndex: 10,
        };
      }
    }

    if (largeImgNode) {
      overrides[largeImgNode.id] = {
        isAbsolute: true,
        visible: true,
        binding: largeImageSource === 'player' ? 'avatarUrl' : 'characterImageUrl',
        x: largeImgX,
        y: 0,
        width: largeImgW,
        height,
        objectFit: 'cover',
        objectPosition: isBar ? 'center 23%' : 'top center',
        maskImage: isBar ? 'linear-gradient(to right, transparent 0%, black 18%)' : undefined,
        borderRadius: 0,
        zIndex: 1,
      };
    }

    if (isBar) {
      if (prefixNode) {
        overrides[prefixNode.id] = {
          isAbsolute: true,
          x: infoStartX,
          y: 10,
          width: infoWidth,
          height: 16,
          fontSize: 12,
          fontWeight: 'bold',
          color: '#38bdf8',
          zIndex: 5,
        };
      }

      if (nameNode) {
        overrides[nameNode.id] = {
          isAbsolute: true,
          x: infoStartX,
          y: 24,
          width: infoWidth,
          height: 34,
          fontSize: Math.min(28, Math.max(20, Math.floor(height * 0.30))),
          fontWeight: 'bold',
          color: '#ffffff',
          zIndex: 5,
        };
      }

      const flagH = 18;
      const flagW = 28;
      const bottomY = 58;

      if (flagNode) {
        overrides[flagNode.id] = {
          isAbsolute: true,
          x: infoStartX,
          y: bottomY,
          width: flagW,
          height: flagH,
          borderRadius: 4,
          objectFit: 'cover',
          zIndex: 5,
        };
      }

      if (charNameNode) {
        overrides[charNameNode.id] = {
          isAbsolute: true,
          x: infoStartX + flagW + 8,
          y: bottomY - 1,
          width: Math.max(60, infoWidth - flagW - 8),
          height: flagH + 2,
          fontSize: 14,
          fontWeight: 'bold',
          color: '#cbd5e1',
          zIndex: 5,
        };
      }
    } else {
      if (prefixNode) {
        overrides[prefixNode.id] = {
          isAbsolute: true,
          x: infoStartX,
          y: 18,
          width: infoWidth,
          height: 20,
          fontSize: 14,
          fontWeight: 'bold',
          color: '#38bdf8',
          zIndex: 5,
        };
      }

      if (nameNode) {
        overrides[nameNode.id] = {
          isAbsolute: true,
          x: infoStartX,
          y: 40,
          width: infoWidth,
          height: 38,
          fontSize: 26,
          fontWeight: 'bold',
          color: '#ffffff',
          zIndex: 5,
        };
      }

      const flagH = 22;
      const flagW = 34;
      const bottomY = Math.max(86, Math.floor(height * 0.38));

      if (flagNode) {
        overrides[flagNode.id] = {
          isAbsolute: true,
          x: infoStartX,
          y: bottomY,
          width: flagW,
          height: flagH,
          borderRadius: 4,
          objectFit: 'cover',
          zIndex: 5,
        };
      }

      if (charNameNode) {
        overrides[charNameNode.id] = {
          isAbsolute: true,
          x: infoStartX + flagW + 8,
          y: bottomY - 1,
          width: Math.max(60, infoWidth - flagW - 8),
          height: flagH + 2,
          fontSize: 16,
          fontWeight: 'bold',
          color: '#cbd5e1',
          zIndex: 5,
        };
      }
    }
  } else {
    const badgeSize = 64;
    const badgeX = 20;
    const badgeY = 20;

    if (bgNode) {
      overrides[bgNode.id] = { isAbsolute: true, x: 0, y: 0, width, height, borderRadius: 24, zIndex: 1 };
    }
    if (badgeNode) {
      overrides[badgeNode.id] = {
        isAbsolute: true,
        x: badgeX,
        y: badgeY,
        width: badgeSize,
        height: badgeSize,
        borderRadius: 16,
        color: badgeColor,
        border: badgeBorder,
        zIndex: 10,
      };
    }
    if (placementNode) {
      overrides[placementNode.id] = {
        isAbsolute: true,
        x: badgeX,
        y: badgeY,
        width: badgeSize,
        height: badgeSize,
        fontSize: Math.floor(badgeSize * 0.62),
        fontWeight: 'bold',
        color: badgeTextColor,
        textAlign: 'center',
        zIndex: 25,
      };
    }

    if (largeImgNode) {
      overrides[largeImgNode.id] = {
        isAbsolute: true,
        visible: true,
        binding: largeImageSource === 'player' ? 'avatarUrl' : 'characterImageUrl',
        x: 0,
        y: 0,
        width,
        height: Math.floor(height * 0.74),
        objectFit: 'cover',
        objectPosition: 'top center',
        zIndex: 1,
      };
    }

    const smallImgSize = 92;
    if (smallImgNode) {
      if (!showSmallImage) {
        overrides[smallImgNode.id] = { visible: false };
      } else {
        overrides[smallImgNode.id] = {
          isAbsolute: true,
          visible: true,
          binding: smallImageSource === 'character' ? 'characterImageUrl' : 'avatarUrl',
          x: 20,
          y: height - smallImgSize - 20,
          width: smallImgSize,
          height: smallImgSize,
          objectFit: 'contain',
          borderRadius: 14,
          border: '2px solid rgba(255, 255, 255, 0.25)',
          backgroundColor: 'rgba(0, 0, 0, 0.45)',
          zIndex: 5,
        };
      }
    }

    const nameStartX = showSmallImage ? (20 + smallImgSize + 16) : 24;
    const nameW = width - nameStartX - 20;

    if (prefixNode) {
      overrides[prefixNode.id] = {
        isAbsolute: true,
        x: nameStartX,
        y: height - 100,
        width: nameW,
        height: 22,
        fontSize: 16,
        fontWeight: 'bold',
        color: '#38bdf8',
        zIndex: 6,
      };
    }
    if (nameNode) {
      overrides[nameNode.id] = {
        isAbsolute: true,
        x: nameStartX,
        y: height - 76,
        width: nameW,
        height: 42,
        fontSize: 32,
        fontWeight: 'bold',
        color: '#ffffff',
        zIndex: 6,
      };
    }

    const flagY = height - 34;
    if (flagNode) {
      overrides[flagNode.id] = {
        isAbsolute: true,
        x: nameStartX,
        y: flagY,
        width: 36,
        height: 24,
        borderRadius: 4,
        objectFit: 'cover',
        zIndex: 6,
      };
    }
    if (charNameNode) {
      overrides[charNameNode.id] = {
        isAbsolute: true,
        x: nameStartX + 46,
        y: flagY,
        width: nameW - 46,
        height: 24,
        fontSize: 18,
        fontWeight: 'bold',
        color: '#cbd5e1',
        zIndex: 6,
      };
    }
  }

  return overrides;
}

export function ResultCardRenderer({
  scene,
  definitionId,
  standing,
  width,
  height,
  cueVisible = true,
  variantOverrides,
  variant,
  className,
  largeImageSource = 'character',
  showSmallImage = true,
  smallImageSource = 'player',
}: ResultCardRendererProps) {
  const definition = scene.nodes[definitionId] as GroupNode | undefined;
  if (!definition || definition.type !== 'group') return null;

  const inferredVariant: CardVariantKind = standing.placement === 1
    ? 'champion'
    : standing.placement <= 4 ? 'podium' : 'standard';

  const adaptiveOverrides = computeAdaptiveCardOverrides(
    scene,
    definition,
    width,
    height,
    standing.placement,
    largeImageSource,
    showSmallImage,
    smallImageSource,
  );

  const baseVariantOverrides = variantOverrides || definition.variants?.[variant || inferredVariant] || {};
  const resolvedOverrides: Record<string, Partial<CardVariantOverride>> = {
    ...baseVariantOverrides,
    ...adaptiveOverrides,
  };

  const scaleX = width / Math.max(1, definition.width || width);
  const scaleY = height / Math.max(1, definition.height || height);

  const childNodes = definition.childIds.map((id) => scene.nodes[id]).filter(Boolean) as any[];
  const largeImgNode = childNodes.find(
    (n) => n.type === 'image' && (
      n.binding === 'characterImageUrl' ||
      n.name?.toLowerCase().includes('character art') ||
      n.name?.toLowerCase().includes('hero') ||
      (!n.name?.toLowerCase().includes('flag') && !n.name?.toLowerCase().includes('avatar') && !n.name?.toLowerCase().includes('photo'))
    )
  );
  const smallImgNode = childNodes.find(
    (n) => n.type === 'image' && (
      n.binding === 'avatarUrl' ||
      n.name?.toLowerCase().includes('player photo') ||
      n.name?.toLowerCase().includes('avatar') ||
      (n.id !== largeImgNode?.id && !n.name?.toLowerCase().includes('flag'))
    )
  );

  const isHorizontal = width > height * 1.25;
  const isBar = isHorizontal && (height <= 130 || width > height * 3.2);

  const badgeSize = isBar
    ? Math.max(38, Math.min(54, height - 20))
    : isHorizontal
    ? Math.max(48, Math.min(56, Math.floor(height * 0.28)))
    : 64;
  const badgeX = isBar ? 16 : isHorizontal ? 14 : 20;

  const smallImgSize = isBar
    ? Math.max(42, Math.min(58, height - 20))
    : isHorizontal
    ? Math.max(74, Math.min(88, Math.floor(height * 0.38)))
    : 92;
  const smallImgX = isBar ? (badgeX + badgeSize + 14) : isHorizontal ? 14 : 20;
  const smallImgY = isBar
    ? Math.floor((height - smallImgSize) / 2)
    : isHorizontal
    ? (14 + badgeSize + 10)
    : (height - smallImgSize - 20);

  const rawSmallSrc = smallImageSource === 'character'
    ? standing.presentation?.character?.value?.image_url
    : standing.presentation?.avatar_url?.value;
  const smallSrc = rawSmallSrc || PLAYER_IMAGE_PLACEHOLDER;

  return (
    <div
      data-testid={`result-card-${standing.entrant_id}`}
      data-result-card-definition={definitionId}
      className={className}
      style={{ position: 'relative', width, height, overflow: 'hidden' }}
    >
      {definition.childIds.map((childId) => (
        <CardTemplateNode
          key={childId}
          scene={scene}
          nodeId={childId}
          standing={standing}
          scaleX={scaleX}
          scaleY={scaleY}
          variantOverrides={resolvedOverrides}
          cueVisible={cueVisible}
        />
      ))}
      {!smallImgNode && showSmallImage && (
        <img
          key="synthetic-small-img"
          data-testid="synthetic-small-image"
          src={smallSrc}
          alt={smallImageSource === 'character' ? 'Character' : 'Player'}
          crossOrigin="anonymous"
          onError={(e) => {
            if (!e.currentTarget.src.endsWith(PLAYER_IMAGE_PLACEHOLDER)) {
              e.currentTarget.crossOrigin = '';
              e.currentTarget.src = PLAYER_IMAGE_PLACEHOLDER;
            }
          }}
          style={{
            position: 'absolute',
            left: smallImgX,
            top: smallImgY,
            width: smallImgSize,
            height: smallImgSize,
            objectFit: 'contain',
            borderRadius: isHorizontal ? 12 : 14,
            border: '2px solid rgba(255, 255, 255, 0.25)',
            backgroundColor: 'rgba(0, 0, 0, 0.45)',
            zIndex: 10,
            pointerEvents: 'none',
          }}
        />
      )}
    </div>
  );
}
