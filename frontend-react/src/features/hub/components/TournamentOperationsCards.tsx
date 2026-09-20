import { useMemo, useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { useHubStore } from '@/store/useHubStore';
import startGgLogo from '@/assets/Start.gg.svg';
import challongeLogo from '@/assets/challonge-logo.svg';
import { tournamentAccent, withAccentAlpha } from './tournamentAccent';
import { removeTournamentFromHub, tournamentRemovalConfirmation } from '../tournamentRemoval';
import { getApiErrorMessage, reopenTournamentSetup } from '@/features/tournament-setup/api';

// PostgreSQL TIMESTAMP values are serialized without an offset. They are
// stored as UTC by the API, so make that explicit before comparing with the
// browser clock; otherwise the card appears stale by the user's timezone.
function parseServerTimestamp(value: string): number {
  const normalized = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value) ? value : `${value}Z`;
  return new Date(normalized).getTime();
}

function freshnessLabel(lastSyncedAt?: string | null, syncStatus?: string) {
  if (syncStatus === 'error') return 'Sync needs attention';
  if (!lastSyncedAt) return 'Not synced yet';
  const ageMs = Date.now() - parseServerTimestamp(lastSyncedAt);
  if (!Number.isFinite(ageMs)) return syncStatus || 'Unknown';
  const minutes = Math.max(0, Math.floor(ageMs / 60000));
  return minutes < 1 ? 'Synced just now' : `Synced ${minutes}m ago`;
}

const actionButtonClass = 'min-h-8 min-w-[4.5rem] rounded-md border px-3 py-1.5 text-xs font-bold transition-colors disabled:cursor-wait disabled:opacity-50';

export function TournamentOperationsCards() {
  const navigate = useNavigate();
  const {
    tournaments, matches, pinnedTournamentSlugs, currentSlug, currentEventId,
    events, setCurrentSlug, setTournaments, setMatches, removePinnedTournament,
  } = useHubStore();
  const [busySlug, setBusySlug] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const pinned = useMemo(() => pinnedTournamentSlugs
    .map((slug) => tournaments.find((tournament) => tournament.slug === slug))
    .filter((tournament): tournament is NonNullable<typeof tournament> => Boolean(tournament)), [pinnedTournamentSlugs, tournaments]);

  if (!pinned.length) return null;

  const selectTournament = (slug: string) => {
    setCurrentSlug(slug);
  };

  const sync = async (slug: string) => {
    setBusySlug(`sync:${slug}`);
    setMessage(null);
    try {
      await axios.post(`/api/tournaments/${encodeURIComponent(slug)}/sync/bracket`);
      const [tournamentsResponse, matchesResponse] = await Promise.all([axios.get('/api/tournaments'), axios.get('/api/active-matches')]);
      setTournaments(tournamentsResponse.data.tournaments || []);
      setMatches(matchesResponse.data.matches || []);
    } catch (error: any) {
      setMessage(getApiErrorMessage(error, 'Could not synchronize this tournament.'));
    } finally {
      setBusySlug(null);
    }
  };

  const runLifecycle = async (slug: string, name: string, action: 'start' | 'reset') => {
    const prompt = action === 'start'
      ? `Start the ${name} bracket on its provider now?`
      : `Reset match results for ${name} through the provider API now? This clears provider match results and states, then reloads the bracket in aiTOB. It does not reset the provider bracket lifecycle from STARTED to CREATED.`;
    if (!window.confirm(prompt)) return;
    setBusySlug(`${action}:${slug}`);
    setMessage(null);
    try {
      const response = await axios.post(`/api/tournaments/${encodeURIComponent(slug)}/lifecycle`, { action });
      setMessage(response.data.message || `Tournament ${action} requested.`);
      const [tournamentsResponse, matchesResponse] = await Promise.all([axios.get('/api/tournaments'), axios.get('/api/active-matches')]);
      setTournaments(tournamentsResponse.data.tournaments || []);
      setMatches(matchesResponse.data.matches || []);
    } catch (error: any) {
      setMessage(getApiErrorMessage(error, `Could not ${action} this tournament.`));
    } finally {
      setBusySlug(null);
    }
  };

  const editTournament = async (slug: string) => {
    setBusySlug(`edit:${slug}`);
    setMessage(null);
    try {
      const draft = await reopenTournamentSetup(slug);
      navigate(`/admin/tournaments/setup/${encodeURIComponent(draft.id)}/provider`);
    } catch (error: any) {
      setMessage(getApiErrorMessage(error, 'Could not reopen this tournament setup.'));
    } finally {
      setBusySlug(null);
    }
  };

  const setAccent = async (slug: string, accentColor: string) => {
    const previous = tournaments;
    setTournaments(tournaments.map((tournament) => tournament.slug === slug
      ? { ...tournament, accent_color: accentColor }
      : tournament));
    try {
      await axios.patch(`/api/tournaments/${encodeURIComponent(slug)}/settings`, { accent_color: accentColor });
    } catch (error: any) {
      setTournaments(previous);
      setMessage(getApiErrorMessage(error, 'Could not save this tournament colour.'));
    }
  };

  const removeTournament = async (slug: string, name: string) => {
    const confirmed = window.confirm(tournamentRemovalConfirmation(name));
    if (!confirmed) return;
    setBusySlug(`remove:${slug}`);
    setMessage(null);
    try {
      const { tournaments: remaining, matches: refreshedMatches } = await removeTournamentFromHub(slug);
      removePinnedTournament(slug);
      setTournaments(remaining);
      setMatches(refreshedMatches);
      if (currentSlug === slug) setCurrentSlug(remaining[0]?.slug || null);
    } catch (error: any) {
      setMessage(getApiErrorMessage(error, 'Could not remove the tournament.'));
    } finally {
      setBusySlug(null);
    }
  };

  return (
    <section className="bg-cardDark/50 backdrop-blur-md rounded-lg p-4 shadow-md flex flex-col gap-3 border border-white/10 relative z-10">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 pb-2">
        <h2 className="text-accentYellow font-bold text-lg tracking-wide uppercase">Tournament Operations</h2>
        <span className="text-[11px] text-textDim">Select a card to change the Match Dashboard</span>
      </div>
      {message && <p role="alert" className="rounded-lg border border-statusRed/30 bg-statusRed/10 px-3 py-2 text-xs text-statusRed">{message}</p>}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
      {pinned.map((tournament) => {
        const tournamentMatches = matches.filter((match) => match.tournament_slug === tournament.slug);
        const called = tournamentMatches.filter((match) => match.status === 'called').length;
        const ready = tournamentMatches.filter((match) => match.p1_ready && match.p2_ready && match.status !== 'complete').length;
        const live = tournamentMatches.filter((match) => match.status === 'in_progress').length;
        const conflicts = tournamentMatches.filter((match) => match.status === 'conflict').length;
        const isChallonge = tournament.provider_type === 'challonge';
        const accent = tournamentAccent(tournament);
        const selectedEvent = tournament.slug === currentSlug ? events.find((event) => event.id === currentEventId) : null;
        const scopeLabel = isChallonge
          ? 'Challonge · one bracket'
          : selectedEvent
            ? `Start.gg · Event: ${selectedEvent.name}`
            : 'Start.gg · tournament (select to choose event)';
        const isBusy = busySlug?.endsWith(`:${tournament.slug}`);
        return (
          <article
            key={tournament.slug}
            role="button"
            tabIndex={0}
            aria-label={`Open ${tournament.name} in Match Dashboard`}
            onClick={() => selectTournament(tournament.slug)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                selectTournament(tournament.slug);
              }
            }}
            style={{
              borderColor: withAccentAlpha(accent, tournament.slug === currentSlug ? 0.55 : 0.28),
              boxShadow: tournament.slug === currentSlug ? `0 0 0 1px ${withAccentAlpha(accent, 0.14)}` : undefined,
            }}
            className="cursor-pointer rounded-lg border bg-black/15 p-3 transition-colors hover:brightness-110"
          >
            <div className="flex items-start justify-between gap-3 border-b border-white/10 pb-2">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 style={{ color: accent }} className="truncate font-bold text-sm tracking-wide">{tournament.name}</h3>
                  <span style={{ borderColor: withAccentAlpha(accent, 0.45), backgroundColor: withAccentAlpha(accent, 0.12), color: accent }} className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-bold">
                    <img src={isChallonge ? challongeLogo : startGgLogo} alt="" aria-hidden="true" className="h-3.5 w-3.5 object-contain" />
                    {isChallonge ? 'CHALLONGE' : 'START.GG'}
                  </span>
                </div>
                <p className="mt-1 text-xs text-textDim">{scopeLabel} · {freshnessLabel(tournament.provider_last_synced_at, tournament.provider_sync_status)}</p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <input
                  type="color"
                  value={accent}
                  onClick={(event) => event.stopPropagation()}
                  onChange={(event) => void setAccent(tournament.slug, event.target.value)}
                  aria-label={`Set ${tournament.name} colour`}
                  title="Tournament colour"
                  className="h-7 w-7 cursor-pointer rounded border border-white/20 bg-transparent p-0.5"
                />
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    void removeTournament(tournament.slug, tournament.name);
                  }}
                  disabled={isBusy}
                  aria-label={`Remove ${tournament.name} from aiTOB`}
                  title="Remove this tournament from aiTOB"
                  className="rounded-md border border-statusRed/30 px-2 py-1 text-sm font-bold text-statusRed hover:bg-statusRed/10 disabled:opacity-50"
                >
                  ×
                </button>
              </div>
            </div>
            <div className="mt-3 grid grid-cols-4 gap-2 text-center">
              {[['Called', called, 'text-blue-200'], ['Ready', ready, 'text-statusGreen'], ['Live', live, ''], ['Conflicts', conflicts, conflicts ? 'text-statusRed' : 'text-textLight']].map(([label, value, color]) => (
                <div key={String(label)} className="rounded-md bg-black/20 px-2 py-2">
                  <strong style={label === 'Live' ? { color: accent } : undefined} className={`block text-base ${color}`}>{value}</strong>
                  <span className="text-[10px] text-textDim">{label}</span>
                </div>
              ))}
            </div>
            <div className="mt-3 grid grid-cols-4 gap-2">
              <button type="button" onClick={(event) => {
                event.stopPropagation();
                void runLifecycle(tournament.slug, tournament.name, 'start');
              }} disabled={isBusy} title="Start provider bracket" className={`${actionButtonClass} w-full border-statusGreen/30 text-statusGreen hover:bg-statusGreen/10`}>Start</button>
              <button type="button" onClick={(event) => {
                event.stopPropagation();
                void runLifecycle(tournament.slug, tournament.name, 'reset');
              }} disabled={isBusy} title="Reset provider match results" className={`${actionButtonClass} w-full border-amber-300/30 text-amber-200 hover:bg-amber-300/10`}>Reset</button>
              <button type="button" onClick={(event) => {
                event.stopPropagation();
                void sync(tournament.slug);
              }} disabled={isBusy} title="Sync tournament data" className={`${actionButtonClass} w-full border-white/15 text-textLight hover:bg-white/5`}>Sync</button>
              <button type="button" onClick={(event) => {
                event.stopPropagation();
                void editTournament(tournament.slug);
              }} disabled={isBusy} title="Edit tournament setup" className={`${actionButtonClass} w-full border-accentYellow/40 text-accentYellow hover:bg-accentYellow/10`}>Edit</button>
            </div>
          </article>
        );
      })}
      </div>
    </section>
  );
}
