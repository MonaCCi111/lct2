import type { RiskLevel } from '../../domain/prediction/types';
import type { TicketStatus } from '../../domain/ticket/types';

export interface TicketDto {
  ticket_id: string;
  prediction_id: string | null;
  object_id: number;
  object_name: string;
  sensor_name: string | null;
  piket: string | null;
  title: string;
  description: string;
  status: TicketStatus;
  priority: RiskLevel | null;
  assignee: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

// Backend assigns ticket_id, status, created_at and updated_at; the client never sends them.
export interface CreateTicketRequestDto {
  prediction_id: string | null;
  object_id: number;
  title: string;
  description: string;
  assignee: string | null;
}

export interface UpdateTicketStatusRequestDto {
  status: TicketStatus;
}
