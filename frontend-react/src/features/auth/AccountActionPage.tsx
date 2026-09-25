import { useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import axios from 'axios';

type ActionKind = 'verify' | 'reset' | 'invite' | 'companyInvite';

const copy: Record<ActionKind, { title: string; intro: string; success: string }> = {
  verify: {
    title: 'Verify your aiTOB email',
    intro: 'Confirm this one-time link to mark the account email as verified.',
    success: 'Email verified successfully. You can close this page.',
  },
  reset: {
    title: 'Reset your aiTOB password',
    intro: 'Choose a new password for this account. The link can only be used once.',
    success: 'Password reset successfully. You can sign in with the new password.',
  },
  invite: {
    title: 'Join an aiTOB workspace',
    intro: 'Create the account that will receive the invited workspace role.',
    success: 'Invitation accepted successfully. You can now sign in.',
  },
  companyInvite: {
    title: 'Create your aiTOB workspace',
    intro: 'Accept this private staging invitation to create your company workspace and Owner account.',
    success: 'Workspace created successfully. You can now sign in.',
  },
};

export function AccountActionPage({ kind }: { kind: ActionKind }) {
  const [params] = useSearchParams();
  const token = useMemo(() => params.get('token')?.trim() || '', [params]);
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(kind === 'verify');
  const [done, setDone] = useState(false);
  const [notice, setNotice] = useState('');

  useEffect(() => {
    if (kind !== 'verify') return;
    if (!token) {
      setBusy(false);
      setNotice('This verification link is missing its token.');
      return;
    }
    axios.post('/api/session/email-verification/confirm', { token })
      .then(() => { setDone(true); setNotice(copy[kind].success); })
      .catch((error) => {
        setNotice(error.response?.data?.detail || 'This verification link is invalid or expired.');
      })
      .finally(() => setBusy(false));
  }, [kind, token]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!token) { setNotice('This link is missing its token.'); return; }
    setBusy(true);
    setNotice('');
    try {
      if (kind === 'reset') {
        await axios.post('/api/session/password/reset', { token, new_password: password });
      } else if (kind === 'companyInvite') {
        await axios.post('/api/platform/workspace-invitations/accept', {
          token, password, display_name: displayName,
        });
      } else {
        await axios.post('/api/workspace/invitations/accept', {
          token, password, display_name: displayName,
        });
      }
      setDone(true);
      setNotice(copy[kind].success);
    } catch (error: any) {
      setNotice(error.response?.data?.detail || 'This link is invalid, expired, or already used.');
    } finally {
      setBusy(false);
    }
  };

  const needsForm = kind !== 'verify' && !done;
  return (
    <main className="min-h-screen bg-appDark px-4 py-16 text-white">
      <section className="mx-auto max-w-md rounded-2xl border border-white/10 bg-cardDark p-6 shadow-2xl">
        <p className="text-[10px] font-bold uppercase tracking-[0.25em] text-accentYellow">aiTOB</p>
        <h1 className="mt-3 text-2xl font-bold">{copy[kind].title}</h1>
        <p className="mt-2 text-sm text-textDim">{copy[kind].intro}</p>
        {needsForm && (
          <form className="mt-6 space-y-4" onSubmit={submit}>
            {(kind === 'invite' || kind === 'companyInvite') && (
              <label className="block text-sm text-textDim">
                Display name
                <input required minLength={1} maxLength={120} value={displayName} onChange={(e) => setDisplayName(e.target.value)} className="mt-1 w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-white" />
              </label>
            )}
            <label className="block text-sm text-textDim">
              {kind === 'invite' || kind === 'companyInvite' ? 'Account password' : 'New password'}
              <input required minLength={10} type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="mt-1 w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-white" />
            </label>
            <button disabled={busy} type="submit" className="w-full rounded-lg bg-accentYellow px-4 py-2 text-sm font-bold text-black disabled:opacity-50">
              {busy ? 'Working…' : kind === 'invite' || kind === 'companyInvite' ? 'Accept invitation' : 'Reset password'}
            </button>
          </form>
        )}
        {kind === 'verify' && busy && <p className="mt-6 text-sm text-textDim">Confirming your link…</p>}
        {notice && <p className={`mt-5 rounded-lg border px-3 py-2 text-sm ${done ? 'border-statusGreen/40 text-statusGreen' : 'border-statusOrange/40 text-statusOrange'}`}>{notice}</p>}
        {!token && !notice && <p className="mt-5 text-sm text-statusOrange">This link is missing its token.</p>}
      </section>
    </main>
  );
}
