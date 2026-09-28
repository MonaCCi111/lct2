import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Plus, RefreshCw } from 'lucide-react';
import { useTickets } from '../../api/queries/hooks';
import { PageHeader } from '../../components/feedback/PageShell';
import { StaleState } from '../../components/feedback/States';
import { Button } from '../../components/ui/Button';
import type { Ticket } from '../../domain/ticket/types';
import { TicketsFilters } from './TicketsFilters';
import { TicketsRegistryTable } from './TicketsRegistryTable';
import { TicketDetailDrawer } from './TicketDetailDrawer';
import { CreateTicketDrawer } from './CreateTicketDrawer';
import {
  formatTicketCount,
  hasTicketFilters,
  initialTicketFilters,
  selectTickets,
} from './ticket-registry-model';
import './tickets-page.css';

export default function TicketsPage() {
  const query = useTickets();
  const [filters, setFilters] = useState(initialTicketFilters);
  // Detail and create state live in the URL so Prediction Investigation can deep-link into them.
  const [params, setParams] = useSearchParams();
  const ticketId = params.get('ticketId');
  const predictionId = params.get('predictionId');
  const [manualCreate, setManualCreate] = useState(false);

  const rows = useMemo(() => selectTickets(query.data ?? [], filters), [query.data, filters]);
  const filtered = hasTicketFilters(filters);
  const reset = () => setFilters(initialTicketFilters);

  const openTicket = (id: string) =>
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        next.delete('predictionId');
        next.set('ticketId', id);
        return next;
      },
      { replace: true },
    );
  const closeDrawers = () =>
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        next.delete('ticketId');
        next.delete('predictionId');
        return next;
      },
      { replace: true },
    );

  return (
    <div className="tickets-registry">
      <PageHeader
        title="Наряды"
        description="Рабочие задания по предиктивным рискам"
        action={
          <div className="tickets-header-actions">
            <Button variant="ghost" disabled={query.isFetching} onClick={() => void query.refetch()}>
              <RefreshCw size={14} aria-hidden="true" />
              Обновить
            </Button>
            <Button variant="primary" onClick={() => setManualCreate(true)}>
              <Plus size={15} aria-hidden="true" />
              Новый наряд
            </Button>
          </div>
        }
      />
      <section className="tickets-registry-panel" aria-label="Реестр нарядов">
        <TicketsFilters filters={filters} onChange={setFilters} onReset={reset} filtered={filtered} />
        {query.data && query.isError && (
          <StaleState onRefresh={() => void query.refetch()} refreshing={query.isFetching} />
        )}
        <TicketsRegistryTable
          rows={rows}
          loading={query.isPending}
          error={!query.data ? query.error?.message : undefined}
          onRetry={() => void query.refetch()}
          filtered={filtered && Boolean(query.data?.length)}
          onReset={reset}
          onOpen={(ticket: Ticket) => openTicket(ticket.id)}
          activeTicketId={ticketId}
        />
        <footer className="tickets-registry-footer" aria-live="polite">
          {query.data
            ? filtered
              ? `${rows.length} из ${formatTicketCount(query.data.length)}`
              : formatTicketCount(query.data.length)
            : query.isPending
              ? 'Загрузка нарядов…'
              : 'Журнал нарядов недоступен'}
        </footer>
      </section>
      <TicketDetailDrawer ticketId={ticketId} onClose={closeDrawers} />
      <CreateTicketDrawer
        open={predictionId !== null || manualCreate}
        predictionId={predictionId}
        onClose={() => {
          setManualCreate(false);
          closeDrawers();
        }}
        onCreated={(ticket) => {
          setManualCreate(false);
          openTicket(ticket.id);
        }}
        onOpenTicket={(id) => {
          setManualCreate(false);
          openTicket(id);
        }}
      />
    </div>
  );
}
