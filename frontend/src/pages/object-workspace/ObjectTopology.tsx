import { useEffect, useMemo, useRef, useState } from 'react';
import { RefreshCw, X } from 'lucide-react';
import type { UseQueryResult } from '@tanstack/react-query';
import type { ObjectTopology as Topology, TopologySegment } from '../../domain/object/topology';
import { EmptyState, ErrorState, Skeleton, StaleState } from '../../components/feedback/States';
import { Button, IconButton } from '../../components/ui/Button';
import { formatPiket } from '../../utils/formatters';
import { TopologySegmentMark } from './TopologySegment';
import {
  TOPOLOGY_AXIS_Y,
  TOPOLOGY_FALLBACK_WIDTH,
  TOPOLOGY_HEIGHT,
  TOPOLOGY_LABEL_Y,
  TOPOLOGY_PADDING_X,
  TOPOLOGY_PIKET_LABEL_Y,
  buildTopologyLayout,
  formatPredictionCount,
} from './object-workspace-model';

const legend = [
  { tone: 'critical', label: 'Критический' },
  { tone: 'high', label: 'Высокий' },
  { tone: 'medium', label: 'Умеренный' },
  { tone: 'neutral', label: 'Без отклонений' },
];

// Renders in CSS pixels so stroke weights and type stay constant at every workspace width.
function useMeasuredWidth() {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(TOPOLOGY_FALLBACK_WIDTH);
  useEffect(() => {
    const node = ref.current;
    if (!node || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(([entry]) => {
      const next = Math.round(entry?.contentRect.width ?? 0);
      if (next > 0) setWidth(next);
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  return { ref, width };
}

export function ObjectTopology({
  query,
  selected,
  onSelect,
  visiblePredictions,
}: {
  query: UseQueryResult<Topology>;
  selected: TopologySegment | null;
  onSelect: (segment: TopologySegment | null) => void;
  visiblePredictions: number;
}) {
  const { ref, width } = useMeasuredWidth();
  const topology = query.data;
  const layout = useMemo(
    () => (topology && topology.segments.length > 0 ? buildTopologyLayout(topology, width, selected) : null),
    [topology, width, selected],
  );
  return (
    <section className="object-topology" aria-labelledby="object-topology-title">
      <header className="workspace-block-heading">
        <div>
          <h2 id="object-topology-title">Топология объекта</h2>
          <p>Участки по пикетам и их состояние</p>
        </div>
        <div className="topology-tools">
          <span className="topology-legend" aria-hidden="true">
            {legend.map((item) => (
              <span key={item.tone} className="topology-legend-item">
                <span className={`semantic-marker risk-marker tone-${item.tone}`} />
                {item.label}
              </span>
            ))}
          </span>
          <IconButton
            variant="ghost"
            label="Обновить топологию"
            disabled={query.isFetching}
            onClick={() => void query.refetch()}
          >
            <RefreshCw size={14} />
          </IconButton>
        </div>
      </header>
      {topology && query.isError && (
        <StaleState onRefresh={() => void query.refetch()} refreshing={query.isFetching} />
      )}
      <div className="topology-canvas" ref={ref}>
        {query.isPending ? (
          <div className="topology-skeleton" role="status" aria-label="Загрузка топологии">
            <Skeleton className="topology-skeleton-line" />
            <Skeleton className="topology-skeleton-ticks" />
          </div>
        ) : !topology ? (
          <ErrorState message={query.error?.message} onRetry={() => void query.refetch()} />
        ) : layout === null ? (
          <EmptyState
            title="Топология объекта недоступна"
            description="Для объекта пока не сформирована структура участков по пикетам."
          />
        ) : (
          <svg
            className="topology-svg"
            width={layout.width}
            height={TOPOLOGY_HEIGHT}
            viewBox={`0 0 ${layout.width} ${TOPOLOGY_HEIGHT}`}
            role="group"
            aria-label={`Схема участков: ${formatPiket(layout.piketFrom)} — ${formatPiket(layout.piketTo)}`}
          >
            <line
              className="topology-baseline"
              x1={TOPOLOGY_PADDING_X}
              x2={layout.width - TOPOLOGY_PADDING_X}
              y1={TOPOLOGY_AXIS_Y}
              y2={TOPOLOGY_AXIS_Y}
            />
            {layout.segmentLabels.map((item) => (
              <g key={item.segmentId} className="topology-segment-label" aria-hidden="true">
                <text x={item.x} y={TOPOLOGY_LABEL_Y}>
                  {item.label}
                </text>
                <line x1={item.x} x2={item.x} y1={TOPOLOGY_LABEL_Y + 6} y2={TOPOLOGY_AXIS_Y - 10} />
              </g>
            ))}
            {layout.segments.map((item) => (
              <TopologySegmentMark
                key={item.segment.segmentId}
                layout={item}
                selected={item.segment.segmentId === selected?.segmentId}
                onSelect={(segment) => onSelect(segment.segmentId === selected?.segmentId ? null : segment)}
              />
            ))}
            {layout.piketLabels.map((item) => (
              <g key={item.value} className="topology-piket" aria-hidden="true">
                <line x1={item.x} x2={item.x} y1={TOPOLOGY_AXIS_Y + 9} y2={TOPOLOGY_AXIS_Y + 15} />
                <text x={item.x} y={TOPOLOGY_PIKET_LABEL_Y}>
                  {formatPiket(item.value)}
                </text>
              </g>
            ))}
          </svg>
        )}
      </div>
      <footer className="topology-footer">
        {selected ? (
          <>
            <span aria-live="polite">
              Выбран участок: {formatPiket(selected.piketFrom)} — {formatPiket(selected.piketTo)} ·{' '}
              {selected.label} · {formatPredictionCount(visiblePredictions)}
            </span>
            <Button variant="ghost" onClick={() => onSelect(null)}>
              <X size={13} />
              Сбросить
            </Button>
          </>
        ) : (
          <span>
            {layout
              ? 'Выберите участок, чтобы отфильтровать прогнозы по диапазону пикетов'
              : 'Участки объекта не загружены'}
          </span>
        )}
      </footer>
    </section>
  );
}
