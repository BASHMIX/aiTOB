import { useSearchParams } from 'react-router-dom';
import { useOBSViewerData } from './hooks/useOBSViewerData';
import { OBSElement } from './components/OBSElement';
import { SceneRenderer } from '@/scene/SceneRenderer';

export function OBSViewer() {
  const [searchParams] = useSearchParams();
  const slot = searchParams.get('slot') || 'default'; // This is the station ID (e.g. station_1)

  const {
    state,
    transitionState,
    cascadeDelays,
    glitchedElementIds,
    projectionKind,
    resultsProjection,
    sceneDoc,
  } = useOBSViewerData(slot);

  if (projectionKind === 'tournament-results' && resultsProjection && sceneDoc) {
    const sessionState = resultsProjection.session?.state;
    if (sessionState === 'cleared' || sessionState === 'error' || sessionState === 'ready') {
      return <div data-testid="obs-viewer-transparent" className="w-[1920px] h-[1080px] bg-transparent" />;
    }

    return (
      <div
        data-testid="obs-tournament-results-view"
        className="relative w-[1920px] h-[1080px] overflow-hidden"
        style={{
          backgroundColor: 'transparent',
          fontFamily: sceneDoc.canvas?.globalFontFamily || 'inherit',
        }}
      >
        <SceneRenderer
          scene={sceneDoc}
          standings={resultsProjection.entries || []}
          activeCueIndex={resultsProjection.session?.cue_index}
          playbackState={resultsProjection.session?.state}
          playbackUpdatedAt={resultsProjection.session?.updated_at}
        />
      </div>
    );
  }

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
            activeMatch={state.activeMatch}
            cascadeDelay={cascadeDelays[id] || 0}
            transitionState={transitionState}
            isGlitched={glitchedElementIds[id] === true}
            allElements={state.elements}
          />
        ))}
    </div>
  );
}
