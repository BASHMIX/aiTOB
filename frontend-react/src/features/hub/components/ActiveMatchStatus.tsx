import { useHubStore } from '@/store/useHubStore';
import { ActiveMatchCard } from './ActiveMatchCard';

export function ActiveMatchStatus() {
  const { matches } = useHubStore();
  const activeMatches = matches.filter(m => m.status === 'in_progress' || m.status === 'called' || m.status === 'not_started');

  return (
    <section className="bg-cardDark/50 backdrop-blur-md rounded-lg p-4 shadow-md flex flex-col gap-3 border border-white/10 relative z-10">
      <h2 className="text-accentYellow font-bold text-lg tracking-wide uppercase border-b border-white/10 pb-2">
        Active Match Status
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {activeMatches.length === 0 ? (
          <div className="text-center p-5 text-textDim text-sm col-span-full">
            No active matches. Assign sets from the Match Dashboard.
          </div>
        ) : (
          activeMatches.map((match) => (
            <ActiveMatchCard key={match.set_id} match={match} />
          ))
        )}
      </div>
    </section>
  );
}
