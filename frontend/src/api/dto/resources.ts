export interface ObjectDto {
  object_id: number;
  object_name: string;
  parent_object_id: number | null;
  subsystem: string;
}
export interface SystemDto {
  status: 'operational' | 'degraded';
  updated_at: string;
}
