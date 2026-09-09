import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { useHubStore } from '@/store/useHubStore';

type Proposal = {
  id: string; action_type: 'call' | 'announcement_draft'; match_id?: string | null;
  reason: string; payload_json: string; approval_status: string; execution_status: string;
  expires_at: string; approved_by?: string | null; execution_error?: string | null;
};

export function ActionProposalReview({ tournamentSlug }: { tournamentSlug: string }) {
  const { matches } = useHubStore();
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [action, setAction] = useState<'call' | 'announcement_draft'>('call');
  const [matchId, setMatchId] = useState('');
  const [reason, setReason] = useState('');
  const [announcement, setAnnouncement] = useState('');
  const [busy, setBusy] = useState(false);
  const candidates = useMemo(() => matches.filter((match) => match.tournament_slug === tournamentSlug), [matches, tournamentSlug]);

  const refresh = async () => {
    const response = await axios.get('/api/action-proposals', { params: { tournament_slug: tournamentSlug } });
    setProposals(response.data.proposals || []);
  };
  useEffect(() => { void refresh(); }, [tournamentSlug]);

  const create = async () => {
    setBusy(true);
    try {
      await axios.post('/api/action-proposals', {
        tournament_slug: tournamentSlug, action_type: action,
        match_id: action === 'call' ? matchId : undefined,
        payload: action === 'announcement_draft' ? { text: announcement } : {}, reason,
      });
      setReason(''); setAnnouncement(''); await refresh();
    } catch (error) {
      alert(axios.isAxiosError(error) ? (error.response?.data?.message || 'Could not create proposal') : 'Could not create proposal');
    } finally { setBusy(false); }
  };
  const review = async (proposal: Proposal, outcome: 'approve' | 'reject') => {
    setBusy(true);
    try {
      await axios.post(`/api/action-proposals/${proposal.id}/${outcome}`, outcome === 'reject' ? { reason: 'Rejected by organizer' } : {});
      await refresh();
    } finally { setBusy(false); }
  };

  return <section className="mt-5 overflow-hidden rounded-xl border border-white/10 bg-cardDark shadow-sm">
    <header className="border-b border-white/10 px-5 py-4">
      <h2 className="text-base font-bold tracking-wide text-white">Action proposals</h2>
      <p className="mt-1 text-xs text-textDim">Reviewable organizer intent only. The Assistant cannot approve, Call, or announce from here.</p>
    </header>
    <div className="space-y-3 p-5">
      <div className="grid gap-2 md:grid-cols-[170px_1fr]">
        <select value={action} onChange={(e) => setAction(e.target.value as typeof action)} className="rounded bg-black/40 px-3 py-2 text-sm text-white">
          <option value="call">Propose Call</option><option value="announcement_draft">Announcement draft</option>
        </select>
        {action === 'call' ? <select value={matchId} onChange={(e) => setMatchId(e.target.value)} className="rounded bg-black/40 px-3 py-2 text-sm text-white">
          <option value="">Select a match…</option>
          {candidates.map((match) => <option key={match.set_id} value={match.set_id}>{match.p1_name} vs {match.p2_name} · {match.round_name}</option>)}
        </select> : <input value={announcement} onChange={(e) => setAnnouncement(e.target.value)} placeholder="Announcement draft" className="rounded bg-black/40 px-3 py-2 text-sm text-white" />}
      </div>
      <div className="flex gap-2"><input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why is this needed?" className="min-w-0 flex-1 rounded bg-black/40 px-3 py-2 text-sm text-white" />
        <button disabled={busy || !reason || (action === 'call' ? !matchId : !announcement)} onClick={create} className="rounded bg-accentYellow px-3 py-2 text-xs font-bold text-black disabled:opacity-40">Create proposal</button></div>
      <p className="text-[11px] text-textDim">Approval re-checks match state and permissions. A changed or expired proposal returns to review; approval does not prove delivery.</p>
      <div className="space-y-2 border-t border-white/10 pt-3">
        {proposals.length === 0 && <p className="text-xs text-textDim">No proposals for this tournament.</p>}
        {proposals.map((proposal) => <article key={proposal.id} className="rounded-lg border border-white/10 bg-black/20 p-3 text-xs">
          <div className="flex flex-wrap items-center justify-between gap-2"><strong className="text-white">{proposal.action_type === 'call' ? 'Call' : 'Announcement draft'} {proposal.match_id ? `· ${proposal.match_id}` : ''}</strong><span className="font-mono text-textDim">{proposal.approval_status} · {proposal.execution_status}</span></div>
          <p className="mt-1 text-textDim">Reason: {proposal.reason} · Expires: {new Date(proposal.expires_at).toLocaleString()}</p>
          {proposal.execution_error && <p className="mt-1 text-statusRed">Execution: {proposal.execution_error}</p>}
          {proposal.approval_status === 'pending' && <div className="mt-2 flex gap-2"><button disabled={busy} onClick={() => review(proposal, 'approve')} className="rounded bg-statusGreen/20 px-2 py-1 font-bold text-green-200">Approve</button><button disabled={busy} onClick={() => review(proposal, 'reject')} className="rounded bg-statusRed/20 px-2 py-1 font-bold text-red-200">Reject</button></div>}
        </article>)}
      </div>
    </div>
  </section>;
}
