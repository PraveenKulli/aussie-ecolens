// src/pages/NotifyPage.jsx
import React, { useState } from 'react';
import { subscribeNotifications, unsubscribeNotifications } from '../services/api';

const SPECIES_OPTIONS = [
  'Sus_scrofa', 'Felis_catus', 'Canis_familiaris', 'Bos_taurus',
  'Casuarius_casuarius', 'Alectura_lathami', 'Thylogale_stigmatica',
  'Perameles_nasuta', 'Uromys_caudimaculatus', 'Hypsiprymnodon_moschatus',
  'Megapodius_reinwardt', 'Orthonyx_spaldingii', 'Heteromyias_cinereifrons',
];

export default function NotifyPage() {
  const [mode,    setMode]    = useState('subscribe');
  const [email,   setEmail]   = useState('');
  const [tags,    setTags]    = useState([]);
  const [subArn,  setSubArn]  = useState('');
  const [result,  setResult]  = useState(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState('');

  function toggleTag(t) {
    setTags(prev => prev.includes(t) ? prev.filter(x => x !== t) : [...prev, t]);
  }

  async function handleSubscribe(e) {
    e.preventDefault();
    if (!tags.length) { setError('Select at least one species to watch'); return; }
    setError(''); setResult(null); setLoading(true);
    try {
      const res = await subscribeNotifications(email, tags);
      setResult(res);
    } catch (err) {
      setError(err.response?.data?.error || err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleUnsubscribe(e) {
    e.preventDefault();
    setError(''); setResult(null); setLoading(true);
    try {
      const res = await unsubscribeNotifications(subArn);
      setResult(res);
    } catch (err) {
      setError(err.response?.data?.error || err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-xl mx-auto">
      <h1 className="text-2xl font-bold text-green-800 mb-2">Tag Alerts</h1>
      <p className="text-gray-500 text-sm mb-6">Subscribe to email notifications when specific species are detected</p>

      <div className="flex gap-2 mb-6">
        {[['subscribe', '🔔 Subscribe'], ['unsubscribe', '🔕 Unsubscribe']].map(([m, label]) => (
          <button key={m} onClick={() => { setMode(m); setResult(null); setError(''); }}
            className={`px-5 py-2 rounded-lg text-sm font-medium transition-colors ${
              mode === m ? 'bg-green-700 text-white' : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50'
            }`}>{label}</button>
        ))}
      </div>

      {mode === 'subscribe' && (
        <form onSubmit={handleSubscribe} className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email address</label>
            <input type="email" required value={email} onChange={e => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Species to watch</label>
            <div className="flex flex-wrap gap-2">
              {SPECIES_OPTIONS.map(t => (
                <button key={t} type="button" onClick={() => toggleTag(t)}
                  className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                    tags.includes(t)
                      ? 'bg-green-700 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-green-100 hover:text-green-800'
                  }`}>{t.replace('_', ' ')}</button>
              ))}
            </div>
            {tags.length > 0 && (
              <p className="text-xs text-gray-400 mt-2">Watching: {tags.join(', ')}</p>
            )}
          </div>
          {error && <p className="text-red-600 text-sm">{error}</p>}
          <button type="submit" disabled={loading}
            className="bg-green-700 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-green-800 transition-colors disabled:opacity-50">
            {loading ? 'Subscribing…' : '🔔 Subscribe'}
          </button>
          {result && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-sm">
              <p className="font-medium text-green-800">{result.message}</p>
              <p className="text-xs text-gray-500 mt-1">{result.note}</p>
              {result.subscription_arn && (
                <p className="text-xs text-gray-400 mt-2 font-mono break-all">ARN: {result.subscription_arn}</p>
              )}
            </div>
          )}
        </form>
      )}

      {mode === 'unsubscribe' && (
        <form onSubmit={handleUnsubscribe} className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Subscription ARN</label>
            <input type="text" required value={subArn} onChange={e => setSubArn(e.target.value)}
              placeholder="arn:aws:sns:us-east-1:..."
              className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500 font-mono text-xs" />
            <p className="text-xs text-gray-400 mt-1">Your subscription ARN was shown when you subscribed</p>
          </div>
          {error && <p className="text-red-600 text-sm">{error}</p>}
          <button type="submit" disabled={loading}
            className="bg-red-600 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-red-700 transition-colors disabled:opacity-50">
            {loading ? 'Unsubscribing…' : '🔕 Unsubscribe'}
          </button>
          {result && (
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-sm text-gray-700">
              {result.message}
            </div>
          )}
        </form>
      )}
    </div>
  );
}
