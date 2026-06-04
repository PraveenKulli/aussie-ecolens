// src/components/Layout.jsx
import React from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { logout } from '../services/auth';

const nav = [
  { to: '/',        label: '🏠 Dashboard' },
  { to: '/upload',  label: '📤 Upload' },
  { to: '/query',   label: '🔍 Search' },
  { to: '/manage',  label: '🏷️  Manage' },
  { to: '/notify',  label: '🔔 Alerts' },
];

export default function Layout() {
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate('/login');
  }

  return (
    <div className="min-h-screen bg-green-50 flex flex-col">
      {/* Top nav */}
      <header className="bg-white shadow-sm border-b border-green-100">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between h-16">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🦘</span>
            <span className="font-bold text-xl text-green-800 tracking-tight">Aussie EcoLens</span>
          </div>
          <nav className="hidden md:flex gap-1">
            {nav.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  `px-4 py-2 rounded-lg text-sm font-medium transition-colors ` +
                  (isActive
                    ? 'bg-green-700 text-white'
                    : 'text-green-700 hover:bg-green-100')
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
          <button
            onClick={handleLogout}
            className="text-sm text-red-600 hover:text-red-800 font-medium px-3 py-2 rounded-lg hover:bg-red-50 transition-colors"
          >
            Sign out
          </button>
        </div>
      </header>

      {/* Mobile nav */}
      <nav className="md:hidden bg-white border-b border-green-100 px-2 py-2 flex gap-1 overflow-x-auto">
        {nav.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `px-3 py-1.5 rounded text-xs font-medium whitespace-nowrap ` +
              (isActive ? 'bg-green-700 text-white' : 'text-green-700 hover:bg-green-100')
            }
          >
            {label}
          </NavLink>
        ))}
      </nav>

      <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>

      <footer className="bg-white border-t border-green-100 py-4 text-center text-xs text-gray-400">
        Aussie EcoLens — FIT5225 Assignment 2 · Multi-cloud Wildlife Platform · AWS + GCP
      </footer>
    </div>
  );
}
