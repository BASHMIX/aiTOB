import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

export function OBSViewer() {
  const [searchParams] = useSearchParams();
  const slot = searchParams.get('slot') || 'default'; // This is the station ID (e.g. station_1)

  const [state, setState] = useState<any>({ elements: {} });

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
        baseConfig = typeof currentPreset.config === 'string' ? JSON.parse(currentPreset.config) : currentPreset.config;
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

      setState(baseConfig);
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
          
          let content = null;
          if (el.type === 'text') {
            const strokeStyle = el.strokeWidth && el.strokeColor
              ? `${el.strokeWidth}px ${el.strokeColor}`
              : 'initial';

            const textShadowStyle = el.shadowColor
              ? `${el.shadowOffsetX || 0}px ${el.shadowOffsetY || 0}px ${el.shadowBlur || 0}px ${el.shadowColor}`
              : 'none';

            content = (
              <div style={{ 
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
              }}>
                {el.text}
              </div>
            );
          } else if (el.type === 'image') {
            const imgShadow = el.shadowColor 
              ? `drop-shadow(${el.shadowOffsetX || 0}px ${el.shadowOffsetY || 0}px ${el.shadowBlur || 0}px ${el.shadowColor})`
              : 'none';
            content = (
              <img 
                src={el.src} 
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
              <div style={{ 
                width: '100%', 
                height: '100%', 
                backgroundColor: el.color || 'rgba(0,0,0,0.5)',
                borderRadius: el.type === 'circle' ? '50%' : `${el.borderRadius || 0}px`,
                boxShadow: shapeShadow,
                border: borderStyle,
                boxSizing: 'border-box'
              }} />
            );
          }

          return (
            <div key={id} style={{
              position: 'absolute',
              left: el.x,
              top: el.y,
              width: el.width || 'auto',
              height: el.height || 'auto',
              zIndex: el.zIndex || 1
            }}>
              {content}
            </div>
          );
        })}
    </div>
  );
}
