import type { TopologySegment } from '../../domain/object/topology';
import { formatPiket, formatProbability, getRiskLabel } from '../../utils/formatters';
export function TopologyTooltipContent({ segment }: { segment: TopologySegment }) {
  return (
    <div className="topology-tooltip">
      <span className="topology-tooltip-range">
        {formatPiket(segment.piketFrom)} — {formatPiket(segment.piketTo)}
      </span>
      <span className="topology-tooltip-label">{segment.label}</span>
      <dl>
        <div>
          <dt>Риск участка</dt>
          <dd>{getRiskLabel(segment.riskLevel)}</dd>
        </div>
        <div>
          <dt>Активных прогнозов</dt>
          <dd>{segment.activePredictions}</dd>
        </div>
        <div>
          <dt>Критических</dt>
          <dd>{segment.criticalPredictions}</dd>
        </div>
        <div>
          <dt>Высоких</dt>
          <dd>{segment.highPredictions}</dd>
        </div>
        <div>
          <dt>Макс. вероятность</dt>
          <dd>{formatProbability(segment.maxFailureProbability)}</dd>
        </div>
      </dl>
    </div>
  );
}
