import { useState } from 'react';
import { useEditorStore } from '@/store/useEditorStore';

export function SidebarAddElements() {
  const store = useEditorStore();
  const [addId, setAddId] = useState('');

  const addGenericElement = (type: 'text' | 'image' | 'rect' | 'circle') => {
    const id = `${type}_${Date.now()}`;
    const base = { id, x: 960, y: 540, visible: true, zIndex: 10 };

    if (type === 'text') {
      store.addElement({ ...base, type: 'text', text: 'New Text', fontSize: 48, color: '#ffffff' });
    } else if (type === 'image') {
      store.addElement({ ...base, type: 'image', width: 300, height: 300, src: '/static/player_placeholder.jpg' });
    } else if (type === 'rect') {
      store.addElement({ ...base, type: 'rect', width: 400, height: 200, color: 'rgba(0,0,0,0.5)', borderRadius: 0 });
    } else if (type === 'circle') {
      store.addElement({ ...base, type: 'circle', width: 200, height: 200, color: 'rgba(0,255,255,0.5)', borderRadius: 100 });
    }
  };

  return (
    <>
      <h2 className="text-[#00ffcc] uppercase tracking-wide mb-3 font-bold mt-10">Add Elements</h2>
      <div className="grid grid-cols-2 gap-2 mb-3">
        <button onClick={() => addGenericElement('text')} className="bg-[#3a3a3a] hover:bg-[#444] border border-[#555] rounded py-2 text-center text-xs font-bold">📄 Add Text</button>
        <button onClick={() => addGenericElement('image')} className="bg-[#3a3a3a] hover:bg-[#444] border border-[#555] rounded py-2 text-center text-xs font-bold">🖼️ Add Image</button>
        <button onClick={() => addGenericElement('rect')} className="bg-[#3a3a3a] hover:bg-[#444] border border-[#555] rounded py-2 text-center text-xs font-bold">⬛ Add Rect</button>
        <button onClick={() => addGenericElement('circle')} className="bg-[#3a3a3a] hover:bg-[#444] border border-[#555] rounded py-2 text-center text-xs font-bold">⚪ Add Circle</button>
      </div>
      <hr className="border-[#3a3a3a] my-3" />

      <h2 className="text-[#00ffcc] uppercase tracking-wide mb-3 font-bold">Live Data Hooks</h2>
      <div className="flex gap-2 mb-3">
        <select className="flex-1 bg-[#3a3a3a] border border-[#555] rounded px-2 py-1.5 focus:border-[#00ffcc] outline-none" value={addId} onChange={e => setAddId(e.target.value)}>
          <option value="">-- Select Data Field --</option>
          {['p1_name', 'p2_name', 'p1_score', 'p2_score', 'p1_team', 'p2_team', 'tournament_round', 'tournament_name', 'p1_avatar', 'p2_avatar', 'p1_flag', 'p2_flag']
            .filter(id => !store.elements[id] || !store.elements[id].visible)
            .map((id) => (
              <option key={id} value={id}>{id}</option>
          ))}
        </select>
        <button
          className="bg-[#00ffcc] text-[#111] font-bold px-3 rounded hover:bg-[#00d4aa]"
          onClick={() => { if (addId) store.restoreElement(addId); }}
        >+ Add</button>
      </div>
      <hr className="border-[#3a3a3a] my-3" />
    </>
  );
}
