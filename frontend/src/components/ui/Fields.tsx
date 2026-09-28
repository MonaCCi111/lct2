import { useId, type InputHTMLAttributes, type SelectHTMLAttributes } from 'react';
import { ChevronDown, Search } from 'lucide-react';
export function Input({
  label,
  className = '',
  id,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  const generatedId = useId();
  return (
    <label className={`field ${className}`} htmlFor={id ?? generatedId}>
      <span>{label}</span>
      <input id={id ?? generatedId} {...props} className="input" />
    </label>
  );
}
export function SearchInput({
  label = 'Поиск',
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label?: string }) {
  return (
    <div className="search-input">
      <Search size={15} aria-hidden="true" />
      <input type="search" {...props} aria-label={label} className="input" />
    </div>
  );
}
export function Select({
  label,
  options,
  id,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & {
  label: string;
  options: readonly { value: string; label: string }[];
}) {
  const generatedId = useId();
  return (
    <div className="field">
      <label htmlFor={id ?? generatedId}>{label}</label>
      <span className="select-wrap">
        <select id={id ?? generatedId} {...props} className="input">
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <ChevronDown size={14} aria-hidden="true" />
      </span>
    </div>
  );
}
