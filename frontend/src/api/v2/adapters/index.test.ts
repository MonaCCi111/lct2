import { describe, expect, it } from 'vitest';
import { toV2Draft, toV2Evidence, toV2Meta, toV2Object, toV2Page } from '.';
import {
  v2ForecastDraftFixture,
  v2ForecastEvidenceFixture,
  v2MetaFixture,
  v2ObjectFixture,
  v2ObservedDraftFixture,
} from '../mocks/fixtures';

describe('API v2 read-only adapters', () => {
  it('maps Meta without assigning a timezone to the historical cutoff', () => {
    expect(toV2Meta(v2MetaFixture)).toEqual({
      contractVersion: 'dispatcher_api_v1',
      dataVersion: 'ml_handoff_v1',
      dataCutoff: '2026-06-30T23:59:59',
      sourceTimezoneKnown: false,
      realFeedbackAvailable: false,
      liveIngestionAvailable: false,
    });
  });

  it('maps the dispatcher object name verbatim without legacy name helpers', () => {
    expect(toV2Object(v2ObjectFixture)).toEqual({
      objectId: 5333,
      objectName: 'ДУ объект Кси',
      kind: 'controlHouse',
      parentId: 5327,
      channelCount: 215,
    });
  });

  it('keeps forecast score model-specific and exposes no legacy semantic fields', () => {
    const draft = toV2Draft(v2ForecastDraftFixture);
    expect(draft.score).toBe(0.9848484848484849);
    expect(draft.modelVersion).toBe('power_phase_scada_v2');
    expect(draft.forecastHorizonHours).toBe(48);
    expect(draft.reviewState).toBe('pending');
    expect(draft.itsValue).toBeNull();
    expect(draft).not.toHaveProperty('failureProbability');
    expect(draft).not.toHaveProperty('riskLevel');
    expect(draft).not.toHaveProperty('maintenanceUrgency');
    expect(draft).not.toHaveProperty('healthIndex');
    expect(String(draft.score)).not.toBe('98.48%');
  });

  it('maps observed drafts with null score, model, horizon and ITS intact', () => {
    const draft = toV2Draft(v2ObservedDraftFixture);
    expect(draft).toMatchObject({
      basisKind: 'observed_status',
      modelVersion: null,
      score: null,
      forecastHorizonHours: null,
      itsValue: null,
      reviewState: 'pending',
    });
  });

  it('records the optional forecast horizon contract gap without making the field required', () => {
    expect(Object.hasOwn(v2ForecastDraftFixture, 'forecast_horizon_hours')).toBe(true);
    const { forecast_horizon_hours: _omitted, ...withoutHorizon } = v2ForecastDraftFixture;
    expect(toV2Draft(withoutHorizon).forecastHorizonHours).toBeNull();
  });

  it('preserves raw evidence values, alarm fields, references and timestamps', () => {
    expect(toV2Evidence(v2ForecastEvidenceFixture)).toMatchObject({
      channelId: 178259,
      sourceTime: null,
      eventTime: '2025-12-10T08:16:53',
      availableAt: '2025-12-10T08:16:53',
      observedValue: 'Есть питание',
      numericValue: null,
      sourceAlarm: null,
      recordedAlarm: false,
      sourceRef: v2ForecastEvidenceFixture.source_ref,
    });
  });

  it('maps cursor pagination without rebuilding or interpreting items', () => {
    const page = toV2Page({ items: [v2ObjectFixture], next_cursor: 'object:5333' }, toV2Object);
    expect(page.nextCursor).toBe('object:5333');
    expect(page.items).toEqual([toV2Object(v2ObjectFixture)]);
  });

  it.each(['pending', 'approved', 'rejected'] as const)('preserves review_state=%s', (reviewState) => {
    expect(toV2Draft({ ...v2ForecastDraftFixture, review_state: reviewState }).reviewState).toBe(reviewState);
  });
});
