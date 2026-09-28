import type { RiskLevel } from '../prediction/types';

export type TicketStatus = 'draft' | 'approved' | 'rejected' | 'completed';

/** Reference list of maintenance crews. A real staffing directory is out of the current scope. */
export const assigneeOptions = [
  'Смена А',
  'Смена Б',
  'Инженер КИП',
  'Электротехническая группа',
  'Служба вентиляции',
] as const;

export interface Ticket {
  id: string;
  predictionId: string | null;
  objectId: number;
  objectName: string;
  sensorName: string | null;
  piket: string | null;
  title: string;
  description: string;
  status: TicketStatus;
  priority: RiskLevel | null;
  assignee: string | null;
  createdAt: string;
  updatedAt: string;
  completedAt: string | null;
}

/**
 * Canonical lifecycle. Backend owns the rule; this map only drives which actions are offered,
 * so a rejected or completed ticket exposes no further transition in the interface.
 */
export const ticketTransitions: Record<TicketStatus, readonly TicketStatus[]> = {
  draft: ['approved', 'rejected'],
  approved: ['completed'],
  rejected: [],
  completed: [],
};
export const getAllowedTicketTransitions = (status: TicketStatus): readonly TicketStatus[] =>
  ticketTransitions[status];
export const isAllowedTicketTransition = (from: TicketStatus, to: TicketStatus) =>
  ticketTransitions[from].includes(to);
