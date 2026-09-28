import { CartesianGrid, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts';
import { DataState, Note, label, query, useHistorical, type Row } from './shared';

type CasePoint = Row & { event_time: string; channel_id: number | null; numeric_value: number | null; text_value: string | null; numeric_unit: string | null; gap_hours: number | null };
type CaseChart = { points: CasePoint[]; source: string; limitations: string; view_at: string };

export function CasePointsChart({ caseId, kind, threshold }: { caseId: string; kind: 'draft_id' | 'situation_id'; threshold?: number | null }) {
  const chart = useHistorical<CaseChart>(query('/charts/cases', { [kind]: caseId }));
  const points = chart.data?.points ?? [];
  const numeric = points.filter((p) => typeof p.numeric_value === 'number');
  const times = [...new Set(numeric.map((p) => p.event_time))].sort();
  const channelIds = [...new Set(numeric.map((p) => p.channel_id))];
  const colors = ['#729fc5', '#d6a15e', '#8bb49a', '#bd8fba', '#d27c79'];
  return <section className="dispatch-panel">
    <h2>График исходных измерений</h2>
    <p>Каждая точка соответствует отдельному свидетельству. Между точками и через пропуски значения не интерполируются.</p>
    <DataState loading={chart.isPending} error={chart.error?.message} />
    {numeric.length > 0 ? <>
      <div className="dispatch-chart dispatch-chart-lg"><ResponsiveContainer width="100%" height="100%"><ScatterChart margin={{ top: 8, right: 18, left: 0, bottom: 10 }}>
        <CartesianGrid stroke="var(--border-subtle)" vertical={false} />
        <XAxis type="number" dataKey="time_index" name="Время источника" domain={[0, Math.max(1, times.length - 1)]} tickFormatter={(i) => times[Math.round(i)]?.replace('T', ' ').slice(5, 16) ?? ''} tick={{ fontSize: 10 }} />
        <YAxis type="number" dataKey="numeric_value" tick={{ fontSize: 11 }} />
        <Tooltip cursor={{ strokeDasharray: '3 3' }} content={({ active, payload }) => active && payload?.[0]?.payload ? <div className="dispatch-chart-tooltip"><strong>{label(payload[0].payload.event_time)}</strong><span>Канал {label(payload[0].payload.channel_id)}: {label(payload[0].payload.numeric_value)} {label(payload[0].payload.numeric_unit, '')}</span></div> : null} />
        {channelIds.map((id, i) => <Scatter key={String(id)} name={`Канал ${id}`} data={numeric.filter((p) => p.channel_id === id).map((p) => ({ ...p, time_index: times.indexOf(p.event_time) }))} fill={colors[i % colors.length]} />)}
        {typeof threshold === 'number' && <ReferenceLine y={threshold} stroke="var(--status-warning)" strokeDasharray="5 4" label="Заявленный порог" />}
      </ScatterChart></ResponsiveContainer></div>
      <div className="dispatch-legend">{channelIds.map((id, i) => <span key={String(id)} style={{ '--legend-color': colors[i % colors.length] } as React.CSSProperties}>Канал {id}</span>)}</div>
    </> : <Note>Числовых свидетельств для этого случая нет. Текстовые состояния приведены в таблице ниже.</Note>}
    {chart.data && <small>График построен по сохранённым свидетельствам. Источник: {chart.data.source}. Доступно на {chart.data.view_at}.</small>}
  </section>;
}
