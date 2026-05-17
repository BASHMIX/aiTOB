import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { HubDashboard } from './features/hub/HubDashboard';
import { EditorDashboard } from './features/editor/EditorDashboard';
import { OBSViewer } from './features/obs/OBSViewer';

import { LoginPage } from './features/auth/LoginPage';
import { AuthGuard } from './components/auth/AuthGuard';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Navigate to="/admin/hub" replace />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/admin/hub" element={<AuthGuard><HubDashboard /></AuthGuard>} />
        <Route path="/admin/editor" element={<AuthGuard><EditorDashboard /></AuthGuard>} />
        <Route path="/obs" element={<OBSViewer />} />
      </Routes>
    </Router>
  );
}

export default App;
