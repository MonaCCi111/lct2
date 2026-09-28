import type { AnalyticsRange, AnalyticsSummary } from '../../domain/analytics/types';
import { OPERATIONAL_TIME_ZONE } from '../../utils/formatters';
export const analyticsRangeLabels: Record<AnalyticsRange, string> = {
  '24h': '24 ч',
  '7d': '7 дней',
  '30d': '30 дней',
};
export const isAnalyticsEmpty = (data: AnalyticsSummary) =>
  data.riskTimeline.length === 0 &&
  data.urgencyDistribution.length === 0 &&
  data.topObjects.length === 0 &&
  data.ticketStatusDistribution.length === 0 &&
  data.mlDomainCoverage.length === 0 &&
  Object.values(data.totals).every((value) => value === 0);
export const formatAnalyticsDay = (value: number) =>
  new Intl.DateTimeFormat('ru-RU', {
    timeZone: OPERATIONAL_TIME_ZONE,
    day: '2-digit',
    month: '2-digit',
  }).format(value);
