import type { KeyboardEvent } from 'react';
import { Tooltip } from '../../components/ui/Tooltip';
import { formatPiket, getRiskLabel } from '../../utils/formatters';
import { TopologyTooltipContent } from './TopologyTooltipContent';
import { TOPOLOGY_AXIS_Y, formatPredictionCount, type SegmentLayout } from './object-workspace-model';

const HIT_HEIGHT = 30;
const thickness = (risk: SegmentLayout['segment']['riskLevel'], selected: boolean) =>
  (risk === 'high' || risk === 'critical' ? 8 : risk === 'medium' ? 6 : 4) + (selected ? 3 : 0);

export function TopologySegmentMark({
  layout,
  selected,
  onSelect,
}: {
  layout: SegmentLayout;
  selected: boolean;
  onSelect: (segment: SegmentLayout['segment']) => void;
}) {
  const { segment, x, width } = layout;
  const height = thickness(segment.riskLevel, selected);
  // Risk is never conveyed by colour alone: the accessible name carries the same state.
  const label = `Участок ${formatPiket(segment.piketFrom)} — ${formatPiket(segment.piketTo)}, ${
    segment.label
  }, ${getRiskLabel(segment.riskLevel).toLocaleLowerCase('ru-RU')} риск, ${formatPredictionCount(
    segment.activePredictions,
  )}`;
  const activate = (event: KeyboardEvent<SVGGElement>) => {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    event.preventDefault();
    onSelect(segment);
  };
  return (
    <Tooltip content={<TopologyTooltipContent segment={segment} />}>
      <g
        className={`topology-segment tone-${segment.riskLevel ?? 'neutral'} ${selected ? 'is-selected' : ''}`}
        role="button"
        tabIndex={0}
        aria-pressed={selected}
        aria-label={label}
        onClick={() => onSelect(segment)}
        onKeyDown={activate}
      >
        <rect
          className="topology-segment-hit"
          x={x}
          y={TOPOLOGY_AXIS_Y - HIT_HEIGHT / 2}
          width={width}
          height={HIT_HEIGHT}
        />
        <rect
          className="topology-segment-line"
          x={x}
          y={TOPOLOGY_AXIS_Y - height / 2}
          width={width}
          height={height}
          rx={1}
        />
        <rect
          className="topology-segment-ring"
          x={x - 1}
          y={TOPOLOGY_AXIS_Y - HIT_HEIGHT / 2}
          width={width + 2}
          height={HIT_HEIGHT}
          rx={2}
        />
      </g>
    </Tooltip>
  );
}
