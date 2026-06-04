// src/pages/UploadPage.jsx
import React, { useState, useRef } from 'react';
import { sha256, presignUpload, uploadToS3, confirmUpload } from '../services/api';

const ACCEPT = 'image/jpeg,image/png,image/bmp,image/webp,video/mp4,video/quicktime,video/x-msvideo';

export default function UploadPage() {
  const inputRef  = useRef(null);
  const [files,   setFiles]   = useState([]);
  const [results, setResults] = useState([]);
  const [uploading, setUploading] = useState(false);

  function onDrop(e) {
    e.preventDefault();
    addFiles([...e.dataTransfer.files]);
  }

  function addFiles(newFiles) {
    const valid = newFiles.filter(f =>
      f.type.startsWith('image/') || f.type.startsWith('video/')
    );
    setFiles(prev => [...prev, ...valid.map(f => ({ file: f, id: Math.random() }))]);
  }

  function removeFile(id) {
    setFiles(prev => prev.filter(f => f.id !== id));
  }

  async function handleUpload() {
    if (!files.length) return;
    setUploading(true);
    setResults([]);
    const res = [];

    for (const { file, id } of files) {
      try {
        const checksum = await sha256(file);
        const presign  = await presignUpload(file.name, checksum, file.type);

        if (presign.duplicate) {
          res.push({
            id, name: file.name, status: 'duplicate',
            message: '⚠️ Duplicate — already exists in the system',
            thumbnail_url: presign.thumbnail_url,
            tags: presign.tags,
          });
          continue;
        }

        await uploadToS3(presign.upload_url, file);
        const confirm = await confirmUpload(presign.file_key, file.name, checksum, file.type);

        res.push({
          id, name: file.name, status: 'success',
          message: '✅ Uploaded! Processing started…',
          file_id: confirm.file_id,
        });
      } catch (err) {
        res.push({
          id, name: file.name, status: 'error',
          message: `❌ Error: ${err.response?.data?.error || err.message}`,
        });
      }
    }

    setResults(res);
    setFiles([]);
    setUploading(false);
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-green-800 mb-2">Upload Media</h1>
      <p className="text-gray-500 text-sm mb-6">Upload images or videos — species are auto-detected by our ML model</p>

      {/* Drop zone */}
      <div
        onDrop={onDrop}
        onDragOver={e => e.preventDefault()}
        onClick={() => inputRef.current?.click()}
        className="border-2 border-dashed border-green-300 rounded-xl bg-green-50 hover:bg-green-100 transition-colors cursor-pointer p-10 text-center mb-4"
      >
        <div className="text-4xl mb-3">🖼️</div>
        <p className="font-medium text-green-800">Drag & drop files here</p>
        <p className="text-sm text-gray-500 mt-1">or click to browse · Images & Videos</p>
        <input
          ref={inputRef} type="file" multiple accept={ACCEPT} className="hidden"
          onChange={e => addFiles([...e.target.files])}
        />
      </div>

      {/* Queued files */}
      {files.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 mb-4 divide-y divide-gray-100">
          {files.map(({ file, id }) => (
            <div key={id} className="flex items-center gap-3 px-4 py-3">
              <span className="text-xl">{file.type.startsWith('video/') ? '🎬' : '🖼️'}</span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800 truncate">{file.name}</p>
                <p className="text-xs text-gray-400">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
              </div>
              <button onClick={() => removeFile(id)} className="text-gray-400 hover:text-red-500 text-lg">×</button>
            </div>
          ))}
        </div>
      )}

      <button
        onClick={handleUpload} disabled={uploading || files.length === 0}
        className="w-full bg-green-700 text-white py-3 rounded-xl font-medium hover:bg-green-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {uploading ? 'Uploading…' : `Upload ${files.length} file${files.length !== 1 ? 's' : ''}`}
      </button>

      {/* Results */}
      {results.length > 0 && (
        <div className="mt-6 space-y-2">
          <h2 className="font-semibold text-gray-700">Results</h2>
          {results.map(r => (
            <div key={r.id}
              className={`rounded-lg p-4 text-sm border ${
                r.status === 'success'   ? 'bg-green-50 border-green-200' :
                r.status === 'duplicate' ? 'bg-yellow-50 border-yellow-200' :
                'bg-red-50 border-red-200'
              }`}
            >
              <p className="font-medium text-gray-800">{r.name}</p>
              <p className="mt-0.5 text-gray-600">{r.message}</p>
              {r.status === 'duplicate' && r.tags?.length > 0 && (
                <p className="mt-1 text-xs text-gray-500">Tags: {r.tags.join(', ')}</p>
              )}
              {r.status === 'duplicate' && r.thumbnail_url && (
                <img src={r.thumbnail_url} alt="thumb" className="mt-2 h-16 rounded" />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
