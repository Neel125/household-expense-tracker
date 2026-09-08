import { useMemo, useState } from 'react';
import { Card, Field, Select } from '../../components/ui';
import { fmtINR } from '../../lib/format';
import { rdMaturity } from '../../lib/finance';

const COMPOUND = [
  { value: 12, label: 'Monthly' },
  { value: 4, label: 'Quarterly' },
  { value: 2, label: 'Half-yearly' },
  { value: 1, label: 'Yearly' },
];

export default function RDCalculator() {
  const [form, setForm] = useState({ monthly: 5000, ratePct: 7, months: 60, compounds: 4 });
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const r = useMemo(
    () =>
      rdMaturity(
        Number(form.monthly) || 0,
        Number(form.ratePct) || 0,
        Math.max(1, Math.round(Number(form.months) || 0)),
        Number(form.compounds) || 1
      ),
    [form]
  );

  return (
    <div className="grid two-col">
      <Card title="Recurring deposit" pad>
        <div className="form-grid">
          <Field label="Monthly deposit (₹)">
            <input type="number" step="500" value={form.monthly} onChange={set('monthly')} />
          </Field>
          <Field label="Interest rate (%)">
            <input type="number" step="0.05" value={form.ratePct} onChange={set('ratePct')} />
          </Field>
          <Field label="Tenure (months)">
            <input type="number" step="1" min="1" value={form.months} onChange={set('months')} />
          </Field>
          <Field label="Compounding">
            <Select value={form.compounds} onChange={set('compounds')} options={COMPOUND} />
          </Field>
        </div>
      </Card>

      <Card title="Result" pad>
        <div className="grid kpi-row" style={{ marginBottom: 0 }}>
          <div className="kpi">
            <div className="label">Maturity value</div>
            <div className="value">{fmtINR(r.maturity)}</div>
            <div className="foot">after {form.months} deposits</div>
          </div>
          <div className="kpi">
            <div className="label">Total invested</div>
            <div className="value">{fmtINR(r.invested)}</div>
            <div className="foot">₹{Number(form.monthly).toLocaleString('en-IN')} × {form.months}</div>
          </div>
          <div className="kpi">
            <div className="label">Interest earned</div>
            <div className="value">{fmtINR(r.interest)}</div>
            <div className="foot">{form.ratePct}% p.a.</div>
          </div>
        </div>
      </Card>
    </div>
  );
}
