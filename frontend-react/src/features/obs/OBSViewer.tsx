import { useEffect, useState, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';

function resolveCascadeDelays(elements: Record<string, any>) {
  const sorted = Object.entries(elements).sort(
    (a, b) => (a[1].zIndex || 0) - (b[1].zIndex || 0)
  );

  const resolvedDelays: Record<string, number> = {};
  let lastDuration = 0;

  for (let i = 0; i < sorted.length; i++) {
    const [id, el] = sorted[i];
    const anim = el.animation;
    if (!anim || anim.animationType === 'none') {
      resolvedDelays[id] = 0;
      continue;
    }

    const selfDelay = anim.delay || 0;
    const selfDuration = anim.duration || 500;

    if (anim.trigger === 'after-prev' && i > 0) {
      const prevId = sorted[i - 1][0];
      const start = (resolvedDelays[prevId] || 0) + lastDuration + selfDelay;
      resolvedDelays[id] = start;
    } else if (anim.trigger === 'with-prev' && i > 0) {
      const prevId = sorted[i - 1][0];
      const start = (resolvedDelays[prevId] || 0) + selfDelay;
      resolvedDelays[id] = start;
    } else {
      resolvedDelays[id] = selfDelay;
    }

    lastDuration = selfDuration;
  }

  return resolvedDelays;
}

export function OBSViewer() {
  const [searchParams] = useSearchParams();
  const slot = searchParams.get('slot') || 'default'; // This is the station ID (e.g. station_1)

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
        isInitialLoad,
        isPresetChange,
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

  const getAnimationStyles = (el: any, cascadeDelay: number) => {
    const anim = el.animation;
    if (!anim || anim.animationType === 'none') return {};

    const { animationType, direction, duration, delay, tweenType, playOn } = anim;

    // 1. Idle state - disable all transitions to prevent telemetry-triggered updates replaying
    if (transitionState === 'idle') {
      return {
        transition: 'none',
      };
    }

    const easings: Record<string, string> = {
      'linear': 'linear',
      'ease-in': 'ease-in',
      'ease-out': 'ease-out',
      'ease-in-out': 'ease-in-out',
      'bounce': 'cubic-bezier(0.175, 0.885, 0.32, 1.275)',
      'back-out': 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      'elastic': 'cubic-bezier(0.25, 1.36, 0.49, 1.16)'
    };
    const easing = easings[tweenType] || 'ease-out';

    let startX = 0;
    let startY = 0;
    let startOpacity = 1;

    const w = el.width || 250;
    const h = el.height || 60;
    const x = el.x || 0;
    const y = el.y || 0;

    const canvasWidth = 1920;
    const canvasHeight = 1080;

    if (animationType === 'fly-in') {
      if (direction === 'bottom') startY = canvasHeight - y;
      else if (direction === 'top') startY = -y - h;
      else if (direction === 'left') startX = -x - w;
      else if (direction === 'right') startX = canvasWidth - x;
      else if (direction === 'bottom-left') { startX = -x - w; startY = canvasHeight - y; }
      else if (direction === 'bottom-right') { startX = canvasWidth - x; startY = canvasHeight - y; }
      else if (direction === 'top-left') { startX = -x - w; startY = -y - h; }
      else if (direction === 'top-right') { startX = canvasWidth - x; startY = -y - h; }
    } else if (animationType === 'float-in') {
      startOpacity = 0;
      if (direction === 'bottom') startY = 50;
      else if (direction === 'top') startY = -50;
      else if (direction === 'left') startX = -50;
      else if (direction === 'right') startX = 50;
      else if (direction === 'bottom-left') { startX = -35; startY = 35; }
      else if (direction === 'bottom-right') { startX = 35; startY = 35; }
      else if (direction === 'top-left') { startX = -35; startY = -35; }
      else if (direction === 'top-right') { startX = 35; startY = -35; }
    } else if (animationType === 'fade-in') {
      startOpacity = 0;
    }

    const resolvedDelay = cascadeDelay;

    // Exit transition
    const isExit = transitionState === 'out' && (playOn === 'OUT' || playOn === 'BOTH');
    if (isExit) {
      return {
        transition: `transform ${duration}ms ${easing} ${delay}ms, opacity ${duration}ms ${easing} ${delay}ms`,
        transform: `translate(${startX}px, ${startY}px)`,
        opacity: startOpacity,
      };
    }

    // Entrance transition
    const isEntranceEnabled = playOn === 'IN' || playOn === 'BOTH';
    if (isEntranceEnabled) {
      if (transitionState === 'in') {
        return {
          transition: 'none',
          transform: `translate(${startX}px, ${startY}px)`,
          opacity: startOpacity,
        };
      }
      if (transitionState === 'run') {
        return {
          transition: `transform ${duration}ms ${easing} ${resolvedDelay}ms, opacity ${duration}ms ${easing} ${resolvedDelay}ms`,
          transform: 'translate(0, 0)',
          opacity: 1,
        };
      }
    }

    // Default stable state for elements not animating in or out
    return {
      transition: 'none',
      transform: 'translate(0, 0)',
      opacity: 1,
    };
  };

  return (
    <div 
      className="relative w-[1920px] h-[1080px] bg-cover bg-center overflow-hidden"
      style={{
        backgroundColor: 'transparent',
        backgroundImage: state.background_url ? `url('${state.background_url}')` : 'none',
        fontFamily: state.global_font_family || 'inherit'
      }}
    >
      {Object.entries(state.elements || {})
        .sort((a: any, b: any) => (a[1].zIndex || 0) - (b[1].zIndex || 0))
        .map(([id, el]: [string, any]) => {
          if (!el.visible) return null;

          const cascadeDelay = cascadeDelays[id] || 0;
          const animStyles = getAnimationStyles(el, cascadeDelay);

          // Continuous loop / Idle animations
          let loopClass = '';
          if ((transitionState === 'none' || transitionState === 'idle') && el.animation) {
            const idleType = el.animation.idleAnimation || 'none';
            if (idleType !== 'none') {
              loopClass = `idle-animation-${idleType}`;
            } else if (Number(el.animation.loop) === -1) {
              // Legacy fallback
              if (el.animation.animationType === 'fade-in') loopClass = 'continuous-loop-pulse';
              else loopClass = 'continuous-loop-bob';
            }
          }

          // Score changes Glitch class
          const isGlitched = glitchedElementIds[id] === true;
          const glitchClass = isGlitched ? (el.type === 'text' ? 'esports-glitch-text' : 'esports-glitch') : '';

          let content = null;
          if (el.type === 'text') {
            const strokeStyle = el.strokeWidth && el.strokeColor
              ? `${el.strokeWidth}px ${el.strokeColor}`
              : 'initial';

            const textShadowStyle = isGlitched
              ? undefined
              : (el.shadowColor
                ? `${el.shadowOffsetX || 0}px ${el.shadowOffsetY || 0}px ${el.shadowBlur || 0}px ${el.shadowColor}`
                : 'none');

            const hasReveal = el.animation && el.animation.animationType !== 'none' && el.animation.revealStyle && el.animation.revealStyle !== 'all';
            
            // Easing curves matching custom easing utilities
            const easings: Record<string, string> = {
              'linear': 'linear',
              'ease-in': 'ease-in',
              'ease-out': 'ease-out',
              'ease-in-out': 'ease-in-out',
              'bounce': 'cubic-bezier(0.175, 0.885, 0.32, 1.275)',
              'back-out': 'cubic-bezier(0.34, 1.56, 0.64, 1)',
              'elastic': 'cubic-bezier(0.25, 1.36, 0.49, 1.16)'
            };
            const easing = easings[el.animation?.tweenType || 'ease-out'] || 'ease-out';
            const duration = el.animation?.duration || 500;
            const isEntrance = transitionState === 'in' && (el.animation?.playOn === 'IN' || el.animation?.playOn === 'BOTH');
            const isExit = transitionState === 'out' && (el.animation?.playOn === 'OUT' || el.animation?.playOn === 'BOTH');

            let textContentToRender = null;
            if (hasReveal && el.animation.revealStyle === 'letter') {
              const chars = String(el.text || '').split('');
              textContentToRender = (
                <span className="inline-flex flex-wrap w-full items-center justify-inherit" style={{ justifyContent: 'inherit' }}>
                  {chars.map((char, i) => (
                    <span
                      key={i}
                      style={{
                        display: 'inline-block',
                        whiteSpace: char === ' ' ? 'pre' : 'normal',
                        transition: isEntrance ? 'none' : `transform ${duration}ms ${easing}, opacity ${duration}ms ${easing}`,
                        transitionDelay: isEntrance ? '0ms' : `${cascadeDelay + (i * 20)}ms`,
                        transform: isEntrance || isExit ? `translateY(35px) scale(${el.animation?.revealScale ?? 0.3}) rotate(-8deg)` : 'none',
                        opacity: isEntrance || isExit ? 0 : 1,
                      }}
                    >
                      {char}
                    </span>
                  ))}
                </span>
              );
            } else if (hasReveal && el.animation.revealStyle === 'word') {
              const words = String(el.text || '').split(' ');
              textContentToRender = (
                <span className="inline-flex flex-wrap w-full items-center justify-inherit" style={{ justifyContent: 'inherit' }}>
                  {words.map((word, i) => (
                    <span
                      key={i}
                      style={{
                        display: 'inline-block',
                        marginRight: '0.25em',
                        transition: isEntrance ? 'none' : `transform ${duration}ms ${easing}, opacity ${duration}ms ${easing}`,
                        transitionDelay: isEntrance ? '0ms' : `${cascadeDelay + (i * 80)}ms`,
                        transform: isEntrance || isExit ? `translateY(45px) scale(${el.animation?.revealScale ?? 0.3}) rotate(-12deg)` : 'none',
                        opacity: isEntrance || isExit ? 0 : 1,
                      }}
                    >
                      {word}
                    </span>
                  ))}
                </span>
              );
            } else {
              textContentToRender = el.text;
            }

            content = (
              <div 
                style={{ 
                  color: el.color || '#fff', 
                  fontSize: `${el.fontSize || 24}px`,
                  fontWeight: el.fontWeight || 'normal',
                  fontStyle: el.fontStyle || 'normal',
                  textAlign: el.textAlign || 'left',
                  WebkitTextStroke: strokeStyle,
                  textShadow: textShadowStyle,
                  paintOrder: 'stroke fill',
                  width: '100%',
                  height: '100%',
                  whiteSpace: 'pre-wrap', // Support wrap
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: el.textAlign === 'center' ? 'center' : el.textAlign === 'right' ? 'flex-end' : 'flex-start'
                }}
                className={glitchClass}
                data-text={el.text}
              >
                {textContentToRender}
              </div>
            );
          } else if (el.type === 'image') {
            const imgShadow = el.shadowColor 
              ? `drop-shadow(${el.shadowOffsetX || 0}px ${el.shadowOffsetY || 0}px ${el.shadowBlur || 0}px ${el.shadowColor})`
              : 'none';
            content = (
              <img 
                src={el.src} 
                className={glitchClass}
                style={{ 
                  width: '100%', 
                  height: '100%', 
                  objectFit: 'contain',
                  filter: imgShadow
                }} 
              />
            );
          } else if (el.type === 'rect' || el.type === 'circle') {
            const shapeShadow = el.shadowColor
              ? `${el.shadowOffsetX || 0}px ${el.shadowOffsetY || 0}px ${el.shadowBlur || 0}px ${el.shadowColor}`
              : 'none';
            const borderStyle = el.strokeWidth && el.strokeColor
              ? `${el.strokeWidth}px solid ${el.strokeColor}`
              : 'none';
            content = (
              <div 
                className={glitchClass}
                style={{ 
                  width: '100%', 
                  height: '100%', 
                  backgroundColor: el.color || 'rgba(0,0,0,0.5)',
                  borderRadius: el.type === 'circle' ? '50%' : `${el.borderRadius || 0}px`,
                  boxShadow: shapeShadow,
                  border: borderStyle,
                  boxSizing: 'border-box'
                }} 
              />
            );
          }

          return (
            <div 
              key={id} 
              style={{
                position: 'absolute',
                left: el.x,
                top: el.y,
                width: el.width || 'auto',
                height: el.height || 'auto',
                zIndex: el.zIndex || 1,
                ['--glitch-scale' as any]: el.animation?.glitchScale ?? 1.15,
              }}
            >
              <div 
                className={`w-full h-full ${loopClass}`}
                style={{
                  ...animStyles,
                  ['--idle-intensity' as any]: el.animation?.idleIntensity ?? 1.0,
                }}
              >
                {content}
              </div>
            </div>
          );
        })}
    </div>
  );
}
