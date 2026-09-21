import { DataTable, type Column } from '../../components/data-display/DataTable';
import type { AnalyticsMlDomainCoverage } from '../../domain/analytics/types';
import { getModelDomainLabel } from '../../utils/model-domain';
import { formatCount, formatCoverage } from '../../utils/formatters';
const columns: Column<AnalyticsMlDomainCoverage>[] = [
  {
    id: 'domain',
    header: 'Домен модели',
    cell: (item) => (
      <div className="analytics-domain">
        {getModelDomainLabel(item.domain)}
        <span>{item.domain}</span>
      </div>
    ),
  },
  {
    id: 'coverage',
    header: 'Покрытие',
    cell: (item) => (
      <div className="analytics-coverage">
        <span>{formatCoverage(item.coveragePercent)}</span>
        <div className="analytics-bar" aria-hidden="true">
          <span style={{ width: `${item.coveragePercent}%` }} />
        </div>
      </div>
    ),
  },
  {
    id: 'channels',
    header: 'Поддержано / всего каналов',
    align: 'right',
    cell: (item) => `${formatCount(item.channelsSupported)} / ${formatCount(item.channelsTotal)}`,
  },
];
export function MlDomainCoverage({ items }: { items: AnalyticsMlDomainCoverage[] }) {
  return (
    <DataTable
      columns={columns}
      rows={items}
      rowKey={(item) => item.domain}
      caption="ML-покрытие по доменам"
      emptyTitle="Данные покрытия отсутствуют"
    />
  );
}
