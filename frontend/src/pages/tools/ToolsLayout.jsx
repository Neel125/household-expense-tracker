import { NavLink, Outlet } from 'react-router-dom';
import { PageHeader } from '../../components/ui';

// Registry of calculators. The sidebar shows one "Tools" entry that leads
// here; this page's sub-nav lets the user move between calculators
// without going back out.
export const TOOLS = [
  { to: 'home-loan', label: 'Home Loan', icon: '🏠' },
  { to: 'fd', label: 'FD', icon: '💰' },
  { to: 'rd', label: 'RD', icon: '📆' },
  { to: 'sip', label: 'SIP', icon: '📈' },
  { to: 'tax', label: 'Income Tax', icon: '🧾' },
];

export default function ToolsLayout() {
  return (
    <section>
      <PageHeader title="Tools" subtitle="Financial calculators: home loan, FD, RD, SIP and income tax." />
      <nav className="tools-nav">
        {TOOLS.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            end
            className={({ isActive }) => 'tools-tab' + (isActive ? ' active' : '')}
          >
            <span aria-hidden="true">{t.icon}</span>
            {t.label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </section>
  );
}
