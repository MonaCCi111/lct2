import { useRef, useState, type FormEvent } from 'react';
import type { V2Draft } from '../../api/v2/domain/types';
import { useCreateV2DraftDecision, useV2DraftDecisions } from '../../api/v2/queries/hooks';
import { Button } from '../../components/ui/Button';
import { StaleState } from '../../components/feedback/States';
import { DecisionHistory } from './DecisionHistory';
import {
  beginDecisionAttempt,
  decisionErrorMessage,
  validateDecisionReason,
  type DecisionAttempt,
} from './decision-workflow';
import { reviewStateLabels } from './review-model';

export function DecisionPanel({ draft }: { draft: V2Draft }) {
  const history = useV2DraftDecisions(draft.draftId);
  const mutation = useCreateV2DraftDecision();
  const [attempt, setAttempt] = useState<DecisionAttempt | null>(null);
  const [reason, setReason] = useState('');
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [savedDecision, setSavedDecision] = useState<DecisionAttempt['decision'] | null>(null);
  const statusRef = useRef<HTMLDivElement>(null);

  const choose = (decision: DecisionAttempt['decision']) => {
    mutation.reset();
    setFieldError(null);
    setSavedDecision(null);
    setAttempt((current) => beginDecisionAttempt(current, decision));
  };
  const cancel = () => {
    mutation.reset();
    setAttempt(null);
    setReason('');
    setFieldError(null);
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!attempt) return;
    const validation = validateDecisionReason(reason);
    setFieldError(validation);
    if (validation) return;
    mutation.mutate(
      {
        draftId: draft.draftId,
        request: {
          decision: attempt.decision,
          reason: reason.trim(),
          idempotencyKey: attempt.idempotencyKey,
        },
      },
      {
        onSuccess: () => {
          setSavedDecision(attempt.decision);
          setAttempt(null);
          setReason('');
          setTimeout(() => statusRef.current?.focus(), 0);
        },
        onError: () => setTimeout(() => statusRef.current?.focus(), 0),
      },
    );
  };
  const conflict = mutation.isError ? decisionErrorMessage(mutation.error) : null;
  const currentDecision = history.data?.at(-1) ?? draft.decision;

  return (
    <section className="review-decision-panel" aria-labelledby="review-decision-heading">
      <header>
        <div>
          <h2 id="review-decision-heading">Решение диспетчера</h2>
          <p>
            Решение относится к проверке черновика и не подтверждает физическую аварию или ground truth
            модели.
          </p>
        </div>
        <span className="review-decision-current">
          Текущее состояние: <strong>{reviewStateLabels[draft.reviewState]}</strong>
        </span>
      </header>

      {draft.reviewState === 'pending' && !attempt && (
        <div className="review-decision-actions">
          <Button className="review-approve-button" onClick={() => choose('approved')}>
            Одобрить
          </Button>
          <Button variant="danger" onClick={() => choose('rejected')}>
            Отклонить
          </Button>
        </div>
      )}

      {draft.reviewState === 'pending' && attempt && (
        <form className="review-decision-form" onSubmit={submit} noValidate>
          <div>
            <h3>Подтверждение: {reviewStateLabels[attempt.decision]}</h3>
            <p>Контракт требует зафиксировать причину для каждого решения.</p>
          </div>
          <label htmlFor="review-decision-reason">Причина решения</label>
          <textarea
            id="review-decision-reason"
            className="input"
            rows={3}
            value={reason}
            onChange={(event) => {
              setReason(event.target.value);
              if (fieldError) setFieldError(null);
            }}
            aria-invalid={Boolean(fieldError)}
            aria-describedby={fieldError ? 'review-decision-reason-error' : 'review-decision-reason-help'}
            autoFocus
          />
          <p id="review-decision-reason-help" className="review-decision-help">
            Причина сохраняется в append-only истории решений.
          </p>
          {fieldError && (
            <p id="review-decision-reason-error" className="review-decision-field-error" role="alert">
              {fieldError}
            </p>
          )}
          <div className="review-decision-form-actions">
            <Button
              type="submit"
              variant={attempt.decision === 'rejected' ? 'danger' : 'secondary'}
              className={attempt.decision === 'approved' ? 'review-approve-button' : ''}
              disabled={mutation.isPending}
            >
              {mutation.isPending ? 'Сохранение…' : 'Сохранить решение'}
            </Button>
            <Button variant="ghost" onClick={cancel} disabled={mutation.isPending}>
              Отмена
            </Button>
          </div>
        </form>
      )}

      {(savedDecision || mutation.isError) && (
        <div
          className={`review-decision-feedback ${mutation.isError ? 'review-decision-feedback-error' : ''}`}
          role={mutation.isError ? 'alert' : 'status'}
          tabIndex={-1}
          ref={statusRef}
        >
          {savedDecision ? (
            <>
              <strong>Решение сохранено</strong>
              {savedDecision === 'approved' && <span>Наряд не создан.</span>}
            </>
          ) : (
            <strong>{conflict}</strong>
          )}
        </div>
      )}

      {draft.reviewState !== 'pending' && !savedDecision && (
        <div className="review-decision-feedback" role="status">
          <strong>Решение сохранено</strong>
          {draft.reviewState === 'approved' && !currentDecision?.workOrderId && <span>Наряд не создан.</span>}
        </div>
      )}

      <div className="review-decision-history" aria-labelledby="review-history-heading">
        <h3 id="review-history-heading">История решений</h3>
        {history.data && history.isError && (
          <StaleState onRefresh={() => void history.refetch()} refreshing={history.isFetching} />
        )}
        <DecisionHistory
          rows={history.data ?? []}
          loading={history.isPending}
          error={!history.data && history.isError ? history.error.message : undefined}
          retry={() => void history.refetch()}
        />
      </div>
    </section>
  );
}
