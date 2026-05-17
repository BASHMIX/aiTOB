import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

export function OBSViewer() {
  const [searchParams] = useSearchParams();
  const slot = searchParams.get('slot') || 'default';

  const [state, setState] = useState<any>({ elements: {} });

  const fetchData = async () => {
    try {
      // 1. Fetch base overlay config
      const resOverlays = await fetch('/api/overlays');
      const dataOverlays = await resOverlays.json();
      const list = dataOverlays.overlays || [];
      const currentPreset = list.find((p: any) => p.name === slot);
      
      let baseConfig: any = { elements: {}, background_url: '', global_font_url: '', global_font_family: '' };
      if (currentPreset && currentPreset.config) {
        baseConfig = typeof currentPreset.config === 'string' ? JSON.parse(currentPreset.config) : currentPreset.config;
      }

      // 2. Fetch active matches to see if one is assigned to this slot
      const resMatches = await fetch('/api/active-matches');
      const dataMatches = await resMatches.json();
      const activeMatch = (dataMatches.matches || []).find((m: any) => m.station_id === slot);

      // 3. Merge active match data into elements if assigned
      if (activeMatch && baseConfig.elements) {
        const updates: Record<string, any> = {
          p1_name: { text: activeMatch.p1_name || '' },
          p2_name: { text: activeMatch.p2_name || '' },
          p1_score: { text: String(activeMatch.p1_score ?? '0') },
          p2_score: { text: String(activeMatch.p2_score ?? '0') },
          tournament_round: { text: activeMatch.round_name || '' },
          p1_avatar: { src: activeMatch.p1_avatar || '/static/player_placeholder.jpg' },
          p2_avatar: { src: activeMatch.p2_avatar || '/static/player_placeholder.jpg' }
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
          // Hub triggered an update, re-fetch and merge!
          fetchData();
        } else if (data.elements) {
          // Editor pushed a direct layout update
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
            content = (
              <div style={{ 
                color: el.color || '#fff', 
                fontSize: el.fontSize || 24,
                whiteSpace: 'nowrap'
              }}>
                {el.text}
              </div>
            );
          } else if (el.type === 'image') {
            content = <img src={el.src} style={{ width: '100%', height: '100%', objectFit: 'contain' }} />;
          } else if (el.type === 'rect' || el.type === 'circle') {
            content = (
              <div style={{ 
                width: '100%', 
                height: '100%', 
                backgroundColor: el.color || 'rgba(0,0,0,0.5)',
                borderRadius: el.type === 'circle' ? '50%' : `${el.borderRadius || 0}px`
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
