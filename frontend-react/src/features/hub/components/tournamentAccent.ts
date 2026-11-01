import { useState, useEffect } from 'react';

type AccentTournament = { provider_type?: string; accent_color?: string | null; raw_data?: any } | undefined;

const STARTGG_DEFAULT = '#60a5fa';
const CHALLONGE_DEFAULT = '#a78bfa';

export const DEFAULT_EVENT_PALETTE = [
  '#0aefff', // Cyan (Tekken / Sci-fi)
  '#ff4444', // Red (Street Fighter / Combat)
  '#f59e0b', // Amber / Gold
  '#10b981', // Emerald
  '#a855f7', // Purple
  '#ec4899', // Pink
];

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
    if (getLuminance(configured) >= 0.15) {
      return configured;
    }
  }
  return tournament?.provider_type === 'challonge' ? CHALLONGE_DEFAULT : STARTGG_DEFAULT;
}

export function getSavedEventAccents(): Record<string, string> {
  try {
    const raw = localStorage.getItem('hub_event_accent_colors');
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

export const EVENT_ACCENT_CHANGE_EVENT = 'aitob_event_accent_changed';

export function saveEventAccent(eventId: string, color: string): void {
  try {
    const current = getSavedEventAccents();
    current[eventId] = color;
    localStorage.setItem('hub_event_accent_colors', JSON.stringify(current));
    window.dispatchEvent(new CustomEvent(EVENT_ACCENT_CHANGE_EVENT, { detail: { eventId, color } }));
  } catch {}
}

export function useEventAccentWatcher(): number {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const handleUpdate = () => setTick((t) => t + 1);
    window.addEventListener(EVENT_ACCENT_CHANGE_EVENT, handleUpdate);
    return () => window.removeEventListener(EVENT_ACCENT_CHANGE_EVENT, handleUpdate);
  }, []);
  return tick;
}

export function getEventIndex(tournament: any, eventId?: string | number | null): number {
  if (!tournament || !eventId) return 0;
  try {
    const raw = typeof tournament.raw_data === 'string' ? JSON.parse(tournament.raw_data) : tournament.raw_data;
    if (Array.isArray(raw?.events)) {
      const idx = raw.events.findIndex((e: any) => String(e.id) === String(eventId));
      if (idx >= 0) return idx;
    }
  } catch {}
  return 0;
}

export function isMultiEventTournament(tournament: any): boolean {
  if (!tournament) return false;
  try {
    const raw = typeof tournament.raw_data === 'string' ? JSON.parse(tournament.raw_data) : tournament.raw_data;
    return Array.isArray(raw?.events) && raw.events.length > 1;
  } catch {
    return false;
  }
}

export function eventAccent(tournament: any, eventId?: string | number | null, explicitIndex?: number): string {
  if (eventId) {
    const strId = String(eventId);
    const saved = getSavedEventAccents();
    if (saved[strId] && /^#[0-9a-f]{6}$/i.test(saved[strId])) {
      return saved[strId];
    }

    if (isMultiEventTournament(tournament)) {
      const idx = typeof explicitIndex === 'number' ? explicitIndex : getEventIndex(tournament, strId);
      return DEFAULT_EVENT_PALETTE[idx % DEFAULT_EVENT_PALETTE.length];
    }
  }
  return tournamentAccent(tournament);
}

export function withAccentAlpha(color: string, alpha: number): string {
  const normalized = color && /^#[0-9a-f]{6}$/i.test(color) ? color : tournamentAccent({ accent_color: color });
  const channel = Math.round(Math.max(0, Math.min(1, alpha)) * 255).toString(16).padStart(2, '0');
  return `${normalized}${channel}`;
}

