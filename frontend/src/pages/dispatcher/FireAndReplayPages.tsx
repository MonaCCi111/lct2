import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { v2ApiGet } from '../../api/v2/client/http';
import { DataState, Field, HistoricalHeader, Metric, Note, count, label, sourceTime, useHistorical, type Page, type Row } from './shared';

type SmokeYear = { yr: number; signal_records: number; channels: number; objects: number; with_other_status_same_time: number; with_recent_temperature: number; with_comparable_temperature: number };
type FireHistory = { source_status: string; real_fire_count: number | null; confirmed_fire_register_available: boolean; telemetry_candidate_count: number; smoke_signal_statistics_are_fires: boolean; smoke_signal_statistics: SmokeYear[]; source_ref: string; data_cutoff: string };

export function FireHistoryPage() {
  const fire = useHistorical<FireHistory>('/fire-history');
  const rows = fire.data?.smoke_signal_statistics ?? [];
  return <div className="dispatch-page"><HistoricalHeader title="История пожаров и дымовых сигналов" description="Подтверждённые пожары и сообщения датчиков имеют разный статус доказанности." />
    <DataState loading={fire.isPending} error={fire.error?.message} />
    {fire.data && <><section className="dispatch-panel"><h2>Подтверждённые пожары</h2><p className="dispatch-note dispatch-warning">Заказчик не предоставил реестр подтверждённых пожаров. Число реальных пожаров неизвестно; ноль здесь означал бы неподтверждённый вывод. Один телеметрический кандидат не считается пожаром.</p><dl className="dispatch-kv"><dt>Источник</dt><dd>{fire.data.source_status}</dd><dt>Число подтверждённых пожаров</dt><dd>Неизвестно</dd><dt>Телеметрические кандидаты</dt><dd>{count(fire.data.telemetry_candidate_count)} без подтверждения физического пожара</dd><dt>Происхождение</dt><dd>{fire.data.source_ref}</dd></dl></section>
      <div className="dispatch-metrics"><Metric title="Дымовые сообщения" value={count(rows.reduce((n, x) => n + x.signal_records, 0))} detail="Это не число пожаров" /><Metric title="Лет с записями" value={rows.length} /><Metric title="Кандидаты для экспертизы" value={count(fire.data.telemetry_candidate_count)} detail="Физический пожар не подтверждён" /><Metric title="Подтверждённые пожары" value="Нет источника" /></div>
      <div className="dispatch-grid"><section className="dispatch-panel"><h2>Дымовые сообщения по годам</h2><p>Количество исходных сообщений «Обнаружен дым».</p><div className="dispatch-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={rows}><CartesianGrid stroke="var(--border-subtle)" vertical={false} /><XAxis dataKey="yr" /><YAxis tick={{ fontSize: 11 }} /><Tooltip /><Bar dataKey="signal_records" name="Сообщения дыма" fill="var(--status-warning)" /></BarChart></ResponsiveContainer></div></section>
      <section className="dispatch-panel"><h2>Охват источника</h2><p>Сколько каналов и объектов передавали дымовые сообщения.</p><div className="dispatch-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={rows}><CartesianGrid stroke="var(--border-subtle)" vertical={false} /><XAxis dataKey="yr" /><YAxis tick={{ fontSize: 11 }} /><Tooltip /><Bar dataKey="channels" name="Каналы" fill="var(--status-info)" /><Bar dataKey="objects" name="Объекты" fill="var(--accent)" /></BarChart></ResponsiveContainer></div></section></div>
      <section className="dispatch-panel"><h2>Сопоставление с температурой и качеством статусов</h2><div className="dispatch-table-scroll"><table className="dispatch-table"><thead><tr><th>Год</th><th>Дымовых сообщений</th><th>Объектов</th><th>С другим статусом в то же время</th><th>С недавней температурой</th><th>С сопоставимой температурой</th></tr></thead><tbody>{rows.map((y) => <tr key={y.yr}><td>{y.yr}</td><td>{count(y.signal_records)}</td><td>{count(y.objects)}</td><td>{count(y.with_other_status_same_time)}</td><td>{count(y.with_recent_temperature)}</td><td>{count(y.with_comparable_temperature)}</td></tr>)}</tbody></table></div></section>
    </>}
  </div>;
}

type Scenario = { id: string; title: string; object_id: number; start: string; end: string; events_available: boolean };
type ReplayEvent = { seq: number; event_time: string; event_kind: string; object_id: number; channel_id: number | null; source_id: string; payload: string; availability_basis: string };
const eventLabels: Record<string, string> = {
  coverage_baseline: 'Состояние наблюдения', coverage_lost: 'Пауза записей', coverage_restored: 'Запись возобновилась',
  reading: 'Показание', observed_signal: 'Наблюдаемый сигнал', situation_ready: 'Ситуация доступна', draft_created: 'Черновик доступен',
};

async function loadScenarioEvents(id: string, signal?: AbortSignal): Promise<ReplayEvent[]> {
  const all: ReplayEvent[] = [];
  let after = 0;
  while (true) {
    const page = await v2ApiGet<Page<ReplayEvent>>(`/replays/${encodeURIComponent(id)}/events?after_seq=${after}&limit=200`, signal);
    all.push(...page.items);
    if (!page.next_cursor || page.items.length === 0) return all;
    after = page.items.at(-1)!.seq;
  }
}

function parsedPayload(value: string): Row {
  try {
    const parsed: unknown = JSON.parse(value);
    return parsed !== null && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed as Row : { value: parsed };
  } catch { return { raw: value }; }
}

export function ReplayPage() {
  const scenarios = useHistorical<Scenario[]>('/replays');
  const [scenarioId, setScenarioId] = useState('observed_draft');
  const [position, setPosition] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(10);
  const [reason, setReason] = useState('');
  const [simulated, setSimulated] = useState<Record<string, string>>({});
  const events = useQuery({ queryKey: ['replay-events', scenarioId], queryFn: ({ signal }) => loadScenarioEvents(scenarioId, signal), staleTime: Infinity });
  const rows = events.data ?? [];
  const scenario = scenarios.data?.find((s) => s.id === scenarioId);
  const current = rows[position - 1];
  const visible = useMemo(() => rows.slice(0, position), [rows, position]);
  const recent = visible.slice(-24).reverse();
  const eventCounts = useMemo(() => visible.reduce<Record<string, number>>((acc, e) => { acc[e.event_kind] = (acc[e.event_kind] ?? 0) + 1; return acc; }, {}), [visible]);

  useEffect(() => {
    if (!playing || !rows.length) return;
    const timer = window.setInterval(() => setPosition((n) => Math.min(rows.length, n + speed)), 250);
    return () => window.clearInterval(timer);
  }, [playing, rows.length, speed]);
  useEffect(() => { if (position >= rows.length && rows.length) setPlaying(false); }, [position, rows.length]);

  const seek = (next: number) => { setPlaying(false); setPosition(next); setSimulated({}); setReason(''); };
  const nextSignal = rows.findIndex((event, index) => index >= position && !['reading', 'coverage_baseline'].includes(event.event_kind));
  const changeScenario = (id: string) => { setScenarioId(id); seek(0); };
  const shownDraft = [...visible].reverse().find((e) => e.event_kind === 'draft_created');
  const shownDraftId = shownDraft ? String(parsedPayload(shownDraft.payload).draft_id ?? shownDraft.source_id) : null;
  const decide = (choice: string) => {
    if (!shownDraftId || !reason.trim()) return;
    setSimulated((old) => ({ ...old, [shownDraftId]: `${choice}: ${reason.trim()}` }));
    setReason('');
  };

  return <div className="dispatch-page"><HistoricalHeader title="Исторический таймлайн" description="Ползунок показывает только события, доступные к выбранному шагу. Это реконструкция, не живой поток." />
    <div className="dispatch-filters"><Field title="Сценарий"><select value={scenarioId} onChange={(e) => changeScenario(e.target.value)}>{scenarios.data?.map((s) => <option key={s.id} value={s.id}>{s.title}</option>)}</select></Field><span>Объект {scenario?.object_id ?? '…'} · {scenario?.start ?? '…'} – {scenario?.end ?? '…'}</span></div>
    <DataState loading={scenarios.isPending || events.isPending} error={scenarios.error?.message ?? events.error?.message} empty={events.data?.length === 0} />
    {rows.length > 0 && <><section className="dispatch-panel dispatch-replay-controls"><div className="dispatch-replay-clock">{current ? sourceTime(current.event_time) : sourceTime(scenario?.start)} <small>· шаг {count(position)} из {count(rows.length)}</small></div>
      <input className="dispatch-slider" type="range" min={0} max={rows.length} value={position} aria-label="Ползунок исторического таймлайна" onChange={(e) => seek(Number(e.target.value))} />
      <div className="dispatch-replay-toolbar"><button className="dispatch-button dispatch-button-primary" onClick={() => setPlaying((x) => !x)}>{playing ? 'Пауза' : 'Воспроизвести'}</button><button className="dispatch-button" onClick={() => seek(Math.min(rows.length, position + 1))}>Следующее событие</button><button className="dispatch-button" disabled={nextSignal < 0} onClick={() => seek(nextSignal + 1)}>Следующий значимый сигнал</button><button className="dispatch-button" onClick={() => seek(0)}>В начало</button><Field title="Скорость"><select value={speed} onChange={(e) => setSpeed(Number(e.target.value))}><option value={1}>1 событие / шаг</option><option value={10}>10 событий / шаг</option><option value={50}>50 событий / шаг</option><option value={200}>200 событий / шаг</option></select></Field></div>
      <p>Время фактической доставки и часовой пояс исходного журнала неизвестны. Перемотка очищает имитационные решения.</p>
    </section>
      <div className="dispatch-metrics"><Metric title="Показания" value={count(eventCounts.reading ?? 0)} /><Metric title="Сигналы" value={count(eventCounts.observed_signal ?? 0)} /><Metric title="Ситуации" value={count(eventCounts.situation_ready ?? 0)} /><Metric title="Черновики" value={count(eventCounts.draft_created ?? 0)} /></div>
      <section className="dispatch-panel"><h2>События до ползунка</h2><p>Последние 24 события. Более поздние записи скрыты до перемотки или воспроизведения.</p><ol className="dispatch-event-list">{recent.map((e) => <li className="dispatch-event" key={e.seq}><span>#{e.seq} · {sourceTime(e.event_time)}</span><strong>{eventLabels[e.event_kind] ?? e.event_kind}</strong><pre>{e.channel_id !== null ? `Канал ${e.channel_id} · ` : ''}{label(parsedPayload(e.payload).sensor_value ?? parsedPayload(e.payload).observed_value ?? parsedPayload(e.payload).value ?? e.source_id)}</pre></li>)}</ol>{!recent.length && <Note>Переведите ползунок или запустите воспроизведение.</Note>}</section>
      {shownDraftId && <section className="dispatch-panel"><h2>Имитация решения диспетчера</h2><p>Черновик {shownDraftId}. Эти действия не записываются в журнал реальных решений.</p><div className="dispatch-replay-toolbar"><Field title="Причина решения"><input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Напишите основание" /></Field><button className="dispatch-button" disabled={!reason.trim()} onClick={() => decide('Одобрено')}>Одобрить в сценарии</button><button className="dispatch-button" disabled={!reason.trim()} onClick={() => decide('Отклонено')}>Отклонить в сценарии</button></div>{simulated[shownDraftId] && <Note>Имитационное решение: {simulated[shownDraftId]}</Note>}</section>}
    </>}
    <Note>Сейчас доступны восемь проверенных исторических сценариев. Для произвольного объекта и периода нужен архив исходных событий; в переносимом пакете его нет.</Note>
  </div>;
}
