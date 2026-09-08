import { Link } from 'react-router-dom';
import { Card } from '../../components/ui';
import { TOOLS } from './ToolsLayout';

const DESCRIPTIONS = {
  'home-loan': 'EMI, amortization schedule, mid-loan rate change, annual EMI step-up and prepayment.',
  fd: 'Maturity of a lump-sum fixed deposit with your chosen compounding frequency.',
  rd: 'Maturity of a recurring deposit — a fixed amount every month.',
  sip: 'Future value of a monthly SIP, with optional annual step-up.',
  tax: 'Indian income tax — old vs new regime side-by-side.',
};

export default function ToolsIndex() {
  return (
    <div className="grid card-grid">
      {TOOLS.map((t) => (
        <Link key={t.to} to={t.to} className="tool-card">
          <div className="tool-card-icon" aria-hidden="true">{t.icon}</div>
          <div>
            <div className="tool-card-title">{t.label} Calculator</div>
            <div className="note">{DESCRIPTIONS[t.to]}</div>
          </div>
        </Link>
      ))}
    </div>
  );
}
