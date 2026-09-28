import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { v2ApiGet } from '../../api/v2/client/http';
import { useV2Meta } from '../../api/v2/queries/hooks';
import './workspace.css';

export type Row = Record<string, unknown>;
export type Page<T = Row> = { items: T[]; next_cursor: string | null };

export function useHistorical<T>(path: string) {
  return useQuery({
    queryKey: ['historical-v2', path],
    queryFn: ({ signal }) => v2ApiGet<T>(path, signal),
  });
}

export function query(path: string, values: Record<string, string | number | undefined | null>) {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value));
  });
  const suffix = params.toString();
  return suffix ? `${path}?${suffix}` : path;
}

export function label(value: unknown, missing = 'Не указано') {
  return value === null || value === undefined || value === '' ? missing : String(value);
}

export function count(value: unknown) {
  return typeof value === 'number' ? new Intl.NumberFormat('ru-RU').format(value) : label(value, '—');
}

export function sourceTime(value: unknown) {
  return label(value, 'Нет записи');
}

export function HistoricalHeader({ title, description }: { title: string; description: string }) {
  const meta = useV2Meta();
  return (
    <header className="dispatch-heading">
      <div>
        <p className="dispatch-eyebrow">Историческая реконструкция</p>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div className="dispatch-cutoff" role="status">
        <strong>Срез {meta.data?.dataCutoff ?? 'загружается'}</strong>
        <span>Время источника без подтверждённой зоны. Живой поток не подключён.</span>
      </div>
    </header>
  );
}

export function DataState({
  loading,
  error,
  empty,
}: {
  loading: boolean;
  error?: string;
  empty?: boolean;
}) {
  if (loading) return <p className="dispatch-state" role="status">Загрузка исторических данных…</p>;
  if (error) return <p className="dispatch-state dispatch-error" role="alert">{error}</p>;
  if (empty) return <p className="dispatch-state">Для выбранного периода записей нет.</p>;
  return null;
}

export function Metric({ title, value, detail, to }: { title: string; value: string | number; detail?: string; to?: string }) {
  const content = <><span>{title}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</>;
  return to ? <Link className="dispatch-metric" to={to}>{content}</Link> : <div className="dispatch-metric">{content}</div>;
}

export function Pager({ previous, next }: { previous?: () => void; next?: () => void }) {
  return <div className="dispatch-pager">
    <button disabled={!previous} onClick={previous}>Назад</button>
    <button disabled={!next} onClick={next}>Следующие записи</button>
  </div>;
}

export function Field({ title, children }: { title: string; children: React.ReactNode }) {
  return <label className="dispatch-field"><span>{title}</span>{children}</label>;
}

export function Note({ children }: { children: React.ReactNode }) {
  return <p className="dispatch-note">{children}</p>;
}
