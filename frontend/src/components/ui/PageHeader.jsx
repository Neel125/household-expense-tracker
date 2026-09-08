// The title / subtitle / right-aligned controls row every page opens with.
export default function PageHeader({ title, subtitle, children }) {
  return (
    <div className="pagehead">
      <div>
        <h1>{title}</h1>
        {subtitle && <div className="sub">{subtitle}</div>}
      </div>
      {children && <div className="pagehead-controls">{children}</div>}
    </div>
  );
}
