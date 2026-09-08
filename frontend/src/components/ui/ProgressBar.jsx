// A labelled progress meter, reusing the .meter styling. `pct` is 0..100+;
// over 100 flips it to the "over" (warning) colour.
export default function ProgressBar({ pct, over }) {
  const clamped = Math.min(100, Math.max(0, pct || 0));
  const isOver = over ?? pct > 100;
  return (
    <div className={'meter' + (isOver ? ' over' : '')}>
      <span style={{ width: clamped + '%' }} />
    </div>
  );
}
