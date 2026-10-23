import { describe, it, expect } from 'vitest';
import { resolveResultsGroup } from './resolveResultsGroup';
import { createChampionFocusDocument } from '@/features/results/templates';
import { MOCK_NORMAL_STANDINGS, MOCK_TIED_STANDINGS } from '@/features/results/mockData';
import type { ResultsGroupNode, GroupNode } from './types';

describe('resolveResultsGroup pure resolver', () => {
  const doc = createChampionFocusDocument();
  const rgNode = doc.nodes['rg-main'] as ResultsGroupNode;
  const templateGroup = doc.nodes['master-player-card'] as GroupNode;

  it('resolves Top 8 entries into correct slots with variant mappings', () => {
    const instances = resolveResultsGroup(rgNode, templateGroup, MOCK_NORMAL_STANDINGS);

    expect(instances.length).toBe(8);

    // 1st place champion variant
    expect(instances[0].standing.placement).toBe(1);
    expect(instances[0].variant).toBe('champion');
    expect(instances[0].slot.slotId).toBe('slot-1');
    expect(instances[0].transform.x).toBe(80);

    // 2nd - 4th podium variants
    expect(instances[1].standing.placement).toBe(2);
    expect(instances[1].variant).toBe('podium');
    expect(instances[1].slot.slotId).toBe('slot-2');

    expect(instances[2].standing.placement).toBe(3);
    expect(instances[2].variant).toBe('podium');

    expect(instances[3].standing.placement).toBe(4);
    expect(instances[3].variant).toBe('podium');

    // 5th - 8th standard variants
    expect(instances[4].variant).toBe('standard');
    expect(instances[7].variant).toBe('standard');
  });

  it('includes tie overflow entries within the cutoff', () => {
    // MOCK_TIED_STANDINGS has 9 entrants with placement <= 7 (tie at 7th)
    // When pageSize is increased or overflow allowed, verify they are retained
    const customRg: ResultsGroupNode = {
      ...rgNode,
      pageSize: 16,
    };
    const instances = resolveResultsGroup(customRg, templateGroup, MOCK_TIED_STANDINGS);
    expect(instances.length).toBe(9);
    expect(instances[8].standing.entrant_id).toBe('ent-t9');
    expect(instances[8].standing.placement).toBe(7);
  });

  it('paginates correctly when pageNumber or override is provided', () => {
    const customRg: ResultsGroupNode = {
      ...rgNode,
      pageSize: 4,
    };

    // Page 1: 1-4
    const page1 = resolveResultsGroup(customRg, templateGroup, MOCK_NORMAL_STANDINGS, 1);
    expect(page1.length).toBe(4);
    expect(page1[0].standing.placement).toBe(1);
    expect(page1[3].standing.placement).toBe(4);

    // Page 2: 5-8
    const page2 = resolveResultsGroup(customRg, templateGroup, MOCK_NORMAL_STANDINGS, 2);
    expect(page2.length).toBe(4);
    expect(page2[0].standing.placement).toBe(5);
    expect(page2[3].standing.placement).toBe(7);
  });

  it('produces purely ephemeral instances and does not mutate scene nodes', () => {
    const initialNodeKeys = Object.keys(doc.nodes).sort();
    const instances = resolveResultsGroup(rgNode, templateGroup, MOCK_NORMAL_STANDINGS);
    const postNodeKeys = Object.keys(doc.nodes).sort();

    expect(postNodeKeys).toEqual(initialNodeKeys);
    for (const inst of instances) {
      expect(doc.nodes[inst.instanceId]).toBeUndefined();
    }
  });
});
