// src/pages/Dashboard.jsx
import React from 'react';
import { Link } from 'react-router-dom';

const cards = [
  { to: '/upload',  icon: '📤', title: 'Upload Media',     desc: 'Add images or videos — species auto-detected', color: 'green' },
  { to: '/query',   icon: '🔍', title: 'Search Library',   desc: 'Find files by species, tags, or thumbnail URL', color: 'blue' },
  { to: '/manage',  icon: '🏷️', title: 'Manage Tags',      desc: 'Bulk add/remove tags or delete files', color: 'amber' },
  { to: '/notify',  icon: '🔔', title: 'Tag Alerts',        desc: 'Get email alerts when new species are detected', color: 'purple' },
];

const colorMap = {
  green:  'bg-green-50 border-green-200 hover:border-green-400',
  blue:   'bg-blue-50 border-blue-200 hover:border-blue-400',
  amber:  'bg-amber-50 border-amber-200 hover:border-amber-400',
  purple: 'bg-purple-50 border-purple-200 hover:border-purple-400',
};

export default function Dashboard() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-green-800">Welcome to Aussie EcoLens 🦘</h1>
        <p className="text-gray-500 mt-2">Multi-cloud wildlife observation platform · AWS + GCP</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
        {cards.map(({ to, icon, title, desc, color }) => (
          <Link key={to} to={to}
            className={`rounded-xl border p-6 transition-all hover:shadow-md ${colorMap[color]}`}>
            <div className="text-3xl mb-3">{icon}</div>
            <h2 className="font-semibold text-gray-800 text-lg">{title}</h2>
            <p className="text-gray-500 text-sm mt-1">{desc}</p>
          </Link>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold text-gray-700 mb-3">How it works</h2>
        <ol className="space-y-2 text-sm text-gray-600">
          <li className="flex gap-3"><span className="text-green-700 font-bold">1.</span> Upload an image or video — duplicates are detected using SHA-256 checksums</li>
          <li className="flex gap-3"><span className="text-green-700 font-bold">2.</span> AWS Lambda triggers automatically, sending the file to GCP for ML inference</li>
          <li className="flex gap-3"><span className="text-green-700 font-bold">3.</span> MegaDetector locates animals; SpeciesNet identifies the species</li>
          <li className="flex gap-3"><span className="text-green-700 font-bold">4.</span> Tags and thumbnails are saved to DynamoDB; you're notified via SNS email</li>
          <li className="flex gap-3"><span className="text-green-700 font-bold">5.</span> Search your library by species, tag counts, thumbnail URL, or by uploading a sample file</li>
        </ol>
      </div>
    </div>
  );
}
