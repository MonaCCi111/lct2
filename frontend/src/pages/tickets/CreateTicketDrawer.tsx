import { useEffect, useId, useState } from 'react';
import { Link } from 'react-router-dom';
import type { Prediction } from '../../domain/prediction/types';
import type { Ticket } from '../../domain/ticket/types';
import { useCreateTicket, useObjects, usePrediction } from '../../api/queries/hooks';
import { isNotFound } from '../../api/client/http';
import { Drawer } from '../../components/ui/Drawer';
import { Button } from '../../components/ui/Button';
import { Select } from '../../components/ui/Fields';
import { ErrorState, Skeleton } from '../../components/feedback/States';
import { assigneeOptions } from '../../domain/ticket/types';
import { TicketSourceContext } from './TicketSourceContext';
import {
  DESCRIPTION_MAX,
  TITLE_MAX,
  emptyTicketForm,
  hasFormErrors,
  prefillFromPrediction,
  validateTicketForm,
  type TicketFormErrors,
  type TicketFormValues,
} from './ticket-form-model';

const assigneeSelectOptions = [
  { value: '', label: 'Не назначен' },
  ...assigneeOptions.map((value) => ({ value, label: value })),
];

function ExistingTicketNotice({ ticketId, onOpen }: { ticketId: string; onOpen: (id: string) => void }) {
  return (
    <div className="ticket-duplicate" data-testid="duplicate-ticket">
      <p>Для прогноза уже создан наряд</p>
      <p className="ticket-duplicate-id">{ticketId}</p>
      <Button variant="primary" onClick={() => onOpen(ticketId)}>
        Открыть наряд
      </Button>
    </div>
  );
}

export function CreateTicketDrawer({
  open,
  predictionId,
  onClose,
  onCreated,
  onOpenTicket,
}: {
  open: boolean;
  predictionId: string | null;
  onClose: () => void;
  onCreated: (ticket: Ticket) => void;
  onOpenTicket: (ticketId: string) => void;
}) {
  const fieldId = useId();
  const prediction = usePrediction(predictionId ?? '');
  const objects = useObjects();
  const create = useCreateTicket();
  const [values, setValues] = useState<TicketFormValues>(emptyTicketForm);
  const [errors, setErrors] = useState<TicketFormErrors>({});
  const source: Prediction | undefined = predictionId === null ? undefined : prediction.data;

  // The form is rebuilt whenever the drawer opens; closing simply discards the draft.
  useEffect(() => {
    if (open) setValues(emptyTicketForm);
    setErrors({});
  }, [open, predictionId]);
  useEffect(() => {
    if (open && source) setValues(prefillFromPrediction(source));
  }, [open, source]);

  const manual = predictionId === null;
  const objectOptions = [
    { value: '', label: 'Выберите объект' },
    ...(objects.data ?? []).map((item) => ({ value: String(item.id), label: item.name })),
  ];

  const submit = () => {
    const nextErrors = validateTicketForm(values, manual);
    setErrors(nextErrors);
    if (hasFormErrors(nextErrors)) return;
    create.mutate(
      {
        prediction_id: predictionId,
        object_id: source ? source.objectId : Number(values.objectId),
        title: values.title.trim(),
        description: values.description.trim(),
        assignee: values.assignee === '' ? null : values.assignee,
      },
      { onSuccess: onCreated },
    );
  };

  const duplicateTicketId = source?.ticketId ?? null;
  const predictionMissing = predictionId !== null && !prediction.data && isNotFound(prediction.error);

  return (
    <Drawer
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
      title="Создание наряда"
      description="Рабочее задание по предиктивному риску"
    >
      {predictionMissing ? (
        <div className="ticket-missing" data-testid="prediction-missing">
          <h3>Прогноз не найден</h3>
          <p>Создание наряда из указанного прогноза невозможно.</p>
        </div>
      ) : predictionId !== null && prediction.isPending ? (
        <div className="ticket-drawer-loading" role="status" aria-label="Загрузка прогноза">
          <Skeleton />
          <Skeleton />
          <Skeleton />
        </div>
      ) : predictionId !== null && !prediction.data ? (
        <ErrorState message={prediction.error?.message} onRetry={() => void prediction.refetch()} />
      ) : duplicateTicketId !== null ? (
        <ExistingTicketNotice ticketId={duplicateTicketId} onOpen={onOpenTicket} />
      ) : (
        <form
          className="ticket-form"
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          {source && <TicketSourceContext prediction={source} />}
          {manual && (
            <div className="ticket-field">
              <Select
                id={`${fieldId}-object`}
                label="Объект"
                value={values.objectId}
                options={objectOptions}
                aria-invalid={errors.objectId !== undefined}
                aria-describedby={errors.objectId ? `${fieldId}-object-error` : undefined}
                onChange={(event) => setValues({ ...values, objectId: event.target.value })}
              />
              {errors.objectId && (
                <p className="field-error" id={`${fieldId}-object-error`}>
                  {errors.objectId}
                </p>
              )}
            </div>
          )}
          <div className="ticket-field">
            <label htmlFor={`${fieldId}-title`}>Название</label>
            <input
              id={`${fieldId}-title`}
              className="input"
              maxLength={TITLE_MAX}
              value={values.title}
              aria-invalid={errors.title !== undefined}
              aria-describedby={errors.title ? `${fieldId}-title-error` : undefined}
              onChange={(event) => setValues({ ...values, title: event.target.value })}
            />
            {errors.title && (
              <p className="field-error" id={`${fieldId}-title-error`}>
                {errors.title}
              </p>
            )}
          </div>
          <div className="ticket-field">
            <label htmlFor={`${fieldId}-description`}>Описание</label>
            <textarea
              id={`${fieldId}-description`}
              className="input ticket-textarea"
              rows={7}
              maxLength={DESCRIPTION_MAX}
              value={values.description}
              aria-invalid={errors.description !== undefined}
              aria-describedby={errors.description ? `${fieldId}-description-error` : undefined}
              onChange={(event) => setValues({ ...values, description: event.target.value })}
            />
            {errors.description && (
              <p className="field-error" id={`${fieldId}-description-error`}>
                {errors.description}
              </p>
            )}
          </div>
          <div className="ticket-field">
            <Select
              id={`${fieldId}-assignee`}
              label="Исполнитель"
              value={values.assignee}
              options={assigneeSelectOptions}
              onChange={(event) => setValues({ ...values, assignee: event.target.value })}
            />
          </div>
          {create.isError && (
            <p className="field-error ticket-mutation-error" role="alert">
              {create.error.message}
            </p>
          )}
          <div className="ticket-form-actions">
            <Button onClick={onClose} disabled={create.isPending}>
              Отмена
            </Button>
            <Button type="submit" variant="primary" disabled={create.isPending}>
              {create.isPending ? 'Создание…' : 'Создать черновик'}
            </Button>
          </div>
          {source && (
            <p className="ticket-form-note">
              Прогноз: <Link to={`/predictions/${encodeURIComponent(source.id)}`}>Открыть расследование</Link>
            </p>
          )}
        </form>
      )}
    </Drawer>
  );
}
