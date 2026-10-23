import { create } from 'zustand';

export interface AnimationSettings {
  animationType: 'none' | 'fly-in' | 'float-in' | 'fade-in';
  direction: 'bottom' | 'bottom-left' | 'left' | 'top-left' | 'top' | 'top-right' | 'right' | 'bottom-right' | 'in-place';
  duration: number; // in ms
  delay: number; // in ms
  loop: number; // -1 (forever), 0 (none), n (repeat count)
  tweenType: 'linear' | 'ease-in' | 'ease-out' | 'ease-in-out' | 'bounce' | 'back-out' | 'elastic';
  playOn: 'IN' | 'BOTH' | 'OUT';
  trigger: 'on-load' | 'with-prev' | 'after-prev';
  revealStyle?: 'all' | 'word' | 'letter';
  revealScale?: number;
  scoreGlitch?: boolean;
  glitchScale?: number;
  idleAnimation?: 'none' | 'bobbing' | 'pulsing' | 'hovering' | 'spinning';
  idleIntensity?: number;
}

export interface ResultCardTransform {
  x: number;
  y: number;
  scale: number;
  opacity: number;
  rotation: number;
}

export interface ResultCardLifecycle {
  start: ResultCardTransform;
  visible: ResultCardTransform;
  exit: ResultCardTransform;
  enterDurationMs: number;
  visibleHoldMs: number;
  exitDurationMs: number;
  enterEasing: AnimationSettings['tweenType'];
  exitEasing: AnimationSettings['tweenType'];
}

export interface OverlayElement {
  id: string;
  name?: string;
  parentId?: string | null;
  /** Optional live-data element id this visual instance mirrors. */
  sourceId?: string;
  type: 'image' | 'text' | 'rect' | 'circle' | 'group' | 'result-card' | 'results-cards' | 'results-group' | 'match-grid' | 'bracket-tree' | 'victory-path';
  visible: boolean;
  locked?: boolean;
  x: number;
  y: number;
  width?: number;
  height?: number;
  src?: string;
  objectFit?: 'cover' | 'contain' | 'fill';
  text?: string;
  fontSize?: number;
  /** Optional per-element CSS font family; falls back to the global family. */
  fontFamily?: string;
  color?: string;
  zIndex?: number;
  borderRadius?: number;
  
  // Advanced typography & styling properties
  fontWeight?: 'normal' | 'bold';
  fontStyle?: 'normal' | 'italic';
  textAlign?: 'left' | 'center' | 'right';
  strokeWidth?: number;
  strokeColor?: string;
  shadowColor?: string;
  shadowBlur?: number;
  shadowOffsetX?: number;
  shadowOffsetY?: number;
  
  // Animation settings
  animation?: AnimationSettings;

  // Scene v2 Group and Results Group properties
  childIds?: string[];
  templateRole?: 'player-card' | null;
  definitionRole?: 'result-card' | null;
  templateId?: string;
  cardDefinitionId?: string;
  definitionId?: string;
  instanceRole?: 'stage' | 'linked';
  standingOrdinal?: number;
  variant?: 'champion' | 'podium' | 'standard';
  outerAnimation?: ResultCardLifecycle;
  animationOverride?: Partial<ResultCardLifecycle>;
  schedule?: any;
  autoSequence?: any;
  rotation?: number;
  opacity?: number;
  mode?: 'board' | 'sequence';
  cutoff?: 'top8' | 'top16' | 'all';
  pageNumber?: number;
  pageSize?: number;
  layoutPresetId?: string;
  customSlots?: any[];
  variantRules?: any[];
  variants?: Record<string, any>;
  sequence?: any;
  preview?: any;
  themePreset?: string;
  accentColor?: string;
  cardAnimationPreset?: string;
  largeImageSource?: 'character' | 'player';
  showSmallImage?: boolean;
  smallImageSource?: 'player' | 'character';
  binding?: string;
  formatMode?: 'auto' | 'ft2' | 'ft3' | 'ft5' | 'ft7';
  winMarkerStyle?: 'check' | 'solid' | 'dot' | 'image';
  customMarkerUrl?: string;
  markerWidth?: number;
  markerHeight?: number;
  markerOffsetX?: number;
  markerOffsetY?: number;
  boxBorderColor?: string;
  boxBgColor?: string;
  wonColor?: string;
  wonBgColor?: string;
  currentHighlightColor?: string;
  p1ScoreOverride?: number;
  p2ScoreOverride?: number;
  gamesHistoryOverride?: ('p1' | 'p2' | null)[];
  matrixThemePreset?: 'crimson' | 'royal-blue' | 'cyber-gold' | 'emerald' | 'monochrome' | 'custom';
  matrixCardAnimation?: 'none' | 'deal' | 'slam' | 'float' | 'flip' | 'hologram' | 'glow-pulse';

  // Tournament Bracket Tree properties
  bracketLayoutVariant?: 'top8-double-elim' | 'top4-showcase';
  bracketThemePreset?: 'crimson' | 'royal-blue' | 'cyber-gold' | 'emerald' | 'monochrome' | 'custom';
  bracketAccentColor?: string;
  bracketHeaderColor?: string;
  bracketSponsorText?: string;
  bracketGameName?: string;
  bracketTournamentName?: string;
  bracketRoundBestOf?: string;
  bracketShowBackground?: boolean;
  bracketShowSponsors?: boolean;
  bracketShowAvatars?: boolean;
  bracketAvatarSize?: number;
  bracketConnectorColor?: string;
  bracketConnectorActiveColor?: string;
  bracketConnectorWidth?: number;
  bracketCardBgColor?: string;
  bracketCardBorderColor?: string;
  bracketWinnerColor?: string;
  bracketTestMode?: boolean;
  bracketSimulateReset?: boolean;
  bracketBadgeStyle?: 'pill' | 'text';
  top4StageMode?: 'auto' | 'opening_top8' | 'final4' | 'grand_finals';
  bracketCardAnimation?: 'none' | 'deal' | 'slam' | 'float' | 'flip' | 'hologram' | 'glow-pulse';

  // Victory Path properties
  vpTargetPlayer?: 'p1' | 'p2' | 'custom';
  vpCustomPlayerName?: string;
  vpTestMode?: boolean;
  vpThemePreset?: 'crimson' | 'royal-blue' | 'cyber-gold' | 'emerald' | 'monochrome' | 'custom';
  vpAccentColor?: string;
  vpBgColor?: string;
  vpCardBgColor?: string;
  vpBorderColor?: string;
  vpFooterText?: string;
  vpCardAnimation?: 'none' | 'deal' | 'slam' | 'float' | 'flip' | 'hologram' | 'glow-pulse';
}

export interface FontOption {
  family: string;
  url?: string;
}

interface EditorState {
  elements: Record<string, OverlayElement>;
  background_url: string;
  global_font_url: string;
  global_font_family: string;
  font_library: FontOption[];
  selectedId: string | null;
  selectedIds: string[];
  statusMsg: string;
  clipboardStyle: Partial<OverlayElement> | null;
  clipboardPosition: { x: number, y: number } | null;
  activeMatch: any | null;
  resultsPreviewCueIndex: Record<string, number>;
  editingResultCardDefinitionId: string | null;
  
  // History states
  past: Record<string, OverlayElement>[];
  future: Record<string, OverlayElement>[];
  takeSnapshot: () => void;
  undo: () => void;
  redo: () => void;
  
  setElements: (elements: Record<string, OverlayElement>) => void;
  mergeDynamicData: (elements: Record<string, OverlayElement>) => void;
  updateElement: (id: string, updates: Partial<OverlayElement>) => void;
  addElement: (element: OverlayElement) => void;
  deleteElement: (id: string) => void;
  restoreElement: (id: string) => void;
  setSelectedId: (id: string | null) => void;
  setSelectedIds: (ids: string[]) => void;
  toggleSelectedId: (id: string) => void;
  setGlobalSettings: (bg: string, fontUrl: string, fontFamily: string) => void;
  setFontLibrary: (fonts: FontOption[]) => void;
  removeFontFromLibrary: (family: string) => void;
  setStatusMsg: (msg: string) => void;
  setClipboardStyle: (style: Partial<OverlayElement> | null) => void;
  setClipboardPosition: (pos: { x: number, y: number } | null) => void;
  setActiveMatch: (match: any | null) => void;
  setResultsPreviewCueIndex: (resultsGroupId: string, cueIndex: number) => void;
  enterResultCardDesign: (definitionId: string) => void;
  exitResultCardDesign: () => void;
}

export const useEditorStore = create<EditorState>((set) => ({
  elements: {},
  background_url: '',
  global_font_url: '',
  global_font_family: '',
  font_library: [
    { family: "'Cairo', sans-serif", url: 'https://fonts.googleapis.com/css2?family=Cairo:wght@200..1000&display=swap' },
    { family: "'Jaro', sans-serif", url: 'https://fonts.googleapis.com/css2?family=Jaro:opsz@6..72&display=swap' },
    { family: "'Special Gothic Condensed One', sans-serif", url: 'https://fonts.googleapis.com/css2?family=Special+Gothic+Condensed+One&display=swap' },
  ],
  selectedId: null,
  selectedIds: [],
  statusMsg: 'Not connected',
  clipboardStyle: null,
  clipboardPosition: null,
  activeMatch: null,
  resultsPreviewCueIndex: {},
  editingResultCardDefinitionId: null,
  past: [],
  future: [],

  takeSnapshot: () => set((state) => ({
    past: [...state.past, JSON.parse(JSON.stringify(state.elements))].slice(-50),
    future: []
  })),
  undo: () => set((state) => {
    if (state.past.length === 0) return {};
    const previous = state.past[state.past.length - 1];
    const newPast = state.past.slice(0, state.past.length - 1);
    return {
      past: newPast,
      future: [JSON.parse(JSON.stringify(state.elements)), ...state.future],
      elements: previous,
      selectedId: null,
      selectedIds: [],
      editingResultCardDefinitionId: null,
    };
  }),
  redo: () => set((state) => {
    if (state.future.length === 0) return {};
    const next = state.future[0];
    const newFuture = state.future.slice(1);
    return {
      past: [...state.past, JSON.parse(JSON.stringify(state.elements))],
      future: newFuture,
      elements: next,
      selectedId: null,
      selectedIds: [],
      editingResultCardDefinitionId: null,
    };
  }),

  setElements: (elements) => set({ elements }),
  mergeDynamicData: (incomingElements) => set((state) => {
    const newElements = { ...state.elements };
    for (const key in incomingElements) {
      const incoming = incomingElements[key];
      const update = (element: OverlayElement) => ({
        ...element,
        text: incoming.text,
        src: incoming.src,
        visible: incoming.visible
      });
      if (newElements[key]) newElements[key] = update(newElements[key]);
      // Instances remain independent layout elements, but mirror the live
      // content of their source hook instead of creating duplicate hooks.
      Object.keys(newElements).forEach((id) => {
        if (newElements[id].sourceId === key) newElements[id] = update(newElements[id]);
      }
      );
      if (!newElements[key]) newElements[key] = incoming;
    }
    return { elements: newElements };
  }),
  updateElement: (id, updates) => set((state) => ({
    elements: {
      ...state.elements,
      [id]: { ...state.elements[id], ...updates }
    }
  })),
  addElement: (element) => set((state) => {
    const currentClone = JSON.parse(JSON.stringify(state.elements));
    return {
      past: [...state.past, currentClone].slice(-50),
      future: [],
      elements: {
        ...state.elements,
        [element.id]: element
      },
      selectedId: element.id,
      selectedIds: [element.id]
    };
  }),
  deleteElement: (id) => set((state) => {
    const currentClone = JSON.parse(JSON.stringify(state.elements));
    const newElements = { ...state.elements };
    const target = newElements[id];
    if (target?.type === 'result-card' && target.instanceRole === 'stage' && target.parentId) {
      const parent = newElements[target.parentId];
      const replacement = (parent?.childIds || [])
        .filter((childId) => childId !== id)
        .map((childId) => newElements[childId])
        .find((candidate) => candidate?.type === 'result-card');
      if (replacement && target.definitionId) {
        newElements[replacement.id] = { ...replacement, instanceRole: 'stage' };
        const definition = newElements[target.definitionId];
        if (definition) newElements[target.definitionId] = { ...definition, parentId: replacement.id };
        if (parent) {
          newElements[parent.id] = {
            ...parent,
            autoSequence: parent.autoSequence
              ? { ...parent.autoSequence, stageInstanceId: replacement.id }
              : parent.autoSequence,
          };
        }
      }
    }
    const toDelete = new Set<string>([id]);
    let changed = true;
    while (changed) {
      changed = false;
      Object.values(newElements).forEach((el) => {
        const referencedByDeletedGroup = Object.values(newElements).some(
          (parent) => toDelete.has(parent.id)
            && (parent.childIds?.includes(el.id)
              || (parent.type === 'results-group' && (parent.cardDefinitionId === el.id || parent.templateId === el.id))
              || (parent.type === 'result-card' && parent.definitionId === el.id)),
        );
        if (!toDelete.has(el.id) && ((el.parentId && toDelete.has(el.parentId)) || referencedByDeletedGroup)) {
          toDelete.add(el.id);
          changed = true;
        }
      });
    }
    toDelete.forEach((delId) => {
      delete newElements[delId];
    });
    Object.entries(newElements).forEach(([elementId, element]) => {
      if (!element.childIds?.some((childId) => toDelete.has(childId))) return;
      newElements[elementId] = {
        ...element,
        childIds: element.childIds.filter((childId) => !toDelete.has(childId)),
      };
    });
    return {
      past: [...state.past, currentClone].slice(-50),
      future: [],
      elements: newElements,
      selectedId: toDelete.has(state.selectedId || '') ? null : state.selectedId,
      selectedIds: state.selectedIds.filter((selected) => !toDelete.has(selected)),
      editingResultCardDefinitionId: toDelete.has(state.editingResultCardDefinitionId || '')
        ? null
        : state.editingResultCardDefinitionId,
    };
  }),
  restoreElement: (id) => set((state) => {
    const currentClone = JSON.parse(JSON.stringify(state.elements));
    const defaultTemplates: Record<string, OverlayElement> = {
      p1_name: { id: 'p1_name', type: 'text', x: 400, y: 950, fontSize: 48, color: '#ffffff', text: 'Player 1', visible: true },
      p2_name: { id: 'p2_name', type: 'text', x: 1520, y: 950, fontSize: 48, color: '#ffffff', text: 'Player 2', visible: true },
      p1_score: { id: 'p1_score', type: 'text', x: 800, y: 950, fontSize: 64, color: '#ff0000', text: '0', visible: true },
      p2_score: { id: 'p2_score', type: 'text', x: 1120, y: 950, fontSize: 64, color: '#ff0000', text: '0', visible: true },
      p1_prefix: { id: 'p1_prefix', type: 'text', x: 400, y: 900, fontSize: 24, color: '#aaaaaa', text: '[PREFIX]', visible: true },
      p2_prefix: { id: 'p2_prefix', type: 'text', x: 1520, y: 900, fontSize: 24, color: '#aaaaaa', text: '[PREFIX]', visible: true },
      p1_country: { id: 'p1_country', type: 'text', x: 400, y: 860, fontSize: 20, color: '#aaaaaa', text: 'JO', visible: true },
      p2_country: { id: 'p2_country', type: 'text', x: 1520, y: 860, fontSize: 20, color: '#aaaaaa', text: 'JO', visible: true },
      p1_cfn: { id: 'p1_cfn', type: 'text', x: 400, y: 780, fontSize: 20, color: '#ffffff', text: 'CFN', visible: true },
      p2_cfn: { id: 'p2_cfn', type: 'text', x: 1520, y: 780, fontSize: 20, color: '#ffffff', text: 'CFN', visible: true },
      p1_character: { id: 'p1_character', type: 'text', x: 400, y: 820, fontSize: 24, color: '#ffffff', text: 'Character 1', visible: true },
      p2_character: { id: 'p2_character', type: 'text', x: 1520, y: 820, fontSize: 24, color: '#ffffff', text: 'Character 2', visible: true },
      game_name: { id: 'game_name', type: 'text', x: 960, y: 150, fontSize: 24, color: '#aaaaaa', text: 'Game', visible: true },
      tournament_round: { id: 'tournament_round', type: 'text', x: 960, y: 50, fontSize: 32, color: '#ffffff', text: 'Winners Semis', visible: true },
      tournament_name: { id: 'tournament_name', type: 'text', x: 960, y: 100, fontSize: 24, color: '#aaaaaa', text: 'Tournament', visible: true },
      p1_avatar: { id: 'p1_avatar', type: 'image', x: 250, y: 850, width: 180, height: 180, src: '/static/player_placeholder.jpg', visible: true },
      p2_avatar: { id: 'p2_avatar', type: 'image', x: 1670, y: 850, width: 180, height: 180, src: '/static/player_placeholder.jpg', visible: true },
      p1_character_image: { id: 'p1_character_image', type: 'image', x: 250, y: 650, width: 140, height: 140, src: '/static/player_placeholder.jpg', visible: true },
      p2_character_image: { id: 'p2_character_image', type: 'image', x: 1670, y: 650, width: 140, height: 140, src: '/static/player_placeholder.jpg', visible: true },
      p1_flag: { id: 'p1_flag', type: 'image', x: 250, y: 980, width: 120, height: 90, src: '/static/flag_placeholder.png', visible: true },
      p2_flag: { id: 'p2_flag', type: 'image', x: 1670, y: 980, width: 120, height: 90, src: '/static/flag_placeholder.png', visible: true },
      next_p1_name: { id: 'next_p1_name', type: 'text', x: 400, y: 400, fontSize: 36, color: '#ffffff', text: 'Next Player 1', visible: true },
      next_p2_name: { id: 'next_p2_name', type: 'text', x: 1520, y: 400, fontSize: 36, color: '#ffffff', text: 'Next Player 2', visible: true },
      next_p1_score: { id: 'next_p1_score', type: 'text', x: 800, y: 400, fontSize: 48, color: '#ffcc00', text: '0', visible: true },
      next_p2_score: { id: 'next_p2_score', type: 'text', x: 1120, y: 400, fontSize: 48, color: '#ffcc00', text: '0', visible: true },
      next_p1_prefix: { id: 'next_p1_prefix', type: 'text', x: 400, y: 360, fontSize: 20, color: '#aaaaaa', text: '[PREFIX]', visible: true },
      next_p2_prefix: { id: 'next_p2_prefix', type: 'text', x: 1520, y: 360, fontSize: 20, color: '#aaaaaa', text: '[PREFIX]', visible: true },
      next_p1_country: { id: 'next_p1_country', type: 'text', x: 400, y: 320, fontSize: 18, color: '#aaaaaa', text: 'JO', visible: true },
      next_p2_country: { id: 'next_p2_country', type: 'text', x: 1520, y: 320, fontSize: 18, color: '#aaaaaa', text: 'JO', visible: true },
      next_p1_character: { id: 'next_p1_character', type: 'text', x: 400, y: 280, fontSize: 20, color: '#ffffff', text: 'Next Character 1', visible: true },
      next_p2_character: { id: 'next_p2_character', type: 'text', x: 1520, y: 280, fontSize: 20, color: '#ffffff', text: 'Next Character 2', visible: true },
      next_round_name: { id: 'next_round_name', type: 'text', x: 960, y: 200, fontSize: 28, color: '#ffcc00', text: 'Next: Winners Finals', visible: true },
      next_match_number: { id: 'next_match_number', type: 'text', x: 960, y: 250, fontSize: 22, color: '#aaaaaa', text: 'Match #2', visible: true },
      next_match_status: { id: 'next_match_status', type: 'text', x: 960, y: 300, fontSize: 20, color: '#00ffcc', text: 'Up Next', visible: true },
      next_p1_avatar: { id: 'next_p1_avatar', type: 'image', x: 280, y: 350, width: 140, height: 140, src: '/static/player_placeholder.jpg', visible: true },
      next_p2_avatar: { id: 'next_p2_avatar', type: 'image', x: 1640, y: 350, width: 140, height: 140, src: '/static/player_placeholder.jpg', visible: true },
      next_p1_flag: { id: 'next_p1_flag', type: 'image', x: 280, y: 450, width: 80, height: 60, src: '/static/flag_placeholder.png', visible: true },
      next_p2_flag: { id: 'next_p2_flag', type: 'image', x: 1640, y: 450, width: 80, height: 60, src: '/static/flag_placeholder.png', visible: true },
    };
    
    const newEl = state.elements[id] 
      ? { ...state.elements[id], visible: true } 
      : (defaultTemplates[id] || { id, type: 'text', x: 960, y: 540, fontSize: 24, color: '#ffffff', text: 'New Text', visible: true });
      
    return {
      past: [...state.past, currentClone].slice(-50),
      future: [],
      elements: { ...state.elements, [id]: newEl as OverlayElement },
      selectedId: id
    };
  }),
  setSelectedId: (selectedId) => set({ selectedId, selectedIds: selectedId ? [selectedId] : [] }),
  setSelectedIds: (selectedIds) => set({ selectedIds, selectedId: selectedIds[selectedIds.length - 1] || null }),
  toggleSelectedId: (id) => set((state) => {
    const selectedIds = state.selectedIds.includes(id)
      ? state.selectedIds.filter(selected => selected !== id)
      : [...state.selectedIds, id];
    return { selectedIds, selectedId: selectedIds[selectedIds.length - 1] || null };
  }),
  setGlobalSettings: (background_url, global_font_url, global_font_family) => set({
    background_url, global_font_url, global_font_family
  }),
  // Keep built-in fonts available when loading an older saved overlay that
  // contains only its previously configured custom font list.
  setFontLibrary: (font_library) => set((state) => {
    const merged = [...state.font_library, ...font_library];
    const unique = merged.filter((font, index) => merged.findIndex(item => item.family === font.family) === index);
    return { font_library: unique };
  }),
  removeFontFromLibrary: (family) => set((state) => {
    const nextLibrary = state.font_library.filter(font => font.family !== family);
    const updates: Partial<EditorState> = { font_library: nextLibrary };
    if (state.global_font_family === family) {
      updates.global_font_family = '';
      updates.global_font_url = '';
    }
    return updates as any;
  }),
  setStatusMsg: (statusMsg) => set({ statusMsg }),
  setClipboardStyle: (style) => set({ clipboardStyle: style }),
  setClipboardPosition: (pos) => set({ clipboardPosition: pos }),
  setActiveMatch: (activeMatch) => set({ activeMatch }),
  setResultsPreviewCueIndex: (resultsGroupId, cueIndex) => set((state) => ({
    resultsPreviewCueIndex: {
      ...state.resultsPreviewCueIndex,
      [resultsGroupId]: cueIndex,
    },
  })),
  enterResultCardDesign: (editingResultCardDefinitionId) => set({
    editingResultCardDefinitionId,
    selectedId: editingResultCardDefinitionId,
    selectedIds: [editingResultCardDefinitionId],
  }),
  exitResultCardDesign: () => set({ editingResultCardDefinitionId: null }),
}));
