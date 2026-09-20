type AccentTournament = { provider_type?: string; accent_color?: string | null } | undefined;

const STARTGG_DEFAULT = '#60a5fa';
const CHALLONGE_DEFAULT = '#a78bfa';

function getLuminance(hex: string): number {
  const c = hex.replace('#', '');
  const r = parseInt(c.substring(0, 2), 16) / 255;
  const g = parseInt(c.substring(2, 4), 16) / 255;
  const b = parseInt(c.substring(4, 6), 16) / 255;
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function tournamentAccent(tournament: AccentTournament): string {
  const configured = tournament?.accent_color;
  if (configured && /^#[0-9a-f]{6}$/i.test(configured)) {
    // If the configured color has enough contrast on dark backgrounds, use it
    if (getLuminance(configured) >= 0.22) {
      return configured;
    }
  }
  return tournament?.provider_type === 'challonge' ? CHALLONGE_DEFAULT : STARTGG_DEFAULT;
}

export function withAccentAlpha(color: string, alpha: number): string {
  const normalized = tournamentAccent({ accent_color: color });
  const channel = Math.round(Math.max(0, Math.min(1, alpha)) * 255).toString(16).padStart(2, '0');
  return `${normalized}${channel}`;
}
