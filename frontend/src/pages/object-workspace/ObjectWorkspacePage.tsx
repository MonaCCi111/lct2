import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useObjectDetail, useObjectTopology, usePredictions } from '../../api/queries/hooks';
import { compareByUrgency } from '../../api/adapters/operational-queue';
import { EmptyState } from '../../components/feedback/States';
import { ObjectHeader } from './ObjectHeader';
import { ObjectSummary } from './ObjectSummary';
import { ObjectTopology } from './ObjectTopology';
import { ObjectPredictions } from './ObjectPredictions';
import {
  filterObjectPredictions,
  initialObjectPredictionFilters,
  isObjectNotFound,
} from './object-workspace-model';
import './object-workspace.css';

export default function ObjectWorkspacePage() {
  const { objectId } = useParams();
  const id = Number(objectId);
  const detail = useObjectDetail(id);
  const topology = useObjectTopology(id);
  const predictions = usePredictions({ objectId: Number.isFinite(id) ? id : undefined });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filters, setFilters] = useState(initialObjectPredictionFilters);

  const selected = topology.data?.segments.find((item) => item.segmentId === selectedId) ?? null;
  // Ready urgency values are only ordered here, never derived from probability or risk.
  const sorted = useMemo(() => [...(predictions.data ?? [])].sort(compareByUrgency), [predictions.data]);
  const visible = useMemo(
    () => filterObjectPredictions(sorted, filters, selected),
    [sorted, filters, selected],
  );

  if (!Number.isFinite(id) || (!detail.data && isObjectNotFound(detail.error)))
    return (
      <EmptyState
        title="Объект не найден"
        description="Объект с указанным идентификатором отсутствует или недоступен."
        action={
          <Link className="button button-secondary" to="/objects">
            К списку объектов
          </Link>
        }
      />
    );

  return (
    <div className="object-workspace">
      <ObjectHeader query={detail} objectId={id} />
      <ObjectSummary query={detail} />
      <ObjectTopology
        query={topology}
        selected={selected}
        onSelect={(segment) => setSelectedId(segment?.segmentId ?? null)}
        visiblePredictions={visible.length}
      />
      <ObjectPredictions
        query={predictions}
        filters={filters}
        onFiltersChange={setFilters}
        selected={selected}
        onResetSegment={() => setSelectedId(null)}
        predictions={visible}
      />
    </div>
  );
}
