import { describe, expect, it } from 'vitest';
import { formatDataAge, formatDateTime, formatRelativeTime } from './formatters';

describe('operational timestamps in Europe/Moscow', () => {
  it('formats UTC with a four-digit year and explicit MSK label', () => {
    expect(formatDateTime('2026-09-20T15:42:00Z')).toBe('20.09.2026, 18:42 МСК');
  });

  it('formats equivalent offsets and epoch milliseconds identically', () => {
    for (const value of [
      '2026-09-20T18:42:00+03:00',
      '2026-09-20T08:42:00-07:00',
      Date.parse('2026-09-20T15:42:00Z'),
    ]) {
      expect(formatDateTime(value)).toBe('20.09.2026, 18:42 МСК');
    }
  });

  it('handles Moscow midnight, month/year boundaries and winter/summer', () => {
    expect(formatDateTime('2026-09-20T21:00:00Z')).toBe('21.09.2026, 00:00 МСК');
    expect(formatDateTime('2026-12-31T22:30:00Z')).toBe('01.01.2027, 01:30 МСК');
    expect(formatDateTime('2026-01-01T09:00:00Z')).toBe('01.01.2026, 12:00 МСК');
    expect(formatDateTime('2026-07-01T09:00:00Z')).toBe('01.07.2026, 12:00 МСК');
  });

  it('preserves a valid zero epoch', () => {
    expect(formatDateTime(0)).toBe('01.01.1970, 03:00 МСК');
  });

  it.each([null, '', 'invalid', '2026-09-20', '2026-09-20T15:42:00', Number.NaN, Infinity])(
    'rejects missing, invalid, or timezone-ambiguous input: %s',
    (value) => {
      expect(formatDateTime(value)).toBe('—');
      expect(formatRelativeTime(value)).toBe('—');
    },
  );

  it('calculates elapsed time from instants, independently of display timezone', () => {
    const now = Date.parse('2026-09-20T15:42:00Z');
    expect(formatRelativeTime('2026-09-20T18:40:00+03:00', now)).toBe('2 минуты назад');
    expect(formatRelativeTime('2026-09-20T08:40:00-07:00', now)).toBe('2 минуты назад');
    expect(formatRelativeTime('2026-09-20T15:44:00Z', now)).toBe('через 2 минуты');
    expect(formatRelativeTime(now, Number.NaN)).toBe('—');
  });
});

describe('data freshness', () => {
  const now = Date.parse('2026-09-20T15:42:00Z');
  it.each([
    [0, 'только что'],
    [30_000, 'только что'],
    [59_000, 'только что'],
    [-20_000, 'только что'],
  ])('reads a %i ms old timestamp as "%s"', (age, expected) => {
    expect(formatDataAge(new Date(now - age).toISOString(), now)).toBe(expected);
  });
  it('switches to a relative age once a minute has passed', () => {
    expect(formatDataAge(new Date(now - 4 * 60_000).toISOString(), now)).toBe('4 минуты назад');
    expect(formatDataAge(new Date(now - 120 * 60_000).toISOString(), now)).toBe('2 часа назад');
  });
  it('never invents an age for a missing or ambiguous timestamp', () => {
    expect(formatDataAge(null, now)).toBe('—');
    expect(formatDataAge('2026-09-20T15:42:00', now)).toBe('—');
  });
});
