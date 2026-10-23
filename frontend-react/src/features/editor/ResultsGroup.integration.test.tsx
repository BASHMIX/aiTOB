import { describe, it, expect, beforeEach } from 'vitest';
import { useEditorStore } from '@/store/useEditorStore';
import { MOCK_DATASETS } from '@/features/results/mockData';
import { resolveResultsGroup } from '@/scene/resolveResultsGroup';
import type { ResultsGroupNode, GroupNode } from '@/scene/types';

describe('ResultsGroup editor integration and non-serialization regression', () => {
  beforeEach(() => {
    useEditorStore.setState({
      elements: {},
      past: [],
      future: [],
      selectedId: null,
      selectedIds: [],
    });
  });

  it('guarantees preview cards (Top 8, Top 16, All) never pollute store elements, history, or serialized JSON', () => {
    const store = useEditorStore.getState();

    // 1. Setup template and results group
    const tpl: GroupNode = {
      id: 'mc-template',
      type: 'group',
      name: 'Master Card',
      templateRole: 'player-card',
      visible: true,
      x: 0,
      y: 0,
      width: 500,
      height: 700,
      childIds: ['mc-name', 'mc-art'],
    };

    const rg: ResultsGroupNode = {
      id: 'rg-main',
      type: 'results-group',
      name: 'Tournament Results Group',
      templateId: 'mc-template',
      mode: 'board',
      cutoff: 'top8',
      pageNumber: 1,
      pageSize: 8,
      layoutPresetId: 'champion-focus',
      preview: { dataset: 'normal', count: 'top8', pageNumber: 1 },
      variantRules: [],
      sequence: {
        order: 'champion-last',
        startDelayMs: 300,
        intervalMs: 800,
        holdMs: 4000,
        exit: 'sequential',
        loop: false,
        manualCue: false,
      },
      visible: true,
      x: 80,
      y: 150,
      width: 1760,
      height: 850,
    };

    store.addElement(tpl as any);
    store.addElement({
      id: 'mc-name',
      parentId: 'mc-template',
      name: 'Player Name',
      type: 'text',
      visible: true,
      x: 20,
      y: 20,
      text: 'Player',
    } as any);
    store.addElement({
      id: 'mc-art',
      parentId: 'mc-template',
      name: 'Art',
      type: 'image',
      visible: true,
      x: 20,
      y: 100,
    } as any);
    store.addElement(rg as any);

    // 2. Generate preview instances across all preview counts (Top 8, Top 16, All)
    const datasets = ['normal', 'long_names', 'missing_media', 'rtl', 'tied_placements'] as const;
    const cutoffs = ['top8', 'top16', 'all'] as const;

    for (const datasetKey of datasets) {
      for (const cutoff of cutoffs) {
        const testRg: ResultsGroupNode = {
          ...rg,
          cutoff,
          pageSize: cutoff === 'all' ? 32 : cutoff === 'top16' ? 16 : 8,
        };
        const mockStandings = MOCK_DATASETS[datasetKey];
        const instances = resolveResultsGroup(testRg, tpl, mockStandings);

        expect(instances.length).toBeGreaterThan(0);

        // Verify none of the instances leaked into the editor store elements
        const currentElements = useEditorStore.getState().elements;
        for (const inst of instances) {
          expect(currentElements[inst.instanceId]).toBeUndefined();
        }
      }
    }

    // 3. Verify serialized JSON output only contains authored nodes
    const savedElements = useEditorStore.getState().elements;
    const serializedJson = JSON.stringify(savedElements);
    const parsed = JSON.parse(serializedJson);

    expect(Object.keys(parsed).sort()).toEqual([
      'mc-art',
      'mc-name',
      'mc-template',
      'rg-main',
    ]);
  });
});
