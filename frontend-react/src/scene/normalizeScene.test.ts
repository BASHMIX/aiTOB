import { describe, it, expect } from 'vitest';
import { normalizeScene, validateSceneDocument } from './normalizeScene';
import type { SceneDocumentV2 } from './types';

describe('normalizeScene', () => {
  it('migrates obsolete result-card motion to the shared Animation model', () => {
    const scene = normalizeScene({
      schemaVersion: 2,
      canvas: { width: 1920, height: 1080 },
      dataSource: { kind: 'tournament-results' },
      rootIds: ['card'],
      nodes: {
        card: {
          id: 'card', type: 'result-card', definitionId: 'definition', instanceRole: 'stage', standingOrdinal: 1,
          visible: true, x: 400, y: 200, width: 420, height: 560,
          outerAnimation: {
            start: { x: 400, y: 360, scale: 0.2, opacity: 0, rotation: 0 },
            visible: { x: 400, y: 200, scale: 1, opacity: 1, rotation: 0 },
            exit: { x: 900, y: 200, scale: 0.8, opacity: 0, rotation: 0 },
            enterDurationMs: 650, visibleHoldMs: 1000, exitDurationMs: 500,
            enterEasing: 'ease-out', exitEasing: 'ease-in',
          },
        },
        definition: {
          id: 'definition', type: 'group', definitionRole: 'result-card', visible: true,
          x: 0, y: 0, width: 420, height: 560, childIds: [],
        },
      },
    } as any);
    const card = scene.nodes.card as any;
    expect(card.animation).toMatchObject({
      animationType: 'float-in', direction: 'bottom', duration: 650, playOn: 'BOTH',
    });
    expect(card.outerAnimation).toBeUndefined();
    expect(card.animationOverride).toBeUndefined();
  });

  it('removes invalid parent chains between ordinary slide elements', () => {
    const scene = normalizeScene({
      schemaVersion: 2,
      canvas: { width: 1920, height: 1080 },
      dataSource: { kind: 'current-match' },
      rootIds: ['image', 'text'],
      nodes: {
        image: { id: 'image', type: 'image', visible: true, x: 0, y: 0, width: 100, height: 100 },
        text: { id: 'text', type: 'text', parentId: 'image', visible: true, x: 0, y: 0, width: 100, height: 40 },
      },
    } as any);
    expect(scene.nodes.text.parentId).toBeNull();
  });

  it('normalizes legacy flat elements map into Scene v2 document with current-match default', () => {
    const legacyElements = {
      elem1: {
        id: 'elem1',
        type: 'text' as const,
        text: 'Player 1',
        x: 100,
        y: 200,
        width: 300,
        height: 50,
        visible: true,
        zIndex: 2,
        fontFamily: 'Roboto',
        fontSize: 24,
        sourceId: 'p1_name',
        animation: {
          animationType: 'fade-in' as const,
          direction: 'bottom' as const,
          duration: 500,
          delay: 100,
          loop: 0,
          tweenType: 'ease-out' as const,
          playOn: 'IN' as const,
          trigger: 'on-load' as const,
        },
      },
      elem2: {
        id: 'elem2',
        type: 'image' as const,
        src: '/static/player_placeholder.jpg',
        x: 50,
        y: 50,
        width: 100,
        height: 100,
        visible: true,
        zIndex: 1,
      },
    };

    const scene = normalizeScene({ elements: legacyElements });

    expect(scene.schemaVersion).toBe(2);
    expect(scene.dataSource.kind).toBe('current-match');
    expect(scene.canvas.width).toBe(1920);
    expect(scene.canvas.height).toBe(1080);
    expect(scene.canvas.safeArea).toEqual({ top: 54, right: 96, bottom: 54, left: 96 });

    // Stacking order: elem2 (zIndex 1) before elem1 (zIndex 2)
    expect(scene.rootIds).toEqual(['elem2', 'elem1']);

    expect(scene.nodes.elem1).toBeDefined();
    expect(scene.nodes.elem1.id).toBe('elem1');
    expect(scene.nodes.elem1.type).toBe('text');
    expect(scene.nodes.elem1.sourceId).toBe('p1_name');
    expect(scene.nodes.elem1.zIndex).toBe(2);
    expect(scene.nodes.elem1.animation?.animationType).toBe('fade-in');

    expect(scene.nodes.elem2.id).toBe('elem2');
    expect(scene.nodes.elem2.type).toBe('image');
  });

  it('preserves existing Scene v2 document without mutation', () => {
    const v2Doc: SceneDocumentV2 = {
      schemaVersion: 2,
      canvas: {
        width: 1080,
        height: 1080,
        safeArea: { top: 40, right: 40, bottom: 40, left: 40 },
      },
      dataSource: {
        kind: 'tournament-results',
        resultVersionId: 'v-1234',
      },
      rootIds: ['results'],
      nodes: {
        results: {
          id: 'results',
          type: 'results-group',
          name: 'Top 8',
          templateId: 'card-tpl',
          mode: 'board',
          cutoff: 'top8',
          pageNumber: 1,
          pageSize: 16,
          layoutPresetId: 'champion-focus',
          variantRules: [{ fromPlacement: 1, toPlacement: 1, variant: 'champion' }],
          sequence: {
            order: 'placement-desc',
            startDelayMs: 0,
            intervalMs: 300,
            holdMs: 0,
            exit: 'together',
            loop: false,
            manualCue: true,
          },
          visible: true,
          x: 0,
          y: 0,
          width: 1080,
          height: 1080,
        },
        'card-tpl': {
          id: 'card-tpl',
          type: 'group',
          name: 'Master Player Card',
          templateRole: 'player-card',
          childIds: [],
          visible: true,
          x: 0,
          y: 0,
          width: 420,
          height: 560,
        },
      },
    };

    const copy = JSON.parse(JSON.stringify(v2Doc));
    const normalized = normalizeScene(v2Doc);

    expect(normalized.schemaVersion).toBe(2);
    expect(normalized.canvas.width).toBe(1080);
    expect(normalized.dataSource.kind).toBe('tournament-results');
    expect(normalized.dataSource.resultVersionId).toBe('v-1234');
    expect((normalized.nodes.results as any).cardDefinitionId).toBe('card-tpl');
    expect((normalized.nodes.results as any).templateId).toBe('card-tpl');
    expect(normalized.nodes['card-tpl'].name).toBe('Result Card Design');
    // Non-mutating
    expect(v2Doc).toEqual(copy);
  });
});

describe('validateSceneDocument', () => {
  it('validates valid Scene v2 document', () => {
    const v2Doc: SceneDocumentV2 = {
      schemaVersion: 2,
      canvas: { width: 1920, height: 1080 },
      dataSource: { kind: 'tournament-results' },
      rootIds: ['res-group'],
      nodes: {
        'res-group': {
          id: 'res-group',
          type: 'results-group',
          templateId: 'tpl-1',
          mode: 'board',
          cutoff: 'top8',
          pageNumber: 1,
          pageSize: 16,
          layoutPresetId: 'champion-focus',
          variantRules: [],
          sequence: {
            order: 'placement-asc',
            startDelayMs: 0,
            intervalMs: 200,
            holdMs: 0,
            exit: 'together',
            loop: false,
            manualCue: false,
          },
          visible: true,
          x: 0,
          y: 0,
          width: 1920,
          height: 1080,
        },
        'tpl-1': {
          id: 'tpl-1',
          type: 'group',
          parentId: 'res-group',
          templateRole: 'player-card',
          childIds: ['card-name'],
          visible: true,
          x: 0,
          y: 0,
          width: 300,
          height: 400,
        },
        'card-name': {
          id: 'card-name',
          parentId: 'tpl-1',
          type: 'text',
          binding: 'displayName',
          visible: true,
          x: 10,
          y: 10,
          width: 200,
          height: 40,
        },
      },
    };

    const result = validateSceneDocument(v2Doc);
    expect(result.isValid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });

  it('rejects document with unknown node type or missing template', () => {
    const invalidDoc = {
      schemaVersion: 2,
      canvas: { width: 1920, height: 1080 },
      dataSource: { kind: 'tournament-results' },
      rootIds: ['res-group'],
      nodes: {
        'res-group': {
          id: 'res-group',
          type: 'results-group',
          templateId: 'missing-tpl',
          mode: 'board',
          cutoff: 'top8',
          pageNumber: 1,
          pageSize: 16,
          layoutPresetId: 'champion-focus',
          variantRules: [],
          sequence: {
            order: 'placement-asc',
            startDelayMs: 0,
            intervalMs: 200,
            holdMs: 0,
            exit: 'together',
            loop: false,
            manualCue: false,
          },
          visible: true,
          x: 0,
          y: 0,
          width: 1920,
          height: 1080,
        },
      },
    } as unknown as SceneDocumentV2;

    const result = validateSceneDocument(invalidDoc);
    expect(result.isValid).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
  });

  it('rejects generated instances, invalid timing, and cyclic authoring groups', () => {
    const invalid = {
      schemaVersion: 2,
      canvas: { width: 1920, height: 1080 },
      dataSource: { kind: 'tournament-results' },
      rootIds: ['results'],
      nodes: {
        results: {
          id: 'results', type: 'results-group', visible: true,
          x: 0, y: 0, width: 1920, height: 1080,
          templateId: 'template', mode: 'sequence', cutoff: 'top8',
          pageNumber: 1, pageSize: 8, layoutPresetId: 'grid', variantRules: [],
          sequence: { order: 'placement-asc', startDelayMs: 0, intervalMs: -1, holdMs: 0, exit: 'none', loop: false, manualCue: false },
        },
        template: {
          id: 'template', type: 'group', visible: true, parentId: 'results', templateRole: 'player-card',
          x: 0, y: 0, width: 100, height: 100, childIds: ['nested'],
        },
        nested: {
          id: 'nested', type: 'group', visible: true, parentId: 'template', generated: true,
          x: 0, y: 0, width: 100, height: 100, childIds: ['template'],
        },
      },
    } as unknown as SceneDocumentV2;

    const result = validateSceneDocument(invalid);

    expect(result.isValid).toBe(false);
    expect(result.errors.some((error) => error.includes('generated preview instance'))).toBe(true);
    expect(result.errors.some((error) => error.includes('invalid sequence timing'))).toBe(true);
    expect(result.errors.some((error) => error.includes('cycle'))).toBe(true);
  });
});
