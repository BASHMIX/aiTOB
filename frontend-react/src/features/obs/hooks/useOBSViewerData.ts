import { useEffect, useState, useRef } from 'react';
import { resolveCascadeDelays } from '../utils';

export function useOBSViewerData(slot: string) {
  const [state, setState] = useState<any>({ elements: {} });
  const [transitionState, setTransitionState] = useState<'none' | 'in' | 'out' | 'run' | 'idle'>('idle');
  const [cascadeDelays, setCascadeDelays] = useState<Record<string, number>>({});
  const [glitchedElementIds, setGlitchedElementIds] = useState<Record<string, boolean>>({});
  const prevValuesRef = useRef<Record<string, string>>({});
  const currentStateRef = useRef<any>({ elements: {} });

  currentStateRef.current = state;
  const activeMatchRef = useRef<any>(null);
  const tournamentNameRef = useRef<string>('Tournament');

  const fetchData = async () => {
    try {
      // 1. Resolve active overlay name from station configuration
      let overlayName = slot;
      try {
        const resStations = await fetch('/api/stations');
        const dataStations = await resStations.json();
        const station = (dataStations.stations || []).find((s: any) => s.id === slot);
        if (station && station.active_overlay) {
          overlayName = station.active_overlay;
        }
      } catch (err) {
        console.error("Failed to fetch station active overlay details", err);
      }

      // 2. Fetch base overlay preset config
      const resOverlays = await fetch('/api/overlays');
      const dataOverlays = await resOverlays.json();
      const list = dataOverlays.overlays || [];
      const currentPreset = list.find((p: any) => p.name === overlayName);

      let baseConfig: any = { elements: {}, background_url: '', global_font_url: '', global_font_family: '' };
      if (currentPreset && currentPreset.config) {
        const parsed = typeof currentPreset.config === 'string' ? JSON.parse(currentPreset.config) : currentPreset.config;
        baseConfig = {
          elements: parsed.elements || {},
          background_url: parsed.background_url || '',
          global_font_url: parsed.global_font_url || '',
          global_font_family: parsed.global_font_family || ''
        };
      }

      // 3. Fetch active matches to see if one is currently connected to this station
      const resMatches = await fetch('/api/active-matches');
      const dataMatches = await resMatches.json();

      // Match is connected if assigned to this slot and in an active status
      const activeMatch = (dataMatches.matches || []).find(
        (m: any) => m.station_id === slot && ['not_started', 'called', 'in_progress'].includes(m.status)
      );

      // Requirement 3: If no active match is connected, clear the overlay (render blank transparent screen)
      if (!activeMatch) {
        setState({ elements: {}, background_url: '', global_font_url: '', global_font_family: '' });
        return;
      }

      // 4. Resolve tournament name if slug is available
      let tournamentName = 'Tournament';
      if (activeMatch.tournament_slug) {
        try {
          const resTournaments = await fetch('/api/tournaments');
          const dataTournaments = await resTournaments.json();
          const matchedTournament = (dataTournaments.tournaments || []).find((t: any) => t.slug === activeMatch.tournament_slug);
          if (matchedTournament) {
            tournamentName = matchedTournament.name || 'Tournament';
          }
        } catch (err) {
          console.error("Failed to fetch tournament name details", err);
        }
      }
      activeMatchRef.current = activeMatch;
      tournamentNameRef.current = tournamentName;

      // 5. Merge active match telemetry data into elements
      if (baseConfig.elements) {
        const isSwapped = activeMatch.swapped === true || activeMatch.swapped === 1 || activeMatch.swapped === '1';

        // Swap players' data temporarily if swap toggle is active
        const p1Name = isSwapped ? activeMatch.p2_name : activeMatch.p1_name;
        const p2Name = isSwapped ? activeMatch.p1_name : activeMatch.p2_name;
        const p1Score = isSwapped ? activeMatch.p2_score : activeMatch.p1_score;
        const p2Score = isSwapped ? activeMatch.p1_score : activeMatch.p2_score;
        const p1Team = isSwapped ? activeMatch.p2_team : activeMatch.p1_team;
        const p2Team = isSwapped ? activeMatch.p1_team : activeMatch.p2_team;
        const p1Avatar = isSwapped ? activeMatch.p2_avatar : activeMatch.p1_avatar;
        const p2Avatar = isSwapped ? activeMatch.p1_avatar : activeMatch.p2_avatar;
        const p1Country = isSwapped ? activeMatch.p2_country : activeMatch.p1_country;
        const p2Country = isSwapped ? activeMatch.p1_country : activeMatch.p2_country;

        const updates: Record<string, any> = {
          p1_name: { text: p1Name || '' },
          p2_name: { text: p2Name || '' },
          p1_score: { text: String(p1Score ?? '0') },
          p2_score: { text: String(p2Score ?? '0') },
          p1_team: { text: p1Team || '' },
          p2_team: { text: p2Team || '' },
          tournament_round: { text: activeMatch.round_name || '' },
          tournament_name: { text: tournamentName },
          p1_avatar: { src: p1Avatar || '/static/player_placeholder.jpg' },
          p2_avatar: { src: p2Avatar || '/static/player_placeholder.jpg' },
          p1_flag: {
            src: p1Country
              ? `https://flagcdn.com/160x120/${p1Country.toLowerCase()}.png`
              : '/static/flag_placeholder.png'
          },
          p2_flag: {
            src: p2Country
              ? `https://flagcdn.com/160x120/${p2Country.toLowerCase()}.png`
              : '/static/flag_placeholder.png'
          }
        };

        for (const [id, update] of Object.entries(updates)) {
          if (baseConfig.elements[id]) {
            baseConfig.elements[id] = { ...baseConfig.elements[id], ...update };
          }
        }
      }

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
                             (currentState.background_url !== baseConfig.background_url ||
                              Object.keys(currentState.elements || {}).length !== Object.keys(baseConfig.elements || {}).length);

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
    fetchData(); // Initial load

    let ws: WebSocket;
    const connect = () => {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${proto}//${window.location.host}/ws/overlay/${encodeURIComponent(slot)}`;
      ws = new WebSocket(wsUrl);

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
          setState((prev: any) => {
            const next = {
              ...prev,
              background_url: data.background_url ?? prev.background_url,
              global_font_url: data.global_font_url ?? prev.global_font_url,
              global_font_family: data.global_font_family ?? prev.global_font_family
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
              const p1Team = isSwapped ? activeMatch.p2_team : activeMatch.p1_team;
              const p2Team = isSwapped ? activeMatch.p1_team : activeMatch.p2_team;
              const p1Avatar = isSwapped ? activeMatch.p2_avatar : activeMatch.p1_avatar;
              const p2Avatar = isSwapped ? activeMatch.p1_avatar : activeMatch.p2_avatar;
              const p1Country = isSwapped ? activeMatch.p2_country : activeMatch.p1_country;
              const p2Country = isSwapped ? activeMatch.p1_country : activeMatch.p2_country;

              const updates: Record<string, any> = {
                p1_name: { text: p1Name || '' },
                p2_name: { text: p2Name || '' },
                p1_score: { text: String(p1Score ?? '0') },
                p2_score: { text: String(p2Score ?? '0') },
                p1_team: { text: p1Team || '' },
                p2_team: { text: p2Team || '' },
                tournament_round: { text: activeMatch.round_name || '' },
                tournament_name: { text: tournamentNameRef.current },
                p1_avatar: { src: p1Avatar || '/static/player_placeholder.jpg' },
                p2_avatar: { src: p2Avatar || '/static/player_placeholder.jpg' },
                p1_flag: {
                  src: p1Country
                    ? `https://flagcdn.com/160x120/${p1Country.toLowerCase()}.png`
                    : '/static/flag_placeholder.png'
                },
                p2_flag: {
                  src: p2Country
                    ? `https://flagcdn.com/160x120/${p2Country.toLowerCase()}.png`
                    : '/static/flag_placeholder.png'
                }
              };

              for (const [id, update] of Object.entries(updates)) {
                if (next.elements[id]) {
                  next.elements[id] = { ...next.elements[id], ...update };
                }
              }
            }

            return next;
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

  // Dynamic Font Injection
  useEffect(() => {
    if (!state.global_font_url) return;
    let link = document.getElementById('dyn-font') as HTMLLinkElement;
    if (!link) {
      link = document.createElement('link');
      link.id = 'dyn-font';
      link.rel = 'stylesheet';
      document.head.appendChild(link);
    }
    if (link.href !== state.global_font_url) {
      link.href = state.global_font_url;
    }
  }, [state.global_font_url]);

  return {
    state,
    transitionState,
    cascadeDelays,
    glitchedElementIds
  };
}
