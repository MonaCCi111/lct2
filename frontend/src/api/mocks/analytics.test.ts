import { describe, it, expect } from 'vitest';
import { analyticsFixtures, analyticsRangeHours, emptyAnalytics } from './analytics';
import { toAnalyticsSummary } from '../adapters/analytics';
import { analyticsKeys } from '../queries/keys';
import { isAnalyticsEmpty, formatAnalyticsDay } from '../../pages/analytics/analytics-model';
import type { AnalyticsRange } from '../dto/analytics';
describe('analytics aggregate contract', () => {
  for (const range of ['24h', '7d', '30d'] as AnalyticsRange[]) {
    const dto = analyticsFixtures[range];
    it(`${range}: keeps range, historical density, sorted timestamps inside requested window`, () => {
      expect(dto.range).toBe(range);
      const limits = range === '24h' ? [12, 24] : range === '7d' ? [7, 14] : [15, 30];
      expect(dto.risk_timeline.length).toBeGreaterThanOrEqual(limits[0]!);
      expect(dto.risk_timeline.length).toBeLessThanOrEqual(limits[1]!);
      const times = dto.risk_timeline.map((p) => Date.parse(p.timestamp));
      expect(times).toEqual([...times].sort((a, b) => a - b));
      expect(new Set(times).size).toBe(times.length);
      for (const time of times) {
        expect(time).toBeLessThanOrEqual(Date.parse(dto.generated_at));
        expect(time).toBeGreaterThanOrEqual(
          Date.parse(dto.generated_at) - analyticsRangeHours[range] * 3600000,
        );
      }
    });
    it(`${range}: counts, snapshot totals and coverage agree`, () => {
      function nonnegative(value: unknown) {
        if (typeof value === 'number') {
          expect(value).toBeGreaterThanOrEqual(0);
          expect(Number.isFinite(value)).toBe(true);
        } else if (value && typeof value === 'object') Object.values(value).forEach(nonnegative);
      }
      nonnegative(dto);
      expect(dto.risk_timeline.at(-1)).toMatchObject({
        critical: dto.totals.critical_predictions,
        high: dto.totals.high_predictions,
      });
      expect(dto.urgency_distribution.reduce((sum, item) => sum + item.count, 0)).toBe(
        dto.totals.active_predictions,
      );
      expect(
        dto.ticket_status_distribution
          .filter((item) => item.status === 'draft' || item.status === 'approved')
          .reduce((sum, item) => sum + item.count, 0),
      ).toBe(dto.totals.open_tickets);
      let supported = 0,
        total = 0;
      for (const row of dto.ml_domain_coverage) {
        expect(row.channels_supported).toBeLessThanOrEqual(row.channels_total);
        expect(row.coverage_percent).toBeCloseTo((row.channels_supported / row.channels_total) * 100, 1);
        supported += row.channels_supported;
        total += row.channels_total;
      }
      expect(dto.totals.ml_coverage_percent).toBeCloseTo((supported / total) * 100, 1);
    });
    it(`${range}: unique canonical dimensions`, () => {
      for (const values of [
        dto.ml_domain_coverage.map((x) => x.domain),
        dto.top_objects.map((x) => x.object_id),
        dto.ticket_status_distribution.map((x) => x.status),
        dto.urgency_distribution.map((x) => x.urgency),
      ])
        expect(new Set<string | number>(values).size).toBe(values.length);
      expect(dto.ticket_status_distribution.map((x) => x.status)).toEqual([
        'draft',
        'approved',
        'rejected',
        'completed',
      ]);
      expect(dto.ml_domain_coverage.map((x) => x.domain)).toEqual([
        'POWER_PHASE',
        'ANALOG_TEMP',
        'ANALOG_GAS',
        'FIRE_SAFETY',
        'HYDRO_MECHANICS',
      ]);
    });
    it(`${range}: adapter maps all fields and preserves backend ranking`, () => {
      const model = toAnalyticsSummary(dto);
      expect(model.generatedAt).toBe(dto.generated_at);
      expect(model.range).toBe(range);
      expect(model.totals).toEqual({
        activePredictions: 137,
        criticalPredictions: 8,
        highPredictions: 24,
        openTickets: 9,
        completedTickets: dto.totals.completed_tickets,
        mlCoveragePercent: 80,
      });
      expect(model.topObjects.map((x) => x.objectId)).toEqual(dto.top_objects.map((x) => x.object_id));
      expect(model.topObjects[0]).toEqual({
        objectId: 203,
        objectName: 'объект Фита',
        riskLevel: 'critical',
        activePredictions: 24,
        criticalPredictions: 4,
        highPredictions: 7,
        openTickets: 3,
      });
      expect(model.mlDomainCoverage[1]).toEqual({
        domain: 'ANALOG_TEMP',
        channelsTotal: 2500,
        channelsSupported: 2100,
        coveragePercent: 84,
      });
      expect(model.riskTimeline).toEqual(dto.risk_timeline);
      expect(model.urgencyDistribution).toEqual(dto.urgency_distribution);
      expect(model.ticketStatusDistribution).toEqual(dto.ticket_status_distribution);
      expect(analyticsKeys.summary(range)).toEqual(['analytics', 'summary', range]);
      expect(isAnalyticsEmpty(model)).toBe(false);
      expect(isAnalyticsEmpty(toAnalyticsSummary(emptyAnalytics(range)))).toBe(true);
    });
  }
  it('keeps coincident historical snapshots consistent across ranges', () => {
    const seen = new Map<string, { critical: number; high: number; medium: number }>();
    for (const fixture of Object.values(analyticsFixtures)) {
      for (const point of fixture.risk_timeline) {
        const value = { critical: point.critical, high: point.high, medium: point.medium };
        const previous = seen.get(point.timestamp);
        if (previous) expect(value).toEqual(previous);
        seen.set(point.timestamp, value);
      }
    }
  });
  it('formats day boundaries in Moscow', () =>
    expect(formatAnalyticsDay(Date.parse('2026-09-19T22:00:00Z'))).toBe('20.09'));
});
