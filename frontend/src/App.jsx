import React, { createContext, useContext, useState, useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Supervisor from './pages/Supervisor';
import Ingest from './pages/Ingest';
import ReviewQueue from './pages/ReviewQueue';
import Schedule from './pages/Schedule';
import Analytics from './pages/Analytics';
import Risk from './pages/Risk';
import KnowledgeBase from './pages/KnowledgeBase';
import Conflicts from './pages/Conflicts';
import Audit from './pages/Audit';
import Settings from './pages/Settings';

const AuthContext = createContext(null);

export function useAuth() {
  return useContext(AuthContext);
}

function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('synapse_user');
    return saved ? JSON.parse(saved) : null;
  });

  const loginUser = (userData, token) => {
    localStorage.setItem('synapse_token', token);
    localStorage.setItem('synapse_user', JSON.stringify(userData));
    setUser(userData);
  };

  const logout = () => {
    localStorage.removeItem('synapse_token');
    localStorage.removeItem('synapse_user');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loginUser, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

function ProtectedRoute({ children }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/*"
          element={
            <ProtectedRoute>
              <Layout>
                <Routes>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/supervisor" element={<Supervisor />} />
                  <Route path="/ingest" element={<Ingest />} />
                  <Route path="/review" element={<ReviewQueue />} />
                  <Route path="/schedule" element={<Schedule />} />
                  <Route path="/analytics" element={<Analytics />} />
                  <Route path="/risk" element={<Risk />} />
                  <Route path="/knowledge" element={<KnowledgeBase />} />
                  <Route path="/conflicts" element={<Conflicts />} />
                  <Route path="/audit" element={<Audit />} />
                  <Route path="/settings" element={<Settings />} />
                </Routes>
              </Layout>
            </ProtectedRoute>
          }
        />
      </Routes>
    </AuthProvider>
  );
}
