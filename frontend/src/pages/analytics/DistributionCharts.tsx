import type { ReactNode } from 'react';
import type { AnalyticsTicketStatus, AnalyticsUrgencyDistribution } from '../../domain/analytics/types';
import type { MaintenanceUrgency } from '../../domain/prediction/types';
import { ticketStatuses, UrgencyBadge } from '../../components/ui/Badge';
import { formatCount, getUrgencyLabel } from '../../utils/formatters';
function Distribution({
  title,
  items,
}: {
  title: string;
  items: { key: string; label: string; content: ReactNode; count: number; tone?: string }[];
}) {
  const maximum = Math.max(1, ...items.map((item) => item.count));
  const summary = items.map((item) => `${item.label}: ${formatCount(item.count)}`).join('; ');
  return (
    <figure className="analytics-distribution" aria-label={title}>
      <figcaption className="sr-only">
        {title}. {summary || 'Данные отсутствуют.'}
      </figcaption>
      {items.length === 0 ? (
        <p>Данные отсутствуют.</p>
      ) : (
        <ul>
          {items.map((item) => (
            <li key={item.key}>
              <div>
                {item.content}
                <span>{formatCount(item.count)}</span>
              </div>
              {/* The bar repeats the severity of its own row, so the block reads as one scale. */}
              <div className={`analytics-bar ${item.tone ? `tone-${item.tone}` : ''}`} aria-hidden="true">
                <span style={{ width: `${(100 * item.count) / maximum}%` }} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </figure>
  );
}
/** Same scale as the registries: shorter window, louder colour; the normal regime reads green. */
const urgencyBarTones: Record<MaintenanceUrgency, string> = {
  FLASH_1_6H: 'critical',
  URGENT_6_24H: 'high',
  PLANNED_24_48H: 'medium',
  NORMAL: 'low',
};
export function UrgencyDistributionChart({ items }: { items: AnalyticsUrgencyDistribution[] }) {
  return (
    <Distribution
      title="Распределение активных рисков по срочности"
      items={items.map((item) => ({
        key: item.urgency,
        label: getUrgencyLabel(item.urgency),
        content: <UrgencyBadge value={item.urgency} />,
        count: item.count,
        tone: urgencyBarTones[item.urgency],
      }))}
    />
  );
}
export function TicketStatusChart({ items }: { items: AnalyticsTicketStatus[] }) {
  return (
    <Distribution
      title="Распределение нарядов по текущему статусу"
      items={(['draft', 'approved', 'rejected', 'completed'] as const).flatMap((status) => {
        const item = items.find((item) => item.status === status);
        return item
          ? [
              {
                key: status,
                label: ticketStatuses[status].label,
                content: ticketStatuses[status].label,
                count: item.count,
              },
            ]
          : [];
      })}
    />
  );
}
