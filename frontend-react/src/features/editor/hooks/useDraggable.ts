import { useCallback } from 'react';
import type { OverlayElement } from '@/store/useEditorStore';

type UpdateElementFn = (id: string, updates: Partial<OverlayElement>) => void;

export function useDraggable(id: string, updateElement: UpdateElementFn) {
  // Snap dragging stop to precise integers to prevent CSS fractional shift
  const onDragStop = useCallback((_e: any, d: any) => {
    updateElement(id, { x: Math.round(d.x), y: Math.round(d.y) });
  }, [id, updateElement]);

  // Update store coordinates in real-time while dragging to prevent controlled input snapback on re-renders
  const onDrag = useCallback((_e: any, d: any) => {
    updateElement(id, { x: Math.round(d.x), y: Math.round(d.y) });
  }, [id, updateElement]);

  // Snap resizing to precise integers to prevent coordinate drift
  const onResizeStop = useCallback((_e: any, _direction: any, ref: any, _delta: any, position: any) => {
    updateElement(id, {
      width: Math.round(parseInt(ref.style.width, 10)),
      height: Math.round(parseInt(ref.style.height, 10)),
      x: Math.round(position.x),
      y: Math.round(position.y)
    });
  }, [id, updateElement]);

  // Update store width/height/coordinates in real-time while resizing to keep inputs and bounding box in sync
  const onResize = useCallback((_e: any, _direction: any, ref: any, _delta: any, position: any) => {
    updateElement(id, {
      width: Math.round(parseInt(ref.style.width, 10)),
      height: Math.round(parseInt(ref.style.height, 10)),
      x: Math.round(position.x),
      y: Math.round(position.y)
    });
  }, [id, updateElement]);

  return {
    onDragStop,
    onDrag,
    onResizeStop,
    onResize
  };
}
