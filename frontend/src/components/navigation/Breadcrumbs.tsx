import { ChevronRight } from 'lucide-react';
import { Link } from 'react-router-dom';
export interface BreadcrumbItem {
  label: string;
  to?: string;
}
export function Breadcrumbs({ items }: { items: readonly BreadcrumbItem[] }) {
  return (
    <nav aria-label="Путь к странице">
      <ol className="breadcrumbs">
        {items.map((item, index) => (
          <li key={`${index}-${item.label}`}>
            {index > 0 && <ChevronRight size={13} aria-hidden="true" />}
            {item.to ? (
              <Link to={item.to}>{item.label}</Link>
            ) : (
              <span aria-current={index === items.length - 1 ? 'page' : undefined}>{item.label}</span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
