import type { V2Decision, V2Object, V2WorkOrder } from '../../api/v2/domain/types';

export type WorkOrderEligibility =
  | { state: 'allowed'; workOrderId: null }
  | { state: 'pending'; workOrderId: null }
  | { state: 'rejected'; workOrderId: null }
  | { state: 'created'; workOrderId: string };

export function getWorkOrderEligibility(decision: V2Decision | null): WorkOrderEligibility {
  if (!decision) return { state: 'pending', workOrderId: null };
  if (decision.decision === 'rejected') return { state: 'rejected', workOrderId: null };
  return decision.workOrderId
    ? { state: 'created', workOrderId: decision.workOrderId }
    : { state: 'allowed', workOrderId: null };
}

export const workOrderEligibilityText: Record<WorkOrderEligibility['state'], string> = {
  allowed: 'Одобренный черновик готов к созданию наряда.',
  pending: 'Сначала сохраните решение диспетчера.',
  rejected: 'Для отклонённого черновика наряд не создаётся.',
  created: 'Для этого решения уже создан наряд.',
};

export const v2ObjectDisplayName = (objectId: number, objects: readonly V2Object[]) =>
  objects.find((object) => object.objectId === objectId)?.objectName ?? `Объект ${objectId}`;

export interface WorkOrderRow extends V2WorkOrder {
  objectName: string;
}

export const toWorkOrderRows = (
  workOrders: readonly V2WorkOrder[],
  objects: readonly V2Object[],
): WorkOrderRow[] =>
  workOrders.map((workOrder) => ({
    ...workOrder,
    objectName: v2ObjectDisplayName(workOrder.objectId, objects),
  }));
