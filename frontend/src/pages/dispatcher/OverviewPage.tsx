import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useV2Objects } from '../../api/v2/queries/hooks';
import { DataState, Field, HistoricalHeader, Metric, Note, count, query, sourceTime, useHistorical, type Page, type Row } from './shared';

type Day = Row & { activity_date: string; draft_count?: number; review_groups?: number; observed_situations?: number; smoke_situations?: number; gas_situations?: number };

export default function HistoricalOverviewPage() {
  const [from, setFrom] = useState('2026-06-01');
  const [to, setTo] = useState('2026-06-30');
  const [objectId, setObjectId] = useState('');
  const [sensorType, setSensorType] = useState('');
  const [reviewState, setReviewState] = useState('');
  const objects = useV2Objects({ limit: 200 });
  const types = useHistorical<Row[]>('/model-types');
  const overview = useHistorical<{ days: Day[] }>(query('/overview', { from, to, object_id: objectId, sensor_type: sensorType }));
  const groups = useHistorical<Page>(query('/groups', { from, to, object_id: objectId, review_state: reviewState, limit: 8 }));
  const days = overview.data?.days ?? [];
  const total = (field: keyof Day) => days.reduce((sum, day) => sum + (typeof day[field] === 'number' ? day[field] as number : 0), 0);
  const names = new Map(objects.data?.items.map((object) => [object.objectId, object.objectName]) ?? []);
  return <div className="dispatch-page">
    <HistoricalHeader title="Обзор диспетчера" description="Группы черновиков, наблюдаемые события и нагрузка по историческим данным." />
    <div className="dispatch-filters">
      <Field title="С"><input type="date" value={from} max={to} onChange={(event) => setFrom(event.target.value)} /></Field>
      <Field title="По"><input type="date" value={to} min={from} onChange={(event) => setTo(event.target.value)} /></Field>
      <Field title="Объект"><select value={objectId} onChange={(event) => setObjectId(event.target.value)}><option value="">Все объекты</option>{objects.data?.items.map((object) => <option key={object.objectId} value={object.objectId}>{object.objectName}</option>)}</select></Field>
      <Field title="Тип датчика"><select value={sensorType} onChange={(event) => setSensorType(event.target.value)}><option value="">Все типы</option>{types.data?.map((type) => <option key={String(type.sensor_type)} value={String(type.sensor_type)}>{String(type.sensor_type)}</option>)}</select></Field>
      <Field title="Разбор групп"><select value={reviewState} onChange={(event) => setReviewState(event.target.value)}><option value="">Все решения</option><option value="pending">Ожидают</option><option value="approved">Есть одобрение</option><option value="rejected">Есть отклонение</option></select></Field>
    </div>
    <DataState loading={overview.isPending} error={overview.error?.message} empty={days.length === 0} />
    {days.length > 0 && <>
      <div className="dispatch-metrics">
        {!sensorType && <Metric title="Группы за период" value={count(total('review_groups'))} to="/review/groups" />}
        <Metric title="Черновики" value={count(total('draft_count'))} to="/review/drafts" />
        <Metric title="Наблюдаемые ситуации" value={count(total('observed_situations'))} to="/situations" />
        <Metric title="Дым / газ" value={`${count(total('smoke_situations'))} / ${count(total('gas_situations'))}`} to="/fire-history" />
      </div>
      <div className="dispatch-grid">
        <section className="dispatch-panel"><h2>Нагрузка по дням</h2><p>Счётчики исторических карточек. Черновики и группы показаны отдельно.</p>
          <div className="dispatch-chart"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={days} margin={{ top: 8, right: 10, left: -15, bottom: 5 }}>
            <CartesianGrid stroke="var(--border-subtle)" vertical={false} /><XAxis dataKey="activity_date" tick={{ fontSize: 10 }} minTickGap={24} /><YAxis allowDecimals={false} tick={{ fontSize: 11 }} /><Tooltip />
            {!sensorType && <Bar dataKey="review_groups" name="Группы" fill="var(--accent)" opacity={0.75} />}<Line dataKey="draft_count" name="Черновики" stroke="var(--status-warning)" strokeWidth={2} dot={false} />
          </ComposedChart></ResponsiveContainer></div>
        </section>
        <section className="dispatch-panel"><h2>Наблюдаемые события</h2><p>Сигналы дыма и газа не означают подтверждённый пожар или утечку.</p>
          <div className="dispatch-chart"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={days} margin={{ top: 8, right: 10, left: -15, bottom: 5 }}>
            <CartesianGrid stroke="var(--border-subtle)" vertical={false} /><XAxis dataKey="activity_date" tick={{ fontSize: 10 }} minTickGap={24} /><YAxis allowDecimals={false} tick={{ fontSize: 11 }} /><Tooltip />
            <Bar dataKey="smoke_situations" name="Дымовые ситуации" fill="var(--status-warning)" /><Bar dataKey="gas_situations" name="Газовые ситуации" fill="var(--status-info)" />
          </ComposedChart></ResponsiveContainer></div>
        </section>
      </div>
      <section className="dispatch-panel"><div className="dispatch-panel-header"><h2>Группы в выбранном периоде</h2><Link to="/review/groups">Открыть всю очередь</Link></div>{sensorType && <p>Группы ниже охватывают все типы датчиков: связь группы с отдельным типом в сводке не размечена.</p>}
        <DataState loading={groups.isPending} error={groups.error?.message} empty={groups.data?.items.length === 0} />
        <div className="dispatch-table-scroll"><table className="dispatch-table"><thead><tr><th>Доступно в реконструкции</th><th>Объект</th><th>Черновиков</th><th>Прогноз / наблюдение</th><th></th></tr></thead><tbody>
          {groups.data?.items.map((group) => <tr key={String(group.group_id)}><td>{sourceTime(group.available_at)}</td><td>{names.get(Number(group.object_id)) ?? `Объект ${group.object_id}`}</td><td>{count(group.draft_count)}</td><td>{count(group.forecast_count)} / {count(group.observed_count)}</td><td><Link to={`/review/groups/${encodeURIComponent(String(group.group_id))}`}>Разобрать</Link></td></tr>)}
        </tbody></table></div>
      </section>
    </>}
    <Note>Дата и время источника показаны буквально. Фильтр типа меняет графики и счётчики; фильтр разбора – список групп. Для новых показаний ML-черновики пока не рассчитываются в этом сервисе.</Note>
  </div>;
}
