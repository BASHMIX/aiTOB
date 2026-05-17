import { create } from 'zustand';

export interface OverlayElement {
  id: string;
  type: 'image' | 'text' | 'rect' | 'circle';
  visible: boolean;
  x: number;
  y: number;
  width?: number;
  height?: number;
  src?: string;
  text?: string;
  fontSize?: number;
  color?: string;
  zIndex?: number;
  borderRadius?: number;
}

interface EditorState {
  elements: Record<string, OverlayElement>;
  background_url: string;
  global_font_url: string;
  global_font_family: string;
  selectedId: string | null;
  statusMsg: string;
  clipboardStyle: Partial<OverlayElement> | null;
  
  setElements: (elements: Record<string, OverlayElement>) => void;
  mergeDynamicData: (elements: Record<string, OverlayElement>) => void;
  updateElement: (id: string, updates: Partial<OverlayElement>) => void;
  addElement: (element: OverlayElement) => void;
  deleteElement: (id: string) => void;
  restoreElement: (id: string) => void;
  setSelectedId: (id: string | null) => void;
  setGlobalSettings: (bg: string, fontUrl: string, fontFamily: string) => void;
  setStatusMsg: (msg: string) => void;
  setClipboardStyle: (style: Partial<OverlayElement> | null) => void;
}

export const useEditorStore = create<EditorState>((set) => ({
  elements: {},
  background_url: '',
  global_font_url: '',
  global_font_family: '',
  selectedId: null,
  statusMsg: 'Not connected',
  clipboardStyle: null,

  setElements: (elements) => set({ elements }),
  mergeDynamicData: (incomingElements) => set((state) => {
    const newElements = { ...state.elements };
    for (const key in incomingElements) {
      if (newElements[key]) {
        // Only update content properties, preserving layout (x, y, width, height, zIndex)
        newElements[key] = {
          ...newElements[key],
          text: incomingElements[key].text,
          src: incomingElements[key].src,
          visible: incomingElements[key].visible
        };
      } else {
        newElements[key] = incomingElements[key];
      }
    }
    return { elements: newElements };
  }),
  updateElement: (id, updates) => set((state) => ({
    elements: {
      ...state.elements,
      [id]: { ...state.elements[id], ...updates }
    }
  })),
  addElement: (element) => set((state) => ({
    elements: {
      ...state.elements,
      [element.id]: element
    },
    selectedId: element.id
  })),
  deleteElement: (id) => set((state) => {
    const newElements = { ...state.elements };
    delete newElements[id];
    return {
      elements: newElements,
      selectedId: state.selectedId === id ? null : state.selectedId
    };
  }),
  restoreElement: (id) => set((state) => {
    const defaultTemplates: Record<string, OverlayElement> = {
      p1_name: { id: 'p1_name', type: 'text', x: 400, y: 950, fontSize: 48, color: '#ffffff', text: 'Player 1', visible: true },
      p2_name: { id: 'p2_name', type: 'text', x: 1520, y: 950, fontSize: 48, color: '#ffffff', text: 'Player 2', visible: true },
      p1_score: { id: 'p1_score', type: 'text', x: 800, y: 950, fontSize: 64, color: '#ff0000', text: '0', visible: true },
      p2_score: { id: 'p2_score', type: 'text', x: 1120, y: 950, fontSize: 64, color: '#ff0000', text: '0', visible: true },
      p1_team: { id: 'p1_team', type: 'text', x: 400, y: 900, fontSize: 24, color: '#aaaaaa', text: '[TEAM]', visible: true },
      p2_team: { id: 'p2_team', type: 'text', x: 1520, y: 900, fontSize: 24, color: '#aaaaaa', text: '[TEAM]', visible: true },
      tournament_round: { id: 'tournament_round', type: 'text', x: 960, y: 50, fontSize: 32, color: '#ffffff', text: 'Winners Semis', visible: true },
      tournament_name: { id: 'tournament_name', type: 'text', x: 960, y: 100, fontSize: 24, color: '#aaaaaa', text: 'Tournament', visible: true },
      p1_avatar: { id: 'p1_avatar', type: 'image', x: 250, y: 850, width: 180, height: 180, src: '/static/player_placeholder.jpg', visible: true },
      p2_avatar: { id: 'p2_avatar', type: 'image', x: 1670, y: 850, width: 180, height: 180, src: '/static/player_placeholder.jpg', visible: true },
      p1_flag: { id: 'p1_flag', type: 'image', x: 250, y: 980, width: 120, height: 80, src: '/static/flag_placeholder.png', visible: true },
      p2_flag: { id: 'p2_flag', type: 'image', x: 1670, y: 980, width: 120, height: 80, src: '/static/flag_placeholder.png', visible: true },
    };
    
    // If it exists but is hidden, just unhide it. Otherwise, pull from defaults.
    const newEl = state.elements[id] 
      ? { ...state.elements[id], visible: true } 
      : (defaultTemplates[id] || { id, type: 'text', x: 960, y: 540, fontSize: 24, color: '#ffffff', text: 'New Text', visible: true });
      
    return {
      elements: { ...state.elements, [id]: newEl as OverlayElement },
      selectedId: id
    };
  }),
  setSelectedId: (selectedId) => set({ selectedId }),
  setGlobalSettings: (background_url, global_font_url, global_font_family) => set({
    background_url, global_font_url, global_font_family
  }),
  setStatusMsg: (statusMsg) => set({ statusMsg }),
  setClipboardStyle: (style) => set({ clipboardStyle: style })
}));
