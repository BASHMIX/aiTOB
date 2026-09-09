type AccentTournament = { provider_type?: string; accent_color?: string | null } | undefined;

const STARTGG_DEFAULT = '#60a5fa';
const CHALLONGE_DEFAULT = '#a78bfa';

export function tournamentAccent(tournament: AccentTournament): string {
  const configured = tournament?.accent_color;
  if (configured && /^#[0-9a-f]{6}$/i.test(configured)) return configured;
  return tournament?.provider_type === 'challonge' ? CHALLONGE_DEFAULT : STARTGG_DEFAULT;
}

export function withAccentAlpha(color: string, alpha: number): string {
  const normalized = tournamentAccent({ accent_color: color });
  const channel = Math.round(Math.max(0, Math.min(1, alpha)) * 255).toString(16).padStart(2, '0');
  return `${normalized}${channel}`;
}
