import { useMemo, useState } from 'react';
import { Card, Field } from '../../components/ui';
import { fmtINR } from '../../lib/format';
import { sipFutureValue } from '../../lib/finance';

export default function SIPCalculator() {
  const [form, setForm] = useState({ monthly: 10000, returnPct: 12, years: 15, stepUpPct: 10 });
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const flat = useMemo(
    () => sipFutureValue(Number(form.monthly) || 0, Number(form.returnPct) || 0, Number(form.years) || 0, 0),
    [form]
  );
  const stepped = useMemo(
    () =>
      sipFutureValue(
        Number(form.monthly) || 0,
        Number(form.returnPct) || 0,
        Number(form.years) || 0,
        Number(form.stepUpPct) || 0
      ),
    [form]
  );

  const bonus = stepped.futureValue - flat.futureValue;

  return (
    <div className="grid two-col">
      <Card title="SIP" pad>
        <div className="form-grid">
          <Field label="Monthly investment (₹)">
            <input type="number" step="500" value={form.monthly} onChange={set('monthly')} />
          </Field>
          <Field label="Expected return (% p.a.)">
            <input type="number" step="0.5" value={form.returnPct} onChange={set('returnPct')} />
          </Field>
          <Field label="Tenure (years)">
            <input type="number" step="1" min="1" value={form.years} onChange={set('years')} />
          </Field>
          <Field label="Annual step-up (%)" hint="SIP amount grows this % every year.">
            <input type="number" step="1" value={form.stepUpPct} onChange={set('stepUpPct')} />
          </Field>
        </div>
      </Card>

      <Card title="Result" pad>
        <div className="grid kpi-row" style={{ marginBottom: 0 }}>
          <div className="kpi">
            <div className="label">Future value</div>
            <div className="value">{fmtINR(stepped.futureValue)}</div>
            <div className="foot">with {form.stepUpPct}% annual step-up</div>
          </div>
          <div className="kpi">
            <div className="label">Total invested</div>
            <div className="value">{fmtINR(stepped.invested)}</div>
            <div className="foot">over {form.years} year(s)</div>
          </div>
          <div className="kpi">
            <div className="label">Wealth gained</div>
            <div className="value">{fmtINR(stepped.gains)}</div>
            <div className="foot">returns at {form.returnPct}% p.a.</div>
          </div>
        </div>

        {Number(form.stepUpPct) > 0 && (
          <div className="calc-note" style={{ marginTop: 14 }}>
            A flat SIP (no step-up) would end at <strong>{fmtINR(flat.futureValue)}</strong>. Stepping
            up by {form.stepUpPct}% every year gives you <strong>{fmtINR(bonus)}</strong> more.
          </div>
        )}
      </Card>
    </div>
  );
}
