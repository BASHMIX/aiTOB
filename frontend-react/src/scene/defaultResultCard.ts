import type { AnimationSettings, OverlayElement, ResultCardLifecycle } from '@/store/useEditorStore';
import { FLAG_IMAGE_PLACEHOLDER, PLAYER_IMAGE_PLACEHOLDER } from '@/utils/overlayAssets';

export const DEFAULT_RESULT_CARD_WIDTH = 420;
export const DEFAULT_RESULT_CARD_HEIGHT = 560;

export function createDefaultResultCardAnimation(): AnimationSettings {
  return {
    animationType: 'float-in',
    direction: 'bottom',
    duration: 500,
    delay: 0,
    loop: 0,
    tweenType: 'ease-out',
    playOn: 'IN',
    trigger: 'on-load',
    revealStyle: 'all',
    idleAnimation: 'none',
    idleIntensity: 1,
  };
}

export function createDefaultResultCardLifecycle(x: number, y: number): ResultCardLifecycle {
  return {
    start: { x, y: y + 160, scale: 0.15, opacity: 0, rotation: 0 },
    visible: { x, y, scale: 1, opacity: 1, rotation: 0 },
    exit: { x: x + 520, y, scale: 0.82, opacity: 0, rotation: 0 },
    enterDurationMs: 500,
    visibleHoldMs: 1000,
    exitDurationMs: 500,
    enterEasing: 'ease-out',
    exitEasing: 'ease-in',
  };
}

export function createDefaultResultCardDefinition(
  suffix: string | number,
  parentId: string,
): { definition: OverlayElement; children: OverlayElement[] } {
  const definitionId = `result_card_definition_${suffix}`;
  const children: OverlayElement[] = [
    {
      id: `result_card_bg_${suffix}`, parentId: definitionId, name: 'Card Background', type: 'rect',
      visible: true, x: 0, y: 0, width: DEFAULT_RESULT_CARD_WIDTH, height: DEFAULT_RESULT_CARD_HEIGHT,
      color: '#111827', borderRadius: 24, strokeWidth: 2, strokeColor: '#334155', zIndex: 1,
    },
    {
      id: `result_card_character_${suffix}`, parentId: definitionId, name: 'Character Art', type: 'image',
      visible: true, x: 18, y: 86, width: 384, height: 330, src: PLAYER_IMAGE_PLACEHOLDER,
      binding: 'characterImageUrl', borderRadius: 12, zIndex: 2,
    },
    {
      id: `result_card_avatar_${suffix}`, parentId: definitionId, name: 'Player Photo', type: 'image',
      visible: true, x: 24, y: 352, width: 126, height: 126, src: PLAYER_IMAGE_PLACEHOLDER,
      binding: 'avatarUrl', borderRadius: 14, zIndex: 3,
    },
    {
      id: `result_card_badge_${suffix}`, parentId: definitionId, name: 'Placement Badge', type: 'rect',
      visible: true, x: 18, y: 18, width: 72, height: 58, color: '#0ea5e9', borderRadius: 12, zIndex: 4,
    },
    {
      id: `result_card_placement_${suffix}`, parentId: definitionId, name: 'Placement', type: 'text',
      visible: true, x: 18, y: 18, width: 72, height: 58, text: '1', binding: 'placement',
      fontSize: 30, fontWeight: 'bold', textAlign: 'center', color: '#06111b', zIndex: 5,
    },
    {
      id: `result_card_prefix_${suffix}`, parentId: definitionId, name: 'Prefix', type: 'text',
      visible: true, x: 106, y: 20, width: 220, height: 24, text: 'PREFIX', binding: 'prefix',
      fontSize: 16, fontWeight: 'bold', textAlign: 'left', color: '#38bdf8', zIndex: 5,
    },
    {
      id: `result_card_name_${suffix}`, parentId: definitionId, name: 'Player Name', type: 'text',
      visible: true, x: 106, y: 42, width: 286, height: 38, text: 'Player', binding: 'displayName',
      fontSize: 28, fontWeight: 'bold', textAlign: 'left', color: '#ffffff', zIndex: 5,
    },
    {
      id: `result_card_flag_${suffix}`, parentId: definitionId, name: 'Country Flag', type: 'image',
      visible: true, x: 164, y: 366, width: 74, height: 50, src: FLAG_IMAGE_PLACEHOLDER,
      binding: 'countryFlagUrl', borderRadius: 4, zIndex: 5,
    },
    {
      id: `result_card_character_name_${suffix}`, parentId: definitionId, name: 'Featured Character', type: 'text',
      visible: true, x: 164, y: 424, width: 228, height: 32, text: 'Character', binding: 'characterName',
      fontSize: 19, fontWeight: 'bold', textAlign: 'left', color: '#cbd5e1', zIndex: 5,
    },
  ];

  const definition: OverlayElement = {
    id: definitionId,
    parentId,
    name: 'Result Card Design',
    type: 'group',
    definitionRole: 'result-card',
    templateRole: 'player-card',
    visible: true,
    x: 0,
    y: 0,
    width: DEFAULT_RESULT_CARD_WIDTH,
    height: DEFAULT_RESULT_CARD_HEIGHT,
    childIds: children.map((child) => child.id),
    variants: { champion: {}, podium: {}, standard: {} },
    animation: createDefaultResultCardAnimation(),
    zIndex: 1,
  };

  return { definition, children };
}

export function createFreeformResultCardBundle(suffix: string | number) {
  const schedulerId = `results_cards_${suffix}`;
  const cardId = `result_card_${suffix}`;
  const x = 750;
  const y = 250;
  const { definition, children } = createDefaultResultCardDefinition(suffix, cardId);
  const card: OverlayElement = {
    id: cardId,
    parentId: schedulerId,
    name: 'Result Card',
    type: 'result-card',
    definitionId: definition.id,
    instanceRole: 'stage',
    standingOrdinal: 1,
    visible: true,
    x,
    y,
    width: DEFAULT_RESULT_CARD_WIDTH,
    height: DEFAULT_RESULT_CARD_HEIGHT,
    rotation: 0,
    opacity: 1,
    zIndex: 10,
    animation: createDefaultResultCardAnimation(),
  };
  const scheduler: OverlayElement = {
    id: schedulerId,
    name: 'Results Cards',
    type: 'results-cards',
    visible: true,
    x: 0,
    y: 0,
    width: 1920,
    height: 1080,
    childIds: [cardId],
    schedule: {
      order: 'placement-desc',
      delayBetweenStartsMs: 500,
      trigger: 'with-previous',
      keepPreviousVisible: true,
      loop: false,
    },
    autoSequence: {
      enabled: false,
      stageInstanceId: cardId,
      range: 'top8',
      pageNumber: 1,
      pageSize: 16,
      order: 'placement-desc',
      delayBetweenStartsMs: 500,
      endBehavior: 'card-exit',
    },
    preview: { dataset: 'normal', count: 'top8', pageNumber: 1 },
    zIndex: 9,
  };
  return { scheduler, card, definition, children };
}
