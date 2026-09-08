// A content card. `pad` adds inner padding; `title`/`hint`/`actions` render
// the standard card header row.
export default function Card({ title, hint, actions, pad = false, className = '', children, ...props }) {
  const hasHead = title || actions;
  return (
    <div className={'card ' + className} {...props}>
      {hasHead && (
        <div className="card-head">
          <div className="card-title">
            {title}
            {hint && <span className="hint"> · {hint}</span>}
          </div>
          {actions && <div className="card-head-actions">{actions}</div>}
        </div>
      )}
      {pad ? <div className="card-pad">{children}</div> : children}
    </div>
  );
}
