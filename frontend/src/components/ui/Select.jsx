import { Children, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

// Custom listbox instead of a native <select>. Native pickers inside a
// modal (overflow, backdrop-filter, Linux Chromium) open and immediately
// close; this menu is position:fixed on document.body so it stays put.
// onChange still looks like a <select> event: { target: { value, name } }.

function textOf(node) {
  if (node == null || typeof node === 'boolean') return '';
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(textOf).join('');
  if (node.props) return textOf(node.props.children);
  return '';
}

function childrenToOptions(children) {
  const out = [];
  Children.forEach(children, (child) => {
    if (!child || typeof child !== 'object') return;
    if (child.type === 'optgroup') {
      out.push(...childrenToOptions(child.props.children));
      return;
    }
    if (child.type !== 'option') return;
    const label = textOf(child.props.children);
    const raw = child.props.value !== undefined ? child.props.value : label;
    out.push({ value: raw === undefined || raw === null ? '' : String(raw), label });
  });
  return out;
}

function normalizeOptions(options, children, placeholder) {
  let items;
  if (options) {
    items = options.map((o) => {
      if (typeof o === 'object' && o !== null) {
        return { value: String(o.value), label: o.label };
      }
      return { value: String(o), label: String(o) };
    });
  } else {
    items = childrenToOptions(children);
  }
  if (placeholder !== undefined && !items.some((o) => o.value === '')) {
    items = [{ value: '', label: placeholder || '—' }, ...items];
  }
  return items;
}

export default function Select({
  options,
  placeholder,
  children,
  value,
  onChange,
  disabled,
  required,
  className = '',
  id,
  name,
  autoFocus,
}) {
  const items = useMemo(
    () => normalizeOptions(options, children, placeholder),
    [options, children, placeholder],
  );
  const strValue = value === undefined || value === null ? '' : String(value);
  const selected = items.find((o) => o.value === strValue);
  const label = selected ? selected.label : placeholder || 'Select…';
  const isPlaceholder = !selected || selected.value === '';

  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [pos, setPos] = useState(null);
  const wrapRef = useRef(null);
  const menuRef = useRef(null);
  const listId = useId();

  function commit(next) {
    onChange?.({ target: { value: next, name } });
    setOpen(false);
  }

  function place() {
    const el = wrapRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const maxH = Math.min(280, window.innerHeight * 0.5);
    const gap = 4;
    const spaceBelow = window.innerHeight - r.bottom - gap;
    const spaceAbove = r.top - gap;
    const openUp = spaceBelow < Math.min(maxH, 160) && spaceAbove > spaceBelow;
    const height = Math.max(80, Math.min(maxH, openUp ? spaceAbove : spaceBelow));
    setPos({
      left: r.left,
      width: Math.max(r.width, 120),
      maxHeight: height,
      top: openUp ? undefined : r.bottom + gap,
      bottom: openUp ? window.innerHeight - r.top + gap : undefined,
    });
  }

  useLayoutEffect(() => {
    if (!open) return;
    const idx = items.findIndex((o) => o.value === strValue);
    setActive(idx >= 0 ? idx : 0);
    place();
  }, [open, items, strValue]);

  useEffect(() => {
    if (!open || !pos) return;
    menuRef.current?.focus();
  }, [open, pos]);

  useEffect(() => {
    if (!open) return;
    const onScrollOrResize = () => place();
    const onDown = (e) => {
      if (wrapRef.current?.contains(e.target) || menuRef.current?.contains(e.target)) return;
      setOpen(false);
    };
    const onKey = (e) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        setOpen(false);
        wrapRef.current?.querySelector('button')?.focus();
      }
    };
    window.addEventListener('resize', onScrollOrResize);
    window.addEventListener('scroll', onScrollOrResize, true);
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('resize', onScrollOrResize);
      window.removeEventListener('scroll', onScrollOrResize, true);
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const node = menuRef.current?.querySelector('[data-active="true"]');
    node?.scrollIntoView({ block: 'nearest' });
  }, [open, active]);

  function onTriggerKey(e) {
    if (disabled) return;
    if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      setOpen(true);
    }
  }

  function onMenuKey(e) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActive((i) => Math.min(items.length - 1, i + 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActive((i) => Math.max(0, i - 1));
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      const pick = items[active];
      if (pick) commit(pick.value);
    } else if (e.key === 'Home') {
      e.preventDefault();
      setActive(0);
    } else if (e.key === 'End') {
      e.preventDefault();
      setActive(items.length - 1);
    } else if (e.key === 'Tab') {
      setOpen(false);
    }
  }

  const menu = open && pos && createPortal(
    <ul
      ref={menuRef}
      id={listId}
      role="listbox"
      className="select-menu"
      tabIndex={-1}
      onKeyDown={onMenuKey}
      style={{
        left: pos.left,
        width: pos.width,
        maxHeight: pos.maxHeight,
        top: pos.top,
        bottom: pos.bottom,
      }}
    >
      {items.map((o, i) => (
        <li
          key={`${o.value}-${i}`}
          role="option"
          aria-selected={o.value === strValue}
          data-active={active === i ? 'true' : undefined}
          className={
            'select-option'
            + (o.value === strValue ? ' is-selected' : '')
            + (active === i ? ' is-active' : '')
          }
          onMouseEnter={() => setActive(i)}
          onPointerDown={(e) => {
            e.preventDefault();
            commit(o.value);
          }}
        >
          {o.label}
        </li>
      ))}
    </ul>,
    document.body,
  );

  return (
    <div ref={wrapRef} className={'select-wrap' + (className ? ' ' + className : '')}>
      <button
        type="button"
        id={id}
        className={'select-trigger' + (isPlaceholder ? ' is-placeholder' : '')}
        disabled={disabled}
        autoFocus={autoFocus}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        onClick={() => !disabled && setOpen((v) => !v)}
        onKeyDown={onTriggerKey}
      >
        {label}
      </button>
      {required && (
        <select
          tabIndex={-1}
          aria-hidden="true"
          required
          name={name}
          value={strValue}
          onChange={() => {}}
          className="select-native-mirror"
        >
          {items.map((o, i) => (
            <option key={`${o.value}-${i}`} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      )}
      {menu}
    </div>
  );
}
