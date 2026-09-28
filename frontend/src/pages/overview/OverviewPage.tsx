import { RefreshCw } from 'lucide-react';
import { useDashboardSummary } from '../../api/queries/hooks';
import { Button } from '../../components/ui/Button';
import { PageHeader } from '../../components/feedback/PageShell';
import { UpdatedAtLabel } from '../../components/feedback/UpdatedAtLabel';
import { SummaryStrip } from './SummaryStrip';
import { RiskQueue } from './RiskQueue';
import { ObjectStatusPanel } from './ObjectStatusPanel';
import { CoverageStatus, TicketSummary } from './OperationalStatus';
import './overview.css';
export default function OverviewPage() {
  const summary = useDashboardSummary();
  return (
    <div className="overview-page">
      <PageHeader
        title="Оперативный центр"
        description="Текущее состояние инженерной инфраструктуры"
        action={
          <div className="overview-update">
            {summary.data ? (
              <UpdatedAtLabel value={summary.data.generatedAt} />
            ) : (
              <span>{summary.isPending ? 'Загрузка сводки…' : 'Сводка недоступна'}</span>
            )}
            <Button
              variant="ghost"
              aria-label="Обновить сводку"
              disabled={summary.isFetching}
              onClick={() => void summary.refetch()}
            >
              <RefreshCw size={14} />
              <span>Обновить</span>
            </Button>
          </div>
        }
      />
      <SummaryStrip query={summary} />
      <div className="operational-workspace">
        <RiskQueue />
        <aside className="operational-side">
          <ObjectStatusPanel />
          <TicketSummary summary={summary.data} loading={summary.isPending} />
          <CoverageStatus summary={summary.data} loading={summary.isPending} />
        </aside>
      </div>
    </div>
  );
}
