const NECESSITY_TONE = { Need: 'need', Want: 'want', Investment: 'investment', Debt: 'debt' };

// A small status chip. Pass `tone` (good|warning|need|want|...) or a
// `necessity` value which maps to its tone.
export default function Pill({ tone, necessity, children }) {
  const t = tone || NECESSITY_TONE[necessity] || '';
  return (
    <span className={'pill ' + (t ? 'pill-' + t : '')}>
      <span className="dot" />
      {children ?? necessity}
    </span>
  );
}
