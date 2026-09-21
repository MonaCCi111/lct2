import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { AnalyticsRange, AnalyticsRiskTimelinePoint } from '../../domain/analytics/types';
import { formatCount, formatDateTime, formatOperationalTime } from '../../utils/formatters';
import { analyticsRangeLabels, formatAnalyticsDay } from './analytics-model';
const series = [
  { key: 'critical', label: 'Критические' },
  { key: 'high', label: 'Высокие' },
  { key: 'medium', label: 'Умеренные' },
] as const;
export function RiskTimelineTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: readonly { payload?: AnalyticsRiskTimelinePoint }[];
}) {
  const point = payload?.[0]?.payload;
  if (!active || !point) return null;
  return (
    <div className="analytics-tooltip">
      <p>{formatDateTime(point.timestamp)}</p>
      <dl>
        {series.map((item) => (
          <div key={item.key}>
            <dt>{item.label}</dt>
            <dd>{formatCount(point[item.key])}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
export function RiskTimelineChart({
  points,
  range,
}: {
  points: AnalyticsRiskTimelinePoint[];
  range: AnalyticsRange;
}) {
  const last = points.at(-1);
  const summary = `Динамика активных рисков за ${analyticsRangeLabels[range]}. ${last ? `Последняя точка: ${last.critical} критических, ${last.high} высоких, ${last.medium} умеренных.` : 'Точки динамики отсутствуют.'}`;
  return (
    <figure className="analytics-timeline">
      <figcaption className="analytics-chart-summary" data-testid="risk-timeline-summary">
        {summary}
      </figcaption>
      <div className="analytics-legend" aria-hidden="true">
        {series.map((item) => (
          <span key={item.key}>
            <i style={{ background: `var(--risk-${item.key})` }} />
            {item.label}
          </span>
        ))}
      </div>
      <div
        role="img"
        aria-label={summary}
        data-testid="risk-timeline"
        data-range={range}
        data-points={points.length}
      >
        <ResponsiveContainer width="100%" height={214}>
          <LineChart
            data={points.map((point) => ({ ...point, time: Date.parse(point.timestamp) }))}
            margin={{ top: 10, right: 18, bottom: 0, left: 0 }}
          >
            <CartesianGrid stroke="var(--border-subtle)" strokeDasharray="2 4" vertical={false} />
            <XAxis
              dataKey="time"
              type="number"
              scale="time"
              domain={['dataMin', 'dataMax']}
              tickFormatter={range === '24h' ? formatOperationalTime : formatAnalyticsDay}
              tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
              stroke="var(--border-default)"
              tickLine={false}
              minTickGap={32}
            />
            <YAxis
              allowDecimals={false}
              width={34}
              tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
              stroke="var(--border-default)"
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              content={(props) => <RiskTimelineTooltip active={props.active} payload={props.payload} />}
              cursor={{ stroke: 'var(--border-default)' }}
            />
            {series.map((item) => (
              <Line
                key={item.key}
                type="linear"
                dataKey={item.key}
                name={item.label}
                stroke={`var(--risk-${item.key})`}
                strokeWidth={1.5}
                dot={false}
                activeDot={{ r: 3 }}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <details className="analytics-data">
        <summary>Таблица динамики · МСК</summary>
        <div className="table-scroll">
          <table className="data-table">
            <caption className="sr-only">Значения динамики рисков</caption>
            <thead>
              <tr>
                <th scope="col">Время МСК</th>
                {series.map((item) => (
                  <th scope="col" key={item.key}>
                    {item.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {points.map((point) => (
                <tr key={point.timestamp}>
                  <td>{formatDateTime(point.timestamp)}</td>
                  {series.map((item) => (
                    <td key={item.key}>{formatCount(point[item.key])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}
