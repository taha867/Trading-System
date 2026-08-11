import { useEffect, useState } from 'react';
import { Plus, Pencil, Trash2, Loader2, Inbox, Search, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { InputGroup, InputGroupInput, InputGroupAddon } from '@/components/ui/input-group';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { Card, CardHeader, CardTitle, CardDescription, CardAction, CardContent } from '@/components/ui/card';
import { PaginationControls } from '@/components/common/PaginationControls';
import { ConfirmDeleteDialog } from '@/components/common/ConfirmDeleteDialog';
import { CrudDrawer } from '@/components/common/CrudDrawer';

const DEFAULT_PAGE_SIZE = 20;
const SEARCH_DEBOUNCE_MS = 300;
// Radix Select can't represent "no selection" as an empty-string item value —
// this sentinel stands in for "All" in the UI and is stripped back to undefined
// before it ever reaches the query string.
const ALL_VALUE = '__all__';

function formatCell(value) {
  if (value === null || value === undefined || value === '') return '—';
  return String(value);
}

// A search-component filter fires on every keystroke locally but is debounced
// before it ever becomes a query param — typing "privacy" should cost one network
// request, not seven.
function useDebouncedValue(value, delayMs) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

function SearchFilter({ filter, value, onChange }) {
  const [draft, setDraft] = useState(value);
  const debounced = useDebouncedValue(draft, SEARCH_DEBOUNCE_MS);

  useEffect(() => {
    onChange(debounced);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only fire when the debounced value itself changes
  }, [debounced]);

  return (
    <InputGroup className="w-full sm:w-56">
      <InputGroupInput
        placeholder={filter.placeholder ?? `Search ${filter.label.toLowerCase()}…`}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        aria-label={filter.label}
      />
      <InputGroupAddon>
        <Search className="size-4 text-muted-foreground" />
      </InputGroupAddon>
      {draft && (
        <InputGroupAddon align="inline-end">
          <button
            type="button"
            onClick={() => setDraft('')}
            aria-label={`Clear ${filter.label} filter`}
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="size-3.5" />
          </button>
        </InputGroupAddon>
      )}
    </InputGroup>
  );
}

function SelectFilter({ filter, value, onChange }) {
  return (
    <Select value={value || ALL_VALUE} onValueChange={(v) => onChange(v === ALL_VALUE ? '' : v)}>
      <SelectTrigger className="w-full sm:w-48" aria-label={filter.label}>
        <SelectValue placeholder={filter.placeholder ?? `All ${filter.label.toLowerCase()}`} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL_VALUE}>All {filter.label.toLowerCase()}</SelectItem>
        {filter.options.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

function CrudTableFilters({ filters, values, onChange }) {
  if (!filters?.length) return null;
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
      {filters.map((filter) => {
        const FilterControl = filter.component === 'search' ? SearchFilter : SelectFilter;
        return (
          <FilterControl
            key={filter.key}
            filter={filter}
            value={values[filter.key] ?? ''}
            onChange={(next) => onChange(filter.key, next)}
          />
        );
      })}
    </div>
  );
}

export function CrudTable({ config, title, description, icon: Icon, addLabel = 'Add', entityLabel = 'record' }) {
  const [page, setPage] = useState(1);
  const [filterValues, setFilterValues] = useState({});
  const [drawerState, setDrawerState] = useState(null); // { mode: 'create' | 'edit', row? }
  const [deleteRow, setDeleteRow] = useState(null);

  const handleFilterChange = (key, value) => {
    setFilterValues((prev) => ({ ...prev, [key]: value }));
    setPage(1); // a changed filter can only invalidate the current page, not extend it
  };

  const { data, isLoading, isError } = config.useList({ page, page_size: DEFAULT_PAGE_SIZE, ...filterValues });
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
        <CrudTableFilters filters={config.filters} values={filterValues} onChange={handleFilterChange} />
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
