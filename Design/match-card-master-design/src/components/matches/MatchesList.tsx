import { MatchCard, type Match, type MatchStatus } from "./MatchCard";
import { cn } from "@/lib/utils";

export interface MatchesListProps {
  matches: Match[];
}

const GROUPS: { status: MatchStatus | "complete"; label: string; dot: string }[] = [
  { status: "waiting", label: "Not Started", dot: "bg-[var(--tone-activate)]" },
  { status: "live", label: "In Progress", dot: "bg-[var(--tone-send)]" },
  { status: "called", label: "Players Called", dot: "bg-[var(--tone-reset)]" },
  { status: "complete", label: "Complete / DQ", dot: "bg-muted-foreground" },
];

function groupMatches(matches: Match[], key: MatchStatus | "complete") {
  if (key === "complete") return matches.filter((m) => m.status === "done" || m.status === "dq");
  return matches.filter((m) => m.status === key);
}

export function MatchesList({ matches }: MatchesListProps) {
  return (
    <div className="flex flex-col gap-6">
      {GROUPS.map((group) => {
        const items = groupMatches(matches, group.status);
        if (!items.length) return null;
        return (
          <section key={group.label} className="flex flex-col gap-2">
            <header className="flex items-center gap-2 text-sm font-semibold text-foreground">
              <span className={cn("h-2.5 w-2.5 rounded-full", group.dot)} />
              {group.label}
            </header>
            <div className="flex flex-col gap-2">
              {items.map((m) => (
                <MatchCard key={m.id} match={m} />
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
