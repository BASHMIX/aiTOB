
interface EditorContextMenuProps {
  x: number;
  y: number;
  id: string;
  hasClipboardStyle: boolean;
  hasClipboardPosition: boolean;
  onBringToFront: (id: string) => void;
  onSendToBack: (id: string) => void;
  onCopyStyle: (id: string) => void;
  onPasteStyle: (id: string) => void;
  onCopyPosition: (id: string) => void;
  onPastePosition: (id: string) => void;
}

export function EditorContextMenu({
  x, y, id,
  hasClipboardStyle, hasClipboardPosition,
  onBringToFront, onSendToBack,
  onCopyStyle, onPasteStyle,
  onCopyPosition, onPastePosition
}: EditorContextMenuProps) {
  return (
    <div
      className="fixed bg-[#333] border border-[#555] rounded shadow-2xl py-1 z-[9999] min-w-[150px] text-xs"
      style={{ left: x, top: y }}
    >
      <button className="w-full text-left px-4 py-2 hover:bg-accentYellow hover:text-black" onClick={() => onBringToFront(id)}>Bring to Front</button>
      <button className="w-full text-left px-4 py-2 hover:bg-accentYellow hover:text-black" onClick={() => onSendToBack(id)}>Send to Back</button>
      <div className="h-px bg-white/10 my-1" />
      <button className="w-full text-left px-4 py-2 hover:bg-accentYellow hover:text-black" onClick={() => onCopyStyle(id)}>Copy Style</button>
      {hasClipboardStyle && (
        <button className="w-full text-left px-4 py-2 hover:bg-accentYellow hover:text-black" onClick={() => onPasteStyle(id)}>Paste Style</button>
      )}
      <div className="h-px bg-white/10 my-1" />
      <button className="w-full text-left px-4 py-2 hover:bg-accentYellow hover:text-black" onClick={() => onCopyPosition(id)}>Copy Position</button>
      {hasClipboardPosition && (
        <button className="w-full text-left px-4 py-2 hover:bg-accentYellow hover:text-black" onClick={() => onPastePosition(id)}>Paste Position</button>
      )}
    </div>
  );
}
