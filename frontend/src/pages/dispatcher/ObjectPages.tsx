import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useV2Object, useV2Objects } from '../../api/v2/queries/hooks';
import { DataState, Field, HistoricalHeader, Metric, Note, count, label, query, sourceTime, useHistorical, type Page, type Row } from './shared';

export function ObjectsPage() {
  const [search, setSearch] = useState('');
  const objects = useV2Objects({ limit: 200 });
  const items = objects.data?.items.filter((o) => o.objectName.toLowerCase().includes(search.toLowerCase())) ?? [];
  return <div className="dispatch-page"><HistoricalHeader title="Объекты" description="Каталог объектов из исторического пакета. Число каналов включает вложенные объекты." />
    <div className="dispatch-filters"><Field title="Поиск объекта"><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Название или часть названия" /></Field><span>{count(items.length)} объектов в выборке</span></div>
    <section className="dispatch-panel"><DataState loading={objects.isPending} error={objects.error?.message} empty={items.length === 0} /><div className="dispatch-table-scroll"><table className="dispatch-table"><thead><tr><th>Объект</th><th>Вид</th><th>Каналов в поддереве</th><th>ID</th><th></th></tr></thead><tbody>{items.map((o) => <tr key={o.objectId}><td><Link to={`/objects/${o.objectId}`}>{o.objectName}</Link></td><td>{o.kind}</td><td>{count(o.channelCount)}</td><td>{o.objectId}</td><td><Link to={`/objects/${o.objectId}`}>Открыть</Link></td></tr>)}</tbody></table></div></section>
  </div>;
}

type Day = Row & { activity_date: string; draft_count?: number; review_groups?: number; observed_situations?: number; smoke_situations?: number; gas_situations?: number };
export function ObjectDetailPage() {
  const { objectId = '' } = useParams();
  const id = Number(objectId);
  const [from, setFrom] = useState('2026-01-01');
  const [to, setTo] = useState('2026-06-30');
  const object = useV2Object(id);
  const overview = useHistorical<{ days: Day[] }>(query('/overview', { from, to, object_id: id }));
  const situations = useHistorical<Page>(query('/situations', { from, to, object_id: id, limit: 12 }));
  const groups = useHistorical<Page>(query('/groups', { from, to, object_id: id, limit: 12 }));
  const channels = useHistorical<Page>(query('/channels', { object_id: id, limit: 12 }));
  const days = overview.data?.days ?? [];
  const total = (key: keyof Day) => days.reduce((n, d) => n + (typeof d[key] === 'number' ? d[key] as number : 0), 0);
  return <div className="dispatch-page"><Link className="dispatch-link" to="/objects">← Все объекты</Link><HistoricalHeader title={object.data?.objectName ?? `Объект ${objectId}`} description={`Историческая картина объекта ${objectId}: каналы, ситуации и группы.`} />
    <DataState loading={object.isPending} error={object.error?.message} />
    <div className="dispatch-filters"><Field title="С"><input type="date" value={from} max={to} onChange={(e) => setFrom(e.target.value)} /></Field><Field title="По"><input type="date" value={to} min={from} onChange={(e) => setTo(e.target.value)} /></Field></div>
    <div className="dispatch-metrics"><Metric title="Каналы в каталоге" value={count(object.data?.channelCount)} to="/channels" /><Metric title="Группы" value={count(total('review_groups'))} to="/review/groups" /><Metric title="Черновики" value={count(total('draft_count'))} to="/review/drafts" /><Metric title="Ситуации" value={count(total('observed_situations'))} to="/situations" /></div>
    <div className="dispatch-grid"><section className="dispatch-panel"><h2>Изменения по дням</h2><DataState loading={overview.isPending} error={overview.error?.message} empty={days.length === 0} />{days.length > 0 && <div className="dispatch-chart"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={days}><CartesianGrid stroke="var(--border-subtle)" vertical={false} /><XAxis dataKey="activity_date" tick={{ fontSize: 10 }} minTickGap={28} /><YAxis allowDecimals={false} /><Tooltip /><Bar dataKey="observed_situations" name="Наблюдаемые ситуации" fill="var(--status-info)" /><Line dataKey="draft_count" name="Черновики" stroke="var(--status-warning)" strokeWidth={2} dot={false} /></ComposedChart></ResponsiveContainer></div>}</section>
      <section className="dispatch-panel"><h2>Каналы объекта</h2><DataState loading={channels.isPending} error={channels.error?.message} empty={channels.data?.items.length === 0} /><div className="dispatch-table-scroll"><table className="dispatch-table"><thead><tr><th>Канал</th><th>Тип</th><th>Последняя запись</th></tr></thead><tbody>{channels.data?.items.map((c) => <tr key={String(c.channel_id)}><td><Link to={`/channels/${c.channel_id}`}>{label(c.channel_name, String(c.channel_id))}</Link></td><td>{label(c.sensor_type)}</td><td>{sourceTime(c.last_event_time)}</td></tr>)}</tbody></table></div>{channels.data?.next_cursor && <Link className="dispatch-link" to="/channels">Все каналы в реестре</Link>}</section></div>
    <div className="dispatch-grid"><section className="dispatch-panel"><h2>Ситуации</h2><DataState loading={situations.isPending} error={situations.error?.message} empty={situations.data?.items.length === 0} /><div className="dispatch-table-scroll"><table className="dispatch-table"><thead><tr><th>Время</th><th>Ситуация</th><th>Каналов</th></tr></thead><tbody>{situations.data?.items.map((s) => <tr key={String(s.situation_id)}><td>{sourceTime(s.source_first_seen)}</td><td><Link to={`/situations/${encodeURIComponent(String(s.situation_id))}`}>{label(s.situation_kind)}</Link></td><td>{count(s.affected_channels)}</td></tr>)}</tbody></table></div></section>
      <section className="dispatch-panel"><h2>Группы черновиков</h2><DataState loading={groups.isPending} error={groups.error?.message} empty={groups.data?.items.length === 0} /><div className="dispatch-table-scroll"><table className="dispatch-table"><thead><tr><th>Доступно</th><th>Черновиков</th><th></th></tr></thead><tbody>{groups.data?.items.map((g) => <tr key={String(g.group_id)}><td>{sourceTime(g.available_at)}</td><td>{count(g.draft_count)}</td><td><Link to={`/review/groups/${encodeURIComponent(String(g.group_id))}`}>Разобрать</Link></td></tr>)}</tbody></table></div></section></div>
    <Note>Числовой ИТС по объекту не рассчитывается: нет подтверждённого журнала физического состояния и ремонтов. Отсутствие недавней записи не означает исправность или отказ.</Note>
  </div>;
}
