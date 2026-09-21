import { describe, expect, it } from 'vitest';
import { objectDetailFixtures, objectTopologyFixture, objectWorkspacePredictions } from './object-workspace';

// The mock API stands in for the backend: its published aggregates must match its own records,
// so the UI never has a reason to recompute risk levels or counts.
describe('object workspace fixtures', () => {
  const details = objectDetailFixtures.filter((item) => item.object_id >= 201);
  it.each(details.map((item) => [item.object_name, item.object_id] as const))(
    '%s reports aggregates that match its predictions',
    (_name, objectId) => {
      const detail = details.find((item) => item.object_id === objectId)!;
      const predictions = objectWorkspacePredictions.filter((item) => item.object_id === objectId);
      expect(predictions).toHaveLength(detail.active_predictions);
      expect(predictions.filter((item) => item.risk_level === 'critical')).toHaveLength(
        detail.critical_predictions,
      );
      expect(predictions.filter((item) => item.risk_level === 'high')).toHaveLength(detail.high_predictions);
    },
  );
  it.each(details.map((item) => [item.object_name, item.object_id] as const))(
    '%s topology segments match the predictions inside their piket range',
    (_name, objectId) => {
      const topology = objectTopologyFixture(objectId, String(objectId));
      const predictions = objectWorkspacePredictions.filter((item) => item.object_id === objectId);
      expect(topology.segments.length).toBeGreaterThan(0);
      for (const segment of topology.segments) {
        const inside = predictions.filter(
          (item) =>
            item.piket_value !== null &&
            item.piket_value >= segment.piket_from &&
            item.piket_value <= segment.piket_to,
        );
        expect({ id: segment.segment_id, count: inside.length }).toEqual({
          id: segment.segment_id,
          count: segment.active_predictions,
        });
        expect(inside.filter((item) => item.risk_level === 'critical')).toHaveLength(
          segment.critical_predictions,
        );
        expect(inside.filter((item) => item.risk_level === 'high')).toHaveLength(segment.high_predictions);
        const probabilities = inside.map((item) => item.failure_probability ?? 0);
        expect(segment.max_failure_probability).toBe(
          probabilities.length > 0 ? Math.max(...probabilities) : null,
        );
      }
      // Segments must be contiguous so no piket falls into an undefined gap.
      expect(topology.segments.map((segment) => segment.piket_from).slice(1)).toEqual(
        topology.segments.map((segment) => segment.piket_to).slice(0, -1),
      );
    },
  );
  it('keeps the demo object Фита rich enough to exercise the workspace', () => {
    const topology = objectTopologyFixture(203, 'объект Фита');
    expect(topology.segments.length).toBeGreaterThanOrEqual(15);
    expect(topology.segments.length).toBeLessThanOrEqual(25);
    expect(topology.piket_min).toBe(0);
    expect(topology.piket_max).toBe(400);
    expect(topology.segments.filter((item) => item.risk_level === 'critical')).toHaveLength(3);
    const predictions = objectWorkspacePredictions.filter((item) => item.object_id === 203);
    expect(predictions.length).toBeGreaterThanOrEqual(20);
    expect(predictions.filter((item) => item.piket_value === null)).toHaveLength(1);
    expect(new Set(predictions.map((item) => item.sensor_type)).size).toBeGreaterThanOrEqual(5);
  });
});
