import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Home } from './pages/Home';
import { Characters } from './pages/Characters';
import { ProjectDialogues } from './pages/ProjectDialogues';
import { Login } from './pages/Login';
import { Header } from './components/Header';
import { AuthProvider } from './context/AuthContext';
import { useAuth } from './context/useAuth';
import './index.css';

const Guard = ({ children }: { children: JSX.Element }) => {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) return null; // could add spinner
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  return children;
};

export const App = () => (
  <AuthProvider>
    <BrowserRouter>
      <Header />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<Guard><Home /></Guard>} />
        <Route path="/characters" element={<Guard><Characters /></Guard>} />
        <Route path="/projects/:id" element={<Guard><ProjectDialogues /></Guard>} />
      </Routes>
    </BrowserRouter>
  </AuthProvider>
);
