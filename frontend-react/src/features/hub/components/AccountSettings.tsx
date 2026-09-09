import { useEffect, useState } from 'react';
import axios from 'axios';

type Profile = { email: string; display_name: string; role: string; workspace_name: string; mfa_enabled?: boolean };
type Member = { id: string; email: string; display_name: string; role: string; status: string };

export function AccountSettings() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [notice, setNotice] = useState('');
  const [mfaPassword, setMfaPassword] = useState('');
  const [mfaSecret, setMfaSecret] = useState('');
  const [mfaCode, setMfaCode] = useState('');
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('viewer');

  useEffect(() => {
    let alive = true;
    Promise.all([
      axios.get('/api/session'),
      axios.get('/api/workspace/members').catch(() => ({ data: { members: [] } })),
    ]).then(([session, memberResponse]) => {
      if (!alive) return;
      setProfile(session.data);
      setMembers(memberResponse.data.members || []);
    }).catch(() => alive && setNotice('Account settings could not be loaded.'));
    return () => { alive = false; };
  }, []);

  const changePassword = async () => {
    setNotice('');
    try {
      await axios.post('/api/session/password/change', { password: currentPassword, new_password: newPassword });
      setCurrentPassword(''); setNewPassword(''); setNotice('Password updated. Other sessions were revoked.');
    } catch (error) {
      setNotice(axios.isAxiosError(error) ? (error.response?.data?.detail || 'Password update failed.') : 'Password update failed.');
    }
  };

  const beginMfa = async () => {
    try {
      const response = await axios.post('/api/session/mfa/setup', { password: mfaPassword });
      setMfaSecret(response.data.setup_secret); setNotice('Add this secret to your authenticator, then enter its current code.');
    } catch { setNotice('Two-factor setup could not be started.'); }
  };
  const enableMfa = async () => {
    try {
      const response = await axios.post('/api/session/mfa/enable', { setup_secret: mfaSecret, code: mfaCode });
      setRecoveryCodes(response.data.recovery_codes || []); setProfile({ ...profile!, mfa_enabled: true });
      setNotice('Two-factor authentication enabled. Save every recovery code now; they are shown once.');
    } catch { setNotice('The authenticator code was not accepted.'); }
  };
  const inviteMember = async () => {
    try {
      await axios.post('/api/workspace/invitations', { email: inviteEmail, role: inviteRole });
      setInviteEmail(''); setNotice('Invitation created. Email delivery is used when configured.');
    } catch { setNotice('Invitation could not be created.'); }
  };

  if (!profile) return <p className="text-sm text-textDim">{notice || 'Loading account…'}</p>;
  return (
    <div className="space-y-5">
      <section className="rounded-xl border border-white/10 bg-cardDark p-5">
        <h2 className="text-base font-bold text-white">Account & workspace</h2>
        <dl className="mt-4 grid gap-3 text-xs sm:grid-cols-2">
          <div><dt className="text-textDim">Signed in as</dt><dd className="mt-1 font-semibold text-white">{profile.display_name} · {profile.email}</dd></div>
          <div><dt className="text-textDim">Workspace</dt><dd className="mt-1 font-semibold text-white">{profile.workspace_name}</dd></div>
          <div><dt className="text-textDim">Role</dt><dd className="mt-1 font-semibold text-white">{profile.role}</dd></div>
          <div><dt className="text-textDim">Two-factor authentication</dt><dd className="mt-1 font-semibold text-white">{profile.mfa_enabled ? 'Enabled' : 'Not enabled'}</dd></div>
        </dl>
      </section>
      <section className="rounded-xl border border-white/10 bg-cardDark p-5">
        <h2 className="text-base font-bold text-white">Change password</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <input type="password" autoComplete="current-password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} placeholder="Current password" className="rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm text-white" />
          <input type="password" autoComplete="new-password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="New password (10+ characters)" className="rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm text-white" />
        </div>
        <button type="button" onClick={changePassword} disabled={!currentPassword || newPassword.length < 10} className="mt-3 rounded-lg bg-accentYellow px-4 py-2 text-xs font-bold text-black disabled:opacity-40">Update password</button>
        {notice && <p className="mt-3 text-xs text-textDim">{notice}</p>}
      </section>
      {!profile.mfa_enabled && <section className="rounded-xl border border-white/10 bg-cardDark p-5">
        <h2 className="text-base font-bold text-white">Two-factor authentication</h2>
        {!mfaSecret ? <div className="mt-3 flex gap-3"><input type="password" value={mfaPassword} onChange={(e) => setMfaPassword(e.target.value)} placeholder="Confirm your password" className="min-w-0 flex-1 rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm text-white" /><button type="button" onClick={beginMfa} className="rounded-lg border border-accentYellow/50 px-4 py-2 text-xs font-bold text-accentYellow">Begin setup</button></div> : <div className="mt-3 space-y-3"><p className="break-all rounded-lg bg-black/25 p-3 font-mono text-xs text-white">{mfaSecret}</p><div className="flex gap-3"><input inputMode="numeric" value={mfaCode} onChange={(e) => setMfaCode(e.target.value)} placeholder="6-digit code" className="min-w-0 flex-1 rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm text-white" /><button type="button" onClick={enableMfa} className="rounded-lg bg-accentYellow px-4 py-2 text-xs font-bold text-black">Enable 2FA</button></div></div>}
        {recoveryCodes.length > 0 && <div className="mt-4 rounded-lg border border-statusOrange/30 p-3"><p className="text-xs font-bold text-statusOrange">One-use recovery codes</p><div className="mt-2 grid grid-cols-2 gap-1 font-mono text-xs text-white">{recoveryCodes.map((code) => <span key={code}>{code}</span>)}</div></div>}
      </section>}
      {profile.role === 'owner' && <section className="rounded-xl border border-white/10 bg-cardDark p-5">
        <h2 className="text-base font-bold text-white">Workspace members</h2>
        <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_180px_auto]"><input type="email" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} placeholder="Member email" className="rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm text-white" /><select value={inviteRole} onChange={(e) => setInviteRole(e.target.value)} className="rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm text-white"><option value="tournament_organizer">TO</option><option value="stream_operator">Stream operator</option><option value="moderator">Moderator</option><option value="viewer">Viewer</option></select><button type="button" onClick={inviteMember} disabled={!inviteEmail.includes('@')} className="rounded-lg bg-accentYellow px-4 py-2 text-xs font-bold text-black disabled:opacity-40">Invite</button></div>
        <div className="mt-3 space-y-2">{members.map((member) => <div key={member.id} className="flex items-center justify-between rounded-lg border border-white/5 px-3 py-2 text-xs"><span className="text-white">{member.display_name} · {member.email}</span><span className="text-textDim">{member.role} · {member.status}</span></div>)}</div>
      </section>}
    </div>
  );
}
