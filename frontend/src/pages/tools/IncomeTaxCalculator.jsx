import { useMemo, useState } from 'react';
import { Card, Field, SegmentedControl } from '../../components/ui';
import { fmtINR } from '../../lib/format';
import { computeIndiaTax } from '../../lib/finance';

export default function IncomeTaxCalculator() {
  const [form, setForm] = useState({
    gross: 1500000,
    salaried: 'yes',
    d80c: 150000,
    d80d: 25000,
    hra: 0,
    homeLoanInterest: 0,
    otherDeductions: 0,
  });
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const setSalaried = (v) => setForm((f) => ({ ...f, salaried: v }));

  const totalDeductions =
    (Number(form.d80c) || 0) +
    (Number(form.d80d) || 0) +
    (Number(form.hra) || 0) +
    (Number(form.homeLoanInterest) || 0) +
    (Number(form.otherDeductions) || 0);

  const gross = Number(form.gross) || 0;
  const salaried = form.salaried === 'yes';

  const oldR = useMemo(() => computeIndiaTax(gross, totalDeductions, 'old', salaried), [gross, totalDeductions, salaried]);
  const newR = useMemo(() => computeIndiaTax(gross, totalDeductions, 'new', salaried), [gross, totalDeductions, salaried]);
  const better = newR.totalTax <= oldR.totalTax ? 'new' : 'old';
  const savings = Math.abs(newR.totalTax - oldR.totalTax);

  return (
    <div className="grid two-col">
      <Card title="Your details" pad>
        <div className="form-grid">
          <Field label="Annual gross income (₹)">
            <input type="number" step="10000" value={form.gross} onChange={set('gross')} />
          </Field>
          <Field label="Salaried?">
            <SegmentedControl
              value={form.salaried}
              onChange={setSalaried}
              options={[
                { value: 'yes', label: 'Yes' },
                { value: 'no', label: 'No' },
              ]}
            />
          </Field>
        </div>

        <div className="section-label" style={{ marginTop: 18 }}>
          Deductions <span className="note">(applied only in the old regime)</span>
        </div>
        <div className="form-grid">
          <Field label="80C (PF, ELSS, life insurance…)">
            <input type="number" step="1000" value={form.d80c} onChange={set('d80c')} />
          </Field>
          <Field label="80D (health insurance)">
            <input type="number" step="1000" value={form.d80d} onChange={set('d80d')} />
          </Field>
          <Field label="HRA exemption">
            <input type="number" step="1000" value={form.hra} onChange={set('hra')} />
          </Field>
          <Field label="Home loan interest">
            <input type="number" step="1000" value={form.homeLoanInterest} onChange={set('homeLoanInterest')} />
          </Field>
          <Field label="Other deductions">
            <input type="number" step="1000" value={form.otherDeductions} onChange={set('otherDeductions')} />
          </Field>
        </div>
      </Card>

      <Card title="Old vs New regime" pad>
        <div className="regime-compare">
          <RegimeCard title="New regime" result={newR} highlighted={better === 'new'} />
          <RegimeCard title="Old regime" result={oldR} highlighted={better === 'old'} />
        </div>
        <div className="calc-note" style={{ marginTop: 14 }}>
          The <strong>{better === 'new' ? 'new' : 'old'} regime</strong> saves you{' '}
          <strong>{fmtINR(savings)}</strong> per year on this income and these deductions.
          Slabs used: FY 2025-26 (AY 2026-27). Numbers ignore surcharge, capital-gains and business income.
        </div>
      </Card>
    </div>
  );
}

function RegimeCard({ title, result, highlighted }) {
  return (
    <div className={'regime-card' + (highlighted ? ' recommended' : '')}>
      <div className="regime-header">
        <div className="regime-title">{title}</div>
        {highlighted && <span className="badge">Recommended</span>}
      </div>
      <Row label="Standard deduction" value={fmtINR(result.stdDeduction)} />
      <Row label="Other deductions" value={fmtINR(result.deductions)} />
      <Row label="Taxable income" value={fmtINR(result.taxable)} />
      <Row label="Tax before rebate" value={fmtINR(result.baseTax)} />
      <Row label="Rebate (87A)" value={fmtINR(result.rebate)} />
      <Row label="Health & education cess" value={fmtINR(result.cess)} />
      <div className="regime-total">
        <div>Total tax</div>
        <div>{fmtINR(result.totalTax)}</div>
      </div>
      <div className="regime-takehome">
        Take-home: <strong>{fmtINR(result.takeHome)}</strong>
      </div>
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div className="regime-row">
      <span>{label}</span>
      <span>{value}</span>
    </div>
  );
}
