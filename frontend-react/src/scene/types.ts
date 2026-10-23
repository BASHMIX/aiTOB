export type NodeType =
  | 'text'
  | 'image'
  | 'rect'
  | 'circle'
  | 'group'
  | 'result-card'
  | 'results-cards'
  | 'results-group'
  | 'match-grid'
  | 'bracket-tree'
  | 'victory-path';

export type CardVariantKind = 'champion' | 'podium' | 'standard';

export type CutoffKind = 'top8' | 'top16' | 'all';

export type ResultsGroupMode = 'board' | 'sequence';

export type SequenceOrderKind =
  | 'placement-asc'
  | 'placement-desc'
  | 'champion-last'
  | 'podium-first'
  | 'row-major'
  | 'column-major';

export type StandingBindingKey =
  | 'placement'
  | 'displayName'
  | 'prefix'
  | 'countryCode'
  | 'countryFlagUrl'
  | 'avatarUrl'
  | 'characterId'
  | 'characterName'
  | 'characterImageUrl'
  | 'entrantName'
  | 'eventName'
  | 'gameName';

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

export interface ResultsCardsSchedule {
  order: 'placement-asc' | 'placement-desc' | 'custom';
  customOrdinals?: number[];
  delayBetweenStartsMs: number;
  trigger: 'with-previous' | 'after-previous';
  keepPreviousVisible: boolean;
  loop: boolean;
}

export interface AutoSequenceSettings {
  enabled: boolean;
  stageInstanceId: string;
  range: CutoffKind;
  pageNumber: number;
  pageSize: number;
  order: ResultsCardsSchedule['order'];
  customOrdinals?: number[];
  delayBetweenStartsMs: number;
  endBehavior: 'card-exit' | 'keep-visible' | 'clear-after-hold';
}

export interface FontOption {
  family: string;
  url?: string;
}

export interface CanvasSettings {
  width: number;
  height: number;
  backgroundUrl?: string;
  globalFontUrl?: string;
  globalFontFamily?: string;
  fontLibrary?: FontOption[];
  safeArea?: {
    top: number;
    right: number;
    bottom: number;
    left: number;
  };
}

export type DataSourceKind = 'current-match' | 'tournament-results';

export interface SceneDataSource {
  kind: DataSourceKind;
  resultVersionId?: string | null;
}

export interface BaseNode {
  id: string;
  type: NodeType;
  name?: string;
  parentId?: string | null;
  order?: number;
  visible: boolean;
  locked?: boolean;
  zIndex?: number;
  x: number;
  y: number;
  width: number;
  height: number;
  rotation?: number;
  opacity?: number;
  animation?: AnimationSettings;
  /** Legacy field for live data mirroring. */
  sourceId?: string;
}

export interface TextNode extends BaseNode {
  type: 'text';
  text?: string;
  binding?: StandingBindingKey;
  fontSize?: number;
  fontFamily?: string;
  color?: string;
  fontWeight?: 'normal' | 'bold';
  fontStyle?: 'normal' | 'italic';
  textAlign?: 'left' | 'center' | 'right';
  strokeWidth?: number;
  strokeColor?: string;
  shadowColor?: string;
  shadowBlur?: number;
  shadowOffsetX?: number;
  shadowOffsetY?: number;
}

export interface ImageNode extends BaseNode {
  type: 'image';
  src?: string;
  binding?: StandingBindingKey;
  borderRadius?: number;
  objectFit?: 'cover' | 'contain' | 'fill';
  cropSafeArea?: boolean;
  shadowColor?: string;
  shadowBlur?: number;
  shadowOffsetX?: number;
  shadowOffsetY?: number;
}

export interface RectNode extends BaseNode {
  type: 'rect';
  color?: string;
  borderRadius?: number;
  strokeWidth?: number;
  strokeColor?: string;
  shadowColor?: string;
  shadowBlur?: number;
  shadowOffsetX?: number;
  shadowOffsetY?: number;
}

export interface CircleNode extends BaseNode {
  type: 'circle';
  color?: string;
  strokeWidth?: number;
  strokeColor?: string;
  shadowColor?: string;
  shadowBlur?: number;
  shadowOffsetX?: number;
  shadowOffsetY?: number;
}

export interface CardVariantOverride {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  opacity?: number;
  visible?: boolean;
  fontSize?: number;
  fontWeight?: 'normal' | 'bold';
  textAlign?: 'left' | 'center' | 'right';
  color?: string;
  borderRadius?: number;
  strokeWidth?: number;
  strokeColor?: string;
  animation?: AnimationSettings;
  isAbsolute?: boolean;
  binding?: StandingBindingKey;
  objectFit?: 'cover' | 'contain' | 'fill';
  objectPosition?: string;
  zIndex?: number;
  border?: string;
  backgroundColor?: string;
  src?: string;
  maskImage?: string;
}

export interface GroupNode extends BaseNode {
  type: 'group';
  childIds: string[];
  templateRole?: 'player-card' | null;
  definitionRole?: 'result-card' | null;
  variants?: {
    champion?: Record<string, Partial<CardVariantOverride>>;
    podium?: Record<string, Partial<CardVariantOverride>>;
    standard?: Record<string, Partial<CardVariantOverride>>;
  };
}

export interface ResultCardNode extends BaseNode {
  type: 'result-card';
  definitionId: string;
  instanceRole: 'stage' | 'linked';
  standingOrdinal: number;
  variant?: CardVariantKind;
  outerAnimation?: ResultCardLifecycle;
  animationOverride?: Partial<ResultCardLifecycle>;
}

export interface ResultsCardsNode extends BaseNode {
  type: 'results-cards';
  childIds: string[];
  schedule: ResultsCardsSchedule;
  autoSequence?: AutoSequenceSettings;
  preview?: PreviewSettings;
}

export interface LayoutSlot {
  slotId: string;
  ordinal: number;
  x: number;
  y: number;
  width: number;
  height: number;
  variant: CardVariantKind;
}

export interface VariantRule {
  fromPlacement: number;
  toPlacement?: number;
  variant: CardVariantKind;
}

export interface SequenceSettings {
  order: SequenceOrderKind;
  startDelayMs: number;
  intervalMs: number;
  holdMs: number;
  exit: 'together' | 'sequential' | 'none';
  loop: boolean;
  manualCue: boolean;
}

export interface PreviewSettings {
  dataset: 'normal' | 'long_names' | 'missing_media' | 'rtl' | 'tied_placements';
  count: CutoffKind;
  pageNumber: number;
}

export interface ResultsGroupNode extends BaseNode {
  type: 'results-group';
  cardDefinitionId?: string;
  templateId: string;
  mode: ResultsGroupMode;
  cutoff: CutoffKind;
  pageNumber: number;
  pageSize: number;
  layoutPresetId: string;
  customSlots?: LayoutSlot[];
  variantRules: VariantRule[];
  sequence: SequenceSettings;
  preview?: PreviewSettings;
  largeImageSource?: 'character' | 'player';
  showSmallImage?: boolean;
  smallImageSource?: 'player' | 'character';
}

export type SceneNode =
  | TextNode
  | ImageNode
  | RectNode
  | CircleNode
  | GroupNode
  | ResultCardNode
  | ResultsCardsNode
  | ResultsGroupNode;

export interface SceneDocumentV2 {
  schemaVersion: 2;
  canvas: CanvasSettings;
  dataSource: SceneDataSource;
  rootIds: string[];
  nodes: Record<string, SceneNode>;
}

export interface OutputProfile {
  width: number;
  height: number;
  transparent?: boolean;
  safeArea?: {
    top: number;
    right: number;
    bottom: number;
    left: number;
  };
}

export interface PresentationFieldSnapshot<T = string | null> {
  value: T;
  source: 'entrant_override' | 'player_profile' | 'provider_snapshot' | 'placeholder';
}

export interface CharacterPresentationValue {
  id: string | null;
  name: string | null;
  image_url: string | null;
}

export interface FrozenPresentationSnapshot {
  display_name: PresentationFieldSnapshot<string>;
  prefix: PresentationFieldSnapshot<string | null>;
  country: PresentationFieldSnapshot<string | null>;
  avatar_url: PresentationFieldSnapshot<string | null>;
  character: PresentationFieldSnapshot<CharacterPresentationValue>;
}

export interface StandingEntrySnapshot {
  ordinal: number;
  placement: number;
  entrant_id: string;
  entrant_name: string;
  provider_user_id?: string | null;
  player_profile_id?: string | null;
  is_tied: boolean;
  presentation: FrozenPresentationSnapshot;
}

export interface SequenceCue {
  cueId: string;
  standing: StandingEntrySnapshot;
  slot: LayoutSlot;
  variant: CardVariantKind;
  order: number;
  enterMs: number;
  holdMs: number;
  exitMs: number;
}

export interface RenderCardInstance {
  instanceId: string;
  standing: StandingEntrySnapshot;
  slot: LayoutSlot;
  variant: CardVariantKind;
  cueIndex: number;
  visible: boolean;
  transform: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
}

export interface AutoSequenceRuntimeInstance {
  runtimeId: string;
  standing: StandingEntrySnapshot;
  ordinalIndex: number;
  startTimeMs: number;
  endTimeMs: number;
  phase: 'pending' | 'enter' | 'visible' | 'exit' | 'complete';
  progress: number;
  transform: ResultCardTransform;
  visible: boolean;
}
