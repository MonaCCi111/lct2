import { Database, Layers3 } from 'lucide-react';
import type { ReactNode } from 'react';
import { Panel } from '../ui/Panel';
import { Badge } from '../ui/Badge';
import { EmptyState } from './States';
export function PageHeader({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}
export function PageShell({
  title,
  description,
  section,
  message = 'Данные системы будут отображаться здесь.',
}: {
  title: string;
  description: string;
  section: string;
  message?: string;
}) {
  return (
    <>
      <PageHeader title={title} description={description} />
      <Panel title={section} action={<Badge>Раздел подготовлен</Badge>}>
        <div className="placeholder-toolbar">
          <span className="flex items-center gap-2">
            <Layers3 size={14} />
            Рабочая область
          </span>
          <span>Обзор</span>
        </div>
        <EmptyState
          title={message}
          description="Рабочая область подготовлена. Содержимое появится на следующем этапе разработки."
        />
        <div className="placeholder-footer">
          <Database size={14} />
          <span>Данные появятся после подключения функциональности раздела.</span>
        </div>
      </Panel>
    </>
  );
}
