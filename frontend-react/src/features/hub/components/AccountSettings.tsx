import { useEffect, useState } from 'react';
import axios from 'axios';

type Profile = { email: string; display_name: string; role: string; workspace_id: string; workspace_name: string; mfa_enabled?: boolean };
type Subscription = { plan_key: string; status: string; billing_state: string; expires_at?: string | null };
type Member = { id: string; email: string; display_name: string; role: string; status: string };
type Invitation = { id: string; email: string; role: string; expires_at: string; accepted_at?: string | null; cancelled_at?: string | null };

export function AccountSettings() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [profileName, setProfileName] = useState('');
  const [workspaceName, setWorkspaceName] = useState('');
  const [profileBusy, setProfileBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [mfaPassword, setMfaPassword] = useState('');
  const [mfaSecret, setMfaSecret] = useState('');
  const [mfaCode, setMfaCode] = useState('');
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('viewer');
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [subscriptionBusy, setSubscriptionBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    Promise.all([
      axios.get('/api/session'),
      axios.get('/api/workspace/members').catch(() => ({ data: { members: [] } })),
      axios.get('/api/workspace/invitations').catch(() => ({ data: { invitations: [] } })),
    ]).then(([session, memberResponse, invitationResponse]) => {
      if (!alive) return;
      setProfile(session.data);
      setProfileName(session.data.display_name || '');
      setWorkspaceName(session.data.workspace_name || '');
      setMembers(memberResponse.data.members || []);
      setInvitations(invitationResponse.data.invitations || []);
      axios.get(`/api/platform/workspaces/${encodeURIComponent(session.data.workspace_id)}/subscription`)
        .then((response) => alive && setSubscription(response.data))
        .catch(() => { /* only platform administrators can see this panel */ });
    }).catch(() => alive && setNotice('Account settings could not be loaded.'));
    return () => { alive = false; };
  }, []);

  const saveProfile = async () => {
    if (!profile || profileBusy) return;
    const displayChanged = profileName.trim() !== profile.display_name;
    const workspaceChanged = workspaceName.trim() !== profile.workspace_name;
    if (!displayChanged && !workspaceChanged) {
      setNotice('No profile changes to save.');
      return;
    }
    setProfileBusy(true); setNotice('');
    try {
      const response = await axios.patch('/api/session/profile', {
        ...(displayChanged ? { display_name: profileName.trim() } : {}),
        ...(workspaceChanged && profile.role === 'owner' ? { workspace_name: workspaceName.trim() } : {}),
      });
      setProfile(response.data);
      setProfileName(response.data.display_name || '');
      setWorkspaceName(response.data.workspace_name || '');
      setNotice('Profile updated.');
    } catch (error) {
      setNotice(axios.isAxiosError(error) ? (error.response?.data?.detail || 'Profile update failed.') : 'Profile update failed.');
    } finally { setProfileBusy(false); }
  };

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
      const response = await axios.get('/api/workspace/invitations');
      setInvitations(response.data.invitations || []);
      setInviteEmail(''); setNotice('Invitation created. Email delivery is used when configured.');
    } catch { setNotice('Invitation could not be created.'); }
  };
  const cancelInvitation = async (invitation: Invitation) => {
    if (!window.confirm(`Cancel the invitation for ${invitation.email}?`)) return;
    try {
      await axios.delete(`/api/workspace/invitations/${encodeURIComponent(invitation.id)}`);
      setInvitations((current) => current.map((item) => item.id === invitation.id ? { ...item, cancelled_at: new Date().toISOString() } : item));
      setNotice(`Invitation cancelled for ${invitation.email}.`);
    } catch (error) {
      setNotice(axios.isAxiosError(error) ? (error.response?.data?.detail || 'Invitation could not be cancelled.') : 'Invitation could not be cancelled.');
    }
  };
  const changeMemberRole = async (member: Member, role: string) => {
    if (role === member.role) return;
    try {
      await axios.put(`/api/workspace/members/${encodeURIComponent(member.id)}/role`, { role });
      setMembers((current) => current.map((item) => item.id === member.id ? { ...item, role } : item));
      setNotice(`Role updated for ${member.email}.`);
    } catch (error) {
      setNotice(axios.isAxiosError(error) ? (error.response?.data?.detail || 'Role update failed.') : 'Role update failed.');
    }
  };
  const disableMember = async (member: Member) => {
    if (!window.confirm(`Disable ${member.email}'s workspace access?`)) return;
    try {
      await axios.delete(`/api/workspace/members/${encodeURIComponent(member.id)}`);
      setMembers((current) => current.map((item) => item.id === member.id ? { ...item, status: 'disabled' } : item));
      setNotice(`Workspace access disabled for ${member.email}.`);
    } catch (error) {
      setNotice(axios.isAxiosError(error) ? (error.response?.data?.detail || 'Member could not be disabled.') : 'Member could not be disabled.');
    }
  };

  const updateSubscription = async (action: 'activate' | 'extend' | 'suspend') => {
    if (!profile || subscriptionBusy) return;
    setSubscriptionBusy(true); setNotice('');
    try {
      const payload = action === 'activate'
        ? { action, plan_key: 'managed', expires_at: new Date(Date.now() + 30 * 86400000).toISOString() }
        : action === 'extend' ? { action, extend_days: 30 } : { action };
      const response = await axios.post(`/api/platform/workspaces/${encodeURIComponent(profile.workspace_id)}/subscription`, payload);
      setSubscription(response.data);
      setNotice(`Subscription ${action}d.`);
    } catch (error) {
      setNotice(axios.isAxiosError(error) ? (error.response?.data?.detail || 'Subscription update failed.') : 'Subscription update failed.');
    } finally { setSubscriptionBusy(false); }
  };

  if (!profile) return <p className="text-sm text-textDim">{notice || 'Loading account…'}</p>;
  return (
    <div className="space-y-5">
      <section className="rounded-xl border border-white/10 bg-cardDark p-5">
        <h2 className="text-base font-bold text-white">Account & workspace</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <label className="space-y-1.5"><span className="text-[10px] font-mono uppercase tracking-wider text-textDim">Display name</span><input value={profileName} onChange={(event) => setProfileName(event.target.value)} maxLength={120} className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm text-white" /></label>
          <label className="space-y-1.5"><span className="text-[10px] font-mono uppercase tracking-wider text-textDim">Workspace name {profile.role !== 'owner' && <span>(Owner only)</span>}</span><input value={workspaceName} onChange={(event) => setWorkspaceName(event.target.value)} disabled={profile.role !== 'owner'} maxLength={120} className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm text-white disabled:cursor-not-allowed disabled:opacity-50" /></label>
        </div>
        <button type="button" onClick={saveProfile} disabled={profileBusy || !profileName.trim() || (profile.role === 'owner' && !workspaceName.trim())} className="mt-3 rounded-lg border border-accentYellow/50 px-4 py-2 text-xs font-bold text-accentYellow disabled:cursor-not-allowed disabled:opacity-40">{profileBusy ? 'Saving…' : 'Save profile'}</button>
        <dl className="mt-4 grid gap-3 text-xs sm:grid-cols-2">
          <div><dt className="text-textDim">Signed in as</dt><dd className="mt-1 font-semibold text-white">{profile.display_name} · {profile.email}</dd></div>
          <div><dt className="text-textDim">Workspace</dt><dd className="mt-1 font-semibold text-white">{profile.workspace_name}</dd></div>
          <div><dt className="text-textDim">Role</dt><dd className="mt-1 font-semibold text-white">{profile.role}</dd></div>
          <div><dt className="text-textDim">Two-factor authentication</dt><dd className="mt-1 font-semibold text-white">{profile.mfa_enabled ? 'Enabled' : 'Not enabled'}</dd></div>
        </dl>
      </section>
      {subscription && <section className="rounded-xl border border-white/10 bg-cardDark p-5">
        <h2 className="text-base font-bold text-white">Manual workspace activation</h2>
        <p className="mt-1 text-xs text-textDim">Platform-admin control only · no payment or checkout is performed.</p>
        <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-3"><div><dt className="text-textDim">Plan</dt><dd className="font-semibold text-white">{subscription.plan_key}</dd></div><div><dt className="text-textDim">Status</dt><dd className="font-semibold text-white">{subscription.status}</dd></div><div><dt className="text-textDim">Expiry</dt><dd className="font-semibold text-white">{subscription.expires_at ? new Date(subscription.expires_at).toLocaleString() : 'None'}</dd></div></dl>
        <div className="mt-3 flex flex-wrap gap-2"><button type="button" disabled={subscriptionBusy} onClick={() => updateSubscription('activate')} className="rounded-lg bg-accentYellow px-3 py-2 text-xs font-bold text-black disabled:opacity-40">Activate managed</button><button type="button" disabled={subscriptionBusy} onClick={() => updateSubscription('extend')} className="rounded-lg border border-accentYellow/50 px-3 py-2 text-xs font-bold text-accentYellow disabled:opacity-40">Extend 30 days</button><button type="button" disabled={subscriptionBusy} onClick={() => updateSubscription('suspend')} className="rounded-lg border border-statusRed/40 px-3 py-2 text-xs font-bold text-statusRed disabled:opacity-40">Suspend</button></div>
      </section>}
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
        <div className="mt-3 space-y-2">{members.map((member) => <div key={member.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-white/5 px-3 py-2 text-xs"><span className="text-white">{member.display_name} · {member.email}</span><div className="flex items-center gap-2"><select aria-label={`Role for ${member.email}`} value={member.role} disabled={member.role === 'owner' || member.status !== 'active'} onChange={(e) => changeMemberRole(member, e.target.value)} className="rounded border border-white/10 bg-black/20 px-2 py-1 text-textDim"><option value="owner">Owner</option><option value="tournament_organizer">TO</option><option value="stream_operator">Stream operator</option><option value="moderator">Moderator</option><option value="viewer">Viewer</option></select><span className="text-textDim">{member.status}</span>{member.role !== 'owner' && member.status === 'active' && <button type="button" onClick={() => disableMember(member)} className="rounded border border-statusRed/40 px-2 py-1 text-statusRed">Disable</button>}</div></div>)}</div>
        <div className="mt-5 border-t border-white/10 pt-4"><h3 className="text-xs font-bold uppercase tracking-wide text-textDim">Pending invitations</h3><div className="mt-2 space-y-2">{invitations.filter((invitation) => !invitation.accepted_at && !invitation.cancelled_at).map((invitation) => <div key={invitation.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-white/5 px-3 py-2 text-xs"><span className="text-white">{invitation.email} · {invitation.role}<span className="ml-2 text-textDim">expires {new Date(invitation.expires_at).toLocaleDateString()}</span></span><button type="button" onClick={() => cancelInvitation(invitation)} className="rounded border border-statusRed/40 px-2 py-1 text-statusRed">Cancel</button></div>)}{invitations.filter((invitation) => !invitation.accepted_at && !invitation.cancelled_at).length === 0 && <p className="text-xs text-textDim">No pending invitations.</p>}</div></div>
      </section>}
    </div>
  );
}
