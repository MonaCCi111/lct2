import { useState } from 'react';
import type { Ticket, TicketStatus } from '../../domain/ticket/types';
import { getAllowedTicketTransitions } from '../../domain/ticket/types';
import { useUpdateTicketStatus } from '../../api/queries/hooks';
import { Button } from '../../components/ui/Button';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { transitionConfirmations, transitionLabels } from './ticket-registry-model';

/**
 * Only transitions the lifecycle actually allows are offered, so a rejected or completed ticket
 * shows no disabled forest. The mock API validates the transition again on its side.
 */
export function TicketStatusActions({ ticket }: { ticket: Ticket }) {
  const transitions = getAllowedTicketTransitions(ticket.status);
  const [pendingStatus, setPendingStatus] = useState<TicketStatus | null>(null);
  const update = useUpdateTicketStatus();

  if (transitions.length === 0)
    return (
      <p className="ticket-lifecycle-note">
        {ticket.status === 'completed'
          ? 'Наряд выполнен. Дальнейшие действия недоступны.'
          : 'Наряд отклонён. Дальнейшие действия недоступны.'}
      </p>
    );

  const confirmation = pendingStatus === null ? null : transitionConfirmations[pendingStatus];
  return (
    <div className="ticket-lifecycle">
      <div className="ticket-lifecycle-actions">
        {transitions.map((status) => (
          <Button
            key={status}
            variant={status === 'rejected' ? 'danger' : 'primary'}
            disabled={update.isPending}
            onClick={() => {
              update.reset();
              setPendingStatus(status);
            }}
          >
            {transitionLabels[status]}
          </Button>
        ))}
      </div>
      {pendingStatus !== null && confirmation !== null && (
        <ConfirmDialog
          open
          onOpenChange={(next) => {
            if (!next && !update.isPending) setPendingStatus(null);
          }}
          title={confirmation.title}
          description={confirmation.description}
          confirmLabel={transitionLabels[pendingStatus]}
          danger={pendingStatus === 'rejected'}
          pending={update.isPending}
          onConfirm={() =>
            update.mutate(
              { id: ticket.id, status: pendingStatus },
              { onSuccess: () => setPendingStatus(null) },
            )
          }
        >
          {/* A rejected transition is reported inside the dialog, where the action was taken. */}
          {update.isError && (
            <p className="field-error ticket-mutation-error" role="alert">
              {update.error.message}
            </p>
          )}
        </ConfirmDialog>
      )}
    </div>
  );
}
