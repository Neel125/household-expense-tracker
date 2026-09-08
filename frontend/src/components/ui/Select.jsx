// A <select> that can take an `options` array of strings/{value,label} or
// arbitrary children.
export default function Select({ options, placeholder, children, ...props }) {
  return (
    <select {...props}>
      {placeholder !== undefined && <option value="">{placeholder}</option>}
      {options
        ? options.map((o) => {
            const value = typeof o === 'object' ? o.value : o;
            const label = typeof o === 'object' ? o.label : o;
            return (
              <option key={value} value={value}>
                {label}
              </option>
            );
          })
        : children}
    </select>
  );
}
