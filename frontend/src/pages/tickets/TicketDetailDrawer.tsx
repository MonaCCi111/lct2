import { Link } from 'react-router-dom';
import { ArrowUpRight } from 'lucide-react';
import { useTicket } from '../../api/queries/hooks';
import { isNotFound } from '../../api/client/http';
import { Drawer } from '../../components/ui/Drawer';
import { RiskBadge, StatusBadge } from '../../components/ui/Badge';
import { ErrorState, Skeleton } from '../../components/feedback/States';
import { formatDateTime } from '../../utils/formatters';
import { formatObjectName } from '../../utils/object-name';
import { TicketStatusActions } from './TicketStatusActions';

export function TicketDetailDrawer({ ticketId, onClose }: { ticketId: string | null; onClose: () => void }) {
  const query = useTicket(ticketId ?? '');
  const ticket = query.data;
  const missing = !ticket && isNotFound(query.error);
  return (
    <Drawer
      open={ticketId !== null}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
      title={ticket ? ticket.id : (ticketId ?? 'Наряд')}
      description="Рабочее задание по предиктивному риску"
    >
      {missing ? (
        <div className="ticket-missing" data-testid="ticket-missing">
          <h3>Наряд не найден</h3>
          <p>Указанный наряд отсутствует или больше недоступен.</p>
        </div>
      ) : query.isPending ? (
        <div className="ticket-drawer-loading" role="status" aria-label="Загрузка наряда">
          <Skeleton />
          <Skeleton />
          <Skeleton />
        </div>
      ) : !ticket ? (
        <ErrorState message={query.error?.message} onRetry={() => void query.refetch()} />
      ) : (
        <div className="ticket-detail">
          <div className="ticket-detail-headline">
            <StatusBadge value={ticket.status} />
            {ticket.priority !== null && <RiskBadge value={ticket.priority} />}
          </div>
          <h3 className="ticket-detail-title">{ticket.title}</h3>
          <dl className="ticket-detail-list">
            <div>
              <dt>Объект</dt>
              <dd>
                <Link to={`/objects/${ticket.objectId}`} title={ticket.objectName}>
                  {formatObjectName(ticket.objectName)}
                </Link>
              </dd>
            </div>
            <div>
              <dt>Источник</dt>
              <dd>
                {ticket.predictionId === null ? (
                  'Ручной наряд'
                ) : (
                  <Link to={`/predictions/${encodeURIComponent(ticket.predictionId)}`}>
                    {ticket.predictionId}
                    <ArrowUpRight size={13} aria-hidden="true" />
                  </Link>
                )}
              </dd>
            </div>
            {ticket.sensorName !== null && (
              <div>
                <dt>Датчик</dt>
                <dd>
                  {ticket.sensorName}
                  {ticket.piket !== null && ` · ${ticket.piket}`}
                </dd>
              </div>
            )}
            <div>
              <dt>Исполнитель</dt>
              <dd>{ticket.assignee ?? 'Не назначен'}</dd>
            </div>
            <div>
              <dt>Создан</dt>
              <dd>{formatDateTime(ticket.createdAt)}</dd>
            </div>
            <div>
              <dt>Обновлён</dt>
              <dd>{formatDateTime(ticket.updatedAt)}</dd>
            </div>
            {ticket.completedAt !== null && (
              <div>
                <dt>Завершён</dt>
                <dd>{formatDateTime(ticket.completedAt)}</dd>
              </div>
            )}
          </dl>
          <section className="ticket-detail-description" aria-label="Описание наряда">
            <h4>Описание</h4>
            <p>{ticket.description}</p>
          </section>
          {ticket.predictionId !== null && (
            <Link
              className="button button-secondary ticket-detail-link"
              to={`/predictions/${encodeURIComponent(ticket.predictionId)}`}
            >
              Открыть прогноз
              <ArrowUpRight size={14} aria-hidden="true" />
            </Link>
          )}
          <TicketStatusActions ticket={ticket} />
        </div>
      )}
    </Drawer>
  );
}
