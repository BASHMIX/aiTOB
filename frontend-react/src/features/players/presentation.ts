import type { ProvenanceSource } from './types';

export const PLACEHOLDER_AVATAR = '/static/player_placeholder.jpg';

/**
 * Resolve the presentation avatar URL using field-precedence:
 * override -> confirmed profile -> provider snapshot -> placeholder
 */
export function resolveAvatarUrl(
  overrideAvatar?: string | null,
  profileAvatar?: string | null,
  providerAvatar?: string | null,
  placeholder: string = PLACEHOLDER_AVATAR
): string {
  if (overrideAvatar && overrideAvatar.trim()) {
    return overrideAvatar.trim();
  }
  if (profileAvatar && profileAvatar.trim()) {
    return profileAvatar.trim();
  }
  if (providerAvatar && providerAvatar.trim()) {
    return providerAvatar.trim();
  }
  return placeholder;
}

/**
 * Resolve display name using field-precedence:
 * override -> confirmed profile -> provider snapshot -> fallback
 */
export function resolveParticipantDisplayName(
  overrideName?: string | null,
  profileName?: string | null,
  providerName?: string | null,
  fallback: string = ''
): string {
  if (overrideName && overrideName.trim()) {
    return overrideName.trim();
  }
  if (profileName && profileName.trim()) {
    return profileName.trim();
  }
  if (providerName && providerName.trim()) {
    return providerName.trim();
  }
  return fallback;
}

/**
 * Helper to get user-friendly label for provenance sources
 */
export function getProvenanceLabel(source: ProvenanceSource): string {
  switch (source) {
    case 'entrant_override':
      return 'Tournament Override';
    case 'player_profile':
      return 'Player Profile';
    case 'provider_snapshot':
      return 'Bracket Provider';
    case 'placeholder':
    default:
      return 'Default';
  }
}

/**
 * Helper to get badge style classes for provenance sources
 */
export function getProvenanceBadgeClass(source: ProvenanceSource): string {
  switch (source) {
    case 'entrant_override':
      return 'bg-amber-500/20 text-amber-300 border-amber-500/30';
    case 'player_profile':
      return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30';
    case 'provider_snapshot':
      return 'bg-blue-500/20 text-blue-300 border-blue-500/30';
    case 'placeholder':
    default:
      return 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30';
  }
}
