import type { Prediction } from '../../domain/prediction/types';

/**
 * Factors are shown exactly as the model returned them: numbered, neutral typography, no extra
 * numeric fields invented on top of the string and no semantic colour per item.
 */
export function RiskFactors({ prediction }: { prediction: Prediction }) {
  if (!prediction.predictionSupported) return null;
  return (
    <div className="investigation-section">
      <h2>Факторы риска</h2>
      {prediction.topRiskFactors.length === 0 ? (
        <p className="investigation-note">Модель не выделила отдельных факторов для этого канала.</p>
      ) : (
        <ol className="risk-factors">
          {prediction.topRiskFactors.map((factor, index) => (
            <li key={factor}>
              <span className="risk-factor-index" aria-hidden="true">
                {String(index + 1).padStart(2, '0')}
              </span>
              <span className="risk-factor-text">{factor}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
