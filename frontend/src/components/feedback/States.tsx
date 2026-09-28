import { AlertCircle, CircleSlash, Inbox, Clock3 } from 'lucide-react';
import type { ReactNode } from 'react';
import { Button } from '../ui/Button';
export function Skeleton({ className = '' }: { className?: string }) {
  return <span aria-hidden="true" className={`skeleton ${className}`} />;
}
export function LoadingState() {
  return (
    <div role="status" aria-label="Загрузка" className="loading-state">
      <Skeleton />
      <Skeleton />
      <Skeleton />
      <span className="sr-only">Загрузка данных…</span>
    </div>
  );
}
export function EmptyState({
  title = 'Данных пока нет',
  description,
  action,
}: {
  title?: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <Inbox size={24} strokeWidth={1.5} aria-hidden="true" />
      <h3>{title}</h3>
      {description && <p>{description}</p>}
      {action}
    </div>
  );
}
export function ErrorState({
  message = 'Не удалось загрузить данные.',
  onRetry,
}: {
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="error-state" role="alert">
      <AlertCircle size={20} aria-hidden="true" />
      <div>
        <h3>Ошибка загрузки</h3>
        <p>{message}</p>
      </div>
      {onRetry && <Button onClick={onRetry}>Повторить</Button>}
    </div>
  );
}
export function StaleState({
  onRefresh,
  refreshing = false,
}: {
  onRefresh: () => void;
  refreshing?: boolean;
}) {
  return (
    <div className="stale-state" role="status">
      <Clock3 size={15} aria-hidden="true" />
      <span>Показаны сохранённые данные. Требуется обновление.</span>
      <Button variant="ghost" onClick={onRefresh} disabled={refreshing}>
        {refreshing ? 'Обновление…' : 'Обновить'}
      </Button>
    </div>
  );
}
export function UnsupportedMlState() {
  return (
    <span className="unsupported">
      <CircleSlash size={14} aria-hidden="true" />
      ML-анализ недоступен
    </span>
  );
}
