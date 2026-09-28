import { describe, expect, it } from 'vitest';
import { toDashboardSummary } from './dashboard';
import { dashboardSummaryFixture } from '../mocks/dashboard';

describe('Dashboard Summary adapter', () => {
  it('maps the full aggregate to camelCase without retaining DTO object references', () => {
    const summary = toDashboardSummary(dashboardSummaryFixture);
    expect(summary).toEqual({
      generatedAt: '2026-09-20T15:42:00Z',
      modelVersion: '7.2',
      channels: { total: 12480, mlSupported: 9984, mlUnsupported: 2496, coveragePercent: 80 },
      predictions: {
        active: 137,
        critical: 8,
        high: 24,
        medium: 61,
        flash1To6h: 6,
        urgent6To24h: 26,
        planned24To48h: 61,
      },
      objects: { total: 186, affected: 42, critical: 5 },
      tickets: { draft: 12, approved: 19, completedToday: 7 },
    });
    expect(summary.objects).not.toBe(dashboardSummaryFixture.objects);
  });

  it('preserves backend coverage and active counts instead of recomputing aggregates', () => {
    const summary = toDashboardSummary({
      ...dashboardSummaryFixture,
      channels: { ...dashboardSummaryFixture.channels, coverage_percent: 79.75 },
      predictions: { ...dashboardSummaryFixture.predictions, active: 151 },
    });
    expect(summary.channels.coveragePercent).toBe(79.75);
    expect(summary.predictions.active).toBe(151);
  });
});
