/**
 * Compact display labels for sensor types whose full domain value is too long for a dense table
 * column. The domain value itself is never changed — callers keep it for tooltips and search, and
 * anything not listed here is shown exactly as the backend sent it.
 */
const shortLabels: Record<string, string> = {
  'Состояние фазы': 'Фаза',
  'Пожарный датчик': 'Пожарный',
  'КД Дверь': 'Дверь',
};
export const getSensorTypeLabel = (sensorType: string) => shortLabels[sensorType] ?? sensorType;
export const isShortenedSensorType = (sensorType: string) => sensorType in shortLabels;
