import { MatchCard, type MatchData, type MatchStatus } from "./MatchCard";

export interface MatchesListProps {
  matches: MatchData[];
  dqTimerSeconds: number;
  autoDqEnabled: boolean;
  onAction: (action: string, row: any, data?: any) => void;
  onToggleStream: (setId: string, currentVal: boolean) => void;
  stations?: { id: string; name: string }[];
}

const GROUPS: { status: MatchStatus | "complete"; label: string; dot: string; titleCls: string }[] = [
  { status: "waiting", label: "Not Started", dot: "bg-[var(--tone-activate)]", titleCls: "text-gray-400" },
  { status: "live", label: "In Progress", dot: "bg-[var(--tone-send)] animate-pulse", titleCls: "text-[var(--tone-send)]" },
  { status: "called", label: "Players Called", dot: "bg-[var(--tone-reset)]", titleCls: "text-[var(--tone-reset)]" },
  { status: "complete", label: "Complete / DQ", dot: "bg-muted-foreground", titleCls: "text-gray-500" },
];

function groupMatches(matches: MatchData[], key: MatchStatus | "complete") {
  if (key === "complete") return matches.filter((m) => m.status === "done" || m.status === "dq");
  if (key === "waiting") return matches.filter((m) => m.status === "waiting");
  return matches.filter((m) => m.status === key);
}

export function MatchesList({ matches, dqTimerSeconds, autoDqEnabled, onAction, onToggleStream, stations }: MatchesListProps) {
  return (
    <div className="flex flex-col gap-6">
      {GROUPS.map((group) => {
        const items = groupMatches(matches, group.status);
        return (
          <section key={group.label} className="flex flex-col gap-2">
            <header className="flex items-center gap-2 text-sm font-semibold text-[var(--foreground)]">
              <span className={`h-2.5 w-2.5 rounded-full ${group.dot}`} />
              {group.label}
            </header>
            
            <div className="flex flex-col gap-2">
              {items.length === 0 ? (
                <div className="text-center py-3 text-gray-700 text-xs italic">—</div>
              ) : (
                items.map((m) => (
                  <MatchCard 
                    key={m.id} 
                    match={m} 
                    dqTimerSeconds={dqTimerSeconds}
                    autoDqEnabled={autoDqEnabled}
                    onAction={onAction}
                    onToggleStream={onToggleStream}
                    stations={stations}
                  />
                ))
              )}
            </div>
          </section>
        );
      })}
    </div>
  );
}
