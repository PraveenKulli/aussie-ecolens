// src/pages/VerifyPage.jsx
import React, { useState } from 'react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import { confirmEmail } from '../services/auth';

export default function VerifyPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [code, setCode]     = useState('');
  const [email, setEmail]   = useState(location.state?.email || '');
  const [error, setError]   = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await confirmEmail(email, code);
      navigate('/login', { state: { message: 'Email verified! Please sign in.' } });
    } catch (err) {
      setError(err.message || 'Verification failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-800 to-green-600 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-8">
        <div className="text-center mb-8">
          <div className="text-5xl mb-3">📧</div>
          <h1 className="text-2xl font-bold text-green-800">Verify Your Email</h1>
          <p className="text-gray-500 text-sm mt-1">Enter the code sent to your email</p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 mb-4 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {!location.state?.email && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input type="email" required value={email}
                onChange={e => setEmail(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500" />
            </div>
          )}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Verification code</label>
            <input type="text" required value={code}
              onChange={e => setCode(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500 text-center text-xl tracking-widest"
              placeholder="123456" maxLength={6} />
          </div>
          <button type="submit" disabled={loading}
            className="w-full bg-green-700 text-white py-2.5 rounded-lg font-medium hover:bg-green-800 transition-colors disabled:opacity-60">
            {loading ? 'Verifying…' : 'Verify email'}
          </button>
        </form>
        <p className="text-center text-sm text-gray-500 mt-6">
          <Link to="/login" className="text-green-700 font-medium hover:underline">Back to sign in</Link>
        </p>
      </div>
    </div>
  );
}
