import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { DataTable, type Column } from './DataTable';
const columns: Column<{ id: string }>[] = [
  { id: 'id', header: 'Идентификатор', sortable: true, cell: (row) => row.id },
];
const props = {
  columns,
  rows: [{ id: 'TEMP-001' }],
  caption: 'Прогнозы',
  rowKey: (row: { id: string }) => row.id,
};
describe('DataTable', () => {
  it('exposes accessible sorting and row content', async () => {
    const onSort = vi.fn();
    render(<DataTable {...props} onSort={onSort} sort={{ column: 'id', direction: 'asc' }} />);
    expect(screen.getByRole('columnheader')).toHaveAttribute('aria-sort', 'ascending');
    await userEvent.click(screen.getByRole('button', { name: 'Идентификатор' }));
    expect(onSort).toHaveBeenCalledWith({ column: 'id', direction: 'desc' });
    expect(screen.getByText('TEMP-001')).toBeVisible();
  });
  it('renders loading, error with retry, empty and success states', async () => {
    const onRetry = vi.fn();
    const { rerender } = render(<DataTable {...props} loading />);
    expect(screen.getByRole('status')).toHaveTextContent('Загрузка');
    rerender(<DataTable {...props} error="API недоступен" onRetry={onRetry} />);
    expect(screen.getByRole('alert')).toHaveTextContent('API недоступен');
    await userEvent.click(screen.getByRole('button', { name: 'Повторить' }));
    expect(onRetry).toHaveBeenCalledOnce();
    rerender(<DataTable {...props} rows={[]} />);
    expect(screen.getByText('Данных пока нет')).toBeVisible();
    rerender(<DataTable {...props} />);
    expect(screen.getByText('TEMP-001')).toBeVisible();
  });
});
