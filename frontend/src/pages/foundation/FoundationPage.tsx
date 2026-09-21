import { useState } from 'react';
import { MoreHorizontal, Settings2 } from 'lucide-react';
import { PageHeader } from '../../components/feedback/PageShell';
import { Panel, Divider } from '../../components/ui/Panel';
import { Button, IconButton } from '../../components/ui/Button';
import { Input, SearchInput, Select } from '../../components/ui/Fields';
import { RiskBadge, StatusBadge, UrgencyBadge } from '../../components/ui/Badge';
import { Tabs } from '../../components/ui/Tabs';
import { Dropdown } from '../../components/ui/Dropdown';
import { Drawer } from '../../components/ui/Drawer';
import { EmptyState, ErrorState, LoadingState, StaleState } from '../../components/feedback/States';
import { PredictionFixturesPanel } from './PredictionFixturesPanel';
export default function FoundationPage() {
  const [drawer, setDrawer] = useState(false);
  const [state, setState] = useState('success');
  const [message, setMessage] = useState('Компоненты готовы к проверке.');
  return (
    <>
      <PageHeader
        title="Компоненты и данные"
        description="Технический стенд · доступен только в демонстрационном режиме"
      />
      <Tabs
        label="Разделы технического стенда"
        items={[
          {
            value: 'data',
            label: 'Контракт данных',
            content: (
              <div className="sample-stack">
                <p className="muted">
                  Значения риска, срочности и ИТС приходят из API. Для температуры вероятность 46%
                  соответствует критическому риску.
                </p>
                <PredictionFixturesPanel />
              </div>
            ),
          },
          {
            value: 'components',
            label: 'Компоненты',
            content: (
              <div className="sample-grid">
                <Panel title="Действия">
                  <div className="sample-stack">
                    <div className="sample-row">
                      <Button variant="primary" onClick={() => setMessage('Основное действие выполнено.')}>
                        Основное
                      </Button>
                      <Button onClick={() => setMessage('Вторичное действие выполнено.')}>Вторичное</Button>
                      <Button variant="ghost" onClick={() => setMessage('Действие выполнено.')}>
                        Текстовое
                      </Button>
                      <Button
                        variant="danger"
                        onClick={() => setMessage('Пример опасного действия. Данные не изменены.')}
                      >
                        Удалить
                      </Button>
                      <Button disabled>Недоступно</Button>
                    </div>
                    <div className="sample-row">
                      <IconButton label="Открыть параметры" onClick={() => setDrawer(true)}>
                        <Settings2 size={15} />
                      </IconButton>
                      <Dropdown
                        label="Пример меню"
                        trigger={
                          <Button aria-label="Открыть пример меню">
                            <MoreHorizontal size={15} />
                          </Button>
                        }
                        items={[
                          { id: 'open', label: 'Открыть панель', onSelect: () => setDrawer(true) },
                          {
                            id: 'disabled',
                            label: 'Недоступное действие',
                            disabled: true,
                            onSelect: () => undefined,
                          },
                        ]}
                      />
                    </div>
                    <p className="muted" role="status">
                      {message}
                    </p>
                  </div>
                </Panel>
                <Panel title="Поля ввода">
                  <div className="sample-stack">
                    <Input label="Название объекта" placeholder="Введите название" />
                    <SearchInput placeholder="Поиск по объектам" />
                    <Select
                      label="Подсистема"
                      options={[
                        { value: 'all', label: 'Все подсистемы' },
                        { value: 'power', label: 'Электроснабжение' },
                      ]}
                    />
                  </div>
                </Panel>
                <Panel title="Семантические статусы">
                  <div className="sample-stack">
                    <div className="sample-row">
                      {(['low', 'medium', 'high', 'critical'] as const).map((risk) => (
                        <RiskBadge key={risk} value={risk} />
                      ))}
                    </div>
                    <div className="sample-row">
                      {(['NORMAL', 'PLANNED_24_48H', 'URGENT_6_24H', 'FLASH_1_6H'] as const).map((value) => (
                        <UrgencyBadge key={value} value={value} />
                      ))}
                    </div>
                    <Divider />
                    <div className="sample-row">
                      {(['draft', 'approved', 'rejected', 'completed'] as const).map((value) => (
                        <StatusBadge key={value} value={value} />
                      ))}
                    </div>
                  </div>
                </Panel>
                <Panel title="Состояния данных">
                  <Select
                    label="Состояние"
                    value={state}
                    onChange={(event) => setState(event.target.value)}
                    options={['success', 'loading', 'empty', 'error', 'stale'].map((value) => ({
                      value,
                      label: value,
                    }))}
                  />
                  <div className="mt-4">
                    {state === 'loading' ? (
                      <LoadingState />
                    ) : state === 'empty' ? (
                      <EmptyState description="Нет записей по выбранным условиям." />
                    ) : state === 'error' ? (
                      <ErrorState message="Пример ошибки сервиса." onRetry={() => setState('success')} />
                    ) : state === 'stale' ? (
                      <StaleState onRefresh={() => setState('success')} />
                    ) : (
                      <p className="muted" role="status">
                        Данные успешно загружены.
                      </p>
                    )}
                  </div>
                </Panel>
              </div>
            ),
          },
        ]}
      />
      <Drawer
        open={drawer}
        onOpenChange={setDrawer}
        title="Параметры представления"
        description="Проверка фокуса, клавиатуры и боковой панели."
      >
        <p className="muted">Escape закрывает панель и возвращает фокус к элементу, который её открыл.</p>
        <Button className="mt-4" onClick={() => setDrawer(false)}>
          Готово
        </Button>
      </Drawer>
    </>
  );
}
