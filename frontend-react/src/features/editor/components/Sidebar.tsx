import { useState, useEffect } from 'react';
import { useEditorStore } from '@/store/useEditorStore';
import { SidebarAddElements } from './SidebarAddElements';
import { SidebarProperties } from './SidebarProperties';
import { SidebarAnimation } from './SidebarAnimation';

export function Sidebar({ onPush }: { onPush: () => void }) {
  const store = useEditorStore();
  const [isCollapsed, setIsCollapsed] = useState(false);

  const selId = store.selectedId;
  const selEl = selId ? store.elements[selId] : null;

  // Handle global keydown for delete
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return;
      if ((e.key === 'Delete' || e.key === 'Backspace') && store.selectedId) {
        store.deleteElement(store.selectedId);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [store.selectedId]);

  return (
    <div 
      className={`bg-[#2b2b2b] flex flex-col h-screen text-white text-[13px] transition-all duration-300 ease-in-out relative ${
        isCollapsed ? 'w-[64px] min-w-[64px] items-center px-2' : 'w-[360px] min-w-[360px] p-4'
      } overflow-y-auto overflow-x-hidden`}
    >
      <button 
        className={`absolute top-4 right-4 text-[#00ffcc] hover:text-white transition-transform duration-300 z-10 flex items-center justify-center w-8 h-8 rounded bg-[#333] hover:bg-[#444]`}
        style={{ transform: isCollapsed ? 'rotate(180deg)' : 'rotate(0deg)' }}
        onClick={() => setIsCollapsed(!isCollapsed)}
        title="Toggle Sidebar"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M15 18l-6-6 6-6" />
        </svg>
      </button>

      {/* COLLAPSED VIEW: Only Icons */}
      {isCollapsed && (
        <div className="flex flex-col gap-8 mt-16 items-center w-full">
          <button title="Design Elements" onClick={() => setIsCollapsed(false)} className="text-2xl hover:scale-110 transition-transform">🎨</button>
          <button title="Add Logic Elements" onClick={() => setIsCollapsed(false)} className="text-2xl hover:scale-110 transition-transform">➕</button>
          <button title="Element Settings" onClick={() => setIsCollapsed(false)} className="text-2xl hover:scale-110 transition-transform">✏️</button>
          <div className="flex-grow"></div>
          <button title="Push to OBS" onClick={onPush} className="text-2xl hover:scale-110 transition-transform mb-4">⬆️</button>
        </div>
      )}

      {/* EXPANDED VIEW: Full Form */}
      <div className={`flex flex-col w-full transition-opacity duration-300 ${isCollapsed ? 'opacity-0 hidden' : 'opacity-100'}`}>
        
        <SidebarAddElements />

        <h2 className="text-[#00ffcc] uppercase tracking-wide mb-3 font-bold">Element Properties</h2>
        {!selEl || !selId ? (
          <p className="text-[#666] text-[12px]">Click an element on the canvas to edit properties.</p>
        ) : (
          <div className="flex flex-col">
            <SidebarProperties />
            <SidebarAnimation />
            <button className="bg-[#ff4444] text-white font-bold py-2 rounded hover:bg-[#cc2222]" onClick={() => store.deleteElement(selId)}>🗑️ Remove Element</button>
          </div>
        )}
        <hr className="border-[#3a3a3a] my-4" />

        <button className="bg-[#00ffcc] text-[#111] font-bold py-3 rounded hover:bg-[#00d4aa] text-[14px]" onClick={onPush}>⬆ Push to OBS</button>
        <p className="text-[11px] text-[#888] text-center mt-3">{store.statusMsg}</p>
      </div>
    </div>
  );
}
