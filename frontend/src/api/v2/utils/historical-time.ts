export const V2_SOURCE_TIME_LABEL = 'Время источника, зона неизвестна';
export const V2_AVAILABLE_AT_LABEL = 'Доступно в реконструкции';

/**
 * Historical source timestamps have no known timezone. Returning the wire value verbatim is a
 * contract requirement: do not route this through Date, Intl or the v1 Moscow formatter.
 */
export const formatV2HistoricalTimestamp = (value: string | null | undefined) => value ?? '—';
