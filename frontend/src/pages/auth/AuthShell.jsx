import { Link } from 'react-router-dom';

// Centered card used by the login / register / invite screens.
export default function AuthShell({ title, subtitle, children, footer }) {
  return (
    <div className="auth-page">
      <div className="auth-card card card-pad">
        <div className="brand" style={{ marginBottom: 18 }}>
          <div className="brand-mark">₹</div>
          <div className="brand-text">
            <div className="brand-name">Ledger &amp; Card</div>
            <div className="brand-sub">household finances</div>
          </div>
        </div>
        <h1 style={{ margin: '0 0 4px' }}>{title}</h1>
        {subtitle && <p className="note" style={{ marginTop: 0 }}>{subtitle}</p>}
        {children}
        {footer && <div className="auth-footer">{footer}</div>}
      </div>
    </div>
  );
}

export { Link };
