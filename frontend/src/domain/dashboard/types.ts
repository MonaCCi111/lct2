export interface DashboardSummary {
  generatedAt: string;
  modelVersion: string;
  channels: {
    total: number;
    mlSupported: number;
    mlUnsupported: number;
    coveragePercent: number;
  };
  predictions: {
    active: number;
    critical: number;
    high: number;
    medium: number;
    flash1To6h: number;
    urgent6To24h: number;
    planned24To48h: number;
  };
  objects: {
    total: number;
    affected: number;
    critical: number;
  };
  tickets: {
    draft: number;
    approved: number;
    completedToday: number;
  };
}
