import type { ReactNode } from 'react';
import type { MaintenanceUrgency, RiskLevel } from '../../domain/prediction/types';
import type { TicketStatus } from '../../domain/ticket/types';
import { getRiskLabel, getUrgencyLabel } from '../../utils/formatters';
export type Tone = 'neutral' | 'info' | 'success' | 'warning' | 'error' | RiskLevel;
export function Badge({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`badge tone-${tone}`}>{children}</span>;
}
export function RiskBadge({ value }: { value: RiskLevel | null }) {
  return (
    <span className="semantic-indicator risk-indicator">
      <span className={`semantic-marker risk-marker tone-${value ?? 'neutral'}`} aria-hidden="true" />
      {getRiskLabel(value)}
    </span>
  );
}
const urgencyTones: Record<MaintenanceUrgency, Tone> = {
  NORMAL: 'low',
  PLANNED_24_48H: 'medium',
  URGENT_6_24H: 'high',
  FLASH_1_6H: 'critical',
};
export function UrgencyBadge({ value }: { value: MaintenanceUrgency | null }) {
  return (
    <span className="semantic-indicator urgency-indicator">
      <span
        className={`semantic-marker urgency-marker tone-${value === null ? 'neutral' : urgencyTones[value]}`}
        aria-hidden="true"
      />
      {getUrgencyLabel(value)}
    </span>
  );
}
const ticketStatuses: Record<TicketStatus, { label: string; tone: Tone }> = {
  draft: { label: 'Черновик', tone: 'neutral' },
  approved: { label: 'Согласован', tone: 'info' },
  rejected: { label: 'Отклонён', tone: 'error' },
  completed: { label: 'Выполнен', tone: 'success' },
};
export function StatusBadge({ value }: { value: TicketStatus }) {
  return (
    <span className={`badge workflow-status tone-${ticketStatuses[value].tone}`}>
      {ticketStatuses[value].label}
    </span>
  );
}
