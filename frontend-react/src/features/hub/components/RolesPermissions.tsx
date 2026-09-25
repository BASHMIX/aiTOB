import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';

type RoleProjection = { key: string; label: string; permissions: string[] };
type RolesResponse = { current_role: string; current_permissions: string[]; roles: RoleProjection[] };

const permissionLabels: Record<string, string> = {
  'workspace.read': 'View workspace',
  'workspace.manage': 'Manage members',
  'settings.manage': 'Manage settings',
  'integrations.manage': 'Connect providers & Discord',
  'tournament.manage': 'Create & edit tournaments',
  'match.operate': 'Manage match lifecycle',
  'match.call': 'Call matches',
  'match.ready': 'Confirm attendance',
  'match.start': 'Start matches',
  'match.stream': 'Select streamed matches',
  'stream.manage': 'Manage stream queue',
  'station.manage': 'Manage stations',
  'overlay.manage': 'Manage OBS overlays',
  'result.report': 'Report results',
  'dq.manual': 'Apply manual DQ',
  'assistant.use': 'Use AI assistant',
  'proposal.review': 'Review AI proposals',
  'conflict.manage': 'Resolve conflicts',
};

export function RolesPermissions() {
  const [data, setData] = useState<RolesResponse | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    axios.get('/api/workspace/roles')
      .then((response) => setData(response.data))
      .catch(() => setError('Roles and permissions could not be loaded.'));
  }, []);

  const permissions = useMemo(() => Array.from(new Set(
    (data?.roles || []).flatMap((role) => role.permissions),
  )).sort((a, b) => (permissionLabels[a] || a).localeCompare(permissionLabels[b] || b)), [data]);

  if (error) return <p role="alert" className="rounded-lg border border-statusRed/30 bg-statusRed/10 p-3 text-sm text-statusRed">{error}</p>;
  if (!data) return <p className="py-8 text-center text-sm text-textDim">Loading roles and permissions…</p>;

  return (
    <div className="space-y-5 animate-fadeIn">
      <section className="rounded-xl border border-accentYellow/20 bg-accentYellow/5 p-4">
        <h2 className="text-base font-bold text-white">Role-based access</h2>
        <p className="mt-1 text-xs leading-relaxed text-textDim">Permissions are enforced by the API. Hidden controls are a usability safeguard, not the security boundary.</p>
        <p className="mt-3 text-xs text-white">Your role: <strong className="text-accentYellow">{data.roles.find((role) => role.key === data.current_role)?.label || data.current_role}</strong></p>
      </section>
      <div className="overflow-x-auto rounded-xl border border-white/10 bg-cardDark">
        <table className="min-w-[760px] w-full border-collapse text-left text-xs">
          <thead><tr className="border-b border-white/10 bg-black/20"><th className="sticky left-0 bg-cardDark px-4 py-3 text-textDim">Permission</th>{data.roles.map((role) => <th key={role.key} className={`px-3 py-3 text-center ${role.key === data.current_role ? 'text-accentYellow' : 'text-white'}`}>{role.label}</th>)}</tr></thead>
          <tbody>{permissions.map((permission) => <tr key={permission} className="border-b border-white/5 last:border-0"><td className="sticky left-0 bg-cardDark px-4 py-2.5 text-textLight"><span className="font-semibold">{permissionLabels[permission] || permission}</span><span className="ml-2 font-mono text-[9px] text-textDim">{permission}</span></td>{data.roles.map((role) => { const allowed = role.permissions.includes(permission); return <td key={role.key} className="px-3 py-2.5 text-center"><span aria-label={allowed ? 'Allowed' : 'Not allowed'} className={allowed ? 'text-statusGreen' : 'text-white/20'}>{allowed ? '✓' : '—'}</span></td>; })}</tr>)}</tbody>
        </table>
      </div>
    </div>
  );
}
