/**
 * Presentation-only scales for the two numeric operational metrics in the registries.
 *
 * They describe the magnitude of the metric itself so a long column can be scanned quickly, and
 * they are never a risk or urgency computation: `riskLevel` and `maintenanceUrgency` always come
 * from the backend. A 46% probability can legitimately sit in a critical row — the number keeps
 * its own scale and the risk column keeps the backend verdict.
 */
export type MetricTone = 'critical' | 'high' | 'medium' | null;
/** Failure probability is a 0..1 fraction; the higher it is, the louder it reads. */
export function probabilityTone(value: number | null): MetricTone {
  if (value === null || !Number.isFinite(value)) return null;
  if (value >= 0.8) return 'critical';
  if (value >= 0.6) return 'high';
  if (value >= 0.4) return 'medium';
  return null;
}
/** ИТС is a 0..100 condition index where a low value is the worrying end of the scale. */
export function healthIndexTone(value: number | null): MetricTone {
  if (value === null || !Number.isFinite(value)) return null;
  if (value < 30) return 'critical';
  if (value < 50) return 'high';
  if (value < 70) return 'medium';
  return null;
}
