import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip as ChartTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { TelemetrySeries } from '../../domain/telemetry/types';
import { formatOperationalTime } from '../../utils/formatters';
import { TelemetryPointMarker, TelemetryTooltip, chartAxis, chartGrid } from './telemetry-chart-parts';
import type { StateChartModel } from './prediction-investigation-model';

/**
 * Discrete channels are drawn as a step chart: the state holds until the next sample, so no
 * interpolation suggests a value the sensor never reported. The vertical index is internal
 * positioning; axis ticks and tooltips always show the real state name.
 */
export function StateTelemetryChart({ chart, series }: { chart: StateChartModel; series: TelemetrySeries }) {
  return (
    <ResponsiveContainer width="100%" height={268}>
      <LineChart data={[...chart.data]} margin={{ top: 8, right: 16, bottom: 4, left: 4 }}>
        <CartesianGrid {...chartGrid} />
        <XAxis
          dataKey="time"
          type="number"
          scale="time"
          domain={['dataMin', 'dataMax']}
          tickFormatter={(value: number) => formatOperationalTime(value)}
          {...chartAxis}
        />
        <YAxis
          width={104}
          type="number"
          domain={[-0.4, chart.states.length - 0.6]}
          ticks={chart.states.map((_, index) => index)}
          tickFormatter={(value: number) => chart.states[value] ?? ''}
          {...chartAxis}
        />
        <ChartTooltip
          content={(props) => <TelemetryTooltip active={props.active} payload={props.payload} unit={null} />}
          cursor={{ stroke: 'var(--border-default)', strokeWidth: 1 }}
        />
        <Line
          type="stepAfter"
          dataKey="stateIndex"
          name={series.sensorName}
          stroke="var(--accent)"
          strokeWidth={1.5}
          connectNulls={false}
          isAnimationActive={false}
          activeDot={{ r: 3, fill: 'var(--accent)', stroke: 'none' }}
          dot={TelemetryPointMarker}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
