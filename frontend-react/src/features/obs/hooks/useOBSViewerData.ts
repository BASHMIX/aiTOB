import { useEffect, useState, useRef } from 'react';
import { resolveCascadeDelays } from '../utils';
import { countryFlagUrl } from '@/utils/country';
import { prepareOverlayAssets } from '@/utils/overlayAssets';

export function useOBSViewerData(slot: string) {
  const [state, setState] = useState<any>({ elements: {} });
  const [transitionState, setTransitionState] = useState<'none' | 'in' | 'out' | 'run' | 'idle'>('idle');
  const [cascadeDelays, setCascadeDelays] = useState<Record<string, number>>({});
  const [glitchedElementIds, setGlitchedElementIds] = useState<Record<string, boolean>>({});
  const prevValuesRef = useRef<Record<string, string>>({});
  const currentStateRef = useRef<any>({ elements: {} });
  const assetRequestRef = useRef(0);

  currentStateRef.current = state;
  const activeMatchRef = useRef<any>(null);
  const nextMatchRef = useRef<any>(null);
  const nextMatchTbdRef = useRef<boolean>(true);
  const tournamentNameRef = useRef<string>('Tournament');

  const fetchData = async () => {
    const assetRequest = ++assetRequestRef.current;
    try {
      const overlayToken = new URLSearchParams(window.location.hash.replace(/^#/, '')).get('access_token') || '';
      const response = await fetch(`/obs/${encodeURIComponent(slot)}/data`, {
        headers: { 'X-Overlay-Token': overlayToken },
      });
      if (!response.ok) throw new Error('Overlay access is unavailable');
      const projection = await response.json();
      const parsed = typeof projection.config === 'string' ? JSON.parse(projection.config) : (projection.config || {});
      let baseConfig: any = {
        elements: parsed.elements || {}, background_url: parsed.background_url || '',
        global_font_url: parsed.global_font_url || '', global_font_family: parsed.global_font_family || '',
        font_library: Array.isArray(parsed.font_library) ? parsed.font_library : [],
      };
      // Compare the actual layout/animation definition, not only element count.
      // Two presets commonly contain the same IDs, so count-based detection
      // incorrectly treated a preset switch as telemetry and never restarted
      // entrance or continuous-loop animations.
      baseConfig.overlay_signature = JSON.stringify({
        background_url: baseConfig.background_url,
        global_font_url: baseConfig.global_font_url,
        global_font_family: baseConfig.global_font_family,
        elements: baseConfig.elements,
      });
      const activeMatch = projection.active_match;
      const nextMatch = projection.next_match;
      const nextMatchTbd = Boolean(projection.next_match_tbd);

      activeMatchRef.current = activeMatch;
      nextMatchRef.current = nextMatch;
      nextMatchTbdRef.current = nextMatchTbd;
      tournamentNameRef.current = projection.tournament_name || 'Tournament';

      // Check whether this slide is a dedicated Next Match slide or contains standard match elements
      const elementKeys = Object.keys(baseConfig.elements || {});
      const hasCurrentMatchElements = elementKeys.some((k) =>
        ['p1_name', 'p2_name', 'p1_score', 'p2_score', 'p1_prefix', 'p2_prefix', 'p1_character', 'p2_character'].includes(k) ||
        ['p1_name', 'p2_name', 'p1_score', 'p2_score', 'p1_prefix', 'p2_prefix', 'p1_character', 'p2_character'].includes(baseConfig.elements[k]?.sourceId)
      );
      const hasNextMatchElements = elementKeys.some((k) =>
        k.startsWith('next_') || baseConfig.elements[k]?.sourceId?.startsWith('next_')
      );
      const isDedicatedNextMatchSlide = hasNextMatchElements && !hasCurrentMatchElements;

      if (isDedicatedNextMatchSlide) {
        // Dedicated next match slide: if no next match or it's TBD, render transparent screen
        if (!nextMatch || nextMatchTbd) {
          if (assetRequest !== assetRequestRef.current) return;
          setState({ elements: {}, background_url: '', global_font_url: '', global_font_family: '', font_library: [], overlay_signature: '' });
          return;
        }
      } else {
        // Normal or mixed scoreboard: if no active match connected, clear overlay (render transparent screen)
        if (!activeMatch) {
          if (assetRequest !== assetRequestRef.current) return;
          setState({ elements: {}, background_url: '', global_font_url: '', global_font_family: '', font_library: [], overlay_signature: '' });
          return;
        }
      }

      // Merge match telemetry data into elements
      if (baseConfig.elements) {
        if (activeMatch) {
          const isSwapped = activeMatch.swapped === true || activeMatch.swapped === 1 || activeMatch.swapped === '1';

          // Swap players' data temporarily if swap toggle is active
          const p1Name = isSwapped ? activeMatch.p2_name : activeMatch.p1_name;
          const p2Name = isSwapped ? activeMatch.p1_name : activeMatch.p2_name;
          const p1Score = isSwapped ? activeMatch.p2_score : activeMatch.p1_score;
          const p2Score = isSwapped ? activeMatch.p1_score : activeMatch.p2_score;
          const p1Prefix = isSwapped
            ? (activeMatch.p2_prefix ?? activeMatch.p2_team)
            : (activeMatch.p1_prefix ?? activeMatch.p1_team);
          const p2Prefix = isSwapped
            ? (activeMatch.p1_prefix ?? activeMatch.p1_team)
            : (activeMatch.p2_prefix ?? activeMatch.p2_team);
          const p1Character = isSwapped ? activeMatch.p2_character : activeMatch.p1_character;
          const p2Character = isSwapped ? activeMatch.p1_character : activeMatch.p2_character;
          const p1CharacterImage = isSwapped ? activeMatch.p2_character_image : activeMatch.p1_character_image;
          const p2CharacterImage = isSwapped ? activeMatch.p1_character_image : activeMatch.p2_character_image;
          const p1Avatar = isSwapped ? activeMatch.p2_avatar : activeMatch.p1_avatar;
          const p2Avatar = isSwapped ? activeMatch.p1_avatar : activeMatch.p2_avatar;
          const p1Country = isSwapped ? activeMatch.p2_country : activeMatch.p1_country;
          const p2Country = isSwapped ? activeMatch.p1_country : activeMatch.p2_country;
          const p1Cfn = isSwapped ? activeMatch.p2_cfn : activeMatch.p1_cfn;
          const p2Cfn = isSwapped ? activeMatch.p1_cfn : activeMatch.p2_cfn;

          const updates: Record<string, any> = {
            p1_name: { text: p1Name || '' },
            p2_name: { text: p2Name || '' },
            p1_score: { text: String(p1Score ?? '0') },
            p2_score: { text: String(p2Score ?? '0') },
            p1_prefix: { text: p1Prefix || '' },
            p2_prefix: { text: p2Prefix || '' },
            // Compatibility for layouts saved with the former field IDs.
            p1_team: { text: p1Prefix || '' },
            p2_team: { text: p2Prefix || '' },
            p1_country: { text: p1Country || '' },
            p2_country: { text: p2Country || '' },
            p1_cfn: { text: p1Cfn || '' },
            p2_cfn: { text: p2Cfn || '' },
            p1_character: { text: p1Character || '' },
            p2_character: { text: p2Character || '' },
            game_name: { text: activeMatch.game_name || '' },
            tournament_round: { text: activeMatch.round_name || '' },
            tournament_name: { text: tournamentNameRef.current },
            p1_avatar: { src: p1Avatar || '/static/player_placeholder.jpg' },
            p2_avatar: { src: p2Avatar || '/static/player_placeholder.jpg' },
            p1_character_image: { src: p1CharacterImage || '/static/player_placeholder.jpg' },
            p2_character_image: { src: p2CharacterImage || '/static/player_placeholder.jpg' },
            p1_flag: {
              src: countryFlagUrl(p1Country) || '/static/flag_placeholder.png'
            },
            p2_flag: {
              src: countryFlagUrl(p2Country) || '/static/flag_placeholder.png'
            }
          };

          for (const [id, update] of Object.entries(updates)) {
            if (baseConfig.elements[id]) {
              baseConfig.elements[id] = { ...baseConfig.elements[id], ...update };
            }
            Object.keys(baseConfig.elements).forEach((elId) => {
              if (baseConfig.elements[elId].sourceId === id) {
                baseConfig.elements[elId] = { ...baseConfig.elements[elId], ...update };
              }
            });
          }
        }

        // Apply Next Match stream queue hooks or conditionally hide if TBD
        if (nextMatch && !nextMatchTbd) {
          const nextUpdates: Record<string, any> = {
            next_p1_name: { text: nextMatch.p1_name || '', visible: true },
            next_p2_name: { text: nextMatch.p2_name || '', visible: true },
            next_p1_score: { text: String(nextMatch.p1_score ?? '0'), visible: true },
            next_p2_score: { text: String(nextMatch.p2_score ?? '0'), visible: true },
            next_p1_prefix: { text: nextMatch.p1_prefix || nextMatch.p1_team || '', visible: true },
            next_p2_prefix: { text: nextMatch.p2_prefix || nextMatch.p2_team || '', visible: true },
            next_p1_country: { text: nextMatch.p1_country || '', visible: true },
            next_p2_country: { text: nextMatch.p2_country || '', visible: true },
            next_p1_character: { text: nextMatch.p1_character || '', visible: true },
            next_p2_character: { text: nextMatch.p2_character || '', visible: true },
            next_round_name: { text: nextMatch.round_name || '', visible: true },
            next_match_number: { text: nextMatch.match_number ? `Match #${nextMatch.match_number}` : '', visible: true },
            next_match_status: { text: nextMatch.match_status || nextMatch.status || 'Up Next', visible: true },
            next_p1_avatar: { src: nextMatch.p1_avatar || '/static/player_placeholder.jpg', visible: true },
            next_p2_avatar: { src: nextMatch.p2_avatar || '/static/player_placeholder.jpg', visible: true },
            next_p1_flag: { src: countryFlagUrl(nextMatch.p1_country) || '/static/flag_placeholder.png', visible: true },
            next_p2_flag: { src: countryFlagUrl(nextMatch.p2_country) || '/static/flag_placeholder.png', visible: true }
          };

          for (const [id, update] of Object.entries(nextUpdates)) {
            if (baseConfig.elements[id]) {
              baseConfig.elements[id] = { ...baseConfig.elements[id], ...update };
            }
            Object.keys(baseConfig.elements).forEach((elId) => {
              if (baseConfig.elements[elId].sourceId === id) {
                baseConfig.elements[elId] = { ...baseConfig.elements[elId], ...update };
              }
            });
          }
        } else {
          // Next match is TBD or queue empty: hide next_* elements
          for (const id of Object.keys(baseConfig.elements)) {
            const el = baseConfig.elements[id];
            if (id.startsWith('next_') || el.sourceId?.startsWith('next_')) {
              baseConfig.elements[id] = {
                ...el,
                text: '',
                src: '',
                visible: false
              };
            }
          }
        }
      }

      // Do not mount the new slide or begin its entrance animation until every
      // visible image is decoded. Missing, broken, or timed-out sources are
      // replaced with a local placeholder first.
      baseConfig = await prepareOverlayAssets(baseConfig);
      if (assetRequest !== assetRequestRef.current) return;

      // 1. Solve cascading triggers delays based on layers order
      const delays = resolveCascadeDelays(baseConfig.elements || {});
      setCascadeDelays(delays);

      // 2. Track score changes and trigger temporary glitch updates
      const prev = prevValuesRef.current;
      const nextPrev = { ...prev };

      for (const [id, el] of Object.entries(baseConfig.elements || {})) {
        const currentText = (el as any).text || '';
        if (prev[id] !== undefined && prev[id] !== currentText) {
          const hasGlitch = (el as any).animation?.scoreGlitch;
          if (hasGlitch) {
            setGlitchedElementIds((curr) => ({ ...curr, [id]: true }));
            setTimeout(() => {
              setGlitchedElementIds((curr) => {
                const copy = { ...curr };
                delete copy[id];
                return copy;
              });
            }, 300);
          }
        }
        nextPrev[id] = currentText;
      }
      prevValuesRef.current = nextPrev;

      // 3. Exit transition delay logic for preset swaps
      const currentState = currentStateRef.current;
      const isInitialLoad = Object.keys(currentState.elements || {}).length === 0;
      const isPresetChange = !isInitialLoad &&
                             currentState.overlay_signature !== baseConfig.overlay_signature;

      console.log("[OBSViewer] fetchData run:", {
        isPresetChange,
        isInitialLoad,
        currentBg: currentState.background_url,
        baseBg: baseConfig.background_url,
        currentElementsCount: Object.keys(currentState.elements || {}).length,
        baseElementsCount: Object.keys(baseConfig.elements || {}).length,
        transitionState
      });

      if (isPresetChange) {
        setTransitionState('out');

        let maxExitTime = 300;
        for (const el of Object.values(currentState.elements || {})) {
          const anim = (el as any).animation;
          if (anim && (anim.playOn === 'OUT' || anim.playOn === 'BOTH')) {
            maxExitTime = Math.max(maxExitTime, (anim.duration || 500) + (anim.delay || 0));
          }
        }

        setTimeout(() => {
          setState(baseConfig);
          setTransitionState('in');

          let maxEntranceTime = 500;
          for (const [id, el] of Object.entries(baseConfig.elements || {})) {
            const anim = (el as any).animation;
            if (anim && (anim.playOn === 'IN' || anim.playOn === 'BOTH')) {
              maxEntranceTime = Math.max(maxEntranceTime, (anim.duration || 500) + (delays[id] || 0));
            }
          }

          setTimeout(() => {
            setTransitionState('run');
            setTimeout(() => {
              setTransitionState('idle');
            }, maxEntranceTime + 100);
          }, 30);
        }, maxExitTime);
      } else if (isInitialLoad) {
        setState(baseConfig);
        setTransitionState('in');

        let maxEntranceTime = 500;
        for (const [id, el] of Object.entries(baseConfig.elements || {})) {
          const anim = (el as any).animation;
          if (anim && (anim.playOn === 'IN' || anim.playOn === 'BOTH')) {
            maxEntranceTime = Math.max(maxEntranceTime, (anim.duration || 500) + (delays[id] || 0));
          }
        }

        setTimeout(() => {
          setTransitionState('run');
          setTimeout(() => {
            setTransitionState('idle');
          }, maxEntranceTime + 100);
        }, 30);
      } else {
        // Simple telemetry updates during match (scores, names). Keep all elements stable!
        setState(baseConfig);
      }
    } catch (e) {
      console.error("Failed to fetch overlay data", e);
    }
  };

  useEffect(() => {
    fetchData(); // Initial load; later changes arrive through the overlay WebSocket.

    let ws: WebSocket;
    const connect = () => {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${proto}//${window.location.host}/ws/overlay/${encodeURIComponent(slot)}`;
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        const token = new URLSearchParams(window.location.hash.replace(/^#/, '')).get('access_token') || '';
        ws.send(JSON.stringify({ type: 'authenticate', token }));
      };

      ws.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if (data.type === 'match_update') {
          // Match score/swap/status updated -> Refresh overlay
          fetchData();
        } else if (data.type === 'overlay_loaded') {
          // Station active overlay changed -> Re-fetch base layout
          fetchData();
        } else if (data.elements) {
          // Editor pushed a direct layout adjustment
          const assetRequest = ++assetRequestRef.current;
          const prev = currentStateRef.current;
          const next = {
            ...prev,
            background_url: data.background_url ?? prev.background_url,
            global_font_url: data.global_font_url ?? prev.global_font_url,
            global_font_family: data.global_font_family ?? prev.global_font_family,
            font_library: data.font_library ?? prev.font_library
          };
          next.elements = { ...prev.elements };
          for (const key in data.elements) {
            next.elements[key] = { ...next.elements[key], ...data.elements[key] };
          }

          // Re-apply current active match telemetry data so player details and scores don't disappear
          const activeMatch = activeMatchRef.current;
          if (activeMatch && next.elements) {
            const isSwapped = activeMatch.swapped === true || activeMatch.swapped === 1 || activeMatch.swapped === '1';
            const p1Name = isSwapped ? activeMatch.p2_name : activeMatch.p1_name;
            const p2Name = isSwapped ? activeMatch.p1_name : activeMatch.p2_name;
            const p1Score = isSwapped ? activeMatch.p2_score : activeMatch.p1_score;
            const p2Score = isSwapped ? activeMatch.p1_score : activeMatch.p2_score;
            const p1Prefix = isSwapped
              ? (activeMatch.p2_prefix ?? activeMatch.p2_team)
              : (activeMatch.p1_prefix ?? activeMatch.p1_team);
            const p2Prefix = isSwapped
              ? (activeMatch.p1_prefix ?? activeMatch.p1_team)
              : (activeMatch.p2_prefix ?? activeMatch.p2_team);
            const p1Character = isSwapped ? activeMatch.p2_character : activeMatch.p1_character;
            const p2Character = isSwapped ? activeMatch.p1_character : activeMatch.p2_character;
            const p1CharacterImage = isSwapped ? activeMatch.p2_character_image : activeMatch.p1_character_image;
            const p2CharacterImage = isSwapped ? activeMatch.p1_character_image : activeMatch.p2_character_image;
            const p1Avatar = isSwapped ? activeMatch.p2_avatar : activeMatch.p1_avatar;
            const p2Avatar = isSwapped ? activeMatch.p1_avatar : activeMatch.p2_avatar;
            const p1Country = isSwapped ? activeMatch.p2_country : activeMatch.p1_country;
            const p2Country = isSwapped ? activeMatch.p1_country : activeMatch.p2_country;
            const p1Cfn = isSwapped ? activeMatch.p2_cfn : activeMatch.p1_cfn;
            const p2Cfn = isSwapped ? activeMatch.p1_cfn : activeMatch.p2_cfn;

            const updates: Record<string, any> = {
              p1_name: { text: p1Name || '' },
              p2_name: { text: p2Name || '' },
              p1_score: { text: String(p1Score ?? '0') },
              p2_score: { text: String(p2Score ?? '0') },
              p1_prefix: { text: p1Prefix || '' },
              p2_prefix: { text: p2Prefix || '' },
              p1_team: { text: p1Prefix || '' },
              p2_team: { text: p2Prefix || '' },
              p1_country: { text: p1Country || '' },
              p2_country: { text: p2Country || '' },
              p1_cfn: { text: p1Cfn || '' },
              p2_cfn: { text: p2Cfn || '' },
              p1_character: { text: p1Character || '' },
              p2_character: { text: p2Character || '' },
              game_name: { text: activeMatch.game_name || '' },
              tournament_round: { text: activeMatch.round_name || '' },
              tournament_name: { text: tournamentNameRef.current },
              p1_avatar: { src: p1Avatar || '/static/player_placeholder.jpg' },
              p2_avatar: { src: p2Avatar || '/static/player_placeholder.jpg' },
              p1_character_image: { src: p1CharacterImage || '/static/player_placeholder.jpg' },
              p2_character_image: { src: p2CharacterImage || '/static/player_placeholder.jpg' },
              p1_flag: { src: countryFlagUrl(p1Country) || '/static/flag_placeholder.png' },
              p2_flag: { src: countryFlagUrl(p2Country) || '/static/flag_placeholder.png' }
            };

            for (const [id, update] of Object.entries(updates)) {
              if (next.elements[id]) next.elements[id] = { ...next.elements[id], ...update };
              Object.keys(next.elements).forEach((elId) => {
                if (next.elements[elId].sourceId === id) {
                  next.elements[elId] = { ...next.elements[elId], ...update };
                }
              });
            }
          }

          // Re-apply Next Match stream queue hooks on pushed elements
          const nextMatch = nextMatchRef.current;
          const nextMatchTbd = nextMatchTbdRef.current;
          if (next.elements) {
            if (nextMatch && !nextMatchTbd) {
              const nextUpdates: Record<string, any> = {
                next_p1_name: { text: nextMatch.p1_name || '', visible: true },
                next_p2_name: { text: nextMatch.p2_name || '', visible: true },
                next_p1_score: { text: String(nextMatch.p1_score ?? '0'), visible: true },
                next_p2_score: { text: String(nextMatch.p2_score ?? '0'), visible: true },
                next_p1_prefix: { text: nextMatch.p1_prefix || nextMatch.p1_team || '', visible: true },
                next_p2_prefix: { text: nextMatch.p2_prefix || nextMatch.p2_team || '', visible: true },
                next_p1_country: { text: nextMatch.p1_country || '', visible: true },
                next_p2_country: { text: nextMatch.p2_country || '', visible: true },
                next_p1_character: { text: nextMatch.p1_character || '', visible: true },
                next_p2_character: { text: nextMatch.p2_character || '', visible: true },
                next_round_name: { text: nextMatch.round_name || '', visible: true },
                next_match_number: { text: nextMatch.match_number ? `Match #${nextMatch.match_number}` : '', visible: true },
                next_match_status: { text: nextMatch.match_status || nextMatch.status || 'Up Next', visible: true },
                next_p1_avatar: { src: nextMatch.p1_avatar || '/static/player_placeholder.jpg', visible: true },
                next_p2_avatar: { src: nextMatch.p2_avatar || '/static/player_placeholder.jpg', visible: true },
                next_p1_flag: { src: countryFlagUrl(nextMatch.p1_country) || '/static/flag_placeholder.png', visible: true },
                next_p2_flag: { src: countryFlagUrl(nextMatch.p2_country) || '/static/flag_placeholder.png', visible: true }
              };

              for (const [id, update] of Object.entries(nextUpdates)) {
                if (next.elements[id]) next.elements[id] = { ...next.elements[id], ...update };
                Object.keys(next.elements).forEach((elId) => {
                  if (next.elements[elId].sourceId === id) {
                    next.elements[elId] = { ...next.elements[elId], ...update };
                  }
                });
              }
            } else {
              for (const id of Object.keys(next.elements)) {
                const el = next.elements[id];
                if (id.startsWith('next_') || el.sourceId?.startsWith('next_')) {
                  next.elements[id] = { ...el, text: '', src: '', visible: false };
                }
              }
            }
          }

          void prepareOverlayAssets(next).then((prepared) => {
            if (assetRequest === assetRequestRef.current) setState(prepared);
          }).catch((error) => {
            console.error('Failed to prepare pushed overlay assets', error);
          });
        }
      };

      ws.onclose = () => {
        setTimeout(connect, 3000);
      };
    };

    connect();
    return () => {
      if (ws) {
        ws.onclose = null;
        ws.close();
      }
    };
  }, [slot]);

  // Dynamic Font Injection: load the global font and every saved library font
  // so per-element font selections work in OBS too.
  useEffect(() => {
    const urls = Array.from(new Set([
      state.global_font_url,
      ...state.font_library.map((font: { url?: string }) => font.url || ''),
    ].filter(Boolean)));
    urls.forEach((url, index) => {
      const id = `dyn-font-${index}`;
      let link = document.getElementById(id) as HTMLLinkElement | null;
      if (!link) {
        link = document.createElement('link');
        link.id = id;
        link.rel = 'stylesheet';
        document.head.appendChild(link);
      }
      if (link.href !== url) link.href = url;
    });
    document.querySelectorAll('link[id^="dyn-font-"]').forEach((node) => {
      const index = Number(node.id.replace('dyn-font-', ''));
      if (!urls[index]) node.remove();
    });
  }, [state.global_font_url, state.font_library]);

  return {
    state,
    transitionState,
    cascadeDelays,
    glitchedElementIds
  };
}
