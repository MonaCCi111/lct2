import type { TicketDto } from '../dto/ticket';
import type { Ticket } from '../../domain/ticket/types';

// Priority is the risk level stored with the ticket; it is never recomputed from probability.
export const toTicket = (dto: TicketDto): Ticket => ({
  id: dto.ticket_id,
  predictionId: dto.prediction_id,
  objectId: dto.object_id,
  objectName: dto.object_name,
  sensorName: dto.sensor_name,
  piket: dto.piket,
  title: dto.title,
  description: dto.description,
  status: dto.status,
  priority: dto.priority,
  assignee: dto.assignee,
  createdAt: dto.created_at,
  updatedAt: dto.updated_at,
  completedAt: dto.completed_at,
});
