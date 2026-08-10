import { useState } from 'react';
import { Plus, Pencil, Trash2, Loader2, Inbox } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { Card, CardHeader, CardTitle, CardDescription, CardAction, CardContent } from '@/components/ui/card';
import { PaginationControls } from '@/components/common/PaginationControls';
import { ConfirmDeleteDialog } from '@/components/common/ConfirmDeleteDialog';
import { CrudDrawer } from '@/components/common/CrudDrawer';

const DEFAULT_PAGE_SIZE = 20;

function formatCell(value) {
  if (value === null || value === undefined || value === '') return '—';
  return String(value);
}

export function CrudTable({ config, title, description, icon: Icon, addLabel = 'Add', entityLabel = 'record' }) {
  const [page, setPage] = useState(1);
  const [drawerState, setDrawerState] = useState(null); // { mode: 'create' | 'edit', row? }
  const [deleteRow, setDeleteRow] = useState(null);

  const { data, isLoading, isError } = config.useList({ page, page_size: DEFAULT_PAGE_SIZE });
  const deleteMutation = config.useDelete();

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const columnCount = config.columns.length + 1;

  return (
    <Card>
      <CardHeader className="[.border-b]:pb-4 border-b">
        <div className="flex items-center gap-3">
          {Icon && (
            <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Icon className="size-4.5" />
            </span>
          )}
          <div>
            <CardTitle className="text-base">{title}</CardTitle>
            {description && <CardDescription>{description}</CardDescription>}
          </div>
        </div>
        <CardAction>
          <Button size="sm" onClick={() => setDrawerState({ mode: 'create' })}>
            <Plus />
            {addLabel}
          </Button>
        </CardAction>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        <div className="overflow-x-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50">
                {config.columns.map((column) => (
                  <TableHead key={column.key}>{column.label}</TableHead>
                ))}
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && (
                <TableRow>
                  <TableCell colSpan={columnCount} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Loader2 className="size-5 animate-spin" />
                      Loading…
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {isError && (
                <TableRow>
                  <TableCell colSpan={columnCount} className="h-32 text-center text-destructive">
                    Failed to load.
                  </TableCell>
                </TableRow>
              )}
              {!isLoading && !isError && items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={columnCount} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Inbox className="size-6 text-muted-foreground/60" />
                      No records yet — add the first one above.
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {items.map((row) => (
                <TableRow key={row.id} className="hover:bg-muted/40">
                  {config.columns.map((column) => (
                    <TableCell key={column.key}>
                      {column.render ? column.render(row) : formatCell(row[column.key])}
                    </TableCell>
                  ))}
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label={`Edit ${entityLabel}`}
                        onClick={() => setDrawerState({ mode: 'edit', row })}
                      >
                        <Pencil />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label={`Delete ${entityLabel}`}
                        onClick={() => setDeleteRow(row)}
                      >
                        <Trash2 className="text-destructive" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        <PaginationControls page={page} pageSize={DEFAULT_PAGE_SIZE} total={total} onPageChange={setPage} />
      </CardContent>

      <CrudDrawer
        config={config}
        open={Boolean(drawerState)}
        mode={drawerState?.mode}
        row={drawerState?.row}
        entityLabel={entityLabel}
        onOpenChange={(nextOpen) => !nextOpen && setDrawerState(null)}
      />

      <ConfirmDeleteDialog
        open={Boolean(deleteRow)}
        onOpenChange={(nextOpen) => !nextOpen && setDeleteRow(null)}
        isPending={deleteMutation.isPending}
        itemLabel={entityLabel}
        onConfirm={async () => {
          await deleteMutation.mutateAsync(deleteRow.id);
          setDeleteRow(null);
        }}
      />
    </Card>
  );
}
