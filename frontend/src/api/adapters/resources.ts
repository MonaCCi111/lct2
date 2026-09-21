import type { ObjectDto } from '../dto/resources';
import type { InfrastructureObject } from '../../domain/object/types';
export const toObject = (dto: ObjectDto): InfrastructureObject => ({
  id: dto.object_id,
  name: dto.object_name,
  parentObjectId: dto.parent_object_id,
  subsystem: dto.subsystem,
});
