import { useEffect } from 'react';

// A centered dialog over a backdrop. Escape and backdrop-click close it.
// `wide` widens it for tabular content — the default width suits a form.
export default function Modal({ title, onClose, children, footer, wide = false }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose?.();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="modal-backdrop" onClick={() => onClose?.()}>
      <div className={'modal' + (wide ? ' modal-wide' : '')} onClick={(e) => e.stopPropagation()}>
        {title && <h3>{title}</h3>}
        {children}
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  );
}
