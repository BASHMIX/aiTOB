import { describe, it, expect, beforeEach } from 'vitest';
import { useEditorStore } from './useEditorStore';

describe('useEditorStore Scene v2 authoring and nested Results Group', () => {
  beforeEach(() => {
    useEditorStore.setState({
      elements: {},
      past: [],
      future: [],
      selectedId: null,
      selectedIds: [],
    });
  });

  it('supports adding a Results Group and Master Card template group', () => {
    const store = useEditorStore.getState();

    // 1. Add Master Card template group
    store.addElement({
      id: 'template-card',
      type: 'group' as any,
      name: 'Master Player Card',
      visible: true,
      x: 0,
      y: 0,
      width: 500,
      height: 700,
      templateRole: 'player-card' as any,
      childIds: ['card-name', 'card-badge'] as any,
    } as any);

    // 2. Add child nodes belonging to template
    store.addElement({
      id: 'card-name',
      parentId: 'template-card',
      type: 'text',
      name: 'Player Name',
      visible: true,
      x: 100,
      y: 50,
      width: 300,
      height: 40,
      text: 'Player 1',
      binding: 'displayName' as any,
    } as any);

    store.addElement({
      id: 'card-badge',
      parentId: 'template-card',
      type: 'rect',
      name: 'Placement Badge',
      visible: true,
      x: 20,
      y: 20,
      width: 60,
      height: 60,
      color: '#e5a50a',
    } as any);

    // 3. Add Results Group referencing the template
    store.addElement({
      id: 'rg-main',
      type: 'results-group' as any,
      name: 'Results Group',
      visible: true,
      x: 100,
      y: 100,
      width: 1720,
      height: 880,
      templateId: 'template-card' as any,
      mode: 'board' as any,
      cutoff: 'top8' as any,
      pageNumber: 1,
      pageSize: 8,
      layoutPresetId: 'champion-focus',
      customSlots: [],
      variantRules: [],
    } as any);

    const elements = useEditorStore.getState().elements;
    expect(elements['template-card']).toBeDefined();
    expect(elements['card-name']?.parentId).toBe('template-card');
    expect(elements['card-badge']?.parentId).toBe('template-card');
    expect(elements['rg-main']?.type).toBe('results-group');

    // Verify mock card instances are never added to authoring elements
    const generatedPlayerInstances = Object.keys(elements).filter(
      (k) => k.startsWith('rg-main-card-') || k.match(/^Player \d+/),
    );
    expect(generatedPlayerInstances.length).toBe(0);
  });

  it('handles undo and redo with nested structures cleanly', () => {
    const store = useEditorStore.getState();

    store.addElement({
      id: 'rg-1',
      type: 'results-group' as any,
      visible: true,
      x: 100,
      y: 100,
      width: 1600,
      height: 900,
    } as any);

    expect(useEditorStore.getState().elements['rg-1']).toBeDefined();

    // Take snapshot then update property
    store.takeSnapshot();
    store.updateElement('rg-1', { x: 200 } as any);
    expect(useEditorStore.getState().elements['rg-1']?.x).toBe(200);

    // Undo update
    store.undo();
    expect(useEditorStore.getState().elements['rg-1']?.x).toBe(100);

    // Redo update
    store.redo();
    expect(useEditorStore.getState().elements['rg-1']?.x).toBe(200);
  });

  it('cascades deletion of template children when parent group is deleted', () => {
    const store = useEditorStore.getState();

    store.addElement({
      id: 'parent-group',
      type: 'group' as any,
      visible: true,
      x: 0,
      y: 0,
      childIds: ['child-1', 'child-2'] as any,
    } as any);

    store.addElement({
      id: 'child-1',
      parentId: 'parent-group',
      type: 'text',
      visible: true,
      x: 10,
      y: 10,
    } as any);

    store.addElement({
      id: 'child-2',
      parentId: 'parent-group',
      type: 'rect',
      visible: true,
      x: 20,
      y: 20,
    } as any);

    // Delete parent group
    store.deleteElement('parent-group');

    const elements = useEditorStore.getState().elements;
    expect(elements['parent-group']).toBeUndefined();
    expect(elements['child-1']).toBeUndefined();
    expect(elements['child-2']).toBeUndefined();
  });

  it('recursively deletes a results group, its master template, and all template children', () => {
    useEditorStore.setState({
      elements: {
        results: { id: 'results', type: 'results-group', templateId: 'master', visible: true, x: 0, y: 0 } as any,
        master: { id: 'master', type: 'group', parentId: 'results', childIds: ['nested'], visible: true, x: 0, y: 0 } as any,
        nested: { id: 'nested', type: 'group', parentId: 'master', childIds: ['leaf'], visible: true, x: 0, y: 0 } as any,
        leaf: { id: 'leaf', type: 'text', parentId: 'nested', visible: true, x: 0, y: 0 } as any,
      },
    });

    useEditorStore.getState().deleteElement('results');

    expect(useEditorStore.getState().elements).toEqual({});
  });
});
