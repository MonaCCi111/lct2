import type { TicketStatus } from '../../domain/ticket/types';
export interface ObjectDto {
  object_id: number;
  object_name: string;
  parent_object_id: number | null;
  subsystem: string;
}
export interface TicketDto {
  ticket_id: string;
  prediction_id: string;
  title: string;
  status: TicketStatus;
  created_at: string;
}
export interface SystemDto {
  status: 'operational' | 'degraded';
  updated_at: string;
}
