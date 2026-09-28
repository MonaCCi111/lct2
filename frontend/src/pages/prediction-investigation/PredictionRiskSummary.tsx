import type { Prediction } from '../../domain/prediction/types';
import { RiskBadge, UrgencyBadge } from '../../components/ui/Badge';
import { UnsupportedMlState } from '../../components/feedback/States';
import { formatHealthIndex, formatProbability } from '../../utils/formatters';
import { getUrgencyGuidance } from './prediction-investigation-model';

/**
 * Risk level, urgency and health index are rendered exactly as the backend supplied them.
 * Nothing here is derived from failureProbability: a 46% ANALOG_TEMP prediction stays critical.
 */
export function PredictionRiskSummary({ prediction }: { prediction: Prediction }) {
  if (!prediction.predictionSupported)
    return (
      <div className="investigation-section" data-testid="ml-unsupported">
        <h2>Предиктивная модель</h2>
        <UnsupportedMlState />
        <p className="investigation-note">
          Тип датчика пока не входит в область активного предиктивного мониторинга.
        </p>
      </div>
    );
  const health = formatHealthIndex(prediction.healthIndex);
  return (
    <div className="investigation-section">
      <h2 className="sr-only">Оценка риска</h2>
      <div className="risk-headline">
        <RiskBadge value={prediction.riskLevel} />
        <p className="risk-guidance">{getUrgencyGuidance(prediction.maintenanceUrgency)}</p>
        <UrgencyBadge value={prediction.maintenanceUrgency} />
      </div>
      <dl className="risk-metrics">
        <div>
          <dt>Вероятность отказа</dt>
          <dd>{formatProbability(prediction.failureProbability)}</dd>
        </div>
        <div>
          <dt>Индекс технического состояния</dt>
          <dd>
            {health}
            {prediction.healthIndex !== null && <span className="risk-metric-scale">/ 100</span>}
          </dd>
          {prediction.healthIndex !== null && (
            <div
              className="health-indicator"
              role="img"
              aria-label={`Индекс технического состояния ${health} из 100`}
            >
              <span style={{ width: `${Math.min(Math.max(prediction.healthIndex, 0), 100)}%` }} />
            </div>
          )}
        </div>
      </dl>
    </div>
  );
}
