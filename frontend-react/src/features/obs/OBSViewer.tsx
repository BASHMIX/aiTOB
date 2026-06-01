import { useSearchParams } from 'react-router-dom';
import { useOBSViewerData } from './hooks/useOBSViewerData';
import { OBSElement } from './components/OBSElement';

export function OBSViewer() {
  const [searchParams] = useSearchParams();
  const slot = searchParams.get('slot') || 'default'; // This is the station ID (e.g. station_1)

  const {
    state,
    transitionState,
    cascadeDelays,
    glitchedElementIds
  } = useOBSViewerData(slot);

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
        .map(([id, el]: [string, any]) => (
          <OBSElement
            key={id}
            id={id}
            el={el}
            cascadeDelay={cascadeDelays[id] || 0}
            transitionState={transitionState}
            isGlitched={glitchedElementIds[id] === true}
          />
        ))}
    </div>
  );
}
