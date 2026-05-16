import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { HubDashboard } from './features/hub/HubDashboard';
import { EditorDashboard } from './features/editor/EditorDashboard';
import { OBSViewer } from './features/obs/OBSViewer';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Navigate to="/admin/hub" replace />} />
        <Route path="/admin/hub" element={<HubDashboard />} />
        <Route path="/admin/editor" element={<EditorDashboard />} />
        <Route path="/obs" element={<OBSViewer />} />
      </Routes>
    </Router>
  );
}

export default App;
