export interface InfrastructureObject {
  id: number;
  name: string;
  parentObjectId: number | null;
  subsystem: string;
}
