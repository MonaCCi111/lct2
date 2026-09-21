import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import type { Prediction } from '../../domain/prediction/types';
import { Skeleton } from '../../components/feedback/States';
import { formatDateTime, reviewStatusLabels } from '../../utils/formatters';

export function PredictionHeader({
  prediction,
  loading,
  predictionId,
}: {
  prediction?: Prediction;
  loading: boolean;
  predictionId: string;
}) {
  return (
    <header className="investigation-header">
      <Link className="investigation-back" to="/predictions">
        <ArrowLeft size={14} aria-hidden="true" />
        Прогнозы
      </Link>
      {loading || !prediction ? (
        <div className="investigation-header-loading" role="status" aria-label="Загрузка прогноза">
          <Skeleton />
          <Skeleton />
        </div>
      ) : (
        <div className="investigation-header-main">
          <div>
            <p className="investigation-eyebrow">{prediction.sensorType}</p>
            <h1>{prediction.sensorName}</h1>
            <p className="investigation-context-line">
              <Link to={`/objects/${prediction.objectId}`}>{prediction.objectName}</Link>
              <span aria-hidden="true">·</span>
              <span>{prediction.piket ?? 'Пикет не указан'}</span>
              <span aria-hidden="true">·</span>
              <span>{prediction.subsystem}</span>
            </p>
          </div>
          <div className="investigation-header-meta">
            <span>Обновлено {formatDateTime(prediction.generatedAt)}</span>
            <span className="badge workflow-status">{reviewStatusLabels[prediction.reviewStatus]}</span>
            <span className="investigation-header-id">{prediction.id}</span>
          </div>
        </div>
      )}
      {!loading && !prediction && <p className="investigation-eyebrow">Прогноз {predictionId}</p>}
    </header>
  );
}
