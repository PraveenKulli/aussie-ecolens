// src/App.jsx
import React, { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Amplify } from 'aws-amplify';
import awsConfig from './aws-config';
import { getUser } from './services/auth';

import LoginPage    from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import VerifyPage   from './pages/VerifyPage';
import Dashboard    from './pages/Dashboard';
import UploadPage   from './pages/UploadPage';
import QueryPage    from './pages/QueryPage';
import ManagePage   from './pages/ManagePage';
import NotifyPage   from './pages/NotifyPage';
import Layout       from './components/Layout';

Amplify.configure(awsConfig);

function RequireAuth({ children }) {
  const [user,    setUser]    = useState(undefined); // undefined = loading
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getUser().then(u => { setUser(u); setLoading(false); });
  }, []);

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center bg-green-50">
      <div className="text-green-700 text-lg font-medium">Loading…</div>
    </div>
  );

  return user ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public */}
        <Route path="/login"    element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/verify"   element={<VerifyPage />} />

        {/* Protected */}
        <Route path="/" element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }>
          <Route index          element={<Dashboard />} />
          <Route path="upload"  element={<UploadPage />} />
          <Route path="query"   element={<QueryPage />} />
          <Route path="manage"  element={<ManagePage />} />
          <Route path="notify"  element={<NotifyPage />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
