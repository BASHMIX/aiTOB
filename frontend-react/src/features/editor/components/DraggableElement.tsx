import { Rnd } from 'react-rnd';
import { useEditorStore } from '@/store/useEditorStore';
import type { OverlayElement } from '@/store/useEditorStore';

interface Props {
  id: string;
  element: OverlayElement;
  scale: number;
  onContextMenu?: (e: React.MouseEvent) => void;
}

export function DraggableElement({ id, element, scale, onContextMenu }: Props) {
  const store = useEditorStore();
  const { updateElement, selectedId, setSelectedId, activeMatch } = store;

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
        {textToRender}
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
      <div className="w-full h-full" onContextMenu={onContextMenu}>
        {content}
      </div>
    </Rnd>
  );
}
