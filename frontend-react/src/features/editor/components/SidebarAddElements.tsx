import { useState } from 'react';
import { useEditorStore } from '@/store/useEditorStore';
import { getResultsLayoutPresetSlots } from '@/features/results/templates';
import { createDefaultResultCardDefinition, createFreeformResultCardBundle } from '@/scene/defaultResultCard';
import { SidebarGlobalSettings } from './SidebarGlobalSettings';

export function SidebarAddElements() {
  const store = useEditorStore();
  const [addId, setAddId] = useState('');

  const addGenericElement = (type: 'text' | 'image' | 'rect' | 'circle') => {
    const id = `${type}_${Date.now()}`;
    const base = { id, x: 960, y: 540, visible: true, zIndex: 10 };

    if (type === 'text') {
      store.addElement({ ...base, type: 'text', text: 'New Text', fontSize: 48, color: '#ffffff' });
    } else if (type === 'image') {
      store.addElement({ ...base, type: 'image', width: 300, height: 300, src: '/static/player_placeholder.jpg' });
    } else if (type === 'rect') {
      store.addElement({ ...base, type: 'rect', width: 400, height: 200, color: 'rgba(0,0,0,0.5)', borderRadius: 0 });
    } else if (type === 'circle') {
      store.addElement({ ...base, type: 'circle', width: 200, height: 200, color: 'rgba(0,255,255,0.5)', borderRadius: 100 });
    }
  };

  const addResultCard = () => {
    const bundle = createFreeformResultCardBundle(Date.now());
    store.takeSnapshot();
    store.setElements({
      ...store.elements,
      ...Object.fromEntries(bundle.children.map((child) => [child.id, child])),
      [bundle.definition.id]: bundle.definition,
      [bundle.card.id]: bundle.card,
      [bundle.scheduler.id]: bundle.scheduler,
    });
    store.setSelectedId(bundle.card.id);
  };

  const addResultsGroup = () => {
    const now = Date.now();
    const rgId = `results_group_${now}`;
    const { definition, children } = createDefaultResultCardDefinition(now, rgId);
    const resultsBounds = { x: 80, y: 150, width: 1760, height: 850 };
    const resultsGroup = {
      id: rgId,
      name: 'Tournament Results Group',
      type: 'results-group' as const,
      templateId: definition.id,
      cardDefinitionId: definition.id,
      mode: 'board' as const,
      cutoff: 'top8' as const,
      pageNumber: 1,
      pageSize: 8,
      layoutPresetId: 'champion-focus',
      customSlots: getResultsLayoutPresetSlots('champion-focus', resultsBounds),
      variantRules: [
        { fromPlacement: 1, toPlacement: 1, variant: 'champion' as const },
        { fromPlacement: 2, toPlacement: 4, variant: 'podium' as const },
        { fromPlacement: 5, variant: 'standard' as const },
      ],
      sequence: {
        order: 'champion-last' as const,
        startDelayMs: 0,
        intervalMs: 800,
        holdMs: 4000,
        exit: 'none' as const,
        loop: false,
        manualCue: true,
      },
      preview: { dataset: 'normal' as const, count: 'top8' as const, pageNumber: 1 },
      visible: true,
      ...resultsBounds,
      zIndex: 11,
      animation: {
        animationType: 'fade-in' as const,
        direction: 'bottom' as const,
        duration: 500,
        delay: 0,
        loop: 0,
        tweenType: 'ease-out' as const,
        playOn: 'IN' as const,
        trigger: 'on-load' as const,
      },
    };

    store.takeSnapshot();
    const nextElements = {
      ...store.elements,
      ...Object.fromEntries(children.map((child) => [child.id, child])),
      [definition.id]: definition,
      [resultsGroup.id]: resultsGroup,
    };
    store.setElements(nextElements);
    store.setSelectedId(resultsGroup.id);
  };

  const addMatchTrackerGroup = () => {
    const now = Date.now();
    const groupId = `tracker_group_${now}`;
    const bgId = `tracker_bg_${now}`;
    const p1AvatarId = `tracker_p1_avatar_${now}`;
    const p2AvatarId = `tracker_p2_avatar_${now}`;
    const p1NameId = `tracker_p1_name_${now}`;
    const p2NameId = `tracker_p2_name_${now}`;
    const gridId = `tracker_grid_${now}`;
    const formatBadgeId = `tracker_format_badge_${now}`;
    const roundBadgeId = `tracker_round_badge_${now}`;

    const groupX = 320;
    const groupY = 880;
    const groupWidth = 1280;
    const groupHeight = 150;

    const groupElement = {
      id: groupId,
      name: 'Match Tracker (Lower-3rd)',
      type: 'group' as const,
      x: groupX,
      y: groupY,
      width: groupWidth,
      height: groupHeight,
      visible: true,
      zIndex: 10,
      childIds: [bgId, p1AvatarId, p2AvatarId, p1NameId, p2NameId, gridId, formatBadgeId, roundBadgeId],
      animation: {
        animationType: 'fly-in' as const,
        direction: 'bottom' as const,
        duration: 500,
        delay: 0,
        loop: 0,
        tweenType: 'ease-out' as const,
        playOn: 'IN' as const,
        trigger: 'on-load' as const,
      },
    };

    const bgElement = {
      id: bgId,
      parentId: groupId,
      name: 'Tracker Banner Background',
      type: 'rect' as const,
      x: groupX,
      y: groupY,
      width: groupWidth,
      height: groupHeight,
      color: 'rgba(8, 14, 32, 0.92)',
      borderRadius: 14,
      strokeWidth: 2,
      strokeColor: 'rgba(56, 189, 248, 0.45)',
      shadowColor: 'rgba(0, 0, 0, 0.65)',
      shadowBlur: 24,
      shadowOffsetY: 8,
      visible: true,
      zIndex: 10,
      animation: {
        animationType: 'fly-in' as const,
        direction: 'bottom' as const,
        duration: 500,
        delay: 0,
        loop: 0,
        tweenType: 'back-out' as const,
        playOn: 'IN' as const,
        trigger: 'on-load' as const,
      },
    };

    const p1AvatarElement = {
      id: p1AvatarId,
      parentId: groupId,
      name: 'P1 Avatar',
      type: 'image' as const,
      binding: 'p1_avatar',
      src: '/static/player_placeholder.jpg',
      x: groupX + 22,
      y: groupY + 18,
      width: 48,
      height: 48,
      borderRadius: 8,
      strokeWidth: 2,
      strokeColor: '#00ffcc',
      visible: true,
      zIndex: 11,
      animation: {
        animationType: 'fly-in' as const,
        direction: 'left' as const,
        duration: 400,
        delay: 150,
        loop: 0,
        tweenType: 'ease-out' as const,
        playOn: 'IN' as const,
        trigger: 'with-prev' as const,
      },
    };

    const p2AvatarElement = {
      id: p2AvatarId,
      parentId: groupId,
      name: 'P2 Avatar',
      type: 'image' as const,
      binding: 'p2_avatar',
      src: '/static/player_placeholder.jpg',
      x: groupX + 22,
      y: groupY + 84,
      width: 48,
      height: 48,
      borderRadius: 8,
      strokeWidth: 2,
      strokeColor: '#f59e0b',
      visible: true,
      zIndex: 11,
      animation: {
        animationType: 'fly-in' as const,
        direction: 'left' as const,
        duration: 400,
        delay: 200,
        loop: 0,
        tweenType: 'ease-out' as const,
        playOn: 'IN' as const,
        trigger: 'with-prev' as const,
      },
    };

    const p1NameElement = {
      id: p1NameId,
      parentId: groupId,
      name: 'P1 Name',
      type: 'text' as const,
      binding: 'p1_name',
      text: 'TOKIDO',
      x: groupX + 80,
      y: groupY + 28,
      width: 180,
      height: 34,
      fontSize: 24,
      fontWeight: 'bold' as const,
      color: '#ffffff',
      shadowColor: 'rgba(0, 0, 0, 0.8)',
      shadowBlur: 6,
      visible: true,
      zIndex: 12,
      animation: {
        animationType: 'fade-in' as const,
        direction: 'left' as const,
        duration: 400,
        delay: 180,
        loop: 0,
        tweenType: 'ease-out' as const,
        playOn: 'IN' as const,
        trigger: 'with-prev' as const,
      },
    };

    const p2NameElement = {
      id: p2NameId,
      parentId: groupId,
      name: 'P2 Name',
      type: 'text' as const,
      binding: 'p2_name',
      text: 'MENARD',
      x: groupX + 80,
      y: groupY + 92,
      width: 180,
      height: 34,
      fontSize: 24,
      fontWeight: 'bold' as const,
      color: '#ffffff',
      shadowColor: 'rgba(0, 0, 0, 0.8)',
      shadowBlur: 6,
      visible: true,
      zIndex: 12,
      animation: {
        animationType: 'fade-in' as const,
        direction: 'left' as const,
        duration: 400,
        delay: 220,
        loop: 0,
        tweenType: 'ease-out' as const,
        playOn: 'IN' as const,
        trigger: 'with-prev' as const,
      },
    };

    const gridElement = {
      id: gridId,
      parentId: groupId,
      name: 'Match Games Matrix',
      type: 'match-grid' as const,
      formatMode: 'auto' as const,
      winMarkerStyle: 'check' as const,
      wonColor: '#f59e0b',
      wonBgColor: 'rgba(245, 158, 11, 0.18)',
      boxBorderColor: 'rgba(56, 189, 248, 0.35)',
      boxBgColor: 'rgba(12, 20, 44, 0.85)',
      currentHighlightColor: '#00ffcc',
      gamesHistoryOverride: ['p1', 'p2', 'p2', 'p2', 'p1', 'p2', null, null, null] as ('p1' | 'p2' | null)[],
      x: groupX + 275,
      y: groupY + 28,
      width: 740,
      height: 90,
      visible: true,
      zIndex: 12,
      animation: {
        animationType: 'float-in' as const,
        direction: 'bottom' as const,
        duration: 450,
        delay: 260,
        loop: 0,
        tweenType: 'ease-out' as const,
        playOn: 'IN' as const,
        trigger: 'with-prev' as const,
      },
    };

    const formatBadgeElement = {
      id: formatBadgeId,
      parentId: groupId,
      name: 'Format Target Badge',
      type: 'text' as const,
      binding: 'match_format_badge',
      text: 'FIRST TO 5 GAMES',
      x: groupX + 1030,
      y: groupY + 36,
      width: 220,
      height: 38,
      fontSize: 22,
      fontWeight: 'bold' as const,
      color: '#f59e0b',
      textAlign: 'center' as const,
      shadowColor: 'rgba(245, 158, 11, 0.45)',
      shadowBlur: 10,
      visible: true,
      zIndex: 12,
      animation: {
        animationType: 'fly-in' as const,
        direction: 'right' as const,
        duration: 400,
        delay: 250,
        loop: 0,
        tweenType: 'ease-out' as const,
        playOn: 'IN' as const,
        trigger: 'with-prev' as const,
      },
    };

    const roundBadgeElement = {
      id: roundBadgeId,
      parentId: groupId,
      name: 'Round Badge',
      type: 'text' as const,
      binding: 'tournament_round',
      text: 'WINNERS FINALS',
      x: groupX + 1030,
      y: groupY + 84,
      width: 220,
      height: 26,
      fontSize: 15,
      fontWeight: 'bold' as const,
      color: '#94a3b8',
      textAlign: 'center' as const,
      visible: true,
      zIndex: 12,
      animation: {
        animationType: 'fade-in' as const,
        direction: 'right' as const,
        duration: 400,
        delay: 300,
        loop: 0,
        tweenType: 'ease-out' as const,
        playOn: 'IN' as const,
        trigger: 'with-prev' as const,
      },
    };

    store.takeSnapshot();
    store.setElements({
      ...store.elements,
      [groupId]: groupElement,
      [bgId]: bgElement,
      [p1AvatarId]: p1AvatarElement,
      [p2AvatarId]: p2AvatarElement,
      [p1NameId]: p1NameElement,
      [p2NameId]: p2NameElement,
      [gridId]: gridElement,
      [formatBadgeId]: formatBadgeElement,
      [roundBadgeId]: roundBadgeElement,
    });
    store.setSelectedId(groupId);
  };

  const addBracketTree = () => {
    const now = Date.now();
    const bracketId = `bracket_tree_${now}`;
    const bracketElement = {
      id: bracketId,
      name: 'Tournament Bracket (Top 8 / Top 4)',
      type: 'bracket-tree' as const,
      x: 60,
      y: 60,
      width: 1800,
      height: 960,
      visible: true,
      zIndex: 10,
      bracketLayoutVariant: 'top8-double-elim' as const,
      bracketGameName: '',
      bracketTournamentName: '',
      bracketRoundBestOf: 'BO5',
      bracketShowBackground: true,
      bracketShowSponsors: true,
      bracketShowAvatars: true,
      bracketAvatarSize: 24,
      bracketConnectorColor: 'rgba(255, 255, 255, 0.18)',
      bracketConnectorActiveColor: '#ffffff',
      bracketConnectorWidth: 2.5,
      bracketCardBgColor: 'rgba(15, 23, 42, 0.94)',
      bracketCardBorderColor: 'rgba(51, 65, 85, 0.8)',
      bracketWinnerColor: '#f59e0b',
      bracketTestMode: false,
      bracketSimulateReset: false,
      bracketBadgeStyle: 'pill' as const,
      animation: {
        animationType: 'fade-in' as const,
        direction: 'in-place' as const,
        duration: 500,
        delay: 0,
        loop: 0,
        tweenType: 'ease-out' as const,
        playOn: 'IN' as const,
        trigger: 'on-load' as const,
      },
    };

    store.takeSnapshot();
    store.setElements({
      ...store.elements,
      [bracketId]: bracketElement,
    });
    store.setSelectedId(bracketId);
  };

  const addVictoryPath = () => {
    const now = Date.now();
    const vpId = `victory_path_${now}`;
    const vpElement = {
      id: vpId,
      name: 'Victory Path (Player Run)',
      type: 'victory-path' as const,
      x: 1420,
      y: 120,
      width: 440,
      height: 780,
      visible: true,
      zIndex: 10,
      vpTargetPlayer: 'p1' as const,
      vpTestMode: false,
      vpFooterText: 'VICTORY PATH',
      animation: {
        animationType: 'fly-in' as const,
        direction: 'right' as const,
        duration: 500,
        delay: 0,
        loop: 0,
        tweenType: 'ease-out' as const,
        playOn: 'IN' as const,
        trigger: 'on-load' as const,
      },
    };

    store.takeSnapshot();
    store.setElements({
      ...store.elements,
      [vpId]: vpElement,
    });
    store.setSelectedId(vpId);
  };

  return (
    <>
      <h2 className="text-[#00ffcc] uppercase tracking-wide mb-3 font-bold mt-10">Add Elements</h2>
      <div className="grid grid-cols-2 gap-2 mb-3">
        <button onClick={() => addGenericElement('text')} className="bg-[#3a3a3a] hover:bg-[#444] border border-[#555] rounded py-2 text-center text-xs font-bold">📄 Add Text</button>
        <button onClick={() => addGenericElement('image')} className="bg-[#3a3a3a] hover:bg-[#444] border border-[#555] rounded py-2 text-center text-xs font-bold">🖼️ Add Image</button>
        <button onClick={() => addGenericElement('rect')} className="bg-[#3a3a3a] hover:bg-[#444] border border-[#555] rounded py-2 text-center text-xs font-bold">⬛ Add Rect</button>
        <button onClick={() => addGenericElement('circle')} className="bg-[#3a3a3a] hover:bg-[#444] border border-[#555] rounded py-2 text-center text-xs font-bold">⚪ Add Circle</button>
        <button onClick={addResultCard} className="bg-[#17352f] hover:bg-[#1d463d] border border-[#2d6a5d] rounded py-2 px-1 text-center text-xs font-bold text-[#00ffcc]" title="Design and animate a freely positioned player card">🪪 Add Result Card</button>
        <button onClick={addResultsGroup} className="bg-[#1b2b3a] hover:bg-[#23384c] border border-[#2e5270] rounded py-2 px-1 text-center text-xs font-bold text-[#00ffcc]" title="Use Result Cards in a reusable results image or group animation template">🏆 Add Results Group</button>
        <button
          onClick={addMatchTrackerGroup}
          className="col-span-2 bg-gradient-to-r from-[#0d1e3d] via-[#162a56] to-[#0d1e3d] hover:from-[#132c57] hover:to-[#132c57] border border-[#38bdf8]/50 rounded py-2.5 px-2 text-center text-xs font-bold text-sky-300 shadow-[0_0_12px_rgba(56,189,248,0.2)] flex items-center justify-center gap-2 transition-all cursor-pointer"
          title="Add esports-style game-by-game match tracker lower-3rd"
        >
          <span>🎮</span> Add Match Tracker (Lower-3rd)
        </button>
        <button
          onClick={addBracketTree}
          className="col-span-2 bg-gradient-to-r from-[#2a1b06] via-[#452b0a] to-[#2a1b06] hover:from-[#3d2708] hover:to-[#3d2708] border border-amber-500/60 rounded py-2.5 px-2 text-center text-xs font-bold text-amber-300 shadow-[0_0_12px_rgba(245,158,11,0.25)] flex items-center justify-center gap-2 transition-all cursor-pointer"
          title="Add Tournament Bracket Tree (Top 8 / Top 4 Showcase)"
        >
          <span>👑</span> Add Bracket Tree (Top 8 / Top 4)
        </button>
        <button
          onClick={addVictoryPath}
          className="col-span-2 bg-gradient-to-r from-[#071c54] via-[#0d2f8a] to-[#071c54] hover:from-[#0a2670] hover:to-[#0a2670] border border-blue-400/60 rounded py-2.5 px-2 text-center text-xs font-bold text-sky-200 shadow-[0_0_12px_rgba(59,130,246,0.3)] flex items-center justify-center gap-2 transition-all cursor-pointer"
          title="Add Player Victory Path (Tournament Run)"
        >
          <span>🏆</span> Add Victory Path (Player Run)
        </button>
      </div>
      <hr className="border-[#3a3a3a] my-3" />

      <SidebarGlobalSettings />
      <hr className="border-[#3a3a3a] my-3" />

      <h2 className="text-[#00ffcc] uppercase tracking-wide mb-3 font-bold">Live Data Hooks</h2>
      <div className="flex gap-2 mb-3">
        <select className="flex-1 bg-[#3a3a3a] border border-[#555] rounded px-2 py-1.5 focus:border-[#00ffcc] outline-none text-xs" value={addId} onChange={e => setAddId(e.target.value)}>
          <option value="">-- Select Data Field --</option>
          <optgroup label="Current Match">
            {['p1_name', 'p2_name', 'p1_score', 'p2_score', 'p1_prefix', 'p2_prefix', 'p1_country', 'p2_country', 'p1_cfn', 'p2_cfn', 'p1_character', 'p2_character', 'game_name', 'tournament_round', 'tournament_name', 'p1_avatar', 'p2_avatar', 'p1_character_image', 'p2_character_image', 'p1_flag', 'p2_flag']
              .filter(id => !store.elements[id] || !store.elements[id].visible)
              .map((id) => (
                <option key={id} value={id}>{id}</option>
            ))}
          </optgroup>
          <optgroup label="Next Match (Stream Queue)">
            {['next_p1_name', 'next_p2_name', 'next_p1_score', 'next_p2_score', 'next_p1_prefix', 'next_p2_prefix', 'next_p1_country', 'next_p2_country', 'next_p1_character', 'next_p2_character', 'next_round_name', 'next_match_number', 'next_match_status', 'next_p1_avatar', 'next_p2_avatar', 'next_p1_flag', 'next_p2_flag']
              .filter(id => !store.elements[id] || !store.elements[id].visible)
              .map((id) => (
                <option key={id} value={id}>{id}</option>
            ))}
          </optgroup>
        </select>
        <button
          className="bg-[#00ffcc] text-[#111] font-bold px-3 rounded hover:bg-[#00d4aa]"
          onClick={() => { if (addId) store.restoreElement(addId); }}
        >+ Add</button>
      </div>
      <hr className="border-[#3a3a3a] my-3" />
    </>
  );
}
