import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { HubDashboard } from './features/hub/HubDashboard';
import { EditorDashboard } from './features/editor/EditorDashboard';
import { OBSViewer } from './features/obs/OBSViewer';
import { TournamentSetupPage } from './features/tournament-setup';
import { PlayerArchivePage } from './features/players/PlayerArchivePage';

import { LoginPage } from './features/auth/LoginPage';
import { AccountActionPage } from './features/auth/AccountActionPage';
import { AuthGuard } from './components/auth/AuthGuard';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Navigate to="/admin/hub" replace />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/verify-email" element={<AccountActionPage kind="verify" />} />
        <Route path="/reset-password" element={<AccountActionPage kind="reset" />} />
        <Route path="/accept-invitation" element={<AccountActionPage kind="invite" />} />
        <Route path="/admin/hub" element={<AuthGuard><HubDashboard /></AuthGuard>} />
        <Route path="/admin/editor" element={<AuthGuard><EditorDashboard /></AuthGuard>} />
        <Route path="/admin/players" element={<AuthGuard><PlayerArchivePage /></AuthGuard>} />
        <Route path="/players" element={<Navigate to="/admin/players" replace />} />
        <Route path="/admin/tournaments/new" element={<AuthGuard><TournamentSetupPage /></AuthGuard>} />
        <Route path="/admin/tournaments/setup/:draftId" element={<AuthGuard><TournamentSetupPage /></AuthGuard>} />
        <Route path="/admin/tournaments/setup/:draftId/:step" element={<AuthGuard><TournamentSetupPage /></AuthGuard>} />
        <Route path="/obs" element={<OBSViewer />} />
      </Routes>
    </Router>
  );
}

export default App;
