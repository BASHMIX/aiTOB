
interface LoadOverlayModalProps {
  isOpen: boolean;
  onClose: () => void;
  stationId: string;
  allSavedOverlays: {name: string, config: any}[];
  onLoad: (name: string) => void;
}

export function LoadOverlayModal({ isOpen, onClose, stationId, allSavedOverlays, onLoad }: LoadOverlayModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/85 backdrop-blur-md flex items-center justify-center z-[99999] p-8 animate-fadeIn">
      <div className="bg-[#222] border border-white/10 rounded-2xl p-8 max-w-6xl w-full max-h-[85vh] flex flex-col relative shadow-2xl">
        {/* Close btn */}
        <button
          onClick={onClose}
          className="absolute top-6 right-6 w-10 h-10 rounded-full bg-white/5 border border-white/10 flex items-center justify-center hover:bg-red-500 hover:text-white transition-all text-lg font-bold text-white"
          title="Close modal"
        >
          ✕
        </button>

        <h2 className="text-[#00ffcc] text-2xl font-black uppercase tracking-wider mb-2">Load Overlay Slide</h2>
        <p className="text-[#aaa] text-sm mb-6">Select a saved overlay preset from the database to load onto this station ({stationId}).</p>

        <div className="flex-grow overflow-y-auto pr-2 grid grid-cols-1 md:grid-cols-3 gap-6">
          {allSavedOverlays.length === 0 ? (
            <div className="col-span-3 text-center py-20 text-white/40">
              <p className="text-lg font-bold mb-2">No saved overlays found in DB</p>
              <p className="text-xs">Create and save a layout in the editor first to populate this list.</p>
            </div>
          ) : (
            allSavedOverlays.map((o) => {
              const elCount = Object.keys(o.config?.elements || {}).length;
              return (
                <div
                  key={o.name}
                  onClick={() => onLoad(o.name)}
                  className="border border-white/10 rounded-xl p-5 bg-[#2b2b2b] hover:border-[#00ffcc] hover:bg-[#333] transition-all cursor-pointer flex flex-col group relative shadow-md overflow-hidden"
                >
                  <div className="absolute top-3 right-3 bg-[#00ffcc]/10 text-[#00ffcc] border border-[#00ffcc]/20 rounded-full px-2.5 py-0.5 text-[9px] font-bold uppercase tracking-wide">
                    {elCount} Elements
                  </div>

                  {/* Slide Thumbnail Preview Grid */}
                  <div className="w-full h-28 bg-[#1a1a1a] rounded-lg border border-white/5 mb-4 relative flex flex-col items-center justify-center overflow-hidden">
                    {o.config?.background_url ? (
                      <div
                        className="absolute inset-0 bg-cover bg-center opacity-40 pointer-events-none"
                        style={{ backgroundImage: `url('${o.config.background_url}')` }}
                      />
                    ) : (
                      <div className="absolute inset-0 bg-checkerboard opacity-25 pointer-events-none" />
                    )}
                    <span className="text-white/80 text-xs font-semibold z-10 group-hover:scale-105 transition-transform pointer-events-none">
                      {o.name}
                    </span>
                  </div>

                  <h3 className="font-bold text-white group-hover:text-[#00ffcc] transition-colors">{o.name}</h3>
                  <p className="text-[11px] text-[#aaa] mt-1 truncate pointer-events-none">
                    Font: {o.config?.global_font_family || 'System Default'}
                  </p>

                  <button
                    className="w-full mt-4 py-2 bg-[#00ffcc] text-[#111] font-bold rounded-lg text-xs uppercase tracking-wider hover:bg-[#00d4aa] transition-colors"
                  >
                    Load Slide
                  </button>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
