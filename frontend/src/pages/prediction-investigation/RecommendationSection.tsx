import { Link } from 'react-router-dom';
import { ArrowUpRight, ClipboardList } from 'lucide-react';
import type { Prediction } from '../../domain/prediction/types';

/**
 * The recommendation text is backend output and is rendered verbatim — never rewritten, shortened
 * or generated on the frontend. The action only hands the prediction over to the tickets flow.
 */
export function RecommendationSection({ prediction }: { prediction: Prediction }) {
  const hasTicket = prediction.ticketId !== null;
  return (
    <div className="investigation-section">
      <h2>Рекомендуемое действие</h2>
      {prediction.recommendation ? (
        <p className="recommendation-text">{prediction.recommendation}</p>
      ) : (
        <p className="investigation-note">
          {prediction.predictionSupported
            ? 'Рекомендация по этому прогнозу не сформирована.'
            : 'Действие определяется регламентом обслуживания датчика.'}
        </p>
      )}
      {hasTicket ? (
        <div className="ticket-handoff" data-testid="existing-ticket">
          <p>
            Наряд уже создан <strong>{prediction.ticketId}</strong>
          </p>
          <Link
            className="button button-secondary"
            to={`/tickets?ticketId=${encodeURIComponent(prediction.ticketId ?? '')}`}
          >
            Открыть наряд
            <ArrowUpRight size={14} aria-hidden="true" />
          </Link>
        </div>
      ) : (
        <Link
          className="button button-primary investigation-cta"
          to={`/tickets?predictionId=${encodeURIComponent(prediction.id)}`}
        >
          <ClipboardList size={15} aria-hidden="true" />
          Создать наряд
        </Link>
      )}
      <p className="investigation-note investigation-cta-note">
        Оформление наряда выполняется в разделе «Наряды».
      </p>
    </div>
  );
}
