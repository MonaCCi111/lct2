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
import { formatOperationalTime, formatTelemetryValue } from '../../utils/formatters';
import { TelemetryPointMarker, TelemetryTooltip, chartAxis, chartGrid } from './telemetry-chart-parts';
import type { NumericChartModel } from './prediction-investigation-model';

export function NumericTelemetryChart({
  chart,
  series,
}: {
  chart: NumericChartModel;
  series: TelemetrySeries;
}) {
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
          width={62}
          tickFormatter={(value: number) => formatTelemetryValue(value, null)}
          domain={['auto', 'auto']}
          {...chartAxis}
        />
        <ChartTooltip
          content={(props) => (
            <TelemetryTooltip active={props.active} payload={props.payload} unit={series.unit} />
          )}
          cursor={{ stroke: 'var(--border-default)', strokeWidth: 1 }}
        />
        <Line
          type="linear"
          dataKey="value"
          name={series.sensorName}
          stroke="var(--accent)"
          strokeWidth={1.5}
          // Gaps in the data must stay gaps: never bridge missing samples.
          connectNulls={false}
          isAnimationActive={false}
          activeDot={{ r: 3, fill: 'var(--accent)', stroke: 'none' }}
          dot={TelemetryPointMarker}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
