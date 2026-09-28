import type { DashboardSummaryDto } from '../dto/dashboard';

// Synthetic network-wide snapshot, independent of the six prediction test cases.
export const dashboardSummaryFixture: DashboardSummaryDto = {
  generated_at: '2026-09-20T15:42:00Z',
  model_version: '7.2',
  channels: {
    total: 12480,
    ml_supported: 9984,
    ml_unsupported: 2496,
    coverage_percent: 80,
  },
  predictions: {
    active: 137,
    critical: 8,
    high: 24,
    medium: 61,
    flash_1_6h: 6,
    urgent_6_24h: 26,
    planned_24_48h: 61,
  },
  objects: {
    total: 186,
    affected: 42,
    critical: 5,
  },
  tickets: {
    draft: 12,
    approved: 19,
    completed_today: 7,
  },
};
