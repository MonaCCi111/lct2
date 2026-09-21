export interface TelemetrySample {
  channelId: number;
  timestamp: string;
  value: number | null;
  unit: string;
  quality: 'valid' | 'missing' | 'invalid';
}
