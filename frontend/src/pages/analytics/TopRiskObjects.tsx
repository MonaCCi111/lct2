import { useNavigate } from 'react-router-dom';
import { DataTable, type Column } from '../../components/data-display/DataTable';
import { RiskBadge } from '../../components/ui/Badge';
import type { AnalyticsObjectRisk } from '../../domain/analytics/types';
import { formatCount } from '../../utils/formatters';
import { formatObjectName } from '../../utils/object-name';
const columns: Column<AnalyticsObjectRisk>[] = [
  {
    id: 'object',
    header: 'Объект',
    cell: (item) => <span title={item.objectName}>{formatObjectName(item.objectName)}</span>,
  },
  { id: 'risk', header: 'Риск', cell: (item) => <RiskBadge value={item.riskLevel} /> },
  ...(
    [
      { id: 'activePredictions', header: 'Активные' },
      { id: 'criticalPredictions', header: 'Критические' },
      { id: 'highPredictions', header: 'Высокие' },
      { id: 'openTickets', header: 'Открытые наряды' },
    ] as const
  ).map((item) => ({
    ...item,
    align: 'right' as const,
    cell: (row: AnalyticsObjectRisk) => formatCount(row[item.id]),
  })),
];
export function TopRiskObjects({ items }: { items: AnalyticsObjectRisk[] }) {
  const navigate = useNavigate();
  return (
    <DataTable
      columns={columns}
      rows={items}
      rowKey={(item) => String(item.objectId)}
      caption="Объекты с наибольшим риском"
      emptyTitle="Объекты с активным риском отсутствуют"
      rowProps={(item) => ({
        tabIndex: 0,
        className: 'analytics-object-row',
        onClick: () => navigate(`/objects/${item.objectId}`),
        onKeyDown: (event) => {
          if (event.key === 'Enter') navigate(`/objects/${item.objectId}`);
        },
        'aria-label': `${item.objectName}: открыть объект`,
      })}
    />
  );
}
