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
/**
 * Squares encode urgency only, never risk: three for 1–6 h, two for 6–24 h, one for 24–48 h and a
 * single neutral square for the normal regime. The count is what the eye reads while scanning a
 * table; the label stays the accessible source of truth.
 */
const urgencySquares: Record<MaintenanceUrgency, number> = {
  FLASH_1_6H: 3,
  URGENT_6_24H: 2,
  PLANNED_24_48H: 1,
  NORMAL: 1,
};
export function UrgencyIndicator({ value }: { value: MaintenanceUrgency | null }) {
  const tone = value === null ? 'neutral' : urgencyTones[value];
  const count = value === null ? 1 : urgencySquares[value];
  return (
    <span className="semantic-indicator urgency-indicator">
      <span className={`urgency-squares tone-${tone}`} aria-hidden="true">
        {Array.from({ length: count }, (_, index) => (
          <span key={index} className="urgency-square" />
        ))}
      </span>
      {getUrgencyLabel(value)}
    </span>
  );
}
/** Historical name kept so existing call sites and tests continue to work. */
export const UrgencyBadge = UrgencyIndicator;
export const ticketStatuses: Record<TicketStatus, { label: string; tone: Tone }> = {
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
