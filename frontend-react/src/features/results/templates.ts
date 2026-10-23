import type { SceneDocumentV2, ResultsGroupNode, GroupNode, TextNode, RectNode, ImageNode } from '@/scene/types';

export interface TemplateDefinition {
  id: string;
  name: string;
  description: string;
  thumbnailUrl?: string;
  document: SceneDocumentV2;
}

function createBaseMasterCard(): {
  templateGroup: GroupNode;
  children: (RectNode | TextNode | ImageNode)[];
} {
  const bg: RectNode = {
    id: 'mc-bg',
    type: 'rect',
    name: 'Card Background',
    parentId: 'master-player-card',
    visible: true,
    x: 0,
    y: 0,
    width: 500,
    height: 700,
    color: '#1a1f2e',
    borderRadius: 16,
    strokeWidth: 2,
    strokeColor: '#2e3a59',
  };

  const characterImage: ImageNode = {
    id: 'mc-character-art',
    type: 'image',
    name: 'Character Art',
    parentId: 'master-player-card',
    visible: true,
    x: 20,
    y: 120,
    width: 460,
    height: 440,
    binding: 'characterImageUrl',
    objectFit: 'contain',
  };

  const placementBadge: RectNode = {
    id: 'mc-placement-badge',
    type: 'rect',
    name: 'Placement Badge',
    parentId: 'master-player-card',
    visible: true,
    x: 20,
    y: 20,
    width: 80,
    height: 80,
    borderRadius: 12,
    color: '#e5a50a',
  };

  const placementText: TextNode = {
    id: 'mc-placement-text',
    type: 'text',
    name: 'Placement Text',
    parentId: 'master-player-card',
    visible: true,
    x: 20,
    y: 35,
    width: 80,
    height: 50,
    binding: 'placement',
    text: '1',
    fontSize: 36,
    fontWeight: 'bold',
    textAlign: 'center',
    color: '#0d1117',
  };

  const prefixText: TextNode = {
    id: 'mc-prefix-text',
    type: 'text',
    name: 'Team / Prefix',
    parentId: 'master-player-card',
    visible: true,
    x: 120,
    y: 25,
    width: 350,
    height: 24,
    binding: 'prefix',
    text: 'FAV',
    fontSize: 18,
    fontWeight: 'normal',
    textAlign: 'left',
    color: '#8b9bb4',
  };

  const nameText: TextNode = {
    id: 'mc-name-text',
    type: 'text',
    name: 'Entrant Name',
    parentId: 'master-player-card',
    visible: true,
    x: 120,
    y: 52,
    width: 350,
    height: 45,
    binding: 'displayName',
    text: 'Knee',
    fontSize: 32,
    fontWeight: 'bold',
    textAlign: 'left',
    color: '#ffffff',
  };

  const countryText: TextNode = {
    id: 'mc-country-text',
    type: 'text',
    name: 'Country',
    parentId: 'master-player-card',
    visible: true,
    x: 20,
    y: 630,
    width: 460,
    height: 30,
    binding: 'countryCode',
    text: 'KR',
    fontSize: 20,
    fontWeight: 'normal',
    textAlign: 'center',
    color: '#8b9bb4',
  };

  const templateGroup: GroupNode = {
    id: 'master-player-card',
    type: 'group',
    name: 'Result Card Design',
    templateRole: 'player-card',
    visible: true,
    x: 0,
    y: 0,
    width: 500,
    height: 700,
    childIds: [
      'mc-bg',
      'mc-character-art',
      'mc-placement-badge',
      'mc-placement-text',
      'mc-prefix-text',
      'mc-name-text',
      'mc-country-text',
    ],
    variants: {
      champion: {
        'mc-bg': { strokeColor: '#e5a50a', strokeWidth: 3 },
        'mc-placement-badge': { color: '#e5a50a' },
        'mc-name-text': { fontSize: 36, color: '#ffd700' },
      },
      podium: {
        'mc-bg': { strokeColor: '#a0b0c0', strokeWidth: 2 },
        'mc-placement-badge': { color: '#8fa0b5' },
        'mc-name-text': { fontSize: 26 },
        'mc-placement-text': { fontSize: 28 },
      },
      standard: {
        'mc-bg': { strokeColor: '#2e3a59', strokeWidth: 1 },
        'mc-placement-badge': { color: '#3a4a6b' },
        'mc-name-text': { fontSize: 20 },
        'mc-placement-text': { fontSize: 20 },
      },
    },
  };

  return {
    templateGroup,
    children: [bg, characterImage, placementBadge, placementText, prefixText, nameText, countryText],
  };
}

export function createChampionFocusDocument(): SceneDocumentV2 {
  const { templateGroup, children } = createBaseMasterCard();

  const titleNode: TextNode = {
    id: 'doc-header-title',
    type: 'text',
    name: 'Tournament Header',
    visible: true,
    x: 80,
    y: 50,
    width: 1760,
    height: 70,
    text: 'FINAL STANDINGS',
    fontSize: 48,
    fontWeight: 'bold',
    textAlign: 'left',
    color: '#ffffff',
  };

  const resultsGroup: ResultsGroupNode = {
    id: 'rg-main',
    type: 'results-group',
    name: 'Top 8 Results Group',
    templateId: 'master-player-card',
    mode: 'board',
    cutoff: 'top8',
    pageNumber: 1,
    pageSize: 8,
    layoutPresetId: 'champion-focus',
    visible: true,
    x: 80,
    y: 150,
    width: 1760,
    height: 850,
    variantRules: [
      { fromPlacement: 1, toPlacement: 1, variant: 'champion' },
      { fromPlacement: 2, toPlacement: 4, variant: 'podium' },
      { fromPlacement: 5, toPlacement: 16, variant: 'standard' },
    ],
    customSlots: [
      // 1st place: Large Champion Card
      { slotId: 'slot-1', ordinal: 1, x: 80, y: 150, width: 480, height: 850, variant: 'champion' },
      // 2nd, 3rd, 4th: Medium Podium Cards
      { slotId: 'slot-2', ordinal: 2, x: 590, y: 150, width: 550, height: 265, variant: 'podium' },
      { slotId: 'slot-3', ordinal: 3, x: 590, y: 442, width: 550, height: 265, variant: 'podium' },
      { slotId: 'slot-4', ordinal: 4, x: 590, y: 735, width: 550, height: 265, variant: 'podium' },
      // 5th, 5th, 7th, 7th: Compact Cards
      { slotId: 'slot-5', ordinal: 5, x: 1170, y: 150, width: 590, height: 195, variant: 'standard' },
      { slotId: 'slot-6', ordinal: 6, x: 1170, y: 368, width: 590, height: 195, variant: 'standard' },
      { slotId: 'slot-7', ordinal: 7, x: 1170, y: 586, width: 590, height: 195, variant: 'standard' },
      { slotId: 'slot-8', ordinal: 8, x: 1170, y: 805, width: 590, height: 195, variant: 'standard' },
    ],
    sequence: {
      order: 'champion-last',
      startDelayMs: 300,
      intervalMs: 800,
      holdMs: 4000,
      exit: 'sequential',
      loop: false,
      manualCue: false,
    },
  };

  const nodes: Record<string, any> = {
    'doc-header-title': titleNode,
    'rg-main': resultsGroup,
    'master-player-card': templateGroup,
  };
  for (const child of children) {
    nodes[child.id] = child;
  }

  return {
    schemaVersion: 2,
    canvas: {
      width: 1920,
      height: 1080,
      backgroundUrl: '',
      safeArea: { top: 40, right: 60, bottom: 40, left: 60 },
    },
    dataSource: { kind: 'tournament-results' },
    rootIds: ['doc-header-title', 'rg-main'],
    nodes,
  };
}

export function createPodiumDocument(): SceneDocumentV2 {
  const doc = createChampionFocusDocument();
  const rg = doc.nodes['rg-main'] as ResultsGroupNode;
  rg.layoutPresetId = 'podium-remaining';
  rg.customSlots = [
    // 2nd Place (Left)
    { slotId: 'slot-2', ordinal: 2, x: 140, y: 220, width: 480, height: 420, variant: 'podium' },
    // 1st Place (Center elevated)
    { slotId: 'slot-1', ordinal: 1, x: 670, y: 150, width: 580, height: 490, variant: 'champion' },
    // 3rd Place (Right)
    { slotId: 'slot-3', ordinal: 3, x: 1300, y: 240, width: 480, height: 400, variant: 'podium' },
    // Remaining 4-8 in lower row
    { slotId: 'slot-4', ordinal: 4, x: 140, y: 700, width: 300, height: 260, variant: 'standard' },
    { slotId: 'slot-5', ordinal: 5, x: 480, y: 700, width: 300, height: 260, variant: 'standard' },
    { slotId: 'slot-6', ordinal: 6, x: 810, y: 700, width: 300, height: 260, variant: 'standard' },
    { slotId: 'slot-7', ordinal: 7, x: 1140, y: 700, width: 300, height: 260, variant: 'standard' },
    { slotId: 'slot-8', ordinal: 8, x: 1470, y: 700, width: 300, height: 260, variant: 'standard' },
  ];
  return doc;
}

export function createEqualGridDocument(): SceneDocumentV2 {
  const doc = createChampionFocusDocument();
  const rg = doc.nodes['rg-main'] as ResultsGroupNode;
  rg.layoutPresetId = 'equal-grid';
  const slots = [];
  const startX = 80;
  const startY = 160;
  const colW = 410;
  const rowH = 390;
  const gapX = 35;
  const gapY = 40;

  for (let i = 0; i < 8; i++) {
    const col = i % 4;
    const row = Math.floor(i / 4);
    slots.push({
      slotId: `slot-${i + 1}`,
      ordinal: i + 1,
      x: startX + col * (colW + gapX),
      y: startY + row * (rowH + gapY),
      width: colW,
      height: rowH,
      variant: (i === 0 ? 'champion' : i < 3 ? 'podium' : 'standard') as any,
    });
  }
  rg.customSlots = slots;
  return doc;
}

export function createRankedListDocument(): SceneDocumentV2 {
  const doc = createChampionFocusDocument();
  const rg = doc.nodes['rg-main'] as ResultsGroupNode;
  rg.layoutPresetId = 'ranked-list';
  const slots = [];
  const startY = 150;
  const rowH = 95;
  const gapY = 12;

  for (let i = 0; i < 8; i++) {
    slots.push({
      slotId: `slot-${i + 1}`,
      ordinal: i + 1,
      x: 100,
      y: startY + i * (rowH + gapY),
      width: 1720,
      height: rowH,
      variant: (i === 0 ? 'champion' : i < 3 ? 'podium' : 'standard') as any,
    });
  }
  rg.customSlots = slots;
  return doc;
}

export const STARTER_TEMPLATES: TemplateDefinition[] = [
  {
    id: 'champion-focus',
    name: 'Champion Focus (Top 8)',
    description: 'Hero presentation for the winner with medium podium and compact remaining placements.',
    document: createChampionFocusDocument(),
  },
  {
    id: 'podium-remaining',
    name: 'Podium + Remaining',
    description: 'Elevated top 3 podium layout with remaining placements positioned below.',
    document: createPodiumDocument(),
  },
  {
    id: 'equal-grid',
    name: 'Equal Grid (2x4)',
    description: 'Clean uniform 8-card grid balanced across the broadcast canvas.',
    document: createEqualGridDocument(),
  },
  {
    id: 'ranked-list',
    name: 'Ranked List',
    description: 'Sleek horizontal list with clear placement hierarchy and team branding.',
    document: createRankedListDocument(),
  },
];

export function getResultsLayoutPresetSlots(
  presetId: string,
  bounds: Pick<ResultsGroupNode, 'x' | 'y' | 'width' | 'height'>,
) {
  const preset = STARTER_TEMPLATES.find((item) => item.id === presetId)
    || STARTER_TEMPLATES[0];
  const source = preset.document.nodes['rg-main'] as ResultsGroupNode;
  const scaleX = bounds.width / source.width;
  const scaleY = bounds.height / source.height;

  return (source.customSlots || []).map((slot) => ({
    ...slot,
    x: bounds.x + (slot.x - source.x) * scaleX,
    y: bounds.y + (slot.y - source.y) * scaleY,
    width: slot.width * scaleX,
    height: slot.height * scaleY,
  }));
}
