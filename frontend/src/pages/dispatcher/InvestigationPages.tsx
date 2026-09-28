import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useV2Objects } from '../../api/v2/queries/hooks';
import { DataState, Field, HistoricalHeader, Metric, Note, Pager, count, label, query, sourceTime, useHistorical, type Page, type Row } from './shared';
import { CasePointsChart } from './CasePointsChart';

const stateName: Record<string, string> = {
  active: 'Прогноз в рабочей очереди', research: 'Исследовательский прогноз', not_released: 'Прогноз не выпущен',
  no_recent_events: 'Нет недавних записей', recent_observation: 'Есть недавние записи',
};
const value = (row: Row, key: string) => label(row[key], '—');
const objName = (names: Map<number, string>, id: unknown) => names.get(Number(id)) ?? `Объект ${id}`;
type CoverageSummary = { channel_count: number; states: Record<string, number>; forecast_capabilities: Record<string, number>; monthly: { month: string; channels: number; recent: number; no_recent: number; uncertain: number }[]; data_cutoff: string };

export function ChannelsPage() {
  const [objectId, setObjectId] = useState('');
  const [sensorType, setSensorType] = useState('');
  const [capability, setCapability] = useState('');
  const [cursorStack, setCursorStack] = useState<string[]>(['']);
  const objects = useV2Objects({ limit: 200 });
  const types = useHistorical<Row[]>('/model-types');
  const coverage = useHistorical<CoverageSummary>(query('/coverage/summary', { object_id: objectId, sensor_type: sensorType }));
  const channels = useHistorical<Page>(query('/channels', { object_id: objectId, sensor_type: sensorType, forecast_capability: capability, limit: 50, cursor: cursorStack.at(-1) }));
  const names = new Map(objects.data?.items.map((object) => [object.objectId, object.objectName]) ?? []);
  const reset = () => setCursorStack(['']);
  return <div className="dispatch-page">
    <HistoricalHeader title="Каналы и охват" description="Каждый канал остаётся видимым, даже если прогноз для него не выпущен или записи устарели." />
    <div className="dispatch-filters">
      <Field title="Объект"><select value={objectId} onChange={(e) => { setObjectId(e.target.value); reset(); }}><option value="">Все объекты</option>{objects.data?.items.map((o) => <option key={o.objectId} value={o.objectId}>{o.objectName}</option>)}</select></Field>
      <Field title="Тип датчика"><select value={sensorType} onChange={(e) => { setSensorType(e.target.value); reset(); }}><option value="">Все 19 типов</option>{types.data?.map((t) => <option key={String(t.sensor_type)} value={String(t.sensor_type)}>{String(t.sensor_type)}</option>)}</select></Field>
      <Field title="Прогноз"><select value={capability} onChange={(e) => { setCapability(e.target.value); reset(); }}><option value="">Любое состояние</option><option value="active">Рабочий</option><option value="research">Исследовательский</option><option value="not_released">Не выпущен</option></select></Field>
    </div>
    {coverage.data && <><div className="dispatch-metrics"><Metric title="Каналов в срезе" value={count(coverage.data.channel_count)} /><Metric title="Недавние записи" value={count(coverage.data.states.recent_events)} /><Metric title="Нет недавних записей" value={count(coverage.data.states.no_recent_events)} /><Metric title="Конфликт записей" value={count(coverage.data.states.recent_conflicting_events)} /></div>
      <div className="dispatch-grid"><section className="dispatch-panel"><h2>Охват записями по месяцам</h2><p>Снимки показывают наличие записей за 72 часа к концу месяца. Число каналов может меняться.</p><div className="dispatch-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={coverage.data.monthly}><CartesianGrid stroke="var(--border-subtle)" vertical={false} /><XAxis dataKey="month" tick={{ fontSize: 10 }} minTickGap={20} /><YAxis allowDecimals={false} /><Tooltip /><Line dataKey="recent" name="Недавние записи" stroke="var(--status-info)" dot={false} connectNulls={false} /><Line dataKey="no_recent" name="Без недавних записей" stroke="var(--status-warning)" dot={false} connectNulls={false} /><Line dataKey="uncertain" name="Неопределённо" stroke="var(--accent)" dot={false} connectNulls={false} /></LineChart></ResponsiveContainer></div></section>
      <section className="dispatch-panel"><h2>Участие в прогнозе</h2><p>Решение о прогнозе зависит от типа и доступности входных данных, включая ранее не встречавшиеся каналы.</p><div className="dispatch-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={Object.entries(coverage.data.forecast_capabilities).map(([status, channels]) => ({ status: stateName[status] ?? status, channels }))} layout="vertical" margin={{ left: 25 }}><CartesianGrid stroke="var(--border-subtle)" horizontal={false} /><XAxis type="number" allowDecimals={false} /><YAxis type="category" dataKey="status" width={145} tick={{ fontSize: 10 }} /><Tooltip /><Bar dataKey="channels" name="Каналы" fill="var(--accent)" /></BarChart></ResponsiveContainer></div></section></div></>}
    <DataState loading={coverage.isPending} error={coverage.error?.message} />
    <section className="dispatch-panel"><div className="dispatch-panel-header"><h2>Реестр каналов</h2><span>{channels.data ? `${channels.data.items.length} на странице` : ''}</span></div>
      <DataState loading={channels.isPending} error={channels.error?.message} empty={channels.data?.items.length === 0} />
      <div className="dispatch-table-scroll"><table className="dispatch-table"><thead><tr><th>Канал</th><th>Объект</th><th>Тип</th><th>Прогноз</th><th>Наблюдение</th><th>Последняя запись</th><th>ИТС</th></tr></thead><tbody>
        {channels.data?.items.map((ch) => <tr key={String(ch.channel_id)}><td><Link to={`/channels/${ch.channel_id}`}>{label(ch.channel_name, `Канал ${ch.channel_id}`)}</Link><small style={{ display: 'block', fontWeight: 400 }}>ID {String(ch.channel_id)}</small></td><td>{objName(names, ch.object_id)}</td><td>{value(ch, 'sensor_type')}</td><td>{stateName[String(ch.forecast_capability)] ?? value(ch, 'forecast_capability')}</td><td>{stateName[String(ch.coverage_observation_state)] ?? value(ch, 'coverage_observation_state')}</td><td>{sourceTime(ch.last_event_time)}</td><td>{ch.its_value === null ? 'Не рассчитан' : String(ch.its_value)}</td></tr>)}
      </tbody></table></div>
      <Pager previous={cursorStack.length > 1 ? () => setCursorStack((s) => s.slice(0, -1)) : undefined} next={channels.data?.next_cursor ? () => setCursorStack((s) => [...s, channels.data!.next_cursor!]) : undefined} />
    </section>
    <section className="dispatch-panel"><h2>Решение по каждому типу</h2><p>Статус относится к типу. Пригодность отдельного канала зависит от его входной истории.</p>
      <DataState loading={types.isPending} error={types.error?.message} />
      <div className="dispatch-table-scroll"><table className="dispatch-table"><thead><tr><th>Тип</th><th>Статус прогноза</th><th>Модель</th><th>Основание решения</th></tr></thead><tbody>{types.data?.map((t) => <tr key={String(t.sensor_type)}><td>{value(t, 'sensor_type')}</td><td>{stateName[String(t.forecast_capability)] ?? value(t, 'forecast_capability')}</td><td>{value(t, 'forecast_model_version')}</td><td>{value(t, 'forecast_reason_text')}</td></tr>)}</tbody></table></div>
    </section>
  </div>;
}

export function ChannelDetailPage() {
  const { channelId = '' } = useParams();
  const channel = useHistorical<Row>(`/channels/${encodeURIComponent(channelId)}`);
  const history = Array.isArray(channel.data?.history) ? channel.data.history as Row[] : [];
  return <div className="dispatch-page">
    <Link className="dispatch-link" to="/channels">← Все каналы</Link>
    <HistoricalHeader title={label(channel.data?.channel_name, `Канал ${channelId}`)} description={`Канал ${channelId}. История доступности и причина участия в моделях.`} />
    <DataState loading={channel.isPending} error={channel.error?.message} />
    {channel.data && <>
      <div className="dispatch-grid"><section className="dispatch-panel"><h2>Состояние на срезе</h2><dl className="dispatch-kv">
        <dt>Тип</dt><dd>{value(channel.data, 'sensor_type')}</dd><dt>Объект</dt><dd>{value(channel.data, 'object_id')}</dd>
        <dt>Наблюдение</dt><dd>{value(channel.data, 'detailed_observation_state')}</dd><dt>Последняя запись</dt><dd>{sourceTime(channel.data.last_event_time)}: {value(channel.data, 'last_recorded_value')}</dd>
        <dt>Прогноз</dt><dd>{stateName[String(channel.data.forecast_capability)] ?? value(channel.data, 'forecast_capability')}</dd><dt>Причина</dt><dd>{value(channel.data, 'forecast_reason_text')}</dd>
        <dt>Справочник состояний</dt><dd>{value(channel.data, 'dictionary_state')}</dd><dt>ИТС</dt><dd>{channel.data.its_value === null ? `Не рассчитан: ${value(channel.data, 'its_reason')}` : String(channel.data.its_value)}</dd>
        <dt>Исходная запись</dt><dd>{value(channel.data, 'last_source_ref')}</dd>
      </dl></section>
      <section className="dispatch-panel"><h2>История наблюдения</h2><p>Месячные снимки. Разрывы между снимками не заполняются выдуманными измерениями.</p>
        {history.length > 0 ? <div className="dispatch-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={history}><CartesianGrid stroke="var(--border-subtle)" vertical={false} /><XAxis dataKey="snapshot_date" tick={{ fontSize: 10 }} minTickGap={26} /><YAxis allowDecimals={false} tick={{ fontSize: 11 }} /><Tooltip /><Line dataKey="event_count_72h" name="Записей за 72 часа" stroke="var(--accent)" dot={false} connectNulls={false} /></LineChart></ResponsiveContainer></div> : <Note>Исторических снимков нет.</Note>}
      </section></div>
      <section className="dispatch-panel"><h2>Последние снимки</h2><div className="dispatch-table-scroll"><table className="dispatch-table"><thead><tr><th>Дата снимка</th><th>Состояние наблюдения</th><th>Записей за 72 часа</th><th>Последнее значение</th><th>Источник</th></tr></thead><tbody>{history.slice(-12).reverse().map((h) => <tr key={String(h.snapshot_date)}><td>{value(h, 'snapshot_date')}</td><td>{value(h, 'observation_state')}</td><td>{count(h.event_count_72h)}</td><td>{value(h, 'last_value')}</td><td>{value(h, 'last_source_ref')}</td></tr>)}</tbody></table></div></section>
    </>}
  </div>;
}

export function SituationsPage() {
  const [objectId, setObjectId] = useState('');
  const [from, setFrom] = useState('2026-06-01');
  const [to, setTo] = useState('2026-06-30');
  const [cursors, setCursors] = useState<string[]>(['']);
  const objects = useV2Objects({ limit: 200 });
  const situations = useHistorical<Page>(query('/situations', { object_id: objectId, from, to, limit: 50, cursor: cursors.at(-1) }));
  const names = new Map(objects.data?.items.map((o) => [o.objectId, o.objectName]) ?? []);
  return <div className="dispatch-page"><HistoricalHeader title="Наблюдаемые ситуации" description="Показания и статусы источника. Ситуация не подтверждает физическую аварию." />
    <div className="dispatch-filters"><Field title="С"><input type="date" value={from} max={to} onChange={(e) => { setFrom(e.target.value); setCursors(['']); }} /></Field><Field title="По"><input type="date" value={to} min={from} onChange={(e) => { setTo(e.target.value); setCursors(['']); }} /></Field><Field title="Объект"><select value={objectId} onChange={(e) => { setObjectId(e.target.value); setCursors(['']); }}><option value="">Все объекты</option>{objects.data?.items.map((o) => <option key={o.objectId} value={o.objectId}>{o.objectName}</option>)}</select></Field></div>
    <section className="dispatch-panel"><DataState loading={situations.isPending} error={situations.error?.message} empty={situations.data?.items.length === 0} /><div className="dispatch-table-scroll"><table className="dispatch-table"><thead><tr><th>Сигнал</th><th>Объект</th><th>Тип</th><th>Каналов</th><th>Доступно</th><th>Роль в очереди</th></tr></thead><tbody>{situations.data?.items.map((s) => <tr key={String(s.situation_id)}><td><Link to={`/situations/${encodeURIComponent(String(s.situation_id))}`}>{value(s, 'situation_kind')}</Link></td><td>{objName(names, s.object_id)}</td><td>{value(s, 'sensor_type')}</td><td>{count(s.affected_channels)}</td><td>{sourceTime(s.available_at)}</td><td>{s.draft_id ? <Link to={`/review/${encodeURIComponent(String(s.draft_id))}`}>Черновик</Link> : 'Информация для проверки'}</td></tr>)}</tbody></table></div><Pager previous={cursors.length > 1 ? () => setCursors((s) => s.slice(0, -1)) : undefined} next={situations.data?.next_cursor ? () => setCursors((s) => [...s, situations.data!.next_cursor!]) : undefined} /></section>
  </div>;
}

export function SituationDetailPage() {
  const { situationId = '' } = useParams();
  const encoded = encodeURIComponent(situationId);
  const [evidenceCursors, setEvidenceCursors] = useState<string[]>(['']);
  const situation = useHistorical<Row>(`/situations/${encoded}`);
  const evidence = useHistorical<Page>(query(`/situations/${encoded}/evidence`, { limit: 200, cursor: evidenceCursors.at(-1) }));
  return <div className="dispatch-page"><Link className="dispatch-link" to="/situations">← Все ситуации</Link><HistoricalHeader title={label(situation.data?.situation_kind, 'Ситуация')} description={`ID ${situationId}. Совместные свидетельства и ограничения вывода.`} />
    <DataState loading={situation.isPending} error={situation.error?.message} />
    {situation.data && <div className="dispatch-grid"><section className="dispatch-panel"><h2>Контекст</h2><dl className="dispatch-kv"><dt>Объект</dt><dd>{value(situation.data, 'object_name')}</dd><dt>Первый сигнал</dt><dd>{sourceTime(situation.data.source_first_seen)}</dd><dt>Доступно</dt><dd>{sourceTime(situation.data.available_at)}</dd><dt>Затронуто каналов</dt><dd>{count(situation.data.affected_channels)}</dd><dt>Ограничения</dt><dd>{value(situation.data, 'limitations')}</dd><dt>Физический инцидент</dt><dd>Не подтверждён данными</dd><dt>Исходный ресурс</dt><dd>{value(situation.data, 'source_ref')}</dd></dl></section>
      <CasePointsChart caseId={situationId} kind="situation_id" threshold={typeof situation.data.stated_threshold === 'number' ? situation.data.stated_threshold : null} /></div>}
    <section className="dispatch-panel"><h2>Исходные свидетельства</h2><DataState loading={evidence.isPending} error={evidence.error?.message} empty={evidence.data?.items.length === 0} /><div className="dispatch-table-scroll"><table className="dispatch-table"><thead><tr><th>Время источника</th><th>Канал</th><th>Значение / статус</th><th>Число</th><th>Тревога</th><th>Источник</th></tr></thead><tbody>{evidence.data?.items.map((e, i) => <tr key={`${e.event_id}-${i}`}><td>{sourceTime(e.source_time ?? e.event_time)}</td><td>{value(e, 'channel_id')}</td><td>{label(e.observed_value ?? e.sensor_value, '—')}</td><td>{label(e.numeric_value, '—')} {label(e.numeric_unit, '')}</td><td>{e.source_alarm === true ? 'Да' : e.source_alarm === false ? 'Нет' : 'Неизвестно'}</td><td>{value(e, 'source_ref')}</td></tr>)}</tbody></table></div><Pager previous={evidenceCursors.length > 1 ? () => setEvidenceCursors((s) => s.slice(0, -1)) : undefined} next={evidence.data?.next_cursor ? () => setEvidenceCursors((s) => [...s, evidence.data!.next_cursor!]) : undefined} /></section>
  </div>;
}
