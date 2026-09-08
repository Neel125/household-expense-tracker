// One button, composed from the design-system classes. Variants map to the
// existing .btn-* modifiers so styling stays centralised in styles.css.
const VARIANTS = {
  default: '',
  primary: 'btn-primary',
  ghost: 'btn-ghost',
  danger: 'btn-ghost btn-danger',
  'primary-danger': 'btn-primary btn-danger',
};

export default function Button({ variant = 'default', size, className = '', type = 'button', ...props }) {
  const classes = ['btn', VARIANTS[variant] || '', size === 'sm' ? 'btn-sm' : '', className]
    .filter(Boolean)
    .join(' ');
  return <button type={type} className={classes} {...props} />;
}
