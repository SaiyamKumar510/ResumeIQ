import { Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout.jsx';
import Dashboard from './pages/Dashboard.jsx';
import Analyze from './pages/Analyze.jsx';
import Results from './pages/Results.jsx';
import History from './pages/History.jsx';
import AnalysisDetails from './pages/AnalysisDetails.jsx';
import NotFound from './pages/NotFound.jsx';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/analyze" element={<Analyze />} />
        <Route path="/results/:id" element={<Results />} />
        <Route path="/history" element={<History />} />
        <Route path="/history/:id" element={<AnalysisDetails />} />
        <Route path="/dashboard" element={<Navigate to="/" replace />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
