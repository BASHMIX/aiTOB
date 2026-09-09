import { Navigate, useLocation } from 'react-router-dom';
import { useEffect, useState } from 'react';
import axios from 'axios';
import { useHubStore } from '@/store/useHubStore';

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const session = useHubStore(state => state.session);
  const setSession = useHubStore(state => state.setSession);
  const logout = useHubStore(state => state.logout);
  const location = useLocation();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    let active = true;
    axios.get('/api/session')
      .then((response) => { if (active) setSession(response.data); })
      .catch(() => { if (active) logout(); })
      .finally(() => { if (active) setChecked(true); });
    return () => { active = false; };
  }, [setSession, logout]);

  if (!checked) return <div className="min-h-screen bg-appDark" aria-label="Checking session" />;
  if (!session) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}
