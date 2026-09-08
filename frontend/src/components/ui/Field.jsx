// A labelled form control wrapper. Compose with Input/Select or raw inputs.
export default function Field({ label, hint, htmlFor, className = '', children }) {
  return (
    <div className={'field ' + className}>
      {label && <label htmlFor={htmlFor}>{label}</label>}
      {children}
      {hint && <div className="note" style={{ marginTop: 4 }}>{hint}</div>}
    </div>
  );
}
