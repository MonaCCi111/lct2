import { useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import type { V2Draft } from '../../api/v2/domain/types';
import { useCreateV2WorkOrder, useV2DraftDecisions, useV2WorkOrder } from '../../api/v2/queries/hooks';
import { Button } from '../../components/ui/Button';
import { getWorkOrderEligibility, workOrderEligibilityText } from './work-order-model';
import {
  beginWorkOrderAttempt,
  validateWorkOrderFields,
  workOrderErrorMessage,
  type WorkOrderAttempt,
} from './work-order-workflow';

export function WorkOrderPanel({ draft }: { draft: V2Draft }) {
  const history = useV2DraftDecisions(draft.draftId);
  const mutation = useCreateV2WorkOrder();
  const [attempt, setAttempt] = useState<WorkOrderAttempt | null>(null);
  const [workType, setWorkType] = useState('');
  const [description, setDescription] = useState('');
  const [errors, setErrors] = useState({
    workType: null as string | null,
    description: null as string | null,
  });
  const feedbackRef = useRef<HTMLDivElement>(null);
  const latestDecision = history.data?.at(-1) ?? draft.decision;
  const eligibility = getWorkOrderEligibility(latestDecision);
  const createdId = mutation.data?.workOrderId ?? eligibility.workOrderId ?? '';
  const workOrder = useV2WorkOrder(createdId);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!attempt || eligibility.state !== 'allowed') return;
    const nextErrors = validateWorkOrderFields(workType, description);
    setErrors(nextErrors);
    if (nextErrors.workType || nextErrors.description) return;
    mutation.mutate(
      {
        draftId: draft.draftId,
        workType: workType.trim(),
        description: description.trim(),
        idempotencyKey: attempt.idempotencyKey,
      },
      { onSettled: () => setTimeout(() => feedbackRef.current?.focus(), 0) },
    );
  };

  return (
    <section className="review-work-order-panel" aria-labelledby="review-work-order-heading">
      <header>
        <div>
          <h2 id="review-work-order-heading">Наряд</h2>
          <p>Отдельное действие после одобрения: черновик → решение диспетчера → наряд.</p>
        </div>
        <Link className="button button-ghost" to="/review/work-orders">
          Все наряды v2
        </Link>
      </header>

      {!createdId && !attempt && (
        <div className="review-work-order-state">
          <span>{workOrderEligibilityText[eligibility.state]}</span>
          {eligibility.state === 'allowed' && (
            <Button onClick={() => setAttempt((current) => beginWorkOrderAttempt(current))}>
              Создать наряд
            </Button>
          )}
        </div>
      )}

      {attempt && eligibility.state === 'allowed' && !mutation.isSuccess && (
        <form className="review-work-order-form" onSubmit={submit} noValidate>
          <div className="field">
            <label htmlFor="v2-work-type">Тип работ</label>
            <input
              id="v2-work-type"
              className="input"
              value={workType}
              onChange={(event) => {
                setWorkType(event.target.value);
                if (errors.workType) setErrors((current) => ({ ...current, workType: null }));
              }}
              aria-invalid={Boolean(errors.workType)}
              aria-describedby={errors.workType ? 'v2-work-type-error' : undefined}
              autoFocus
            />
            {errors.workType && (
              <span id="v2-work-type-error" className="review-decision-field-error" role="alert">
                {errors.workType}
              </span>
            )}
          </div>
          <div className="field">
            <label htmlFor="v2-work-description">Описание работ</label>
            <textarea
              id="v2-work-description"
              className="input"
              rows={3}
              value={description}
              onChange={(event) => {
                setDescription(event.target.value);
                if (errors.description) setErrors((current) => ({ ...current, description: null }));
              }}
              aria-invalid={Boolean(errors.description)}
              aria-describedby={errors.description ? 'v2-work-description-error' : undefined}
            />
            {errors.description && (
              <span id="v2-work-description-error" className="review-decision-field-error" role="alert">
                {errors.description}
              </span>
            )}
          </div>
          <div className="review-decision-form-actions">
            <Button type="submit" className="review-approve-button" disabled={mutation.isPending}>
              {mutation.isPending ? 'Создание…' : 'Создать наряд'}
            </Button>
            <Button
              variant="ghost"
              disabled={mutation.isPending}
              onClick={() => {
                mutation.reset();
                setAttempt(null);
                setWorkType('');
                setDescription('');
              }}
            >
              Отмена
            </Button>
          </div>
        </form>
      )}

      {(createdId || mutation.isError) && (
        <div
          className={`review-work-order-feedback ${mutation.isError ? 'review-decision-feedback-error' : ''}`}
          role={mutation.isError ? 'alert' : 'status'}
          tabIndex={-1}
          ref={feedbackRef}
        >
          {createdId ? (
            <>
              <strong>Наряд создан</strong>
              <Link to={`/review/work-orders/${encodeURIComponent(createdId)}`}>{createdId}</Link>
              {workOrder.data && <span>{workOrder.data.workType}</span>}
            </>
          ) : (
            <strong>{workOrderErrorMessage(mutation.error)}</strong>
          )}
        </div>
      )}
    </section>
  );
}
