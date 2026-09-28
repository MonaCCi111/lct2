export interface DashboardSummaryDto {
  generated_at: string;
  model_version: string;
  channels: {
    total: number;
    ml_supported: number;
    ml_unsupported: number;
    coverage_percent: number;
  };
  predictions: {
    active: number;
    critical: number;
    high: number;
    medium: number;
    flash_1_6h: number;
    urgent_6_24h: number;
    planned_24_48h: number;
  };
  objects: {
    total: number;
    affected: number;
    critical: number;
  };
  tickets: {
    draft: number;
    approved: number;
    completed_today: number;
  };
}
