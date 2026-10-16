import { useEffect, useMemo, useState } from 'react';
import { Button, Card, EmptyState, Field, Modal, PageHeader, Pill, SegmentedControl, Select } from '../components/ui';
import { useData } from '../context/DataContext';
import { fmtINR, shortDate } from '../lib/format';
import {
  CHALLAN_STATUSES,
  FUELS,
  RECORD_KINDS,
  VEHICLE_KINDS,
  paperLabel,
  paperTone,
  recordMeta,
  vehicleIcon,
} from '../lib/garageMeta';

const BLANK_VEHICLE = {
  id: null,
  name: '',
  kind: 'car',
  registration: '',
  make: '',
  model: '',
  year: '',
  color: '',
  fuel: 'petrol',
  chassisNo: '',
  engineNo: '',
  purchaseDate: '',
  odometer: '',
  notes: '',
};

const BLANK_RECORD = {
  id: null,
  kind: 'maintenance',
  title: '',
  date: '',
  expiryDate: '',
  amount: '',
  vendor: '',
  reference: '',
  odometer: '',
  status: 'unpaid',
  notes: '',
};

const DETAIL_TABS = [
  { value: 'papers', label: 'Papers' },
  { value: 'service', label: 'Service' },
  { value: 'challans', label: 'Challans' },
  { value: 'all', label: 'All' },
];

function VehicleModal({ initial, onSave, onClose }) {
  const [form, setForm] = useState(initial);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function submit(e) {
    e.preventDefault();
    const ok = await onSave({
      name: form.name.trim(),
      kind: form.kind,
      registration: form.registration.trim(),
      make: form.make.trim(),
      model: form.model.trim(),
      year: Number(form.year) || 0,
      color: form.color.trim(),
      fuel: form.fuel,
      chassisNo: form.chassisNo.trim(),
      engineNo: form.engineNo.trim(),
      purchaseDate: form.purchaseDate,
      odometer: Number(form.odometer) || 0,
      notes: form.notes.trim(),
    });
    if (ok) onClose();
  }

  return (
    <Modal title={form.id ? `Edit ${form.name || 'vehicle'}` : 'Add vehicle'} onClose={onClose} size="form">
      <form onSubmit={submit}>
        <div className="form-grid">
          <Field label="Name">
            <input value={form.name} onChange={set('name')} placeholder="e.g. Honda City" required autoFocus />
          </Field>
          <Field label="Type">
            <Select value={form.kind} onChange={set('kind')} options={VEHICLE_KINDS} />
          </Field>
          <Field label="Registration">
            <input value={form.registration} onChange={set('registration')} placeholder="GJ01AB1234" />
          </Field>
          <Field label="Make">
            <input value={form.make} onChange={set('make')} placeholder="Honda" />
          </Field>
          <Field label="Model">
            <input value={form.model} onChange={set('model')} placeholder="City" />
          </Field>
          <Field label="Year">
            <input type="number" step="1" value={form.year} onChange={set('year')} placeholder="2020" />
          </Field>
          <Field label="Fuel">
            <Select value={form.fuel} onChange={set('fuel')} options={FUELS} />
          </Field>
          <Field label="Colour">
            <input value={form.color} onChange={set('color')} />
          </Field>
          <Field label="Odometer (km)">
            <input type="number" step="1" value={form.odometer} onChange={set('odometer')} />
          </Field>
          <Field label="Purchase date">
            <input type="date" value={form.purchaseDate} onChange={set('purchaseDate')} />
          </Field>
          <Field label="Chassis no.">
            <input value={form.chassisNo} onChange={set('chassisNo')} />
          </Field>
          <Field label="Engine no.">
            <input value={form.engineNo} onChange={set('engineNo')} />
          </Field>
          <Field label="Notes" className="span-3">
            <input value={form.notes} onChange={set('notes')} placeholder="optional" />
          </Field>
        </div>
        <div className="form-actions">
          <Button type="submit" variant="primary">{form.id ? 'Save' : 'Add vehicle'}</Button>
          <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
        </div>
      </form>
    </Modal>
  );
}

function RecordModal({ vehicle, initial, onSave, onClose }) {
  const [form, setForm] = useState(initial);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const meta = recordMeta(form.kind);

  async function submit(e) {
    e.preventDefault();
    const ok = await onSave(vehicle.id, {
      kind: form.kind,
      title: form.title.trim(),
      date: form.date,
      expiryDate: form.expiryDate,
      amount: Number(form.amount) || 0,
      vendor: form.vendor.trim(),
      reference: form.reference.trim(),
      odometer: Number(form.odometer) || 0,
      status: form.kind === 'challan' ? form.status : '',
      notes: form.notes.trim(),
    }, form.id);
    if (ok) onClose();
  }

  return (
    <Modal
      title={`${form.id ? 'Edit' : 'Add'} ${meta.label.toLowerCase()} · ${vehicle.name}`}
      onClose={onClose}
    >
      <form onSubmit={submit}>
        <Field label="Type">
          <Select value={form.kind} onChange={set('kind')} options={RECORD_KINDS} />
        </Field>
        <Field label="Title">
          <input value={form.title} onChange={set('title')} placeholder={meta.label} />
        </Field>
        <Field label={form.kind === 'challan' ? 'Issued on' : 'Date'}>
          <input type="date" value={form.date} onChange={set('date')} />
        </Field>
        {meta.hasExpiry && (
          <Field label="Valid until">
            <input type="date" value={form.expiryDate} onChange={set('expiryDate')} />
          </Field>
        )}
        <Field label="Amount (₹)">
          <input type="number" step="1" value={form.amount} onChange={set('amount')} />
        </Field>
        <Field label={meta.vendor}>
          <input value={form.vendor} onChange={set('vendor')} />
        </Field>
        <Field label={form.kind === 'challan' ? 'Challan no.' : form.kind === 'insurance' ? 'Policy no.' : 'Reference'}>
          <input value={form.reference} onChange={set('reference')} />
        </Field>
        {meta.hasOdo && (
          <Field label="Odometer (km)">
            <input type="number" step="1" value={form.odometer} onChange={set('odometer')} />
          </Field>
        )}
        {meta.hasStatus && (
          <Field label="Status">
            <Select value={form.status} onChange={set('status')} options={CHALLAN_STATUSES} />
          </Field>
        )}
        <Field label="Notes">
          <input value={form.notes} onChange={set('notes')} />
        </Field>
        <div className="form-actions">
          <Button type="submit" variant="primary">{form.id ? 'Save' : 'Add record'}</Button>
          <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
        </div>
      </form>
    </Modal>
  );
}

function PaperChip({ label, paper }) {
  const days = paper?.daysLeft;
  return (
    <div className="garage-paper">
      <div className="note">{label}</div>
      <div className="garage-paper-val">{paper?.expiryDate ? shortDate(paper.expiryDate) : '—'}</div>
      <Pill tone={paperTone(days)}>{paperLabel(days)}</Pill>
    </div>
  );
}

function RecordRow({ row, onEdit, onDelete }) {
  const meta = recordMeta(row.kind);
  const days = row.daysLeft;
  return (
    <div className="garage-record">
      <div className="garage-record-icon" aria-hidden="true">{meta.icon}</div>
      <div className="garage-record-main">
        <div className="garage-record-title">{row.title || meta.label}</div>
        <div className="note">
          {row.date ? shortDate(row.date) : 'No date'}
          {row.vendor ? ` · ${row.vendor}` : ''}
          {row.reference ? ` · ${row.reference}` : ''}
          {row.odometer ? ` · ${row.odometer.toLocaleString('en-IN')} km` : ''}
        </div>
      </div>
      <div className="garage-record-meta">
        {row.amount > 0 && <div className="num">{fmtINR(row.amount)}</div>}
        {row.kind === 'challan' && (
          <Pill tone={row.status === 'paid' ? 'good' : 'debt'}>{row.status || 'unpaid'}</Pill>
        )}
        {row.expiryDate && <Pill tone={paperTone(days)}>{paperLabel(days)}</Pill>}
      </div>
      <div className="garage-record-actions">
        <Button size="sm" variant="ghost" onClick={() => onEdit(row)}>Edit</Button>
        <Button size="sm" variant="danger" onClick={() => onDelete(row)}>
          Remove
        </Button>
      </div>
    </div>
  );
}

export default function GaragePage() {
  const {
    vehicles,
    addVehicle,
    updateVehicle,
    removeVehicle,
    addVehicleRecord,
    updateVehicleRecord,
    removeVehicleRecord,
  } = useData();
  const [selectedId, setSelectedId] = useState(null);
  const [tab, setTab] = useState('papers');
  const [vehicleModal, setVehicleModal] = useState(null);
  const [recordModal, setRecordModal] = useState(null);

  useEffect(() => {
    if (!vehicles.length) {
      setSelectedId(null);
      return;
    }
    if (!vehicles.some((v) => v.id === selectedId)) setSelectedId(vehicles[0].id);
  }, [vehicles, selectedId]);

  const selected = vehicles.find((v) => v.id === selectedId) || null;

  const stats = useMemo(() => {
    const alerts = vehicles.reduce((n, v) => n + (v.alertCount || 0), 0);
    const challans = vehicles.reduce((n, v) => n + (v.unpaidChallans || 0), 0);
    const fine = vehicles.reduce((n, v) => n + (v.unpaidChallanAmount || 0), 0);
    return { alerts, challans, fine };
  }, [vehicles]);

  const visibleRecords = useMemo(() => {
    if (!selected) return [];
    const rows = selected.records || [];
    if (tab === 'service') return rows.filter((r) => r.kind === 'maintenance');
    if (tab === 'challans') return rows.filter((r) => r.kind === 'challan');
    if (tab === 'papers') return rows.filter((r) => ['insurance', 'puc', 'rc', 'fitness'].includes(r.kind));
    return rows;
  }, [selected, tab]);

  function editVehicle(v) {
    setVehicleModal({
      ...BLANK_VEHICLE,
      ...v,
      year: v.year || '',
      odometer: v.odometer || '',
    });
  }

  function editRecord(row) {
    setRecordModal({
      ...BLANK_RECORD,
      ...row,
      amount: row.amount || '',
      odometer: row.odometer || '',
      status: row.status || 'unpaid',
    });
  }

  async function saveRecord(vehicleId, payload, id) {
    return id
      ? updateVehicleRecord(vehicleId, id, payload)
      : addVehicleRecord(vehicleId, payload);
  }

  return (
    <section className="garage-page">
      <PageHeader title="Garage" subtitle="Household vehicles — insurance, PUC, RC, service and challans in one place.">
        <Button variant="primary" size="sm" onClick={() => setVehicleModal({ ...BLANK_VEHICLE })}>
          + Add vehicle
        </Button>
      </PageHeader>

      {vehicles.length > 0 && (
        <div className="grid kpi-row">
          <div className="kpi">
            <div className="label">Vehicles</div>
            <div className="value">{vehicles.length}</div>
            <div className="foot">on this household</div>
          </div>
          <div className="kpi">
            <div className="label">Due soon</div>
            <div className={'value' + (stats.alerts ? ' tone-warning' : '')}>{stats.alerts}</div>
            <div className="foot">papers in 30 days or overdue</div>
          </div>
          <div className="kpi">
            <div className="label">Open challans</div>
            <div className={'value' + (stats.challans ? ' tone-warning' : '')}>{stats.challans}</div>
            <div className="foot">{stats.fine ? fmtINR(stats.fine) + ' unpaid' : 'none unpaid'}</div>
          </div>
        </div>
      )}

      {vehicles.length === 0 ? (
        <Card pad>
          <EmptyState>No vehicles yet — add the first car or bike to track its papers.</EmptyState>
        </Card>
      ) : (
        <div className="garage-layout">
          <div className="garage-list">
            {vehicles.map((v) => (
              <button
                key={v.id}
                type="button"
                className={'garage-card' + (v.id === selectedId ? ' selected' : '')}
                onClick={() => setSelectedId(v.id)}
              >
                <div className="garage-card-icon" aria-hidden="true">{vehicleIcon(v.kind)}</div>
                <div className="garage-card-main">
                  <div className="garage-card-name">{v.name}</div>
                  <div className="note">
                    {v.registration || 'No RC number'}
                    {v.make || v.model ? ` · ${[v.make, v.model].filter(Boolean).join(' ')}` : ''}
                  </div>
                </div>
                {v.alertCount > 0 && <Pill tone="warning">{v.alertCount}</Pill>}
              </button>
            ))}
          </div>

          {selected && (
            <div className="card garage-detail">
              <div className="card-head">
                <div className="card-title">
                  {vehicleIcon(selected.kind)} {selected.name}
                  <span className="hint">
                    {selected.registration ? ` · ${selected.registration}` : ''}
                    {selected.fuel ? ` · ${selected.fuel}` : ''}
                    {selected.odometer ? ` · ${selected.odometer.toLocaleString('en-IN')} km` : ''}
                  </span>
                </div>
                <div className="card-head-actions">
                  <Button size="sm" variant="ghost" onClick={() => editVehicle(selected)}>Edit</Button>
                  <Button
                    size="sm"
                    variant="danger"
                    onClick={() => {
                      if (window.confirm(`Remove ${selected.name} and its records?`)) removeVehicle(selected.id);
                    }}
                  >
                    Remove
                  </Button>
                </div>
              </div>
              <div className="card-pad">
                <div className="garage-papers">
                  <PaperChip label="Insurance" paper={selected.insurance} />
                  <PaperChip label="PUC" paper={selected.puc} />
                  <PaperChip label="RC" paper={selected.rc} />
                  <PaperChip label="Fitness" paper={selected.fitness} />
                </div>
                {selected.unpaidChallans > 0 && (
                  <div className="takeaway">
                    <strong>{selected.unpaidChallans}</strong> unpaid challan
                    {selected.unpaidChallans === 1 ? '' : 's'}
                    {selected.unpaidChallanAmount > 0 ? ` · ${fmtINR(selected.unpaidChallanAmount)}` : ''}.
                  </div>
                )}
                <div className="garage-detail-bar">
                  <SegmentedControl value={tab} onChange={setTab} options={DETAIL_TABS} />
                  <Button
                    size="sm"
                    variant="primary"
                    onClick={() => setRecordModal({
                      ...BLANK_RECORD,
                      kind: tab === 'challans' ? 'challan' : tab === 'service' ? 'maintenance' : tab === 'papers' ? 'insurance' : 'maintenance',
                    })}
                  >
                    + Record
                  </Button>
                </div>
                {visibleRecords.length === 0 ? (
                  <EmptyState>
                    {tab === 'all' ? 'Nothing logged on this vehicle yet.' : `No ${tab} yet.`}
                  </EmptyState>
                ) : (
                  <div className="garage-records">
                    {visibleRecords.map((row) => (
                      <RecordRow
                        key={row.id}
                        row={row}
                        onEdit={editRecord}
                        onDelete={(r) => {
                          if (window.confirm(`Remove this ${recordMeta(r.kind).label.toLowerCase()}?`)) {
                            removeVehicleRecord(selected.id, r.id);
                          }
                        }}
                      />
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {vehicleModal && (
        <VehicleModal
          initial={vehicleModal}
          onClose={() => setVehicleModal(null)}
          onSave={(payload) => (vehicleModal.id ? updateVehicle(vehicleModal.id, payload) : addVehicle(payload))}
        />
      )}
      {recordModal && selected && (
        <RecordModal
          vehicle={selected}
          initial={recordModal}
          onClose={() => setRecordModal(null)}
          onSave={saveRecord}
        />
      )}
    </section>
  );
}
