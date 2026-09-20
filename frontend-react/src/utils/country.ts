const COUNTRY_ALIASES: Record<string, string> = {
  usa: 'US', 'unitedstatesofamerica': 'US', uk: 'GB',
  southkorea: 'KR', northkorea: 'KP', russia: 'RU',
  iran: 'IR', syria: 'SY', palestine: 'PS',
  bolivia: 'BO', venezuela: 'VE', tanzania: 'TZ',
  vietnam: 'VN', moldova: 'MD', laos: 'LA',
};

let regionNames: Map<string, string> | null = null;

function normalizedName(value: string): string {
  return value
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLocaleLowerCase('en')
    .replace(/[^a-z0-9]/g, '');
}

function regionNameLookup(): Map<string, string> {
  if (regionNames) return regionNames;
  regionNames = new Map(Object.entries(COUNTRY_ALIASES));
  const DisplayNames = (Intl as any).DisplayNames;
  if (!DisplayNames) return regionNames;

  const names = new DisplayNames(['en'], { type: 'region' });
  for (let first = 65; first <= 90; first += 1) {
    for (let second = 65; second <= 90; second += 1) {
      const code = String.fromCharCode(first, second);
      const name = names.of(code);
      if (name && name !== code) regionNames.set(normalizedName(name), code);
    }
  }
  return regionNames;
}

/** Convert either an ISO alpha-2 code or a provider country name to alpha-2. */
export function countryCode(value: unknown): string | null {
  const raw = String(value || '').trim();
  if (!raw) return null;
  const alias = regionNameLookup().get(normalizedName(raw));
  if (alias) return alias;
  if (/^[A-Za-z]{2}$/.test(raw)) return raw.toUpperCase();
  return null;
}

export function countryFlagUrl(value: unknown): string | null {
  const code = countryCode(value);
  return code ? `/static/flags/${code.toLowerCase()}.svg` : null;
}

export function countryFlagEmoji(value: unknown): string | null {
  const code = countryCode(value);
  if (!code) return null;
  return String.fromCodePoint(...code.split('').map(char => 127397 + char.charCodeAt(0)));
}
