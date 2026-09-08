import { useEffect, useRef, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { Avatar } from '../ui';
import { useAuth } from '../../context/AuthContext';

const NAV = [
  { to: '/', end: true, icon: '◆', label: 'Dashboard' },
  { to: '/add', icon: '+', label: 'Add Transaction' },
  { to: '/transactions', icon: '≡', label: 'Transactions' },
  { to: '/accounts', icon: '▭', label: 'Accounts & Cards' },
  { to: '/income', icon: '↑', label: 'Income' },
  { to: '/budgets', icon: '◑', label: 'Budgets' },
  { to: '/goals', icon: '◎', label: 'Goals' },
  { to: '/portfolio', icon: '◈', label: 'Portfolio' },
  { to: '/rewards', icon: '★', label: 'Rewards' },
  { to: '/tools', icon: '∑', label: 'Tools' },
  { to: '/family', icon: '⌂', label: 'Family' },
];

// The pop-over that opens from the bottom profile chip. Holds the moved
// Settings link and Sign out, so we no longer need a dedicated Settings
// entry in the main nav.
function ProfileMenu({ user, onNavigate, onSignOut, onClose }) {
  return (
    <div className="profile-menu" role="menu">
      <button className="profile-menu-item" role="menuitem" onClick={() => { onClose(); onNavigate('/profile'); }}>
        <span className="ic" aria-hidden="true">◐</span>
        <div>
          <div className="profile-menu-title">User profile</div>
          <div className="profile-menu-sub">Name, contact, photo, family</div>
        </div>
      </button>
      <button className="profile-menu-item" role="menuitem" onClick={() => { onClose(); onNavigate('/settings'); }}>
        <span className="ic" aria-hidden="true">⚙</span>
        <div>
          <div className="profile-menu-title">Settings</div>
          <div className="profile-menu-sub">Categories, household, theme</div>
        </div>
      </button>
      <div className="profile-menu-sep" role="separator" />
      <button className="profile-menu-item danger" role="menuitem" onClick={() => { onClose(); onSignOut(); }}>
        <span className="ic" aria-hidden="true">↩</span>
        <div>
          <div className="profile-menu-title">Sign out</div>
          <div className="profile-menu-sub">{user?.email}</div>
        </div>
      </button>
    </div>
  );
}

export default function Sidebar({ navOpen, setNavOpen }) {
  const { user, household, logout } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const footerRef = useRef(null);

  // Close the popover on outside click / Escape.
  useEffect(() => {
    if (!menuOpen) return;
    const onDown = (e) => {
      if (!footerRef.current?.contains(e.target)) setMenuOpen(false);
    };
    const onKey = (e) => e.key === 'Escape' && setMenuOpen(false);
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [menuOpen]);

  const go = (to) => {
    setNavOpen(false);
    navigate(to);
  };

  return (
    <>
      {navOpen && <div className="nav-backdrop" onClick={() => setNavOpen(false)} />}
      <aside className={'rail' + (navOpen ? ' open' : '')}>
        <div className="brand">
          <div className="brand-mark">₹</div>
          <div className="brand-text">
            <div className="brand-name">Ledger &amp; Card</div>
            <div className="brand-sub">{household?.name || 'household finances'}</div>
          </div>
        </div>
        <nav className="navlist">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) => 'navlink' + (isActive ? ' active' : '')}
              title={n.label}
              onClick={() => setNavOpen(false)}
            >
              <span className="ic">{n.icon}</span>
              <span className="nav-label">{n.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="rail-footer" ref={footerRef}>
          {menuOpen && (
            <ProfileMenu
              user={user}
              onNavigate={go}
              onSignOut={logout}
              onClose={() => setMenuOpen(false)}
            />
          )}
          <button
            className={'profile-chip profile-chip-button' + (menuOpen ? ' open' : '')}
            title={user?.email}
            onClick={() => setMenuOpen((s) => !s)}
            aria-haspopup="menu"
            aria-expanded={menuOpen}
          >
            <Avatar src={user?.avatarUrl} name={user?.displayName || user?.email} size="md" />
            <div className="profile-text">
              <div className="profile-name">{user?.displayName || 'You'}</div>
              <div className="profile-sub">{user?.role === 'owner' ? 'owner' : 'member'}</div>
            </div>
            <span className="profile-chip-caret" aria-hidden="true">⋯</span>
          </button>
        </div>
      </aside>
    </>
  );
}
