import { afterEach, describe, expect, it, vi } from 'vitest';
import { formatV2HistoricalTimestamp, V2_AVAILABLE_AT_LABEL, V2_SOURCE_TIME_LABEL } from './historical-time';

afterEach(() => vi.restoreAllMocks());

describe('API v2 historical time', () => {
  it('returns timezone-naive source timestamps literally in a non-Moscow environment', () => {
    vi.stubEnv('TZ', 'America/Los_Angeles');
    const parse = vi.spyOn(Date, 'parse');
    expect(formatV2HistoricalTimestamp('2025-12-10T09:00:00')).toBe('2025-12-10T09:00:00');
    expect(parse).not.toHaveBeenCalled();
  });

  it('provides the contract labels and never adds Moscow or UTC markers', () => {
    expect(V2_SOURCE_TIME_LABEL).toBe('Время источника, зона неизвестна');
    expect(V2_AVAILABLE_AT_LABEL).toBe('Доступно в реконструкции');
    expect(formatV2HistoricalTimestamp('2025-02-02T04:03:57')).not.toMatch(/МСК|UTC|Z|\+03:00/);
    expect(formatV2HistoricalTimestamp(null)).toBe('—');
  });
});
