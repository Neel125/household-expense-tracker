// Two-or-more toggle, e.g. Household / Just me. options: [{value,label}].
export default function SegmentedControl({ value, onChange, options }) {
  return (
    <div className="segmented">
      {options.map((o) => (
        <button key={o.value} className={value === o.value ? 'active' : ''} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}
