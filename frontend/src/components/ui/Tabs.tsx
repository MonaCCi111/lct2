import * as Primitive from '@radix-ui/react-tabs';
import type { ReactNode } from 'react';
export interface TabItem {
  value: string;
  label: string;
  content: ReactNode;
}
export function Tabs({
  items,
  label,
  defaultValue,
}: {
  items: readonly TabItem[];
  label: string;
  defaultValue?: string;
}) {
  return (
    <Primitive.Root defaultValue={defaultValue ?? items[0]?.value}>
      <Primitive.List className="tabs-list" aria-label={label}>
        {items.map((item) => (
          <Primitive.Trigger className="tab-trigger" key={item.value} value={item.value}>
            {item.label}
          </Primitive.Trigger>
        ))}
      </Primitive.List>
      {items.map((item) => (
        <Primitive.Content key={item.value} value={item.value} className="tab-content">
          {item.content}
        </Primitive.Content>
      ))}
    </Primitive.Root>
  );
}
