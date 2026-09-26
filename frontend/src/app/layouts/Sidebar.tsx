import { NavLink } from 'react-router-dom';
import { Hexagon, Server, UserRound } from 'lucide-react';
import { navigation } from '../router/navigation';
import { Divider } from '../../components/ui/Panel';
export function Sidebar({ onSystem, onProfile }: { onSystem: () => void; onProfile: () => void }) {
  return (
    <aside className="sidebar">
      <NavLink className="brand" to="/overview" aria-label="Dolos — оперативный центр">
        <span className="brand-symbol">
          <Hexagon size={17} strokeWidth={1.5} />
        </span>
        <span className="brand-name">DOLOS</span>
      </NavLink>
      <div className="workspace-label">
        Диспетчерская<span>Инженерная инфраструктура</span>
      </div>
      <nav aria-label="Основная навигация">
        <p className="nav-label">Рабочее пространство</p>
        {navigation.map((item, index) => (
          <div key={item.path}>
            {index === 5 && <Divider />}
            <NavLink
              to={item.path}
              title={item.label}
              aria-label={item.label}
              className={({ isActive }) =>
                `nav-link ${item.historical ? 'nav-link-historical' : ''} ${isActive ? 'active' : ''}`
              }
            >
              <item.icon size={17} strokeWidth={1.6} />
              <span>{item.label}</span>
            </NavLink>
          </div>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <Divider />
        <button
          className="nav-link"
          onClick={onSystem}
          aria-label="Состояние системы"
          title="Состояние системы"
        >
          <Server size={17} strokeWidth={1.6} />
          <span>Состояние системы</span>
        </button>
        <button className="nav-link" onClick={onProfile} aria-label="Профиль" title="Профиль">
          <UserRound size={17} strokeWidth={1.6} />
          <span>Профиль</span>
        </button>
        <div className="sidebar-footer">
          DOLOS <span className="float-right">v0.1</span>
        </div>
      </div>
    </aside>
  );
}
