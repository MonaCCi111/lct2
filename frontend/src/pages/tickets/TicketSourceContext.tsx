import type { Prediction } from '../../domain/prediction/types';
import { RiskBadge, UrgencyBadge } from '../../components/ui/Badge';
import { UnsupportedMlState } from '../../components/feedback/States';
import { formatObjectName } from '../../utils/object-name';

/** Compact read-only context of the source prediction — deliberately not a card. */
export function TicketSourceContext({ prediction }: { prediction: Prediction }) {
  return (
    <section className="ticket-source" aria-label="Источник наряда">
      <h3>Источник</h3>
      <p className="ticket-source-id">{prediction.id}</p>
      <p className="ticket-source-sensor">{prediction.sensorName}</p>
      <p className="ticket-source-location" title={prediction.objectName}>
        {formatObjectName(prediction.objectName)}
        {prediction.piket !== null && ` · ${prediction.piket}`}
      </p>
      <p className="ticket-source-semantics">
        {prediction.predictionSupported ? (
          <>
            <RiskBadge value={prediction.riskLevel} />
            <UrgencyBadge value={prediction.maintenanceUrgency} />
          </>
        ) : (
          <UnsupportedMlState />
        )}
      </p>
    </section>
  );
}
