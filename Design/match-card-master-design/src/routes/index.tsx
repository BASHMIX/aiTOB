import { createFileRoute } from "@tanstack/react-router";
import { MatchesList } from "@/components/matches/MatchesList";
import type { Match } from "@/components/matches/MatchCard";

export const Route = createFileRoute("/")({
  component: Index,
});

const MATCHES: Match[] = [
  {
    id: "1",
    pool: "Pool 1",
    round: "Winner Round 1",
    status: "waiting",
    players: [
      { name: "FNC | BASHMIX", score: 2 },
      { name: "LordAhmad", score: 1 },
    ],
  },
  {
    id: "2",
    pool: "Pool 1",
    round: "Winner Round 1",
    status: "live",
    timer: "00:00",
    players: [
      { name: "FNC | BASHMIX", score: 0 },
      { name: "LordAhmad", score: 0 },
    ],
  },
  {
    id: "3",
    pool: "Pool 1",
    round: "Winner Round 1",
    status: "called",
    timer: "00:00",
    players: [
      { name: "FNC | BASHMIX", score: 0 },
      { name: "LordAhmad", score: 0 },
    ],
  },
  {
    id: "4",
    pool: "Pool 1",
    round: "Winner Round 1",
    status: "done",
    players: [
      { name: "FNC | BASHMIX", score: 2 },
      { name: "LordAhmad", score: 1 },
    ],
  },
  {
    id: "5",
    pool: "Pool 1",
    round: "Winner Round 1",
    status: "dq",
    players: [
      { name: "FNC | BASHMIX", score: "DQ" },
      { name: "LordAhmad", score: 0, highlight: true },
    ],
  },
  {
    id: "6",
    pool: "Pool 1",
    round: "Winner Round 1",
    status: "dq",
    players: [
      { name: "FNC | BASHMIX", score: "DQ" },
      { name: "LordAhmad", score: "DQ" },
    ],
  },
];

function Index() {
  return (
    <div className="dark min-h-screen bg-background py-10">
      <main className="mx-auto max-w-3xl px-4">
        <h1 className="mb-6 text-2xl font-bold text-foreground">Matches</h1>
        <MatchesList matches={MATCHES} />
      </main>
    </div>
  );
}
