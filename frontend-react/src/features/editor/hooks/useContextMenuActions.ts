import { useEditorStore } from '@/store/useEditorStore';

export function useContextMenuActions() {
  const copyStyle = (id: string) => {
    const store = useEditorStore.getState();
    const el = store.elements[id];
    if (el) {
      store.setClipboardStyle({
        fontSize: el.fontSize,
        color: el.color,
        borderRadius: el.borderRadius,
        width: el.width,
        height: el.height,
        zIndex: el.zIndex,
        fontWeight: el.fontWeight,
        fontStyle: el.fontStyle,
        textAlign: el.textAlign,
        strokeWidth: el.strokeWidth,
        strokeColor: el.strokeColor,
        shadowColor: el.shadowColor,
        shadowBlur: el.shadowBlur,
        shadowOffsetX: el.shadowOffsetX,
        shadowOffsetY: el.shadowOffsetY,
      });
      store.setStatusMsg("Style Copied 📋");
    }
  };

  const pasteStyle = (id: string) => {
    const store = useEditorStore.getState();
    if (store.clipboardStyle) {
      store.updateElement(id, store.clipboardStyle);
      store.setStatusMsg("Style Pasted 📋");
    }
  };

  const copyPosition = (id: string) => {
    const store = useEditorStore.getState();
    const el = store.elements[id];
    if (el) {
      store.setClipboardPosition({
        x: el.x,
        y: el.y,
      });
      store.setStatusMsg("Position Copied 📍");
    }
  };

  const pastePosition = (id: string) => {
    const store = useEditorStore.getState();
    if (store.clipboardPosition) {
      store.updateElement(id, {
        x: store.clipboardPosition.x,
        y: store.clipboardPosition.y,
      });
      store.setStatusMsg("Position Pasted 📍");
    }
  };

  const bringToFront = (id: string) => {
    const store = useEditorStore.getState();
    const maxZ = Math.max(0, ...Object.values(store.elements).map(el => el.zIndex || 1));
    store.updateElement(id, { zIndex: maxZ + 1 });
  };

  const sendToBack = (id: string) => {
    const store = useEditorStore.getState();
    const minZ = Math.min(0, ...Object.values(store.elements).map(el => el.zIndex || 1));
    store.updateElement(id, { zIndex: minZ - 1 });
  };

  return {
    copyStyle,
    pasteStyle,
    copyPosition,
    pastePosition,
    bringToFront,
    sendToBack
  };
}
