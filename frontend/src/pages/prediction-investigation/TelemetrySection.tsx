import { useMemo } from 'react';
import { RefreshCw } from 'lucide-react';
import type { UseQueryResult } from '@tanstack/react-query';
import type { TelemetryRange, TelemetrySeries } from '../../domain/telemetry/types';
import { EmptyState, ErrorState, Skeleton, StaleState } from '../../components/feedback/States';
import { IconButton } from '../../components/ui/Button';
import { formatDateTime, formatTelemetryValue } from '../../utils/formatters';
import { NumericTelemetryChart } from './NumericTelemetryChart';
import { StateTelemetryChart } from './StateTelemetryChart';
import { TelemetryRangeControl } from './TelemetryRangeControl';
import {
  buildTelemetryChart,
  rangeLabels,
  telemetryEvents,
  telemetrySummary,
} from './prediction-investigation-model';

function TelemetryBody({ series, range }: { series: TelemetrySeries; range: TelemetryRange }) {
  const chart = useMemo(() => buildTelemetryChart(series), [series]);
  const events = useMemo(() => telemetryEvents(series), [series]);
  const summary = telemetrySummary(series, range);
  return (
    <>
      <figure className="telemetry-figure">
        {/* The chart is decorative for assistive technology; the summary below carries the data. */}
        <div className="telemetry-chart" role="img" aria-label={summary}>
          {chart.kind === 'numeric' ? (
            <NumericTelemetryChart chart={chart} series={series} />
          ) : (
            <StateTelemetryChart chart={chart} series={series} />
          )}
        </div>
        <figcaption className="sr-only" data-testid="telemetry-summary">
          {summary}
        </figcaption>
      </figure>
      <div className="telemetry-stats">
        {chart.kind === 'numeric' ? (
          <>
            <span>
              Минимум <strong>{formatTelemetryValue(chart.min, series.unit)}</strong>
            </span>
            <span>
              Максимум <strong>{formatTelemetryValue(chart.max, series.unit)}</strong>
            </span>
            <span>
              Последнее <strong>{formatTelemetryValue(chart.last, series.unit)}</strong>
            </span>
          </>
        ) : (
          <span>
            Последнее состояние <strong>{chart.last ?? '—'}</strong>
          </span>
        )}
        <span>
          Точек <strong>{series.points.length}</strong>
        </span>
      </div>
      {events.length > 0 && (
        <div className="telemetry-events">
          <h3>События периода</h3>
          <ul>
            {events.map((event) => (
              <li key={`${event.kind}-${event.timestamp}`}>
                <span className={`telemetry-event-marker telemetry-event-${event.kind}`} aria-hidden="true" />
                <span className="telemetry-event-kind">
                  {event.kind === 'chatter' ? 'Дребезг сигнала' : 'Аварийное значение'}
                </span>
                <span className="telemetry-event-value">{event.raw}</span>
                <time dateTime={event.timestamp}>{formatDateTime(event.timestamp)}</time>
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}

export function TelemetrySection({
  query,
  range,
  onRangeChange,
}: {
  query: UseQueryResult<TelemetrySeries>;
  range: TelemetryRange;
  onRangeChange: (range: TelemetryRange) => void;
}) {
  const series = query.data;
  return (
    <section className="telemetry-section" aria-labelledby="telemetry-title">
      <header className="investigation-block-heading">
        <div>
          <h2 id="telemetry-title">Телеметрия канала</h2>
          <p>Фактические измерения за {rangeLabels[range]}</p>
        </div>
        <div className="telemetry-tools">
          <TelemetryRangeControl value={range} onChange={onRangeChange} />
          <IconButton
            variant="ghost"
            label="Обновить телеметрию"
            disabled={query.isFetching}
            onClick={() => void query.refetch()}
          >
            <RefreshCw size={14} />
          </IconButton>
        </div>
      </header>
      {series && query.isError && (
        <StaleState onRefresh={() => void query.refetch()} refreshing={query.isFetching} />
      )}
      <div className="telemetry-body">
        {query.isPending ? (
          <div className="telemetry-skeleton" role="status" aria-label="Загрузка телеметрии">
            <Skeleton className="telemetry-skeleton-chart" />
            <Skeleton className="telemetry-skeleton-axis" />
          </div>
        ) : !series ? (
          <ErrorState
            message="Не удалось загрузить телеметрию. Данные прогноза остаются доступны."
            onRetry={() => void query.refetch()}
          />
        ) : series.points.length === 0 ? (
          <EmptyState title="Телеметрия отсутствует" description="За выбранный период данные не получены." />
        ) : (
          <TelemetryBody series={series} range={range} />
        )}
      </div>
    </section>
  );
}
