import type {
  SceneDocumentV2,
  SceneNode,
  CanvasSettings,
  SceneDataSource,
  ResultsGroupNode,
  GroupNode,
} from './types';

const DEFAULT_SAFE_AREA = { top: 54, right: 96, bottom: 54, left: 96 };

const DEFAULT_CANVAS: CanvasSettings = {
  width: 1920,
  height: 1080,
  safeArea: DEFAULT_SAFE_AREA,
  backgroundUrl: '',
  globalFontUrl: '',
  globalFontFamily: '',
  fontLibrary: [],
};

const DEFAULT_DATA_SOURCE: SceneDataSource = {
  kind: 'current-match',
};

function migrateResultCardAnimation(node: SceneNode) {
  if (node.type !== 'result-card') return;
  const raw = node as SceneNode & Record<string, any>;
  const legacy = raw.outerAnimation;
  if (!raw.animation && legacy?.visible) {
    const start = legacy.start || legacy.visible;
    const visible = legacy.visible;
    const dx = Number(start.x || 0) - Number(visible.x || 0);
    const dy = Number(start.y || 0) - Number(visible.y || 0);
    const direction = Math.abs(dx) > Math.abs(dy)
      ? (dx < 0 ? 'left' : 'right')
      : (dy < 0 ? 'top' : 'bottom');
    raw.animation = {
      animationType: Number(start.opacity ?? 1) < Number(visible.opacity ?? 1) ? 'float-in' : 'fly-in',
      direction,
      duration: Math.max(0, Number(legacy.enterDurationMs) || 500),
      delay: 0,
      loop: 0,
      tweenType: legacy.enterEasing || 'ease-out',
      playOn: Number(legacy.exitDurationMs) > 0 ? 'BOTH' : 'IN',
      trigger: 'on-load',
      revealStyle: 'all',
      idleAnimation: 'none',
      idleIntensity: 1,
    };
  }
  delete raw.outerAnimation;
  delete raw.animationOverride;
}

function removeInvalidParentLinks(nodes: Record<string, SceneNode>) {
  Object.values(nodes).forEach((node) => {
    if (!node.parentId) return;
    const parent = nodes[node.parentId];
    const validChild = Boolean(
      parent
      && (
        ((parent.type === 'group' || parent.type === 'results-cards') && parent.childIds?.includes(node.id))
        || (parent.type === 'result-card' && parent.definitionId === node.id)
        || (parent.type === 'results-group' && (parent.cardDefinitionId === node.id || parent.templateId === node.id))
      )
    );
    if (!validChild) node.parentId = null;
  });
}

/**
 * Normalizes any legacy or v2 scene input into a valid SceneDocumentV2 without mutating the input.
 */
export function normalizeScene(raw: unknown): SceneDocumentV2 {
  if (!raw || typeof raw !== 'object') {
    return {
      schemaVersion: 2,
      canvas: { ...DEFAULT_CANVAS },
      dataSource: { ...DEFAULT_DATA_SOURCE },
      rootIds: [],
      nodes: {},
    };
  }

  const input = raw as Record<string, unknown>;

  // If already Scene Document v2, return a safe cloned copy
  if (input.schemaVersion === 2 && input.nodes && typeof input.nodes === 'object') {
    const cloned = JSON.parse(JSON.stringify(input)) as SceneDocumentV2;
    if (!cloned.canvas) {
      cloned.canvas = { ...DEFAULT_CANVAS };
    }
    if (!cloned.canvas.safeArea) {
      cloned.canvas.safeArea = { ...DEFAULT_SAFE_AREA };
    }
    if (!cloned.dataSource) {
      cloned.dataSource = { ...DEFAULT_DATA_SOURCE };
    }
    if (!Array.isArray(cloned.rootIds)) {
      cloned.rootIds = Object.keys(cloned.nodes);
    }
    // Normalize the first Results Group implementation to the shared Result
    // Card definition without persisting or mutating the loaded input.
    Object.values(cloned.nodes).forEach((node) => {
      migrateResultCardAnimation(node);
      if (node.type !== 'results-group') return;
      const definitionId = node.cardDefinitionId || node.templateId;
      node.cardDefinitionId = definitionId;
      const definition = cloned.nodes[definitionId];
      if (definition?.type === 'group') {
        definition.definitionRole = 'result-card';
        if (/master\s*(player\s*)?card/i.test(definition.name || '')) {
          definition.name = 'Result Card Design';
        }
      }
    });
    removeInvalidParentLinks(cloned.nodes);
    return cloned;
  }

  // Legacy format extraction: could be { elements: Record<string, ...> } or directly Record<string, ...>
  let elementsMap: Record<string, Record<string, unknown>> = {};
  if (input.elements && typeof input.elements === 'object') {
    elementsMap = input.elements as Record<string, Record<string, unknown>>;
  } else if (!input.nodes && !input.schemaVersion) {
    elementsMap = input as Record<string, Record<string, unknown>>;
  }

  const nodes: Record<string, SceneNode> = {};
  const elementEntries = Object.entries(elementsMap);

  for (const [id, el] of elementEntries) {
    if (!el || typeof el !== 'object' || typeof el.type !== 'string') continue;
    
    // Copy element attributes
    nodes[id] = {
      ...JSON.parse(JSON.stringify(el)),
      id: String(el.id || id),
      type: el.type as SceneNode['type'],
      x: Number(el.x ?? 0),
      y: Number(el.y ?? 0),
      width: Number(el.width ?? 0),
      height: Number(el.height ?? 0),
      visible: el.visible !== false,
      zIndex: el.zIndex !== undefined ? Number(el.zIndex) : 0,
      sourceId: el.sourceId ? String(el.sourceId) : undefined,
    } as SceneNode;
  }

  Object.values(nodes).forEach((node) => {
    migrateResultCardAnimation(node);
    if (node.type === 'group' && node.templateRole === 'player-card') {
      node.definitionRole = 'result-card';
      if (/master\s*(player\s*)?card/i.test(node.name || '')) node.name = 'Result Card Design';
    }
  });
  removeInvalidParentLinks(nodes);

  // Sort rootIds by zIndex ascending to maintain original stacking order
  const rootIds = Object.keys(nodes).sort((a, b) => {
    const za = nodes[a].zIndex ?? 0;
    const zb = nodes[b].zIndex ?? 0;
    return za - zb;
  });

  const canvas: CanvasSettings = {
    width: Number(input.width || (input.canvas as Record<string, unknown>)?.width || 1920),
    height: Number(input.height || (input.canvas as Record<string, unknown>)?.height || 1080),
    safeArea: {
      top: 54,
      right: 96,
      bottom: 54,
      left: 96,
      ...((input.canvas as Record<string, unknown>)?.safeArea as Record<string, number> || {}),
    },
    backgroundUrl: String(input.backgroundUrl || (input.canvas as Record<string, unknown>)?.backgroundUrl || ''),
    globalFontUrl: String(input.globalFontUrl || (input.canvas as Record<string, unknown>)?.globalFontUrl || ''),
    globalFontFamily: String(input.globalFontFamily || (input.canvas as Record<string, unknown>)?.globalFontFamily || ''),
    fontLibrary: Array.isArray((input.canvas as Record<string, unknown>)?.fontLibrary)
      ? ((input.canvas as Record<string, unknown>)?.fontLibrary as CanvasSettings['fontLibrary'])
      : [],
  };

  const dataSource: SceneDataSource = {
    kind: (input.dataSource as Record<string, unknown>)?.kind === 'tournament-results'
      ? 'tournament-results'
      : 'current-match',
    resultVersionId: (input.dataSource as Record<string, unknown>)?.resultVersionId as string | undefined,
  };

  return {
    schemaVersion: 2,
    canvas,
    dataSource,
    rootIds,
    nodes,
  };
}

export interface SceneValidationResult {
  isValid: boolean;
  errors: string[];
}

/**
 * Validates a SceneDocumentV2 against structural integrity, acyclicity, and contracts.
 */
export function validateSceneDocument(doc: unknown): SceneValidationResult {
  const errors: string[] = [];

  if (!doc || typeof doc !== 'object') {
    return { isValid: false, errors: ['Scene document must be a non-null object'] };
  }

  const scene = doc as Partial<SceneDocumentV2>;

  if (scene.schemaVersion !== 2) {
    errors.push(`Expected schemaVersion 2, got ${scene.schemaVersion}`);
  }

  if (!scene.canvas || typeof scene.canvas !== 'object') {
    errors.push('Scene document must have a canvas object');
  } else {
    if (!Number.isFinite(scene.canvas.width) || scene.canvas.width <= 0) {
      errors.push(`Invalid canvas width: ${scene.canvas.width}`);
    }
    if (!Number.isFinite(scene.canvas.height) || scene.canvas.height <= 0) {
      errors.push(`Invalid canvas height: ${scene.canvas.height}`);
    }
  }

  if (!scene.dataSource || !['current-match', 'tournament-results'].includes(scene.dataSource.kind)) {
    errors.push(`Invalid dataSource kind: ${scene.dataSource?.kind}`);
  }

  if (!scene.nodes || typeof scene.nodes !== 'object') {
    errors.push('Scene document must contain a nodes map');
    return { isValid: false, errors };
  }

  const allowedTypes = new Set(['text', 'image', 'rect', 'circle', 'group', 'result-card', 'results-cards', 'results-group']);
  const allowedBindings = new Set([
    'placement', 'displayName', 'prefix', 'countryCode', 'countryFlagUrl',
    'avatarUrl', 'characterId', 'characterName', 'characterImageUrl',
    'entrantName', 'eventName', 'gameName',
  ]);
  const nodes = scene.nodes;
  const graph = new Map<string, string[]>();

  for (const [id, node] of Object.entries(nodes)) {
    if (!node || typeof node !== 'object') {
      errors.push(`Node '${id}' must be an object`);
      continue;
    }
    if (node.id !== id) {
      errors.push(`Node key '${id}' does not match node id '${node.id}'`);
    }
    if (!allowedTypes.has(node.type)) {
      errors.push(`Node '${id}' has unsupported type '${node.type}'`);
    }
    if (typeof node.visible !== 'boolean') {
      errors.push(`Node '${id}' must declare boolean visibility`);
    }
    for (const field of ['x', 'y', 'width', 'height'] as const) {
      if (!Number.isFinite(node[field])) {
        errors.push(`Node '${id}' has invalid ${field}`);
      }
    }
    const rawNode = node as unknown as Record<string, unknown>;
    if (rawNode.generated === true || 'generatedFrom' in rawNode || 'generatedStanding' in rawNode || 'instanceId' in rawNode) {
      errors.push(`Node '${id}' is a generated preview instance and cannot be persisted`);
    }
    if ('binding' in node && node.binding && !allowedBindings.has(node.binding)) {
      errors.push(`Node '${id}' has unsupported binding '${node.binding}'`);
    }

    // Results Group validation
    if (node.type === 'results-group') {
      const rg = node as ResultsGroupNode;
      const definitionId = rg.cardDefinitionId || rg.templateId;
      if (!definitionId) {
        errors.push(`Results Group '${id}' is missing cardDefinitionId`);
      } else {
        const templateNode = nodes[definitionId];
        if (!templateNode) {
          errors.push(`Results Group '${id}' references non-existent definition '${definitionId}'`);
        } else if (templateNode.type !== 'group') {
          errors.push(`Definition '${definitionId}' must be a group node`);
        } else if (
          (templateNode as GroupNode).definitionRole !== 'result-card'
          && (templateNode as GroupNode).templateRole !== 'player-card'
        ) {
          errors.push(`Definition '${definitionId}' must have definitionRole 'result-card'`);
        }

        if (Array.isArray(scene.rootIds) && scene.rootIds.includes(definitionId)) {
          errors.push(`Result Card definition '${definitionId}' must not be present in rootIds`);
        }
      }
      if (!['board', 'sequence'].includes(rg.mode)) {
        errors.push(`Results Group '${id}' has invalid mode '${rg.mode}'`);
      }
      if (!['top8', 'top16', 'all'].includes(rg.cutoff)) {
        errors.push(`Results Group '${id}' has invalid cutoff '${rg.cutoff}'`);
      }
      if (!Number.isInteger(rg.pageNumber) || rg.pageNumber < 1 || !Number.isInteger(rg.pageSize) || rg.pageSize < 1) {
        errors.push(`Results Group '${id}' has invalid pagination`);
      }
      const sequenceValues = [rg.sequence?.startDelayMs, rg.sequence?.intervalMs, rg.sequence?.holdMs];
      if (
        sequenceValues.some((value) => !Number.isFinite(value))
        || (rg.sequence?.startDelayMs ?? -1) < 0
        || (rg.sequence?.intervalMs ?? 0) < 1
        || (rg.sequence?.holdMs ?? -1) < 0
      ) {
        errors.push(`Results Group '${id}' has invalid sequence timing`);
      }
    }

    if (node.type === 'result-card') {
      const definitionId = node.definitionId;
      const definition = nodes[definitionId];
      if (!definitionId || !definition || definition.type !== 'group') {
        errors.push(`Result Card '${id}' references an invalid definition '${definitionId}'`);
      } else if (
        (definition as GroupNode).definitionRole !== 'result-card'
        && (definition as GroupNode).templateRole !== 'player-card'
      ) {
        errors.push(`Result Card '${id}' definition '${definitionId}' is not a Result Card definition`);
      }
      if (!['stage', 'linked'].includes(node.instanceRole)) {
        errors.push(`Result Card '${id}' has invalid instanceRole '${node.instanceRole}'`);
      }
      if (!Number.isInteger(node.standingOrdinal) || node.standingOrdinal < 1) {
        errors.push(`Result Card '${id}' has invalid standingOrdinal`);
      }
      if (Array.isArray(scene.rootIds) && scene.rootIds.includes(definitionId)) {
        errors.push(`Result Card definition '${definitionId}' must not be present in rootIds`);
      }
    }

    if (node.type === 'results-cards') {
      const delay = node.schedule?.delayBetweenStartsMs;
      if (!Number.isFinite(delay) || delay < 0) {
        errors.push(`Results Cards '${id}' has invalid delayBetweenStartsMs`);
      }
      for (const childId of node.childIds || []) {
        if (nodes[childId]?.type !== 'result-card') {
          errors.push(`Results Cards '${id}' child '${childId}' must be a Result Card`);
        }
      }
    }

    // Group child validation
    if (node.type === 'group' || node.type === 'results-cards') {
      const group = node as GroupNode;
      graph.set(id, Array.isArray(group.childIds) ? group.childIds : []);
      if (Array.isArray(group.childIds)) {
        for (const childId of group.childIds) {
          if (!nodes[childId]) {
            errors.push(`Group '${id}' references missing child '${childId}'`);
          } else if (childId === id) {
            errors.push(`Group '${id}' cannot contain itself as a child`);
          } else if (nodes[childId].parentId !== id) {
            errors.push(`Child '${childId}' must reference parent '${id}'`);
          }
        }
      } else {
        errors.push(`Group '${id}' must declare childIds`);
      }
    } else {
      graph.set(id, []);
    }
  }

  if (Array.isArray(scene.rootIds)) {
    for (const rootId of scene.rootIds) {
      if (!nodes[rootId]) {
        errors.push(`rootId '${rootId}' does not exist in nodes`);
      }
    }
  } else {
    errors.push('Scene document must contain rootIds');
  }

  const visiting = new Set<string>();
  const visited = new Set<string>();
  const visit = (id: string) => {
    if (visiting.has(id)) {
      errors.push(`Scene graph contains a cycle at '${id}'`);
      return;
    }
    if (visited.has(id)) return;
    visiting.add(id);
    for (const childId of graph.get(id) || []) visit(childId);
    visiting.delete(id);
    visited.add(id);
  };
  for (const id of graph.keys()) visit(id);

  return {
    isValid: errors.length === 0,
    errors,
  };
}
