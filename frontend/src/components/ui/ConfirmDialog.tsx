import * as Primitive from '@radix-ui/react-dialog';
import type { ReactNode } from 'react';
import { Button } from './Button';

/**
 * Restrained confirmation for terminal actions. Built on the Radix dialog the Drawer already
 * uses, so focus trapping and Escape behave the same across the app; `window.confirm` is never used.
 */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  onConfirm,
  pending = false,
  danger = false,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel: string;
  onConfirm: () => void;
  pending?: boolean;
  danger?: boolean;
  children?: ReactNode;
}) {
  return (
    <Primitive.Root open={open} onOpenChange={onOpenChange}>
      <Primitive.Portal>
        <Primitive.Overlay className="drawer-overlay" />
        <Primitive.Content className="confirm-dialog" aria-describedby="confirm-dialog-description">
          <Primitive.Title className="confirm-dialog-title">{title}</Primitive.Title>
          <Primitive.Description id="confirm-dialog-description" className="confirm-dialog-description">
            {description}
          </Primitive.Description>
          {children}
          <div className="confirm-dialog-actions">
            <Primitive.Close asChild>
              <Button disabled={pending}>Отмена</Button>
            </Primitive.Close>
            <Button variant={danger ? 'danger' : 'primary'} disabled={pending} onClick={onConfirm}>
              {pending ? 'Выполняется…' : confirmLabel}
            </Button>
          </div>
        </Primitive.Content>
      </Primitive.Portal>
    </Primitive.Root>
  );
}
