import { Activity, Blocks, ChartNoAxesCombined, ClipboardCheck, ClipboardList, Flame, LayoutDashboard, Radio, Waves } from 'lucide-react';
export const navigation = [
  { path: '/overview', label: 'Обзор', icon: LayoutDashboard, historical: true },
  { path: '/objects', label: 'Объекты', icon: Blocks },
  { path: '/channels', label: 'Каналы', icon: Radio, historical: true },
  { path: '/situations', label: 'Ситуации', icon: Activity, historical: true },
  { path: '/review', label: 'Очередь групп', icon: ClipboardCheck, historical: true },
  { path: '/review/work-orders', label: 'Наряды', icon: ClipboardList, historical: true },
  { path: '/analytics', label: 'Качество', icon: ChartNoAxesCombined, historical: true },
  { path: '/fire-history', label: 'История пожаров', icon: Flame, historical: true },
  { path: '/replay', label: 'Таймлайн', icon: Waves, historical: true },
];
