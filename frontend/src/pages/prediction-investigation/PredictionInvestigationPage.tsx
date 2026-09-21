import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { usePrediction, useSensorTelemetry } from '../../api/queries/hooks';
import { isNotFound } from '../../api/client/http';
import { EmptyState, ErrorState } from '../../components/feedback/States';
import { PredictionHeader } from './PredictionHeader';
import { PredictionContextPanel } from './PredictionContextPanel';
import { PredictionTechnicalDetails } from './PredictionTechnicalDetails';
import { TelemetrySection } from './TelemetrySection';
import { defaultTelemetryRange } from './prediction-investigation-model';
import type { TelemetryRange } from '../../domain/telemetry/types';
import './prediction-investigation.css';

export default function PredictionInvestigationPage() {
  const { predictionId = '' } = useParams();
  const [range, setRange] = useState<TelemetryRange>(defaultTelemetryRange);
  const prediction = usePrediction(predictionId);
  // Telemetry is an independent data source: it only starts once the channel id is known.
  const telemetry = useSensorTelemetry(prediction.data?.channelId ?? Number.NaN, { range });

  if (!prediction.data && isNotFound(prediction.error))
    return (
      <EmptyState
        title="Прогноз не найден"
        description="Прогноз с указанным идентификатором отсутствует или больше недоступен."
        action={
          <Link className="button button-secondary" to="/predictions">
            К журналу прогнозов
          </Link>
        }
      />
    );

  return (
    <div className="prediction-investigation">
      <PredictionHeader
        prediction={prediction.data}
        loading={prediction.isPending}
        predictionId={predictionId}
      />
      {!prediction.data && prediction.isError ? (
        <ErrorState message={prediction.error?.message} onRetry={() => void prediction.refetch()} />
      ) : (
        <>
          <div className="investigation-workspace">
            <TelemetrySection query={telemetry} range={range} onRangeChange={setRange} />
            <PredictionContextPanel prediction={prediction.data} loading={prediction.isPending} />
          </div>
          {prediction.data && <PredictionTechnicalDetails prediction={prediction.data} />}
        </>
      )}
    </div>
  );
}
