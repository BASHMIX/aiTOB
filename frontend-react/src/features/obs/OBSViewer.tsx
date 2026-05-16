import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

export function OBSViewer() {
  const [searchParams] = useSearchParams();
  const slot = searchParams.get('slot') || 'default';

  const [state, setState] = useState<any>({ elements: {} });

  useEffect(() => {
    let ws: WebSocket;
    const connect = () => {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${proto}//${window.location.host}/ws/overlay/${encodeURIComponent(slot)}`;
      ws = new WebSocket(wsUrl);
      
      ws.onmessage = (e) => {
        const data = JSON.parse(e.data);
        setState((prev: any) => {
          const next = { 
            ...prev, 
            background_url: data.background_url, 
            global_font_url: data.global_font_url, 
            global_font_family: data.global_font_family 
          };
          next.elements = { ...prev.elements };
          if (data.elements) {
            for (const key in data.elements) {
              next.elements[key] = { ...next.elements[key], ...data.elements[key] };
            }
          }
          return next;
        });
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
      {Object.entries(state.elements || {}).map(([id, el]: [string, any]) => {
        if (!el.visible) return null;

        const isImg = el.type === 'image';
        
        return (
          <div
            key={id}
            className={`absolute select-none text-center box-border ${isImg ? '' : 'whitespace-nowrap'}`}
            style={{
              left: el.x,
              top: el.y,
              width: isImg ? el.width : undefined,
              height: isImg ? el.height : undefined,
              fontSize: !isImg ? el.fontSize : undefined,
              color: !isImg ? el.color : undefined,
            }}
          >
            {isImg ? (
              <img src={el.src} alt="" className="w-full h-full object-contain block" />
            ) : (
              el.text
            )}
          </div>
        );
      })}
    </div>
  );
}
