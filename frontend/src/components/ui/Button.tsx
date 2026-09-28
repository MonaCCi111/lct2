import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { Tooltip } from './Tooltip';
export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
}
export function Button({ variant = 'secondary', className = '', type = 'button', ...props }: ButtonProps) {
  return <button type={type} className={`button button-${variant} ${className}`} {...props} />;
}
export function IconButton({
  label,
  children,
  ...props
}: Omit<ButtonProps, 'children' | 'aria-label'> & { label: string; children: ReactNode }) {
  return (
    <Tooltip content={label}>
      <Button {...props} aria-label={label} className={`icon-button ${props.className ?? ''}`}>
        {children}
      </Button>
    </Tooltip>
  );
}
