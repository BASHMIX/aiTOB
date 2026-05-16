import { useMemo } from 'react';

interface OverlayThumbnailProps {
  config: any;
  isSelected: boolean;
  onClick: () => void;
  name: string;
}

export function OverlayThumbnail({ config, isSelected, onClick, name }: OverlayThumbnailProps) {
  const elements = config?.elements || {};
  const backgroundUrl = config?.background_url || '';

  // Sort by z-index for rendering
  const sortedElements = useMemo(() => {
    return Object.entries(elements).sort((a: any, b: any) => (a[1].zIndex || 1) - (b[1].zIndex || 1));
  }, [elements]);

  return (
    <div 
      onClick={onClick}
      className={`
        relative flex-shrink-0 w-36 h-[86px] rounded border-2 cursor-pointer transition-all overflow-hidden bg-[#111]
        ${isSelected ? 'border-accentYellow shadow-[0_0_10px_rgba(255,220,0,0.3)]' : 'border-white/10 hover:border-white/30'}
      `}
    >
      {/* Mini Canvas */}
      <div 
        className="absolute top-0 left-0 bg-checkerboard origin-top-left"
        style={{ 
          width: '1920px',
          height: '1080px',
          transform: `scale(${140/1920})`,
          fontFamily: config?.global_font_family || 'inherit'
        }}
      >
        {backgroundUrl && (
          <div 
            className="absolute inset-0 bg-cover bg-center"
            style={{ backgroundImage: `url('${backgroundUrl}')` }}
          />
        )}
        {sortedElements.map(([id, el]: [string, any]) => {
          if (!el.visible) return null;
          return (
            <div 
              key={id}
              className="absolute"
              style={{
                left: el.x,
                top: el.y,
                width: el.width,
                height: el.height,
                backgroundColor: el.type === 'text' ? 'transparent' : 'rgba(255,255,255,0.2)',
                color: el.color || '#fff',
                fontSize: `${parseInt(el.fontSize || '24') * 2}px`, // Boosted font size for visibility
                fontWeight: 'bold',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                border: el.type === 'image' ? '4px solid rgba(255,255,255,0.3)' : 'none',
                overflow: 'hidden'
              }}
            >
              {el.type === 'text' ? (el.text || 'T') : null}
              {el.type === 'image' && <div className="w-full h-full bg-white/10" />}
            </div>
          );
        })}
      </div>

      {/* Overlay Label */}
      <div className="absolute inset-x-0 bottom-0 bg-black/80 py-0.5 px-1 text-[10px] font-bold text-center uppercase tracking-tighter truncate z-10">
        {name}
      </div>
    </div>
  );
}
