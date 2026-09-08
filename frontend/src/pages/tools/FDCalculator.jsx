import { useMemo, useState } from 'react';
import { Card, Field, Select } from '../../components/ui';
import { fmtINR } from '../../lib/format';
import { fdMaturity } from '../../lib/finance';

const COMPOUND = [
  { value: 12, label: 'Monthly' },
  { value: 4, label: 'Quarterly' },
  { value: 2, label: 'Half-yearly' },
  { value: 1, label: 'Yearly' },
];

export default function FDCalculator() {
  const [form, setForm] = useState({ principal: 100000, ratePct: 7, years: 5, compounds: 4 });
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const r = useMemo(
    () =>
      fdMaturity(
        Number(form.principal) || 0,
        Number(form.ratePct) || 0,
        Number(form.years) || 0,
        Number(form.compounds) || 1
      ),
    [form]
  );

  return (
    <div className="grid two-col">
      <Card title="Fixed deposit" pad>
        <div className="form-grid">
          <Field label="Principal (₹)">
            <input type="number" step="1000" value={form.principal} onChange={set('principal')} />
          </Field>
          <Field label="Interest rate (%)">
            <input type="number" step="0.05" value={form.ratePct} onChange={set('ratePct')} />
          </Field>
          <Field label="Tenure (years)">
            <input type="number" step="0.25" value={form.years} onChange={set('years')} />
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
            <div className="foot">at end of {form.years} year(s)</div>
          </div>
          <div className="kpi">
            <div className="label">Interest earned</div>
            <div className="value">{fmtINR(r.interest)}</div>
            <div className="foot">{form.ratePct}% p.a., compounded {COMPOUND.find((c) => c.value == form.compounds)?.label.toLowerCase()}</div>
          </div>
          <div className="kpi">
            <div className="label">Principal</div>
            <div className="value">{fmtINR(r.principal)}</div>
            <div className="foot">what you deposited</div>
          </div>
        </div>
        <div className="calc-note" style={{ marginTop: 14 }}>
          TDS is deducted by banks when interest crosses the annual threshold — not modelled here.
        </div>
      </Card>
    </div>
  );
}
