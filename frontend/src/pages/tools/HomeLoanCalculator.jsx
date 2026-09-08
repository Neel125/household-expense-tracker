import { useMemo, useRef, useState } from 'react';
import { Button, Card, Field, SegmentedControl, Select } from '../../components/ui';
import { fmtINR } from '../../lib/format';
import { amortize, emiFor, toYearlySummary } from '../../lib/finance';

const MONTHS = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];
const MONTH_OPTIONS = MONTHS.map((label, i) => ({ value: i + 1, label }));

const now = new Date();
const CURRENT_YEAR = now.getFullYear();
const CURRENT_MONTH = now.getMonth() + 1;

// Turn a calendar {month, year} into an offset (1 = the first month of the loan).
function toOffset(startYear, startMonth, month, year) {
  const y = Number(year);
  const m = Number(month);
  if (!y || !m) return 0;
  return (y - Number(startYear)) * 12 + (m - Number(startMonth)) + 1;
}

// Sort helper so events display in chronological order.
function chrono(a, b) {
  return (Number(a.year) - Number(b.year)) * 12 + (Number(a.month) - Number(b.month));
}

function fmtDate(y, m) {
  return MONTHS[m - 1] + ' ' + y;
}

// ---------------------------------------------------------------------------
// Reusable "list of dated events" editor. Each row is month + year + one
// number field (label + suffix supplied by the caller).
function EventEditor({ title, hint, items, setItems, valueLabel, valueSuffix, valueStep, defaultValue }) {
  const idRef = useRef(items.reduce((max, i) => Math.max(max, i.id || 0), 0));
  const add = () => {
    idRef.current += 1;
    setItems([
      ...items,
      { id: idRef.current, month: CURRENT_MONTH, year: CURRENT_YEAR + 1, value: defaultValue },
    ]);
  };
  const update = (id, patch) =>
    setItems(items.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  const remove = (id) => setItems(items.filter((r) => r.id !== id));

  return (
    <div className="event-list">
      <div className="event-head">
        <div>
          <div className="section-label" style={{ margin: 0 }}>{title}</div>
          {hint && <div className="note" style={{ marginTop: 2 }}>{hint}</div>}
        </div>
        <Button size="sm" variant="ghost" onClick={add}>+ Add</Button>
      </div>
      {items.length === 0 ? (
        <div className="note event-empty">No entries yet — click <em>Add</em> to schedule one.</div>
      ) : (
        <div className="event-rows">
          {items.map((row) => (
            <div className="event-row" key={row.id}>
              <Select
                aria-label="Month"
                value={row.month}
                onChange={(e) => update(row.id, { month: Number(e.target.value) })}
                options={MONTH_OPTIONS}
              />
              <input
                aria-label="Year"
                type="number"
                min={CURRENT_YEAR - 30}
                max={CURRENT_YEAR + 60}
                value={row.year}
                onChange={(e) => update(row.id, { year: Number(e.target.value) })}
              />
              <div className="event-value">
                <input
                  aria-label={valueLabel}
                  type="number"
                  step={valueStep}
                  value={row.value}
                  onChange={(e) => update(row.id, { value: e.target.value })}
                />
                {valueSuffix && <span className="event-suffix">{valueSuffix}</span>}
              </div>
              <button
                type="button"
                className="event-remove"
                aria-label="Remove"
                onClick={() => remove(row.id)}
              >×</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
export default function HomeLoanCalculator() {
  const [form, setForm] = useState({
    principal: 5000000,
    ratePct: 8.5,
    tenureYears: 20,
    startMonth: CURRENT_MONTH,
    startYear: CURRENT_YEAR,
  });
  const [prepayments, setPrepayments] = useState([]);
  const [rateChanges, setRateChanges] = useState([]);
  const [stepUps, setStepUps] = useState([]);
  const [view, setView] = useState('year');

  const set = (k) => (e) => {
    const v = e.target ? e.target.value : e;
    setForm((f) => ({ ...f, [k]: v }));
  };

  const parsed = useMemo(() => {
    const P = Number(form.principal) || 0;
    const rate = Number(form.ratePct) || 0;
    const months = Math.max(1, Math.round((Number(form.tenureYears) || 1) * 12));
    const sy = Number(form.startYear) || CURRENT_YEAR;
    const sm = Number(form.startMonth) || CURRENT_MONTH;

    // Map calendar events → month offsets, and drop anything outside the loan
    // window so the user isn't surprised by silently-ignored inputs.
    const mapEvents = (list, valueKey) =>
      list
        .map((e) => ({
          month: toOffset(sy, sm, e.month, e.year),
          [valueKey]: Number(e.value) || 0,
        }))
        .filter((e) => e.month >= 1 && e.month <= months);

    return {
      P,
      rate,
      months,
      opts: {
        startYear: sy,
        startMonth: sm,
        rateChanges: mapEvents(rateChanges, 'newAnnualRatePct'),
        stepUps: mapEvents(stepUps, 'pct'),
        prepayments: mapEvents(prepayments, 'amount'),
      },
    };
  }, [form, prepayments, rateChanges, stepUps]);

  const result = useMemo(
    () => amortize(parsed.P, parsed.rate, parsed.months, parsed.opts),
    [parsed]
  );
  const flatEmi = useMemo(() => emiFor(parsed.P, parsed.rate, parsed.months), [parsed]);
  const yearly = useMemo(() => toYearlySummary(result.schedule), [result.schedule]);

  const scheduledTotalInterest = flatEmi * parsed.months - parsed.P;
  const savedInterest = scheduledTotalInterest - result.totalInterest;
  const savedMonths = parsed.months - result.monthsActual;
  const closedAt = result.schedule[result.schedule.length - 1];
  // With EMI held flat on rate changes, tenure can extend past the original
  // — a hike absorbs into a longer schedule, a drop into a shorter one.
  const extendedMonths = -savedMonths;

  return (
    <div className="grid two-col">
      <Card title="Loan details" pad>
        <div className="form-grid">
          <Field label="Loan amount (₹)">
            <input type="number" step="10000" value={form.principal} onChange={set('principal')} />
          </Field>
          <Field label="Interest rate (%)">
            <input type="number" step="0.01" value={form.ratePct} onChange={set('ratePct')} />
          </Field>
          <Field label="Tenure (years)">
            <input type="number" step="1" min="1" value={form.tenureYears} onChange={set('tenureYears')} />
          </Field>
          <Field label="Start month">
            <Select value={form.startMonth} onChange={set('startMonth')} options={MONTH_OPTIONS} />
          </Field>
          <Field label="Start year">
            <input type="number" min={CURRENT_YEAR - 30} max={CURRENT_YEAR + 30} value={form.startYear} onChange={set('startYear')} />
          </Field>
        </div>

        <EventEditor
          title="Prepayments"
          hint="EMI stays the same — tenure shortens by whatever extra principal you pay."
          items={prepayments}
          setItems={setPrepayments}
          valueLabel="Amount"
          valueSuffix="₹"
          valueStep="10000"
          defaultValue={100000}
        />

        <EventEditor
          title="Interest-rate changes"
          hint="EMI stays the same — tenure shortens if the rate drops, extends if it rises."
          items={rateChanges}
          setItems={setRateChanges}
          valueLabel="New rate"
          valueSuffix="%"
          valueStep="0.05"
          defaultValue={parsed.rate}
        />

        <EventEditor
          title="EMI step-ups"
          hint="The only knob that moves the EMI — each entry bumps it by this %."
          items={stepUps}
          setItems={setStepUps}
          valueLabel="Increase"
          valueSuffix="%"
          valueStep="1"
          defaultValue={10}
        />
      </Card>

      <div className="stacked">
        <Card title="Result" pad>
          <div className="grid kpi-row" style={{ marginBottom: 0 }}>
            <div className="kpi">
              <div className="label">Starting EMI</div>
              <div className="value">{fmtINR(result.startingEmi)}</div>
              <div className="foot">at {parsed.rate}% p.a.</div>
            </div>
            <div className="kpi">
              <div className="label">Final EMI</div>
              <div className="value">{fmtINR(result.finalEmi)}</div>
              <div className="foot">
                {stepUps.length ? 'after step-ups' : 'unchanged'}
              </div>
            </div>
            <div className="kpi">
              <div className="label">Total interest</div>
              <div className="value">{fmtINR(result.totalInterest)}</div>
              <div className="foot">over the life of the loan</div>
            </div>
            <div className="kpi">
              <div className="label">Total paid</div>
              <div className="value">{fmtINR(result.totalPaid)}</div>
              <div className="foot">principal + interest + prepayments</div>
            </div>
            {result.totalPrepaid > 0 && (
              <div className="kpi">
                <div className="label">Prepaid</div>
                <div className="value">{fmtINR(result.totalPrepaid)}</div>
                <div className="foot">extra principal</div>
              </div>
            )}
            <div className="kpi">
              <div className="label">Loan closes</div>
              <div className="value" style={{ fontSize: 18 }}>
                {result.closed && closedAt
                  ? fmtDate(closedAt.calendarYear, closedAt.calendarMonth)
                  : 'Does not close'}
              </div>
              <div className="foot">
                {result.closed
                  ? `${result.monthsActual} months (${(result.monthsActual / 12).toFixed(1)} yrs)`
                  : 'EMI is smaller than the interest — raise it or add a step-up'}
              </div>
            </div>
          </div>

          {!result.closed && (
            <div className="calc-note calc-note-warn" style={{ marginTop: 14 }}>
              With the current EMI and the scheduled rate changes, this loan
              would never close — the interest at some point exceeds the EMI.
              Add an EMI step-up, remove the rate hike, or start with a larger
              EMI (shorter original tenure) to keep the loan viable.
            </div>
          )}

          {result.closed && (savedInterest > 1 || savedMonths !== 0) && (
            <div className="calc-note" style={{ marginTop: 14 }}>
              {savedInterest > 1 ? (
                <>You save <strong>{fmtINR(savedInterest)}</strong> in interest</>
              ) : (
                <>You pay <strong>{fmtINR(-savedInterest)}</strong> more in interest</>
              )}
              {savedMonths > 0 && (
                <> and finish <strong>{savedMonths} month{savedMonths === 1 ? '' : 's'}</strong> early</>
              )}
              {extendedMonths > 0 && (
                <> and take <strong>{extendedMonths} month{extendedMonths === 1 ? '' : 's'}</strong> longer</>
              )}
              {' '}vs. a plain {parsed.rate}% loan.
            </div>
          )}
        </Card>

        <Card
          title="Amortisation schedule"
          hint={`${result.monthsActual} month${result.monthsActual === 1 ? '' : 's'} until closed`}
          actions={
            <SegmentedControl
              value={view}
              onChange={setView}
              options={[
                { value: 'year', label: 'Year-wise' },
                { value: 'month', label: 'Month-wise' },
              ]}
            />
          }
        >
          <div className="card-pad">
            <div className="table-wrap">
              {view === 'year' ? (
                <table>
                  <thead>
                    <tr>
                      <th>Period</th>
                      <th className="num">EMI paid</th>
                      <th className="num">Principal</th>
                      <th className="num">Interest</th>
                      <th className="num">Prepaid</th>
                      <th className="num">Balance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {yearly.map((y) => (
                      <tr key={y.year}>
                        <td>
                          {y.year}
                          {y.months < 12 && (
                            <span className="note"> · {MONTHS[y.fromMonth - 1]}–{MONTHS[y.toMonth - 1]}</span>
                          )}
                        </td>
                        <td className="num">{fmtINR(y.totalEmi)}</td>
                        <td className="num">{fmtINR(y.totalPrincipal)}</td>
                        <td className="num">{fmtINR(y.totalInterest)}</td>
                        <td className="num">{y.totalPrepaid ? fmtINR(y.totalPrepaid) : '—'}</td>
                        <td className="num">{fmtINR(y.endingBalance)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <table>
                  <thead>
                    <tr>
                      <th>Month</th>
                      <th className="num">EMI</th>
                      <th className="num">Principal</th>
                      <th className="num">Interest</th>
                      <th className="num">Prepaid</th>
                      <th className="num">Balance</th>
                      <th className="num">Rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.schedule.map((r) => (
                      <tr key={r.month}>
                        <td>{fmtDate(r.calendarYear, r.calendarMonth)}</td>
                        <td className="num">{fmtINR(r.emi)}</td>
                        <td className="num">{fmtINR(r.principal)}</td>
                        <td className="num">{fmtINR(r.interest)}</td>
                        <td className="num">{r.prepaid ? fmtINR(r.prepaid) : '—'}</td>
                        <td className="num">{fmtINR(r.balance)}</td>
                        <td className="num">{r.annualRate.toFixed(2)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
