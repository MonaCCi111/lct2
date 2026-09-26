import { useEffect, useState } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { ChevronDown } from 'lucide-react';
import { Sidebar } from './Sidebar';
import { SystemIndicator, SystemStatus } from './SystemStatus';
import { navigation } from '../router/navigation';
import { Breadcrumbs, type BreadcrumbItem } from '../../components/navigation/Breadcrumbs';
import { UpdatedAtLabel } from '../../components/feedback/UpdatedAtLabel';
import { Drawer } from '../../components/ui/Drawer';
import { Dropdown } from '../../components/ui/Dropdown';
import { Button } from '../../components/ui/Button';
import { useSystem } from '../../api/queries/hooks';
import { apiConfig } from '../../api/client/config';
import { useTheme, type ThemePreference } from '../providers/ThemeProvider';
export function AppLayout() {
  const { preference, setPreference } = useTheme();
  const location = useLocation();
  const [panel, setPanel] = useState<'system' | 'profile' | null>(null);
  const system = useSystem();
  const current = navigation.find((item) => location.pathname.startsWith(item.path));
  const detailId = location.pathname.split('/')[2];
  const workOrderRoute = location.pathname === '/review/work-orders';
  const workOrderDetail = location.pathname.startsWith('/review/work-orders/');
  const title =
    workOrderRoute || workOrderDetail
      ? 'Наряды v2'
      : (current?.label ??
        (location.pathname === '/foundation' ? 'Компоненты и данные' : 'Страница не найдена'));
  const crumbs: BreadcrumbItem[] = [{ label: 'Рабочее пространство', to: '/overview' }];
  if (workOrderRoute || workOrderDetail) {
    crumbs.push({ label: 'Очередь проверки', to: '/review' });
    crumbs.push({ label: title, to: workOrderDetail ? '/review/work-orders' : undefined });
    if (workOrderDetail) crumbs.push({ label: decodeURIComponent(location.pathname.split('/')[3] ?? '') });
  } else {
    crumbs.push({ label: title, to: detailId ? current?.path : undefined });
    if (detailId) crumbs.push({ label: decodeURIComponent(detailId) });
  }
  useEffect(() => {
    document.title = `Dolos · ${title}`;
  }, [title]);
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Перейти к содержимому
      </a>
      <Sidebar onSystem={() => setPanel('system')} onProfile={() => setPanel('profile')} />
      <div className="main-column">
        <header className="topbar">
          <Breadcrumbs items={crumbs} />
          <div className="topbar-right">
            <SystemIndicator />
            {location.pathname !== '/overview' && (
              <UpdatedAtLabel className="topbar-time" value={system.data?.updatedAt ?? null} />
            )}
            <Dropdown
              label="Меню профиля"
              trigger={
                <Button variant="ghost" aria-label="Открыть меню профиля">
                  <span className="avatar">ДП</span>
                  <ChevronDown size={12} />
                </Button>
              }
              items={[
                { id: 'profile', label: 'Профиль диспетчера', onSelect: () => setPanel('profile') },
                { id: 'system', label: 'Состояние системы', onSelect: () => setPanel('system') },
              ]}
            />
          </div>
        </header>
        <main id="main-content" className="workspace" tabIndex={-1}>
          <Outlet />
        </main>
        <footer className="workspace-footer">
          <span>Предиктивный мониторинг инфраструктуры</span>
          <span>{apiConfig.enableMocks ? 'Демонстрационный режим' : 'Рабочее пространство'}</span>
        </footer>
      </div>
      <Drawer
        open={panel !== null}
        onOpenChange={(open) => {
          if (!open) setPanel(null);
        }}
        title={panel === 'profile' ? 'Профиль' : 'Состояние системы'}
        description={
          panel === 'profile'
            ? 'Локальное рабочее пространство диспетчера.'
            : 'Подключение и актуальность данных.'
        }
      >
        {panel === 'profile' ? (
          <dl className="definition-list">
            <dt>Роль</dt>
            <dd>Диспетчер</dd>
            <dt>Авторизация</dt>
            <dd>Не подключена на этом этапе</dd>
            <dt>Рабочее место</dt>
            <dd>Локальная сессия</dd>
            <dt>
              <label htmlFor="theme-preference">Тема интерфейса</label>
            </dt>
            <dd>
              <select
                id="theme-preference"
                className="input"
                value={preference}
                onChange={(event) => setPreference(event.target.value as ThemePreference)}
              >
                <option value="system">Системная</option>
                <option value="light">Светлая</option>
                <option value="dark">Тёмная</option>
              </select>
            </dd>
          </dl>
        ) : (
          <>
            <SystemStatus />
            {apiConfig.enableMocks && (
              <p className="mt-6">
                <Link to="/foundation" className="foundation-link" onClick={() => setPanel(null)}>
                  Открыть стенд компонентов и данных
                </Link>
              </p>
            )}
          </>
        )}
      </Drawer>
    </div>
  );
}
