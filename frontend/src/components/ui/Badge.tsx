import type { ReactNode } from 'react';
import { Check } from 'lucide-react';
import type { MaintenanceUrgency, RiskLevel } from '../../domain/prediction/types';
import type { TicketStatus } from '../../domain/ticket/types';
import { getRiskLabel, getUrgencyLabel } from '../../utils/formatters';
export type Tone = 'neutral' | 'info' | 'success' | 'warning' | 'error' | RiskLevel;
export function Badge({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`badge tone-${tone}`}>{children}</span>;
}
/**
 * Risk reads as a dot plus a neutral label by default. Where the row already carries the urgency
 * squares, `showMarker={false}` drops the dot and moves the semantic colour onto the label itself,
 * so the left edge of the row stays calm without losing the severity cue.
 */
export function RiskBadge({ value, showMarker = true }: { value: RiskLevel | null; showMarker?: boolean }) {
  const tone = `tone-${value ?? 'neutral'}`;
  return (
    <span className={`semantic-indicator risk-indicator ${showMarker ? '' : `risk-indicator-text ${tone}`}`}>
      {showMarker && <span className={`semantic-marker risk-marker ${tone}`} aria-hidden="true" />}
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
 * Urgency reads as a compact mini-chart, never as risk: three columns rise from left to right and
 * the shorter the maintenance window, the more of them are lit. The steps that are not reached
 * stay as faint placeholders, so every level keeps the same footprint and the scale itself is
 * visible. The label stays the source of truth.
 */
const urgencyColumns = ['sm', 'md', 'lg'] as const;
const urgencyLevels: Record<MaintenanceUrgency, number> = {
  FLASH_1_6H: 3,
  URGENT_6_24H: 2,
  PLANNED_24_48H: 1,
  NORMAL: 0,
};
export function UrgencyIndicator({ value }: { value: MaintenanceUrgency | null }) {
  const tone = value === null ? 'neutral' : urgencyTones[value];
  // The normal regime is not a shorter deadline but the absence of one, so it reads as a check.
  if (value === 'NORMAL')
    return (
      <span className="semantic-indicator urgency-indicator urgency-normal">
        <span className="urgency-meter urgency-check tone-low" aria-hidden="true">
          <Check size={13} strokeWidth={3} />
        </span>
        {getUrgencyLabel(value)}
      </span>
    );
  // Without a value there is no step to light up: the bare scale says "no data" on its own.
  const level = value === null ? 0 : urgencyLevels[value];
  return (
    <span className="semantic-indicator urgency-indicator">
      <span className={`urgency-meter tone-${tone}`} aria-hidden="true">
        {urgencyColumns.map((size, index) => (
          <span
            key={size}
            className={`urgency-column urgency-column-${size} ${index < level ? 'urgency-column-on' : ''}`}
          />
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
