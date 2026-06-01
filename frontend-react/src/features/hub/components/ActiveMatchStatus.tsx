import { useHubStore } from '@/store/useHubStore';
import { ActiveMatchCard } from './ActiveMatchCard';

export function ActiveMatchStatus() {
  const { matches } = useHubStore();

  // The stream panel: shows ONLY matches that are live (in_progress) AND flagged for stream
  // coverage (is_stream_match) — these are the matches whose data is wired to a stream station
  // and pushed to the OBS overlay. Match lifecycle state (Not Started / Called / In Progress /
  // Complete) lives in the Match Dashboard; this panel is purely the on-stream view.
  const displayed = matches.filter(m => m.status === 'in_progress' && m.is_stream_match);

  return (
    <section className="bg-cardDark/50 backdrop-blur-md rounded-lg p-4 shadow-md flex flex-col gap-3 border border-white/10 relative z-10">
      <h2 className="text-accentYellow font-bold text-lg tracking-wide uppercase border-b border-white/10 pb-2">
        On-Stream Match Live
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {displayed.length === 0 ? (
          <div className="text-center p-5 text-textDim text-sm col-span-full">
            No matches live on stream. Flag a match for stream and start it from the Match Dashboard.
          </div>
        ) : (
          displayed.map((match) => (
            <ActiveMatchCard key={match.set_id} match={match} />
          ))
        )}
      </div>
    </section>
  );
}
