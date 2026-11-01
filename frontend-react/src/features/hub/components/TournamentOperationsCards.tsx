import { useMemo, useState, useRef } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { useHubStore } from '@/store/useHubStore';
import startGgLogo from '@/assets/Start.gg.svg';
import challongeLogo from '@/assets/challonge-logo.svg';
import { tournamentAccent, eventAccent, saveEventAccent, withAccentAlpha, useEventAccentWatcher } from './tournamentAccent';
import { removeTournamentFromHub, tournamentRemovalConfirmation } from '../tournamentRemoval';
import { getApiErrorMessage, reopenTournamentSetup } from '@/features/tournament-setup/api';
import { usePermission } from '@/hooks/usePermission';

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

const actionButtonClass = 'min-h-8 min-w-[4.5rem] rounded-md border px-2.5 py-1 text-xs font-bold transition-colors disabled:cursor-wait disabled:opacity-50';

interface ProjectedCard {
  key: string;
  tournament: any;
  eventId: string | null;
  eventName: string;
  gameName: string;
  isMultiEvent: boolean;
  accent: string;
}

export function TournamentOperationsCards() {
  const canManageTournaments = usePermission('tournament.manage');
  const navigate = useNavigate();
  const scrollRef = useRef<HTMLDivElement>(null);
  const {
    tournaments, matches, pinnedTournamentSlugs, currentSlug, currentEventId,
    setCurrentSlug, setTournaments, setMatches, removePinnedTournament, selectTournamentEvent,
  } = useHubStore();
  const [busySlug, setBusySlug] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [colorVersion, setColorVersion] = useState(0);
  const accentWatcher = useEventAccentWatcher();

  const pinned = useMemo(() => pinnedTournamentSlugs
    .map((slug) => tournaments.find((tournament) => tournament.slug === slug))
    .filter((tournament): tournament is NonNullable<typeof tournament> => Boolean(tournament)), [pinnedTournamentSlugs, tournaments]);

  const projectedCards = useMemo<ProjectedCard[]>(() => {
    const list: ProjectedCard[] = [];
    for (const tournament of pinned) {
      const isChallonge = tournament.provider_type === 'challonge';
      const accent = tournamentAccent(tournament);
      if (isChallonge) {
        list.push({
          key: tournament.slug,
          tournament,
          eventId: null,
          eventName: tournament.name,
          gameName: tournament.game || 'Challonge Bracket',
          isMultiEvent: false,
          accent,
        });
        continue;
      }

      let parsedEvents: Array<{ id: string | number; name: string; videogame?: { name?: string } }> = [];
      try {
        if (tournament.raw_data) {
          const parsed = typeof tournament.raw_data === 'string' ? JSON.parse(tournament.raw_data) : tournament.raw_data;
          if (Array.isArray(parsed?.events)) {
            parsedEvents = parsed.events;
          }
        }
      } catch {
        // fallback
      }

      if (parsedEvents.length > 1) {
        parsedEvents.forEach((ev, idx) => {
          list.push({
            key: `${tournament.slug}::${ev.id}`,
            tournament,
            eventId: String(ev.id),
            eventName: ev.name,
            gameName: ev.videogame?.name || tournament.game || 'Tournament Event',
            isMultiEvent: true,
            accent: eventAccent(tournament, String(ev.id), idx),
          });
        });
      } else if (parsedEvents.length === 1) {
        list.push({
          key: `${tournament.slug}::${parsedEvents[0].id}`,
          tournament,
          eventId: String(parsedEvents[0].id),
          eventName: parsedEvents[0].name || tournament.name,
          gameName: parsedEvents[0].videogame?.name || tournament.game || 'Tournament Event',
          isMultiEvent: false,
          accent: eventAccent(tournament, String(parsedEvents[0].id), 0),
        });
      } else {
        list.push({
          key: tournament.slug,
          tournament,
          eventId: tournament.event_id || null,
          eventName: tournament.name,
          gameName: tournament.game || 'Tournament',
          isMultiEvent: false,
          accent: tournamentAccent(tournament),
        });
      }
    }
    return list;
  }, [pinned, colorVersion, accentWatcher]);

  if (!projectedCards.length) return null;

  const selectCard = (card: ProjectedCard) => {
    if (selectTournamentEvent) {
      selectTournamentEvent(card.tournament.slug, card.eventId);
    } else {
      setCurrentSlug(card.tournament.slug);
    }
  };

  const scrollLeft = () => {
    scrollRef.current?.scrollBy({ left: -360, behavior: 'smooth' });
  };

  const scrollRight = () => {
    scrollRef.current?.scrollBy({ left: 360, behavior: 'smooth' });
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

  const handleColorChange = async (card: ProjectedCard, newColor: string) => {
    if (card.eventId) {
      saveEventAccent(card.eventId, newColor);
      setColorVersion((v) => v + 1);
    }
    if (!card.isMultiEvent || !card.eventId) {
      await setAccent(card.tournament.slug, newColor);
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
        <div className="flex items-center gap-3">
          <h2 className="text-accentYellow font-bold text-lg tracking-wide uppercase">Tournament Operations</h2>
          <span className="text-[11px] text-textDim hidden sm:inline">Select an event card to change Match Dashboard focus</span>
        </div>
        <div className="flex items-center gap-2">
          {projectedCards.length > 2 && (
            <div className="flex items-center gap-1 bg-black/30 p-1 rounded-md border border-white/10">
              <button
                type="button"
                onClick={scrollLeft}
                className="p-1 rounded text-textDim hover:text-white hover:bg-white/10 transition-colors"
                title="Scroll Left"
                aria-label="Scroll Left"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M15 19l-7-7 7-7" />
                </svg>
              </button>
              <button
                type="button"
                onClick={scrollRight}
                className="p-1 rounded text-textDim hover:text-white hover:bg-white/10 transition-colors"
                title="Scroll Right"
                aria-label="Scroll Right"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M9 5l7 7-7 7" />
                </svg>
              </button>
            </div>
          )}
        </div>
      </div>

      {message && <p role="alert" className="rounded-lg border border-statusRed/30 bg-statusRed/10 px-3 py-2 text-xs text-statusRed">{message}</p>}

      <div
        ref={scrollRef}
        className="flex items-stretch gap-3.5 overflow-x-auto pb-2 scrollbar-none [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden snap-x scroll-smooth"
      >
        {projectedCards.map((card) => {
          const cardMatches = matches.filter((match) => {
            if (match.tournament_slug !== card.tournament.slug) return false;
            if (card.eventId && match.event_id && String(match.event_id) !== String(card.eventId)) return false;
            return true;
          });
          const called = cardMatches.filter((match) => match.status === 'called').length;
          const ready = cardMatches.filter((match) => match.p1_ready && match.p2_ready && match.status !== 'complete').length;
          const live = cardMatches.filter((match) => match.status === 'in_progress').length;
          const conflicts = cardMatches.filter((match) => match.status === 'conflict').length;
          const isChallonge = card.tournament.provider_type === 'challonge';
          const isBusy = busySlug?.endsWith(`:${card.tournament.slug}`);

          const isSelected = card.tournament.slug === currentSlug &&
            (card.eventId ? String(card.eventId) === String(currentEventId) : !currentEventId);

          return (
            <article
              key={card.key}
              role="button"
              tabIndex={0}
              aria-label={`Open ${card.eventName} in Match Dashboard`}
              onClick={() => selectCard(card)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  selectCard(card);
                }
              }}
              style={{
                borderColor: withAccentAlpha(card.accent, isSelected ? 0.75 : 0.25),
                boxShadow: isSelected ? `0 0 16px ${withAccentAlpha(card.accent, 0.25)}, inset 0 0 0 1px ${withAccentAlpha(card.accent, 0.35)}` : undefined,
              }}
              className={`min-w-[320px] sm:min-w-[350px] max-w-[380px] shrink-0 snap-start flex flex-col justify-between cursor-pointer rounded-lg border bg-black/25 p-3.5 transition-all duration-200 hover:brightness-110 hover:border-white/30 ${
                isSelected ? 'bg-black/40 ring-1 ring-white/10' : ''
              }`}
            >
              <div>
                <div className="flex items-start justify-between gap-3 border-b border-white/10 pb-2.5">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5 flex-wrap mb-1">
                      <span className="text-[11px] font-black tracking-wider uppercase text-white bg-white/10 px-2 py-0.5 rounded border border-white/15">
                        🎮 {card.gameName}
                      </span>
                      {card.isMultiEvent && (
                        <span className="text-[10px] font-bold text-accentYellow/90 bg-accentYellow/10 px-1.5 py-0.5 rounded border border-accentYellow/30">
                          EVENT
                        </span>
                      )}
                      <span
                        style={{ borderColor: withAccentAlpha(card.accent, 0.45), backgroundColor: withAccentAlpha(card.accent, 0.12), color: card.accent }}
                        className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-bold ml-auto"
                      >
                        <img src={isChallonge ? challongeLogo : startGgLogo} alt="" aria-hidden="true" className="h-3 w-3 object-contain" />
                        {isChallonge ? 'CHALLONGE' : 'START.GG'}
                      </span>
                    </div>

                    <h3 style={{ color: card.accent }} className="truncate font-bold text-base tracking-wide mt-1">
                      {card.eventName}
                    </h3>

                    <p className="mt-1 text-xs text-textDim flex items-center gap-1.5 truncate">
                      <span className="font-medium text-textLight">{card.tournament.name}</span>
                      <span>·</span>
                      <span>{freshnessLabel(card.tournament.provider_last_synced_at, card.tournament.provider_sync_status)}</span>
                    </p>

                    {isSelected && (
                      <div className="mt-1.5 flex items-center gap-1.5 text-[10px] font-bold text-statusGreen">
                        <span className="relative flex h-2 w-2">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-statusGreen opacity-75"></span>
                          <span className="relative inline-flex rounded-full h-2 w-2 bg-statusGreen"></span>
                        </span>
                        <span>Active in Match Dashboard</span>
                      </div>
                    )}
                  </div>

                  {canManageTournaments && (
                    <div className="flex shrink-0 items-center gap-1.5">
                      <input
                        type="color"
                        value={card.accent}
                        onClick={(event) => event.stopPropagation()}
                        onChange={(event) => void handleColorChange(card, event.target.value)}
                        aria-label={`Set ${card.eventName} colour`}
                        title="Event colour"
                        className="h-6 w-6 cursor-pointer rounded border border-white/20 bg-transparent p-0.5"
                      />
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          void removeTournament(card.tournament.slug, card.tournament.name);
                        }}
                        disabled={isBusy}
                        aria-label={`Remove ${card.tournament.name} from aiTOB`}
                        title="Remove this tournament from aiTOB"
                        className="rounded-md border border-statusRed/30 px-1.5 py-0.5 text-xs font-bold text-statusRed hover:bg-statusRed/10 disabled:opacity-50"
                      >
                        ×
                      </button>
                    </div>
                  )}
                </div>

                <div className="mt-3 grid grid-cols-4 gap-2 text-center">
                  {[['Called', called, 'text-blue-200'], ['Ready', ready, 'text-statusGreen'], ['Live', live, ''], ['Conflicts', conflicts, conflicts ? 'text-statusRed' : 'text-textLight']].map(([label, value, color]) => (
                    <div key={String(label)} className="rounded-md bg-black/25 px-2 py-1.5">
                      <strong style={label === 'Live' ? { color: card.accent } : undefined} className={`block text-base ${color}`}>{value}</strong>
                      <span className="text-[10px] text-textDim">{label}</span>
                    </div>
                  ))}
                </div>
              </div>

              {canManageTournaments && (
                <div className="mt-3 grid grid-cols-4 gap-1.5 pt-2 border-t border-white/5">
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      void runLifecycle(card.tournament.slug, card.tournament.name, 'start');
                    }}
                    disabled={isBusy}
                    title="Start provider bracket"
                    className={`${actionButtonClass} w-full border-statusGreen/30 text-statusGreen hover:bg-statusGreen/10`}
                  >
                    Start
                  </button>
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      void runLifecycle(card.tournament.slug, card.tournament.name, 'reset');
                    }}
                    disabled={isBusy}
                    title="Reset provider match results"
                    className={`${actionButtonClass} w-full border-amber-300/30 text-amber-200 hover:bg-amber-300/10`}
                  >
                    Reset
                  </button>
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      void sync(card.tournament.slug);
                    }}
                    disabled={isBusy}
                    title="Sync tournament data"
                    className={`${actionButtonClass} w-full border-white/15 text-textLight hover:bg-white/5`}
                  >
                    Sync
                  </button>
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      void editTournament(card.tournament.slug);
                    }}
                    disabled={isBusy}
                    title="Edit tournament setup"
                    className={`${actionButtonClass} w-full border-accentYellow/40 text-accentYellow hover:bg-accentYellow/10`}
                  >
                    Edit
                  </button>
                </div>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}
