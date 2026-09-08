import { useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import Sidebar from './Sidebar';
import { Avatar } from '../ui';
import { useAuth } from '../../context/AuthContext';
import { useData } from '../../context/DataContext';

const TITLES = {
  '/': 'Dashboard',
  '/add': 'Add',
  '/transactions': 'Transactions',
  '/accounts': 'Accounts',
  '/income': 'Income',
  '/budgets': 'Budgets',
  '/goals': 'Goals',
  '/portfolio': 'Portfolio',
  '/tools': 'Tools',
  '/family': 'Family',
  '/profile': 'Profile',
  '/settings': 'Settings',
};

// The authenticated shell: fixed sidebar + top bar (mobile) + routed page.
export default function AppLayout() {
  const [navOpen, setNavOpen] = useState(false);
  const { pathname } = useLocation();
  const { user } = useAuth();
  const { loading } = useData();
  const navigate = useNavigate();

  return (
    <div className="app">
      <header className="topbar">
        <button className="icon-btn" onClick={() => setNavOpen(true)} aria-label="Open menu">
          ☰
        </button>
        <div className="topbar-title">{TITLES[pathname] || 'Ledger & Card'}</div>
        <button
          className="topbar-avatar"
          onClick={() => navigate('/profile')}
          aria-label="Open profile"
        >
          <Avatar src={user?.avatarUrl} name={user?.displayName || user?.email} size="md" />
        </button>
      </header>
      <Sidebar navOpen={navOpen} setNavOpen={setNavOpen} />
      <main className="main">
        {loading ? <div className="empty" style={{ marginTop: 40 }}>Loading your books…</div> : <Outlet />}
      </main>
    </div>
  );
}
