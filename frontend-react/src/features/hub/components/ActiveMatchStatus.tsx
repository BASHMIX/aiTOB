import { useRef } from 'react';
import { useHubStore } from '@/store/useHubStore';
import { ActiveMatchCard } from './ActiveMatchCard';

export function ActiveMatchStatus() {
  const { matches } = useHubStore();
  const scrollRef = useRef<HTMLDivElement>(null);

  // The stream panel: shows ONLY matches that are live (in_progress) AND flagged for stream
  // coverage (is_stream_match) — these are the matches whose data is wired to a stream station
  // and pushed to the OBS overlay. Match lifecycle state (Not Started / Called / In Progress /
  // Complete) lives in the Match Dashboard; this panel is purely the on-stream view.
  const displayed = matches.filter(m => m.broadcast_state === 'live');

  const scrollLeft = () => {
    scrollRef.current?.scrollBy({ left: -380, behavior: 'smooth' });
  };

  const scrollRight = () => {
    scrollRef.current?.scrollBy({ left: 380, behavior: 'smooth' });
  };

  return (
    <section className="bg-cardDark/50 rounded-lg p-4 shadow-md flex flex-col gap-3 border border-white/10 relative">
      <div className="flex justify-between items-center border-b border-white/10 pb-2 relative z-30 bg-[#161c28] -mx-2 px-3 pt-1 rounded-t">
        <div className="flex items-center gap-2">
          <h2 className="text-accentYellow font-bold text-lg tracking-wide uppercase">
            On-Stream Match Live
          </h2>
          {displayed.length > 0 && (
            <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-statusRed/20 text-statusRed border border-statusRed/30">
              <span className="w-1.5 h-1.5 rounded-full bg-statusRed animate-pulse"></span>
              {displayed.length} Live
            </span>
          )}
        </div>
        {displayed.length > 2 && (
          <div className="flex items-center gap-1 bg-black/30 p-1 rounded-md border border-white/10">
            <button
              type="button"
              onClick={scrollLeft}
              className="p-1 rounded text-textDim hover:text-white hover:bg-white/10 transition-colors"
              title="Scroll Left"
              aria-label="Scroll Left"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <button
              type="button"
              onClick={scrollRight}
              className="p-1 rounded text-textDim hover:text-white hover:bg-white/10 transition-colors"
              title="Scroll Right"
              aria-label="Scroll Right"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>
        )}
      </div>

      <div
        ref={scrollRef}
        className="flex items-stretch gap-3.5 overflow-x-auto pb-2 scrollbar-none [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden snap-x scroll-smooth"
      >
        {displayed.length === 0 ? (
          <div className="w-full text-center py-6 px-4 text-textDim text-sm bg-black/10 rounded-lg border border-dashed border-white/10">
            No matches live on stream. Flag a match for stream and start it from the Match Dashboard.
          </div>
        ) : (
          displayed.map((match) => (
            <div key={match.set_id} className="min-w-[340px] sm:min-w-[380px] max-w-[440px] shrink-0 snap-start">
              <ActiveMatchCard match={match} />
            </div>
          ))
        )}
      </div>
    </section>
  );
}
