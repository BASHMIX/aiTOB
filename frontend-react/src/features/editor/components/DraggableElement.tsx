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
  const { updateElement, selectedId, setSelectedId } = useEditorStore();

  if (!element.visible) return null;

  const isImg = element.type === 'image';
  const isShape = element.type === 'rect' || element.type === 'circle';
  const isSelected = selectedId === id;

  // Render content
  let content = null;
  if (isImg) {
    content = <img src={element.src} alt="" className="w-full h-full object-contain block pointer-events-none" />;
  } else if (isShape) {
    content = (
      <div 
        className="w-full h-full"
        style={{ 
          backgroundColor: element.color || 'rgba(255,255,255,0.5)', 
          borderRadius: element.type === 'circle' ? '50%' : `${element.borderRadius || 0}px`
        }} 
      />
    );
  } else {
    content = (
      <div 
        style={{ fontSize: element.fontSize, color: element.color }} 
        className="whitespace-nowrap w-full h-full"
      >
        {element.text}
      </div>
    );
  }

  // Handle Rnd callbacks
  const onDragStop = (_e: any, d: any) => {
    updateElement(id, { x: d.x, y: d.y });
  };

  const onResizeStop = (_e: any, _direction: any, ref: any, _delta: any, position: any) => {
    updateElement(id, {
      width: parseInt(ref.style.width, 10),
      height: parseInt(ref.style.height, 10),
      ...position
    });
  };

  const hasFixedSize = isImg || isShape;

  return (
    <Rnd
      scale={scale}
      position={{ x: element.x, y: element.y }}
      size={hasFixedSize ? { width: element.width || 100, height: element.height || 100 } : undefined}
      onDragStop={onDragStop}
      onDragStart={() => setSelectedId(id)}
      onResizeStop={hasFixedSize ? onResizeStop : undefined}
      onResizeStart={() => setSelectedId(id)}
      disableDragging={false}
      enableResizing={hasFixedSize}
      style={{ zIndex: isSelected ? 100 : (element.zIndex || 1) }}
      onMouseDown={(e: any) => {
        e.stopPropagation();
        setSelectedId(id);
      }}
      onClick={(e: any) => {
        e.stopPropagation();
        setSelectedId(id);
      }}
      className={`select-none text-center box-border ${isSelected ? 'outline-dashed outline-2 outline-[#00ffcc]' : ''}`}
      bounds="parent"
      dragGrid={[5, 5]}
      resizeGrid={[5, 5]}
    >
      <div className="w-full h-full" onContextMenu={onContextMenu}>
        {content}
      </div>
    </Rnd>
  );
}
