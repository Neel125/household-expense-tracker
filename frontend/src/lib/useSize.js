import { useEffect, useRef, useState } from 'react';

// Reports the pixel width of the element the returned ref is attached to.
// The SVG charts use this to draw at a 1:1 viewBox — i.e. one user unit is
// one CSS pixel — so their labels stay ~10px on a phone and on an ultrawide
// instead of scaling down into illegibility with the container.
export function useContainerWidth(fallback = 560) {
  const ref = useRef(null);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof ResizeObserver === 'undefined') {
      // Old browsers / jsdom: measure once and follow window resizes.
      const read = () => setWidth(el.clientWidth);
      read();
      window.addEventListener('resize', read);
      return () => window.removeEventListener('resize', read);
    }
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect?.width;
      if (w) setWidth(Math.round(w));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return [ref, width || fallback];
}

// Truncates a label to roughly the pixel budget available for it, so long
// card names don't collide with their neighbours on a narrow chart.
export function fitLabel(text, px, perChar = 5.6) {
  const max = Math.max(3, Math.floor(px / perChar));
  return text.length > max ? text.slice(0, max - 1) + '…' : text;
}
