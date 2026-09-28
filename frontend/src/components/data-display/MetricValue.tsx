import type { MetricTone } from '../../utils/metric-tone';
/**
 * A numeric operational value that carries a restrained severity colour. The text is the value
 * itself — colour only speeds up scanning and never replaces the number or the risk column.
 */
export function MetricValue({ value, tone }: { value: string; tone: MetricTone }) {
  return <span className={`metric-value ${tone ? `tone-${tone}` : ''}`}>{value}</span>;
}
