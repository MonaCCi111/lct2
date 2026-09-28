import { formatDataAge, formatDateTime } from '../../utils/formatters';

/**
 * Data freshness in one place: the relative age is what the operator reads, while the exact
 * Moscow timestamp stays available through the title and to screen readers. No stale threshold is
 * implied — the backend does not define one, so the label never turns into a warning by itself.
 */
export function UpdatedAtLabel({
  value,
  prefix = 'Обновлено',
  fallback = '—',
  className,
}: {
  value: string | null | undefined;
  prefix?: string;
  fallback?: string;
  className?: string;
}) {
  if (value === null || value === undefined) return <span className={className}>{fallback}</span>;
  const exact = formatDateTime(value);
  return (
    <time className={`updated-at ${className ?? ''}`} dateTime={value} title={exact}>
      {prefix} {formatDataAge(value)}
      <span className="sr-only">, точное время {exact}</span>
    </time>
  );
}
