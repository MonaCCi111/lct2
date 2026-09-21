import { useEffect, useState, type ReactNode } from 'react';
import { RefreshCw } from 'lucide-react';
import { useAnalyticsSummary } from '../../api/queries/hooks';
import type { AnalyticsRange, AnalyticsSummary } from '../../domain/analytics/types';
import { PageHeader } from '../../components/feedback/PageShell';
import { EmptyState, ErrorState, Skeleton, StaleState } from '../../components/feedback/States';
import { Button } from '../../components/ui/Button';
import { formatDateTime } from '../../utils/formatters';
import { AnalyticsRangeControl } from './AnalyticsRangeControl';
import { AnalyticsSummaryStrip } from './AnalyticsSummaryStrip';
import { RiskTimelineChart } from './RiskTimelineChart';
import { TicketStatusChart, UrgencyDistributionChart } from './DistributionCharts';
import { TopRiskObjects } from './TopRiskObjects';
import { MlDomainCoverage } from './MlDomainCoverage';
import { analyticsRangeLabels, isAnalyticsEmpty } from './analytics-model';
import './analytics-page.css';
function Section({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  return (
    <section className="analytics-section" aria-label={title}>
      <header>
        <h2>{title}</h2>
        {note && <p>{note}</p>}
      </header>
      {children}
    </section>
  );
}
function AnalyticsSkeleton() {
  return (
    <div role="status" aria-label="Загрузка аналитики">
      <div className="analytics-summary analytics-skeleton-strip">
        {Array.from({ length: 5 }, (_, i) => (
          <Skeleton key={i} />
        ))}
      </div>
      <div className="analytics-grid">
        {Array.from({ length: 4 }, (_, i) => (
          <div className="analytics-section analytics-skeleton-panel" key={i}>
            <Skeleton />
            <Skeleton />
            <Skeleton />
          </div>
        ))}
      </div>
      <div className="analytics-section analytics-skeleton-panel">
        <Skeleton />
        <Skeleton />
      </div>
    </div>
  );
}
export default function AnalyticsPage() {
  const [range, setRange] = useState<AnalyticsRange>('7d');
  const query = useAnalyticsSummary(range);
  const [lastSummary, setLastSummary] = useState<AnalyticsSummary>();
  useEffect(() => {
    if (query.data && !query.isPlaceholderData) setLastSummary(query.data);
  }, [query.data, query.isPlaceholderData]);
  const data = query.data ?? lastSummary;
  const refresh = () => void query.refetch();
  return (
    <div className="analytics-page">
      {/* Same header structure as the other pages: title and description left, freshness and the
          refresh control right; the range filter keeps its own row. */}
      <PageHeader
        title="Аналитика"
        description="Состояние предиктивного мониторинга"
        action={
          <div className="analytics-update">
            <span>{data ? `Обновлено ${formatDateTime(data.generatedAt)}` : 'Агрегат не загружен'}</span>
            <Button
              variant="ghost"
              aria-label="Обновить аналитику"
              disabled={query.isFetching}
              onClick={refresh}
            >
              <RefreshCw size={14} aria-hidden="true" />
              Обновить
            </Button>
          </div>
        }
      />
      <div className="analytics-controls">
        <AnalyticsRangeControl value={range} onChange={setRange} />
      </div>
      {data && data.range !== range && (
        <p role="status" className="analytics-range-notice">
          Показаны данные за {analyticsRangeLabels[data.range]}.{' '}
          {query.isFetching ? 'Загружается' : 'Не удалось загрузить'} период {analyticsRangeLabels[range]}.
        </p>
      )}
      {query.isError && data && <StaleState onRefresh={refresh} refreshing={query.isFetching} />}
      {!data ? (
        query.isPending ? (
          <AnalyticsSkeleton />
        ) : (
          <ErrorState message="Не удалось загрузить аналитику." onRetry={refresh} />
        )
      ) : isAnalyticsEmpty(data) ? (
        <EmptyState
          title="Аналитические данные отсутствуют"
          description="За выбранный период агрегаты пока не сформированы."
        />
      ) : (
        <>
          <AnalyticsSummaryStrip data={data} />
          <div className="analytics-grid" aria-busy={query.isFetching}>
            <Section
              title="Динамика рисков"
              note={`Исторические срезы · ${analyticsRangeLabels[data.range]} · МСК`}
            >
              <RiskTimelineChart points={data.riskTimeline} range={data.range} />
            </Section>
            <Section title="Распределение по срочности" note="Активные риски на момент обновления">
              <UrgencyDistributionChart items={data.urgencyDistribution} />
            </Section>
            <Section title="Объекты с наибольшим риском" note="Активные риски и нагрузка по нарядам">
              <TopRiskObjects items={data.topObjects} />
            </Section>
            <Section title="Статусы нарядов" note="Текущие статусы всех нарядов">
              <TicketStatusChart items={data.ticketStatusDistribution} />
            </Section>
          </div>
          <Section
            title="ML-покрытие по доменам"
            note="Доля каналов, поддерживаемых моделью; не оценка риска"
          >
            <MlDomainCoverage items={data.mlDomainCoverage} />
          </Section>
        </>
      )}
    </div>
  );
}
