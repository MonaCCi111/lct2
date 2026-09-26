import { describe, expect, it } from 'vitest';
import { toV2Decision } from '../../api/v2/adapters';
import { v2DecisionFixture } from '../../api/v2/mocks/fixtures';
import { getWorkOrderEligibility, v2ObjectDisplayName } from './work-order-model';

describe('v2 work-order UI model', () => {
  it('uses the authoritative latest decision for create eligibility', () => {
    expect(getWorkOrderEligibility(null).state).toBe('pending');
    expect(getWorkOrderEligibility(toV2Decision({ ...v2DecisionFixture, decision: 'rejected' })).state).toBe(
      'rejected',
    );
    expect(getWorkOrderEligibility(toV2Decision(v2DecisionFixture)).state).toBe('allowed');
    expect(
      getWorkOrderEligibility(toV2Decision({ ...v2DecisionFixture, work_order_id: 'WO-V2-0001' })),
    ).toEqual({ state: 'created', workOrderId: 'WO-V2-0001' });
  });

  it('uses a v2 object name and falls back to the numeric object id', () => {
    const objects = [
      { objectId: 5333, objectName: 'ДУ объект Кси', kind: 'controlHouse', parentId: null, channelCount: 1 },
    ];
    expect(v2ObjectDisplayName(5333, objects)).toBe('ДУ объект Кси');
    expect(v2ObjectDisplayName(5003, objects)).toBe('Объект 5003');
  });
});
