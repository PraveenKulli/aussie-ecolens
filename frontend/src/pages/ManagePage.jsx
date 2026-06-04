// src/pages/ManagePage.jsx
import React, { useState } from 'react';
import { editTags, deleteFiles } from '../services/api';

export default function ManagePage() {
  const [mode, setMode] = useState('tags'); // 'tags' | 'delete'

  // Tag editing state
  const [urlsInput, setUrlsInput] = useState('');
  const [tagsInput, setTagsInput] = useState('');
  const [operation, setOperation] = useState(1);
  const [tagResult, setTagResult] = useState(null);
  const [tagLoading, setTagLoading] = useState(false);
  const [tagError,   setTagError]   = useState('');

  // Delete state
  const [delUrls,    setDelUrls]    = useState('');
  const [delResult,  setDelResult]  = useState(null);
  const [delLoading, setDelLoading] = useState(false);
  const [delError,   setDelError]   = useState('');

  async function handleTagEdit(e) {
    e.preventDefault();
    setTagError(''); setTagResult(null); setTagLoading(true);
    try {
      const urls = urlsInput.split('\n').map(u => u.trim()).filter(Boolean);
      const tags = tagsInput.split(',').map(t => t.trim()).filter(Boolean);
      const res  = await editTags(urls, tags, operation);
      setTagResult(res);
    } catch (err) {
      setTagError(err.response?.data?.error || err.message);
    } finally {
      setTagLoading(false);
    }
  }

  async function handleDelete(e) {
    e.preventDefault();
    if (!window.confirm('Are you sure? This will permanently delete the files.')) return;
    setDelError(''); setDelResult(null); setDelLoading(true);
    try {
      const urls = delUrls.split('\n').map(u => u.trim()).filter(Boolean);
      const res  = await deleteFiles(urls);
      setDelResult(res);
      if (res.deleted?.length) setDelUrls('');
    } catch (err) {
      setDelError(err.response?.data?.error || err.message);
    } finally {
      setDelLoading(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-green-800 mb-2">Manage Files</h1>
      <p className="text-gray-500 text-sm mb-6">Bulk edit tags or delete files from your library</p>

      {/* Mode toggle */}
      <div className="flex gap-2 mb-6">
        {[['tags', '🏷️  Edit Tags'], ['delete', '🗑️  Delete Files']].map(([m, label]) => (
          <button key={m} onClick={() => setMode(m)}
            className={`px-5 py-2 rounded-lg text-sm font-medium transition-colors ${
              mode === m ? 'bg-green-700 text-white' : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50'
            }`}>
            {label}
          </button>
        ))}
      </div>

      {mode === 'tags' && (
        <form onSubmit={handleTagEdit} className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              File URLs <span className="text-gray-400 font-normal">(one per line)</span>
            </label>
            <textarea rows={4} required value={urlsInput} onChange={e => setUrlsInput(e.target.value)}
              placeholder="https://your-bucket.s3.amazonaws.com/uploads/uuid1.jpg&#10;https://your-bucket.s3.amazonaws.com/uploads/uuid2.jpg"
              className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500 font-mono text-xs" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Tags <span className="text-gray-400 font-normal">(comma-separated)</span>
            </label>
            <input type="text" required value={tagsInput} onChange={e => setTagsInput(e.target.value)}
              placeholder="Sus_scrofa, Felis_catus"
              className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Operation</label>
            <div className="flex gap-4">
              {[[1, '➕ Add tags'], [0, '➖ Remove tags']].map(([val, label]) => (
                <label key={val} className="flex items-center gap-2 cursor-pointer">
                  <input type="radio" name="operation" checked={operation === val}
                    onChange={() => setOperation(val)}
                    className="accent-green-700" />
                  <span className="text-sm text-gray-700">{label}</span>
                </label>
              ))}
            </div>
          </div>

          {tagError && <p className="text-red-600 text-sm">{tagError}</p>}

          <button type="submit" disabled={tagLoading}
            className="bg-green-700 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-green-800 transition-colors disabled:opacity-50">
            {tagLoading ? 'Updating…' : 'Apply changes'}
          </button>

          {tagResult && (
            <div className="mt-4 bg-green-50 border border-green-200 rounded-lg p-4 text-sm">
              <p className="font-medium text-green-800 mb-2">{tagResult.message}</p>
              {tagResult.updated?.map((u, i) => (
                <div key={i} className="text-xs text-gray-600 truncate">
                  ✓ {u.url} → [{u.tags?.join(', ')}]
                </div>
              ))}
              {tagResult.errors?.map((e, i) => (
                <div key={i} className="text-xs text-red-600">✗ {e.url}: {e.error}</div>
              ))}
            </div>
          )}
        </form>
      )}

      {mode === 'delete' && (
        <form onSubmit={handleDelete} className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
            ⚠️ Deletion is permanent. Files, thumbnails, and all database records will be removed.
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              File URLs to delete <span className="text-gray-400 font-normal">(one per line)</span>
            </label>
            <textarea rows={5} required value={delUrls} onChange={e => setDelUrls(e.target.value)}
              placeholder="https://your-bucket.s3.amazonaws.com/uploads/uuid1.jpg"
              className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-red-400 font-mono text-xs" />
          </div>

          {delError && <p className="text-red-600 text-sm">{delError}</p>}

          <button type="submit" disabled={delLoading}
            className="bg-red-600 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-red-700 transition-colors disabled:opacity-50">
            {delLoading ? 'Deleting…' : '🗑️ Delete files'}
          </button>

          {delResult && (
            <div className="mt-4 bg-red-50 border border-red-200 rounded-lg p-4 text-sm">
              <p className="font-medium text-red-800 mb-2">{delResult.message}</p>
              {delResult.deleted?.map((d, i) => (
                <div key={i} className="text-xs text-gray-600">✓ Deleted: {d.url}</div>
              ))}
              {delResult.errors?.map((e, i) => (
                <div key={i} className="text-xs text-red-600">✗ {e.url}: {e.error}</div>
              ))}
            </div>
          )}
        </form>
      )}
    </div>
  );
}
