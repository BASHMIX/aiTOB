import { useHubStore } from '@/store/useHubStore';


export function sessionCan(
  session: { role?: string; permissions?: string[] } | null | undefined,
  permission: string,
): boolean {
  if (!session) return false;
  if (Array.isArray(session.permissions)) return session.permissions.includes(permission);
  // Compatibility for an already-open session created before the permissions
  // projection was added. The next /api/session refresh supplies exact values.
  return session.role === 'owner';
}


export function usePermission(permission: string): boolean {
  return useHubStore((state) => sessionCan(state.session, permission));
}
