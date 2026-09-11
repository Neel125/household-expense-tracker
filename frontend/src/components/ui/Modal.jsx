import { useEffect } from 'react';

// A centered dialog over a dimmed overlay. Escape or a press on the dim
// layer closes it.
//
// The blur lives on a sibling behind the dialog — not on an ancestor of
// the form — because Chromium closes native date/select popups when any
// ancestor has backdrop-filter. Close is bound to *mousedown on the dim
// layer*, not click: choosing a picker value fires mousedown on the
// option, the list closes, then the leftover click would otherwise land
// on the overlay and dismiss the whole dialog.
//
// `wide` / `size="wide"` suits tables; `size="form"` is the multi-field
// layout (investments, debts) and grows with the viewport.
export default function Modal({ title, onClose, children, footer, wide = false, size }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose?.();
    window.addEventListener('keydown', onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  const sizeClass =
    size === 'form' || size === 'xl'
      ? ' modal-form'
      : wide || size === 'wide'
        ? ' modal-wide'
        : '';

  return (
    <div className="modal-backdrop">
      <div
        className="modal-backdrop-dim"
        onMouseDown={(e) => {
          if (e.button === 0) onClose?.();
        }}
      />
      <div className={'modal' + sizeClass} role="dialog" aria-modal="true">
        {title && <h3>{title}</h3>}
        {children}
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  );
}
