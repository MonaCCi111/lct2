import * as Primitive from '@radix-ui/react-dropdown-menu';
import type { ReactNode } from 'react';
export interface DropdownItem {
  id: string;
  label: string;
  onSelect: () => void;
  disabled?: boolean;
  danger?: boolean;
}
export function Dropdown({
  trigger,
  items,
  label,
}: {
  trigger: ReactNode;
  items: readonly DropdownItem[];
  label: string;
}) {
  return (
    <Primitive.Root>
      <Primitive.Trigger asChild>{trigger}</Primitive.Trigger>
      <Primitive.Portal>
        <Primitive.Content className="dropdown" aria-label={label} sideOffset={6} align="end">
          {items.map((item) => (
            <Primitive.Item
              key={item.id}
              className={`dropdown-item ${item.danger ? 'text-error' : ''}`}
              disabled={item.disabled}
              onSelect={item.onSelect}
            >
              {item.label}
            </Primitive.Item>
          ))}
        </Primitive.Content>
      </Primitive.Portal>
    </Primitive.Root>
  );
}
