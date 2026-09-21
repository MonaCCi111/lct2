import type { AnalyticsRange, AnalyticsSummaryDto } from '../dto/analytics';
const generatedAt = '2026-09-20T15:42:00Z';
export const analyticsRangeHours: Record<AnalyticsRange, number> = { '24h': 24, '7d': 168, '30d': 720 };
// Authored historical snapshots, independent of the prediction and ticket list fixtures.
const history: Record<AnalyticsRange, number[][]> = {
  '24h': [
    [5, 20, 57],
    [5, 21, 58],
    [6, 20, 57],
    [6, 22, 59],
    [7, 22, 60],
    [6, 23, 59],
    [6, 24, 61],
    [7, 23, 62],
    [7, 25, 62],
    [9, 26, 63],
    [9, 25, 62],
    [8, 25, 60],
    [8, 24, 61],
  ],
  '7d': [
    [4, 18, 51],
    [5, 19, 53],
    [4, 21, 54],
    [6, 20, 56],
    [7, 22, 58],
    [6, 23, 60],
    [5, 20, 57],
    [8, 24, 61],
  ],
  '30d': [
    [3, 14, 40],
    [4, 15, 43],
    [3, 17, 45],
    [5, 16, 46],
    [4, 18, 48],
    [6, 19, 47],
    [5, 17, 49],
    [4, 19, 50],
    [6, 21, 52],
    [7, 20, 54],
    [5, 22, 53],
    [6, 23, 55],
    [5, 19, 53],
    [6, 20, 56],
    [6, 23, 60],
    [8, 24, 61],
  ],
};
function fixture(range: AnalyticsRange): AnalyticsSummaryDto {
  const values = history[range];
  const end = Date.parse(generatedAt);
  const duration = analyticsRangeHours[range] * 3_600_000;
  return {
    generated_at: generatedAt,
    range,
    totals: {
      active_predictions: 137,
      critical_predictions: 8,
      high_predictions: 24,
      open_tickets: 9,
      completed_tickets: range === '24h' ? 1 : range === '7d' ? 3 : 4,
      ml_coverage_percent: 80,
    },
    risk_timeline: values.map(([critical = 0, high = 0, medium = 0], index) => ({
      timestamp: new Date(end - duration + (duration * index) / (values.length - 1)).toISOString(),
      critical,
      high,
      medium,
    })),
    urgency_distribution: [
      { urgency: 'FLASH_1_6H', count: 6 },
      { urgency: 'URGENT_6_24H', count: 26 },
      { urgency: 'PLANNED_24_48H', count: 61 },
      { urgency: 'NORMAL', count: 44 },
    ],
    top_objects: [
      {
        object_id: 203,
        object_name: 'объект Фита',
        risk_level: 'critical',
        active_predictions: 24,
        critical_predictions: 4,
        high_predictions: 7,
        open_tickets: 3,
      },
      {
        object_id: 201,
        object_name: 'объект Альфа',
        risk_level: 'critical',
        active_predictions: 19,
        critical_predictions: 2,
        high_predictions: 5,
        open_tickets: 2,
      },
      {
        object_id: 202,
        object_name: 'объект Бета',
        risk_level: 'critical',
        active_predictions: 16,
        critical_predictions: 1,
        high_predictions: 4,
        open_tickets: 1,
      },
      {
        object_id: 204,
        object_name: 'объект Кси',
        risk_level: 'critical',
        active_predictions: 14,
        critical_predictions: 1,
        high_predictions: 3,
        open_tickets: 1,
      },
      {
        object_id: 205,
        object_name: 'объект Тау',
        risk_level: 'high',
        active_predictions: 12,
        critical_predictions: 0,
        high_predictions: 3,
        open_tickets: 1,
      },
    ],
    ticket_status_distribution: [
      { status: 'draft', count: 5 },
      { status: 'approved', count: 4 },
      { status: 'rejected', count: 2 },
      { status: 'completed', count: 4 },
    ],
    ml_domain_coverage: [
      { domain: 'POWER_PHASE', channels_total: 3000, channels_supported: 2400, coverage_percent: 80 },
      { domain: 'ANALOG_TEMP', channels_total: 2500, channels_supported: 2100, coverage_percent: 84 },
      { domain: 'ANALOG_GAS', channels_total: 2000, channels_supported: 1500, coverage_percent: 75 },
      { domain: 'FIRE_SAFETY', channels_total: 2480, channels_supported: 1984, coverage_percent: 80 },
      { domain: 'HYDRO_MECHANICS', channels_total: 2500, channels_supported: 2000, coverage_percent: 80 },
    ],
  };
}
export const analyticsFixtures: Record<AnalyticsRange, AnalyticsSummaryDto> = {
  '24h': fixture('24h'),
  '7d': fixture('7d'),
  '30d': fixture('30d'),
};
export function emptyAnalytics(range: AnalyticsRange): AnalyticsSummaryDto {
  return {
    generated_at: generatedAt,
    range,
    totals: {
      active_predictions: 0,
      critical_predictions: 0,
      high_predictions: 0,
      open_tickets: 0,
      completed_tickets: 0,
      ml_coverage_percent: 0,
    },
    risk_timeline: [],
    urgency_distribution: [],
    top_objects: [],
    ticket_status_distribution: [],
    ml_domain_coverage: [],
  };
}
