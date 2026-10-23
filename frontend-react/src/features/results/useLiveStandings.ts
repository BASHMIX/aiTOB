import { useState, useEffect } from 'react';
import type { StandingEntrySnapshot } from '@/scene/types';
import { MOCK_DATASETS } from './mockData';

export function deriveStandingsFromBracketTree(bracketTree: any): StandingEntrySnapshot[] {
  if (!bracketTree || !bracketTree.matches) return [];

  const matches = bracketTree.matches;
  const entries: StandingEntrySnapshot[] = [];

  const createEntry = (
    player: any,
    placement: number,
    ordinal: number,
    isTied: boolean
  ): StandingEntrySnapshot => {
    const rawName = player?.name || `Player ${ordinal}`;
    const prefix = player?.prefix || null;
    const country = player?.country || null;
    const avatar = player?.avatar_url || null;
    const characterName = player?.character || null;
    const characterUrl = player?.character_url || null;

    return {
      ordinal,
      placement,
      entrant_id: String(player?.id || `bracket-p-${ordinal}`),
      entrant_name: rawName,
      is_tied: isTied,
      presentation: {
        display_name: { value: rawName, source: 'provider_snapshot' },
        prefix: { value: prefix, source: 'provider_snapshot' },
        country: { value: country, source: 'provider_snapshot' },
        avatar_url: { value: avatar, source: 'provider_snapshot' },
        character: {
          value: { id: null, name: characterName, image_url: characterUrl },
          source: 'placeholder',
        },
      },
    };
  };

  const getWinnerAndLoser = (m: any) => {
    if (!m) return { winner: null, loser: null };
    const p1 = m.p1;
    const p2 = m.p2;
    const isP1Winner = (m.winner_id && String(m.winner_id) === String(p1?.id)) || Boolean(p1?.is_winner);
    const isP2Winner = (m.winner_id && String(m.winner_id) === String(p2?.id)) || Boolean(p2?.is_winner);
    if (isP1Winner) return { winner: p1, loser: p2 };
    if (isP2Winner) return { winner: p2, loser: p1 };
    return { winner: p1, loser: p2 };
  };

  // Grand Finals: winner is 1st, loser is 2nd
  const gf = matches.grand_finals_reset || matches.grand_finals;
  if (gf) {
    const { winner, loser } = getWinnerAndLoser(gf);
    if (winner?.name) entries.push(createEntry(winner, 1, 1, false));
    if (loser?.name && (!winner?.name || loser.name !== winner.name)) {
      entries.push(createEntry(loser, 2, 2, false));
    }
  }

  // Losers Finals: loser is 3rd
  const lf = matches.losers_finals;
  if (lf) {
    const { loser } = getWinnerAndLoser(lf);
    if (loser?.name && !entries.some((e) => e.entrant_name === loser.name)) {
      entries.push(createEntry(loser, 3, 3, false));
    }
  }

  // Losers Semis: loser is 4th
  const lsf = matches.losers_semis;
  if (lsf) {
    const { loser } = getWinnerAndLoser(lsf);
    if (loser?.name && !entries.some((e) => e.entrant_name === loser.name)) {
      entries.push(createEntry(loser, 4, 4, false));
    }
  }

  // Losers Quarters: losers are tied 5th
  const lqf = matches.losers_quarters || [];
  const lqfMatches = Array.isArray(lqf) ? lqf : [lqf];
  lqfMatches.forEach((m: any, idx: number) => {
    const { loser } = getWinnerAndLoser(m);
    if (loser?.name && !entries.some((e) => e.entrant_name === loser.name)) {
      entries.push(createEntry(loser, 5, 5 + idx, true));
    }
  });

  // Losers Round 1: losers are tied 7th
  const lr1 = matches.losers_round1 || [];
  const lr1Matches = Array.isArray(lr1) ? lr1 : [lr1];
  lr1Matches.forEach((m: any, idx: number) => {
    const { loser } = getWinnerAndLoser(m);
    if (loser?.name && !entries.some((e) => e.entrant_name === loser.name)) {
      entries.push(createEntry(loser, 7, 7 + idx, true));
    }
  });

  return entries.sort((a, b) => a.ordinal - b.ordinal);
}

export function useLiveStandings(
  tournamentSlug: string | null | undefined,
  eventId: string | null | undefined,
  isTestMode = false,
  datasetKey: string = 'normal'
) {
  const [standings, setStandings] = useState<StandingEntrySnapshot[]>(() => {
    if (datasetKey === 'demo_preview') return MOCK_DATASETS.normal;
    if (datasetKey === 'normal' || datasetKey === 'live') {
      return (!tournamentSlug) ? MOCK_DATASETS.normal : [];
    }
    return MOCK_DATASETS[datasetKey] || MOCK_DATASETS.normal;
  });
  const [isLive, setIsLive] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isTestMode || (datasetKey !== 'live' && datasetKey !== 'normal')) {
      if (datasetKey === 'demo_preview') {
        setStandings(MOCK_DATASETS.normal);
      } else {
        setStandings(MOCK_DATASETS[datasetKey] || MOCK_DATASETS.normal);
      }
      setIsLive(false);
      setLoading(false);
      return;
    }

    if (!tournamentSlug) {
      setStandings(MOCK_DATASETS[datasetKey] || MOCK_DATASETS.normal);
      setIsLive(false);
      return;
    }

    let cancelled = false;
    setLoading(true);

    const fetchLive = async () => {
      try {
        // 1. Try results/latest
        const effEvent = eventId || 'primary';
        const resLatest = await fetch(
          `/api/tournaments/${encodeURIComponent(tournamentSlug)}/events/${encodeURIComponent(effEvent)}/results/latest`
        );
        if (resLatest.ok) {
          const data = await resLatest.json();
          if (!cancelled && data.entries && data.entries.length > 0) {
            setStandings(data.entries);
            setIsLive(true);
            setLoading(false);
            return;
          }
        }

        // 2. Fallback to bracket-tree auto-derivation
        const params = new URLSearchParams();
        if (eventId) params.set('event_id', eventId);
        const q = params.toString() ? `?${params.toString()}` : '';
        const resTree = await fetch(
          `/api/tournaments/${encodeURIComponent(tournamentSlug)}/bracket-tree${q}`
        );
        if (resTree.ok) {
          const treeData = await resTree.json();
          const derived = deriveStandingsFromBracketTree(treeData);
          if (!cancelled && derived.length > 0) {
            setStandings(derived);
            setIsLive(true);
            setLoading(false);
            return;
          }
        }

        // 3. Fallback to default mock only if completely empty
        if (!cancelled) {
          setStandings((prev) => (prev.length > 0 ? prev : MOCK_DATASETS.normal));
          setIsLive(false);
        }
      } catch {
        if (!cancelled) {
          setStandings((prev) => (prev.length > 0 ? prev : MOCK_DATASETS.normal));
          setIsLive(false);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchLive();
    const interval = setInterval(fetchLive, 30000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [tournamentSlug, eventId, isTestMode, datasetKey]);

  return { standings, isLive, loading };
}
