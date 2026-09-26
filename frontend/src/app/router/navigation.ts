import {
  Activity,
  Blocks,
  ChartNoAxesCombined,
  ClipboardCheck,
  ClipboardList,
  LayoutDashboard,
} from 'lucide-react';
export const navigation = [
  { path: '/overview', label: 'Оперативный центр', icon: LayoutDashboard },
  { path: '/objects', label: 'Объекты', icon: Blocks },
  { path: '/predictions', label: 'Прогнозы', icon: Activity },
  { path: '/review', label: 'Очередь проверки', icon: ClipboardCheck, historical: true },
  { path: '/tickets', label: 'Наряды', icon: ClipboardList },
  { path: '/analytics', label: 'Аналитика', icon: ChartNoAxesCombined },
];
