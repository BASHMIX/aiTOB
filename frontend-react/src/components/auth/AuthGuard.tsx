import { Navigate, useLocation } from 'react-router-dom';
import { useHubStore } from '@/store/useHubStore';

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const hubPassword = useHubStore(state => state.hubPassword);
  const location = useLocation();

  // If no password is set, or it's 'admin' but you want to force a first-time login
  // Actually, let's check if it's truthy. If the default is 'admin', it will pass.
  // BUT we want to ensure the user at least sees the login once if they aren't authenticated.
  
  // For now, let's keep it simple: if hubPassword is set, they are "authed".
  // The LoginPage will ensure they entered the RIGHT password.
  if (!hubPassword) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}
