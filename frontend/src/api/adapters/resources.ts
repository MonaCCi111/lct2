import type { ObjectDto, TicketDto } from '../dto/resources';
import type { InfrastructureObject } from '../../domain/object/types';
import type { Ticket } from '../../domain/ticket/types';
export const toObject = (dto: ObjectDto): InfrastructureObject => ({
  id: dto.object_id,
  name: dto.object_name,
  parentObjectId: dto.parent_object_id,
  subsystem: dto.subsystem,
});
export const toTicket = (dto: TicketDto): Ticket => ({
  id: dto.ticket_id,
  predictionId: dto.prediction_id,
  title: dto.title,
  status: dto.status,
  createdAt: dto.created_at,
});
