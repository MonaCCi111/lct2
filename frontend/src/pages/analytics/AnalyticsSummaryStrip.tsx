import type { AnalyticsSummary } from '../../domain/analytics/types';
import { formatCount, formatCoverage } from '../../utils/formatters';
export function AnalyticsSummaryStrip({ data }: { data: AnalyticsSummary }) {
  const totals = data.totals;
  return (
    <dl className="analytics-summary" aria-label="Сводка аналитики">
      {[
        ['Активные риски', formatCount(totals.activePredictions)],
        ['Критические', formatCount(totals.criticalPredictions)],
        ['Открытые наряды', formatCount(totals.openTickets)],
        ['ML-покрытие', formatCoverage(totals.mlCoveragePercent)],
        ['Выполнено за период', formatCount(totals.completedTickets)],
      ].map(([label, value], i) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd className={i === 1 ? 'analytics-critical' : undefined}>{value}</dd>
        </div>
      ))}
    </dl>
  );
}
