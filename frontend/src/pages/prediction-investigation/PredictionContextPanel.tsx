import type { Prediction } from '../../domain/prediction/types';
import { Skeleton } from '../../components/feedback/States';
import { PredictionRiskSummary } from './PredictionRiskSummary';
import { RiskFactors } from './RiskFactors';
import { RecommendationSection } from './RecommendationSection';

/**
 * One structured panel with dividers instead of six separate cards: the order follows how the
 * dispatcher decides — state, why, what to do, then the action.
 */
export function PredictionContextPanel({
  prediction,
  loading,
}: {
  prediction?: Prediction;
  loading: boolean;
}) {
  return (
    <aside className="investigation-context" aria-label="Оценка прогноза">
      {loading || !prediction ? (
        <div className="investigation-context-loading" role="status" aria-label="Загрузка оценки прогноза">
          {Array.from({ length: 4 }, (_, index) => (
            <div key={index}>
              <Skeleton />
              <Skeleton />
            </div>
          ))}
        </div>
      ) : (
        <>
          <PredictionRiskSummary prediction={prediction} />
          <RiskFactors prediction={prediction} />
          <RecommendationSection prediction={prediction} />
        </>
      )}
    </aside>
  );
}
