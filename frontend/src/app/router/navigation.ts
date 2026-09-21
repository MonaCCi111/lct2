import { Activity, Blocks, ChartNoAxesCombined, ClipboardList, LayoutDashboard } from 'lucide-react';
export const navigation = [
  { path: '/overview', label: 'Оперативный центр', icon: LayoutDashboard },
  { path: '/objects', label: 'Объекты', icon: Blocks },
  { path: '/predictions', label: 'Прогнозы', icon: Activity },
  { path: '/tickets', label: 'Наряды', icon: ClipboardList },
  { path: '/analytics', label: 'Аналитика', icon: ChartNoAxesCombined },
];
