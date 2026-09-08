// Small profile avatar. Falls back to first-letter initials when no image
// URL is provided. `size` maps to a CSS class so the same primitive can
// serve the sidebar chip, the profile header, and the family cards.
export default function Avatar({ src, name, size = 'md', className = '' }) {
  const initial = (name || '?').trim().slice(0, 1).toUpperCase() || '?';
  const cls = ['avatar', `avatar-${size}`, className].filter(Boolean).join(' ');
  if (src) {
    return (
      <span className={cls} aria-label={name}>
        <img src={src} alt="" />
      </span>
    );
  }
  return <span className={cls} aria-label={name}>{initial}</span>;
}
