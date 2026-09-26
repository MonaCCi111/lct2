import type { V2DraftDto, V2WorkOrderDto, V2WorkOrderRequestDto } from '../dto/types';
import { latestV2Decision, linkV2WorkOrderToDecision } from './decisions';

type StoredWorkOrder = V2WorkOrderDto & { idempotency_key: string };
let workOrders: StoredWorkOrder[] = [];
let sequence = 0;

export class V2WorkOrderMockError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

export function resetV2WorkOrderStore() {
  workOrders = [];
  sequence = 0;
}

const toDto = ({ idempotency_key: _key, ...item }: StoredWorkOrder): V2WorkOrderDto => ({ ...item });
export const listV2WorkOrders = () => workOrders.map(toDto);
export const findV2WorkOrder = (id: string) => {
  const item = workOrders.find((workOrder) => workOrder.work_order_id === id);
  return item ? toDto(item) : null;
};

export function createV2WorkOrder(
  body: V2WorkOrderRequestDto,
  draft: V2DraftDto,
  now: string,
): V2WorkOrderDto {
  const idempotent = workOrders.find((item) => item.idempotency_key === body.idempotency_key);
  if (idempotent) return toDto(idempotent);

  if (body.draft_id !== draft.draft_id) throw new V2WorkOrderMockError('Черновик для наряда не найден.', 404);
  if (!body.work_type?.trim()) throw new V2WorkOrderMockError('Укажите тип работ.', 400);
  if (!body.description?.trim()) throw new V2WorkOrderMockError('Добавьте описание работ.', 400);
  if (!body.idempotency_key?.trim())
    throw new V2WorkOrderMockError('Для создания наряда требуется idempotency_key.', 400);

  const decision = latestV2Decision(draft.draft_id);
  if (!decision || decision.decision !== 'approved')
    throw new V2WorkOrderMockError('Наряд можно создать только после одобрения черновика.', 409);
  if (decision.work_order_id || workOrders.some((item) => item.draft_id === draft.draft_id))
    throw new V2WorkOrderMockError('Для этого решения уже создан наряд.', 409);

  sequence += 1;
  const workOrderId = `WO-V2-${String(sequence).padStart(4, '0')}`;
  const workOrder: StoredWorkOrder = {
    work_order_id: workOrderId,
    draft_id: draft.draft_id,
    object_id: draft.object_id,
    status: 'created',
    work_type: body.work_type.trim(),
    description: body.description.trim(),
    created_at: now,
    created_by: 'dispatcher.demo',
    external_work_order_id: null,
    assignee_id: body.assignee_id ?? null,
    due_at: body.due_at ?? null,
    idempotency_key: body.idempotency_key,
  };
  linkV2WorkOrderToDecision(draft.draft_id, workOrderId);
  workOrders = [...workOrders, workOrder];
  return toDto(workOrder);
}
