// src/pages/QueryPage.jsx
import React, { useState } from 'react';
import { queryByTags, queryByThumbnail, queryByFile } from '../services/api';

const TABS = ['By Tags', 'By Species', 'By Thumbnail URL', 'By File'];

export default function QueryPage() {
  const [tab,     setTab]     = useState(0);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState('');
  const [selected, setSelected] = useState(null); // for lightbox

  // Form states
  const [tagInput,     setTagInput]     = useState(''); // "koala:3, wombat:2"
  const [speciesInput, setSpeciesInput] = useState(''); // "dingo, kangaroo"
  const [thumbUrl,     setThumbUrl]     = useState('');
  const [queryFile,    setQueryFile]    = useState(null);

  async function run(e) {
    e.preventDefault();
    setError(''); setResults(null); setLoading(true);
    try {
      let res;
      if (tab === 0) {
        // Parse "koala:3, wombat:2" → {koala:3, wombat:2}
        const tags = {};
        tagInput.split(',').forEach(part => {
          const [k, v] = part.trim().split(':');
          if (k) tags[k.trim()] = v ? parseInt(v.trim()) : 1;
        });
        res = await queryByTags({ tags });
      } else if (tab === 1) {
        const species = speciesInput.split(',').map(s => s.trim()).filter(Boolean);
        res = await queryByTags({ species });
      } else if (tab === 2) {
        res = await queryByThumbnail(thumbUrl.trim());
        // Wrap single result as array for consistent rendering
        if (res.file_url) res = { results: [res], count: 1 };
      } else {
        res = await queryByFile(queryFile);
      }
      setResults(res);
    } catch (err) {
      setError(err.response?.data?.error || err.message || 'Query failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-green-800 mb-2">Search Wildlife</h1>
      <p className="text-gray-500 text-sm mb-6">Search your library using tags, species, thumbnail URLs, or an uploaded file</p>

      {/* Tab bar */}
      <div className="flex gap-1 bg-gray-100 rounded-xl p-1 mb-6">
        {TABS.map((label, i) => (
          <button key={i} onClick={() => { setTab(i); setResults(null); setError(''); }}
            className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${
              tab === i ? 'bg-white text-green-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <form onSubmit={run} className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        {tab === 0 && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Tags with counts <span className="text-gray-400 font-normal">(e.g. Sus_scrofa:2, Felis_catus:1)</span>
            </label>
            <input type="text" value={tagInput} onChange={e => setTagInput(e.target.value)}
              required placeholder="Sus_scrofa:2, Felis_catus:1"
              className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500" />
            <p className="text-xs text-gray-400 mt-1">Returns files containing ALL listed species with at least the specified count</p>
          </div>
        )}

        {tab === 1 && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Species names <span className="text-gray-400 font-normal">(comma-separated)</span>
            </label>
            <input type="text" value={speciesInput} onChange={e => setSpeciesInput(e.target.value)}
              required placeholder="Canis_dingo, Macropus_giganteus"
              className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500" />
          </div>
        )}

        {tab === 2 && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Thumbnail URL</label>
            <input type="url" value={thumbUrl} onChange={e => setThumbUrl(e.target.value)}
              required placeholder="https://your-bucket.s3.amazonaws.com/thumbnails/..."
              className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500" />
          </div>
        )}

        {tab === 3 && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Upload a query file</label>
            <input type="file" accept="image/*,video/*" onChange={e => setQueryFile(e.target.files[0])}
              required
              className="text-sm text-gray-600 file:mr-3 file:py-2 file:px-4 file:border file:border-gray-300 file:rounded-lg file:text-sm file:font-medium file:bg-green-50 file:text-green-700 hover:file:bg-green-100" />
            <p className="text-xs text-gray-400 mt-1">Species are detected in this file, then all matching files in your library are returned. The query file is not stored.</p>
          </div>
        )}

        {error && <p className="text-red-600 text-sm mt-3">{error}</p>}

        <button type="submit" disabled={loading}
          className="mt-4 bg-green-700 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-green-800 transition-colors disabled:opacity-50">
          {loading ? 'Searching…' : '🔍 Search'}
        </button>
      </form>

      {/* Results */}
      {results && (
        <div>
          <h2 className="font-semibold text-gray-700 mb-3">
            {results.count ?? results.results?.length ?? 0} result(s) found
            {results.detected_tags?.length > 0 && (
              <span className="ml-2 text-sm font-normal text-gray-400">
                (detected: {results.detected_tags.join(', ')})
              </span>
            )}
          </h2>

          {/* Thumbnail grid */}
          {results.results?.length > 0 ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
              {results.results.map((r, i) => (
                <div key={i} onClick={() => setSelected(r)}
                  className="cursor-pointer rounded-xl overflow-hidden border border-gray-200 hover:border-green-400 hover:shadow-md transition-all group">
                  {r.thumbnail_url ? (
                    <img src={r.thumbnail_url} alt={r.tags?.join(', ')}
                      className="w-full h-32 object-cover group-hover:opacity-90 transition-opacity" />
                  ) : (
                    <div className="w-full h-32 bg-gray-100 flex items-center justify-center text-3xl">
                      {r.file_type === 'video' ? '🎬' : '🖼️'}
                    </div>
                  )}
                  <div className="p-2">
                    <p className="text-xs text-gray-500 truncate">{r.tags?.slice(0,2).join(', ')}{r.tags?.length > 2 ? '…' : ''}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12 text-gray-400">
              <div className="text-4xl mb-2">🔭</div>
              <p>No files match your query</p>
            </div>
          )}

          {/* Single thumbnail→full result */}
          {results.file_url && !results.results && (
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <p className="text-sm text-gray-600 mb-2">Full-size image URL:</p>
              <a href={results.file_url} target="_blank" rel="noopener noreferrer"
                className="text-green-700 underline text-sm break-all">{results.file_url}</a>
              {results.tags?.length > 0 && (
                <p className="mt-2 text-xs text-gray-400">Tags: {results.tags.join(', ')}</p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Lightbox */}
      {selected && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4"
          onClick={() => setSelected(null)}>
          <div className="bg-white rounded-2xl max-w-2xl w-full overflow-hidden" onClick={e => e.stopPropagation()}>
            <div className="p-4 border-b flex items-center justify-between">
              <h3 className="font-semibold text-gray-800">
                {selected.file_type === 'video' ? '🎬 Video' : '🖼️ Image'}
              </h3>
              <button onClick={() => setSelected(null)} className="text-gray-400 hover:text-gray-700 text-xl">×</button>
            </div>
            <div className="p-4">
              {selected.thumbnail_url && (
                <img src={selected.thumbnail_url} alt="preview"
                  className="w-full rounded-lg mb-3 max-h-64 object-contain bg-gray-50" />
              )}
              <p className="text-sm text-gray-500 mb-1">Full-size URL:</p>
              <a href={selected.file_url} target="_blank" rel="noopener noreferrer"
                className="text-green-700 underline text-sm break-all">{selected.file_url}</a>
              {selected.tags?.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1">
                  {selected.tags.map(t => (
                    <span key={t} className="bg-green-100 text-green-800 text-xs px-2 py-1 rounded-full">{t}</span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
