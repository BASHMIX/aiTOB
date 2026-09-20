import axios from 'axios';

export const tournamentRemovalConfirmation = (name: string) =>
  `Remove “${name}” from aiTOB?\n\nThis disconnects the tournament from aiTOB and deletes its local tracking data. The provider bracket remains unchanged. Provider matches that have not started are removed from local tracking; if an active Hub match prevents removal, the server will show the exact reason.`;

export async function removeTournamentFromHub(slug: string) {
  await axios.delete(`/api/tournaments/${encodeURIComponent(slug)}`);
  const [tournamentsResponse, matchesResponse] = await Promise.all([
    axios.get('/api/tournaments'),
    axios.get('/api/active-matches'),
  ]);
  return {
    tournaments: tournamentsResponse.data.tournaments || [],
    matches: matchesResponse.data.matches || [],
  };
}
