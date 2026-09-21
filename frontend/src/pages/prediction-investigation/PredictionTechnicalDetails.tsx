import type { Prediction } from '../../domain/prediction/types';
import { formatDateTime } from '../../utils/formatters';

/**
 * Secondary technical context. It is collapsed by default so it never competes with the
 * operational information the dispatcher needs first.
 */
export function PredictionTechnicalDetails({ prediction }: { prediction: Prediction }) {
  const rows: [string, string][] = [
    ['Идентификатор прогноза', prediction.id],
    ['Канал', `#${prediction.channelId}`],
    ['Тег', prediction.tag],
    ['Домен модели', prediction.modelDomain ?? 'Не применяется'],
    ['Версия модели', prediction.modelVersion],
    ['Подсистема', prediction.subsystem],
    ['Сформирован', formatDateTime(prediction.generatedAt)],
    [
      'Горизонт планирования',
      prediction.leadTimeHours === null ? '—' : `${prediction.leadTimeHours} ч (ориентировочно)`,
    ],
  ];
  return (
    <details className="investigation-technical">
      <summary>Технические данные</summary>
      <dl className="investigation-technical-list">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}
