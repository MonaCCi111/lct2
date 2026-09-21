import { Link } from 'react-router-dom';
import { ArrowUpRight } from 'lucide-react';
import type { DashboardSummary } from '../../domain/dashboard/types';
import { Skeleton } from '../../components/feedback/States';
import { formatCount, formatCoverage } from '../../utils/formatters';
export function TicketSummary({ summary, loading }: { summary?: DashboardSummary; loading: boolean }) {
  return (
    <section className="ticket-summary" aria-label="Сводка нарядов">
      <header>
        <h2>Наряды</h2>
        <Link to="/tickets">
          Перейти к нарядам
          <ArrowUpRight size={13} />
        </Link>
      </header>
      {summary ? (
        <dl>
          <div>
            <dt>Черновики</dt>
            <dd>{formatCount(summary.tickets.draft)}</dd>
          </div>
          <div>
            <dt>Утверждены</dt>
            <dd>{formatCount(summary.tickets.approved)}</dd>
          </div>
          <div>
            <dt>Выполнено сегодня</dt>
            <dd>{formatCount(summary.tickets.completedToday)}</dd>
          </div>
        </dl>
      ) : loading ? (
        <Skeleton />
      ) : (
        <p className="muted">Сводка нарядов недоступна</p>
      )}
    </section>
  );
}
export function CoverageStatus({ summary, loading }: { summary?: DashboardSummary; loading: boolean }) {
  return (
    <div className="coverage-status">
      {summary ? (
        <>
          <span>
            ML покрытие: <strong>{formatCoverage(summary.channels.coveragePercent)}</strong>
          </span>
          <span>
            {formatCount(summary.channels.mlSupported)} / {formatCount(summary.channels.total)} каналов
          </span>
        </>
      ) : loading ? (
        <Skeleton />
      ) : (
        <span>Данные ML-покрытия недоступны</span>
      )}
    </div>
  );
}
