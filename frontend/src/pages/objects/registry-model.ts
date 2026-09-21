import type { ObjectStatusSummary } from '../../domain/object/status';
import type { RiskLevel } from '../../domain/prediction/types';
import { formatCoverage } from '../../utils/formatters';

export type RegistryRiskFilter = RiskLevel | 'all';
const priority: Record<RiskLevel, number> = { critical: 0, high: 1, medium: 2, low: 3 };
const names = new Intl.Collator('ru', { sensitivity: 'base', numeric: true });

// Presentation ordering of supplied aggregates; never derive risk or counts from predictions.
export function selectObjects(
  rows: readonly ObjectStatusSummary[],
  search: string,
  risk: RegistryRiskFilter,
) {
  const term = search.trim().toLocaleLowerCase('ru');
  return rows
    .filter(
      (row) =>
        (risk === 'all' || row.riskLevel === risk) && row.objectName.toLocaleLowerCase('ru').includes(term),
    )
    .sort(
      (a, b) =>
        (a.riskLevel === null ? 4 : priority[a.riskLevel]) -
          (b.riskLevel === null ? 4 : priority[b.riskLevel]) ||
        b.criticalPredictions - a.criticalPredictions ||
        b.activePredictions - a.activePredictions ||
        names.compare(a.objectName, b.objectName) ||
        a.objectId - b.objectId,
    );
}

export function registryCoverage(row: ObjectStatusSummary) {
  // This is only the ratio of supplied channel counts, not coverage reconstructed from predictions.
  return row.channelsTotal > 0 ? formatCoverage((row.mlSupportedChannels / row.channelsTotal) * 100) : '—';
}
