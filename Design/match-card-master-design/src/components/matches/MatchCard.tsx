import { Play } from "lucide-react";
import { ActionButton } from "./ActionButton";
import { cn } from "@/lib/utils";

export type MatchStatus = "waiting" | "live" | "called" | "done" | "dq";

export interface MatchPlayer {
  name: string;
  score: number | "DQ";
  /** highlight the score cell green (e.g. forfeit win) */
  highlight?: boolean;
}

export interface Match {
  id: string;
  pool: string;
  round: string;
  status: MatchStatus;
  players: [MatchPlayer, MatchPlayer];
  timer?: string;
}

const STATUS_META: Record<
  MatchStatus,
  { label: string; tone: "activate" | "send" | "reset" | "dq" | "neutral" }
> = {
  waiting: { label: "WAITING", tone: "activate" },
  live: { label: "LIVE", tone: "send" },
  called: { label: "CALLED", tone: "reset" },
  done: { label: "DONE", tone: "neutral" },
  dq: { label: "DQ", tone: "dq" },
};

const TONE_TEXT: Record<string, string> = {
  activate: "text-[var(--tone-activate)]",
  send: "text-[var(--tone-send)]",
  reset: "text-[var(--tone-reset)]",
  dq: "text-[var(--tone-dq)]",
  neutral: "text-muted-foreground",
};
const TONE_BORDER: Record<string, string> = {
  activate: "border-[var(--tone-activate)]",
  send: "border-[var(--tone-send)]",
  reset: "border-[var(--tone-reset)]",
  dq: "border-[var(--tone-dq)]",
  neutral: "border-border",
};
const PANEL_TONE: Record<string, string> = {
  activate: "border-[var(--tone-activate)]/50 bg-[var(--tone-activate)]/5",
  send: "border-[var(--tone-send)]/50 bg-[var(--tone-send)]/5",
  reset: "border-[var(--tone-reset)]/50 bg-[var(--tone-reset)]/5",
  dq: "border-[var(--tone-dq)]/50 bg-[var(--tone-dq)]/5",
  neutral: "border-border bg-card",
};

function ScoreCell({ player }: { player: MatchPlayer }) {
  const isDQ = player.score === "DQ";
  return (
    <div
      className={cn(
        "flex h-12 min-w-12 items-center justify-center px-3 text-base font-semibold border-l border-border text-slate-100",
        isDQ && "text-[var(--tone-dq)]",
        player.highlight && "bg-[var(--tone-send)]/15 text-[var(--tone-send)]",
      )}
    >
      {player.score}
    </div>
  );
}

function PlayersBlock({ players }: { players: Match["players"] }) {
  return (
    <div className="flex-1 overflow-hidden">
      {players.map((p, i) => (
        <div
          key={i}
          className={cn(
            "flex items-center justify-between",
            i === 0 && "border-b border-border",
          )}
        >
          <div className="flex-1 px-3 py-2.5 text-sm font-medium text-foreground">
            {p.name}
          </div>
          <ScoreCell player={p} />
        </div>
      ))}
    </div>
  );
}

function MatchActions({ match }: { match: Match }) {
  switch (match.status) {
    case "waiting":
      return (
        <>
          <ActionButton tone="activate" label="Activate" />
          <button
            type="button"
            aria-label="Preview"
            className="inline-flex h-8 w-10 items-center justify-center rounded-md border border-[var(--tone-activate)] text-[var(--tone-activate)] hover:bg-[var(--tone-activate)]/10"
          >
            <Play className="h-3.5 w-3.5" fill="currentColor" />
          </button>
        </>
      );
    case "live":
      return (
        <>
          <ActionButton tone="send" label="Send" />
          <ActionButton tone="dq" label="DQ" />
        </>
      );
    case "called":
      return (
        <>
          <ActionButton tone="reset" label="Reset" />
          <ActionButton tone="dq" label="DQ" />
        </>
      );
    case "done":
      return <ActionButton tone="reset" label="Reset" />;
    case "dq":
      return (
        <>
          <ActionButton tone="reset" label="Reset" />
          <ActionButton tone="dq" label="DQ" />
        </>
      );
  }
}

export function MatchCard({ match }: { match: Match }) {
  const meta = STATUS_META[match.status];
  const showTimer = match.status === "live" || match.status === "called";

  return (
    <div className={cn("flex items-stretch overflow-hidden rounded-md border", PANEL_TONE[meta.tone])}>
      <PlayersBlock players={match.players} />

      <div className="relative flex w-[260px] flex-col justify-between border-l border-border/60 px-3 py-2">
        <span
          className={cn(
            "absolute right-2 top-2 rounded border px-2 py-0.5 text-[10px] font-bold tracking-wider",
            TONE_TEXT[meta.tone],
            TONE_BORDER[meta.tone],
          )}
        >
          {meta.label}
        </span>

        <div>
          <div className="flex items-center gap-1.5 text-sm font-medium text-foreground">
            <span className="inline-flex h-4 w-4 items-center justify-center rounded-sm bg-muted text-[10px] font-bold">
              A
            </span>
            {match.pool}
          </div>
          <div className="text-xs text-muted-foreground">{match.round}</div>
        </div>

        <div className="mt-2 flex items-center gap-2">
          <MatchActions match={match} />
          {showTimer && (
            <span
              className={cn(
                "ml-auto font-mono text-base font-semibold tabular-nums",
                match.status === "live" ? "text-[var(--tone-send)]" : "text-[var(--tone-reset)]",
              )}
            >
              {match.timer ?? "00:00"}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
