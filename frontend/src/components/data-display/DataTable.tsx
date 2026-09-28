import type {
  ReactNode,
  TableHTMLAttributes,
  HTMLAttributes,
  ThHTMLAttributes,
  TdHTMLAttributes,
} from 'react';
import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react';
import { EmptyState, ErrorState, Skeleton } from '../feedback/States';
import { Tooltip } from '../ui/Tooltip';
export const Table = (props: TableHTMLAttributes<HTMLTableElement>) => (
  <table {...props} className={`data-table ${props.className ?? ''}`} />
);
export const TableHead = (props: HTMLAttributes<HTMLTableSectionElement>) => <thead {...props} />;
export const TableBody = (props: HTMLAttributes<HTMLTableSectionElement>) => <tbody {...props} />;
export const TableRow = (props: HTMLAttributes<HTMLTableRowElement>) => <tr {...props} />;
export const TableHeader = (props: ThHTMLAttributes<HTMLTableCellElement>) => <th scope="col" {...props} />;
export const TableCell = (props: TdHTMLAttributes<HTMLTableCellElement>) => <td {...props} />;
export function TruncatedText({ text }: { text: string }) {
  return (
    <Tooltip content={text}>
      <span className="truncate" tabIndex={0}>
        {text}
      </span>
    </Tooltip>
  );
}
export interface Column<T> {
  id: string;
  header: string;
  /** Optional affordance rendered next to the header, e.g. an explanation of the column notation. */
  headerHint?: ReactNode;
  cell: (row: T) => ReactNode;
  align?: 'left' | 'right' | 'center';
  width?: string;
  sortable?: boolean;
  className?: string;
}
export interface SortState {
  column: string;
  direction: 'asc' | 'desc';
}
interface DataTableProps<T> {
  columns: readonly Column<T>[];
  rows: readonly T[];
  rowKey: (row: T) => string;
  caption: string;
  loading?: boolean;
  error?: string;
  onRetry?: () => void;
  sort?: SortState;
  onSort?: (sort: SortState) => void;
  stickyHeader?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyAction?: ReactNode;
  skeletonRows?: number;
  rowProps?: (row: T) => HTMLAttributes<HTMLTableRowElement>;
}
// Controlled sort API supports both local and backend sorting; the caller owns order.
export function DataTable<T>({
  columns,
  rows,
  rowKey,
  caption,
  loading,
  error,
  onRetry,
  sort,
  onSort,
  stickyHeader = true,
  emptyTitle,
  emptyDescription,
  emptyAction,
  skeletonRows = 4,
  rowProps,
}: DataTableProps<T>) {
  return (
    <div className={`table-scroll ${stickyHeader ? 'table-sticky' : ''}`} aria-busy={loading}>
      <Table>
        <caption className="sr-only">{caption}</caption>
        <TableHead>
          <TableRow>
            {columns.map((column) => {
              const active = sort?.column === column.id;
              const SortIcon = active ? (sort.direction === 'asc' ? ArrowUp : ArrowDown) : ArrowUpDown;
              return (
                <TableHeader
                  key={column.id}
                  className={column.className}
                  style={{ width: column.width, textAlign: column.align }}
                  // A hint button inside the cell would otherwise leak into the column name that
                  // assistive tech announces for every cell below it.
                  aria-label={column.headerHint ? column.header : undefined}
                  aria-sort={
                    column.sortable
                      ? active
                        ? sort.direction === 'asc'
                          ? 'ascending'
                          : 'descending'
                        : 'none'
                      : undefined
                  }
                >
                  {column.sortable && onSort ? (
                    <button
                      className="sort-button"
                      onClick={() =>
                        onSort({
                          column: column.id,
                          direction: active && sort.direction === 'asc' ? 'desc' : 'asc',
                        })
                      }
                    >
                      {column.header}
                      <SortIcon size={12} aria-hidden="true" />
                    </button>
                  ) : (
                    column.header
                  )}
                  {/* Keeps the hint on the same line as the label so headers stay one row tall. */}
                  {column.headerHint && <span className="column-header-hint">{column.headerHint}</span>}
                </TableHeader>
              );
            })}
          </TableRow>
        </TableHead>
        <TableBody>
          {loading ? (
            Array.from({ length: skeletonRows }, (_, index) => (
              <TableRow key={index}>
                {columns.map((column) => (
                  <TableCell key={column.id} className={column.className}>
                    <Skeleton />
                  </TableCell>
                ))}
              </TableRow>
            ))
          ) : error ? (
            <TableRow>
              <TableCell colSpan={columns.length}>
                <ErrorState message={error} onRetry={onRetry} />
              </TableCell>
            </TableRow>
          ) : rows.length === 0 ? (
            <TableRow>
              <TableCell colSpan={columns.length}>
                <EmptyState title={emptyTitle} description={emptyDescription} action={emptyAction} />
              </TableCell>
            </TableRow>
          ) : (
            rows.map((row) => (
              <TableRow key={rowKey(row)} {...rowProps?.(row)}>
                {columns.map((column) => (
                  <TableCell
                    key={column.id}
                    className={`${column.align === 'right' ? 'numeric' : ''} ${column.className ?? ''}`}
                    style={{ textAlign: column.align }}
                  >
                    {column.cell(row)}
                  </TableCell>
                ))}
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
      {loading && (
        <span role="status" className="sr-only">
          Загрузка данных…
        </span>
      )}
    </div>
  );
}
