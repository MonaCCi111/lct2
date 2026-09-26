import { ApiError } from '../../api/client/http';

export interface WorkOrderAttempt {
  idempotencyKey: string;
}

export const createWorkOrderIdempotencyKey = () => crypto.randomUUID();

export const beginWorkOrderAttempt = (
  current: WorkOrderAttempt | null,
  createKey: () => string = createWorkOrderIdempotencyKey,
): WorkOrderAttempt => current ?? { idempotencyKey: createKey() };

export function validateWorkOrderFields(workType: string, description: string) {
  return {
    workType: workType.trim() === '' ? 'Укажите тип работ.' : null,
    description: description.trim() === '' ? 'Добавьте описание работ.' : null,
  };
}

export const workOrderErrorMessage = (error: unknown) =>
  error instanceof ApiError && error.status === 409
    ? 'Для этого решения уже создан наряд.'
    : error instanceof Error
      ? error.message
      : 'Не удалось создать наряд.';
