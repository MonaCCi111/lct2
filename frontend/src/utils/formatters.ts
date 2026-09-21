import type { MaintenanceUrgency, RiskLevel } from '../domain/prediction/types';
export const riskLabels: Record<RiskLevel, string> = {
  low: 'Низкий',
  medium: 'Умеренный',
  high: 'Высокий',
  critical: 'Критический',
};
export const urgencyLabels: Record<MaintenanceUrgency, string> = {
  NORMAL: 'Штатный режим',
  PLANNED_24_48H: '24–48 ч',
  URGENT_6_24H: '6–24 ч',
  FLASH_1_6H: '1–6 ч',
};
export const getRiskLabel = (risk: RiskLevel | null) => (risk === null ? 'Нет данных' : riskLabels[risk]);
export const getUrgencyLabel = (urgency: MaintenanceUrgency | null) =>
  urgency === null ? 'Нет данных' : urgencyLabels[urgency];
const probabilityFormatter = new Intl.NumberFormat('ru-RU', { style: 'percent', maximumFractionDigits: 0 });
const numberFormatter = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 });
const coverageFormatter = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 1 });
const relativeFormatter = new Intl.RelativeTimeFormat('ru-RU', { numeric: 'auto' });
export const formatCount = (value: number) => numberFormatter.format(value);
export const formatCoverage = (value: number) => `${coverageFormatter.format(value)}%`;
export const formatProbability = (value: number | null) =>
  value === null || !Number.isFinite(value) ? '—' : probabilityFormatter.format(value);
export const formatHealthIndex = (value: number | null) =>
  value === null || !Number.isFinite(value) ? '—' : numberFormatter.format(value);
// Display only: numeric piket values stay numbers for filtering, sorting and topology geometry.
export function formatPiket(value: number | null) {
  if (value === null || !Number.isFinite(value)) return '—';
  const piket = Math.trunc(value);
  const meters = Math.round((value - piket) * 100);
  return meters === 0 ? `ПК ${piket}` : `ПК ${piket}+${String(meters).padStart(2, '0')}`;
}
export const OPERATIONAL_TIME_ZONE = 'Europe/Moscow';
const dateTimeFormatter = new Intl.DateTimeFormat('ru-RU', {
  timeZone: OPERATIONAL_TIME_ZONE,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
});
const timeFormatter = new Intl.DateTimeFormat('ru-RU', {
  timeZone: OPERATIONAL_TIME_ZONE,
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
});
export function formatOperationalTime(value: string | number | null) {
  const instant = timestamp(value);
  return Number.isFinite(instant) ? timeFormatter.format(instant) : '—';
}

function timestamp(value: string | number | null): number {
  if (value === null) return Number.NaN;
  // Operational API strings must carry an offset; never infer the browser's timezone.
  if (typeof value === 'string' && !/T.*(?:Z|[+-]\d{2}:\d{2})$/i.test(value)) return Number.NaN;
  return new Date(value).getTime();
}

export function formatDateTime(value: string | number | null) {
  const instant = timestamp(value);
  return Number.isFinite(instant) ? `${dateTimeFormatter.format(instant)} МСК` : '—';
}
export function formatRelativeTime(value: string | number | null, now = Date.now()) {
  const instant = timestamp(value);
  if (!Number.isFinite(instant) || !Number.isFinite(now)) return '—';
  const seconds = Math.round((instant - now) / 1000);
  const formatter = relativeFormatter;
  if (Math.abs(seconds) < 60) return formatter.format(seconds, 'second');
  if (Math.abs(seconds) < 3600) return formatter.format(Math.round(seconds / 60), 'minute');
  if (Math.abs(seconds) < 86400) return formatter.format(Math.round(seconds / 3600), 'hour');
  return formatter.format(Math.round(seconds / 86400), 'day');
}
