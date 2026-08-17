import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { ListOrdered, RefreshCw, Loader2, Inbox } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardAction, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { FormSelect } from '@/components/custom';
import { useSellThrough, useRecalculateReorderPriority } from '@/hooks/reportingHooks/reportingQueries';
import { useModels } from '@/hooks/catalogHooks/modelQueries';
import { modelKeys } from '@/utils/queryKeys';
import { WINDOW_DAYS_OPTIONS, DEFAULT_WINDOW_DAYS } from '@/utils/constants';

const LOOKUP_PAGE = { page: 1, page_size: 500 };

export function ReorderPriorityTable() {
  const [windowDays, setWindowDays] = useState(String(DEFAULT_WINDOW_DAYS));
  const queryClient = useQueryClient();

  // Read-only ranking — this is what the table always renders, and it never
  // writes anything.
  const { data, isLoading, isError } = useSellThrough(Number(windowDays));
  // Lazy — only ever runs when "Recalculate" below is pressed.
  const { refetch: recalculate, isFetching: isRecalculating } = useRecalculateReorderPriority(Number(windowDays));
  // For the "Saved priority" column — Model.priority as Catalog currently has
  // it stored, so a user can see whether it's drifted from the live ranking
  // before choosing to commit (i.e. click Recalculate).
  const { data: modelsData } = useModels(LOOKUP_PAGE);

  const savedPriorityByModelId = Object.fromEntries((modelsData?.items ?? []).map((m) => [m.id, m.priority]));
  const entries = data?.entries ?? [];

  const handleRecalculate = async () => {
    const result = await recalculate();
    // fetchClient already toasted a failure — only invalidate Catalog's Model
    // list on success, so a failed recalculation doesn't cause a pointless
    // extra refetch.
    if (!result.isError) {
      queryClient.invalidateQueries({ queryKey: modelKeys.lists() });
    }
  };

  return (
    <Card>
      <CardHeader className="border-b [.border-b]:pb-4">
        <div className="flex items-center gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <ListOrdered className="size-4.5" />
          </span>
          <div>
            <CardTitle className="text-base">Reorder Priority</CardTitle>
            <CardDescription>Ranked by sell-through — rank 1 reorders first from China next.</CardDescription>
          </div>
        </div>
        {/* Two controls in one CardAction cell — stacks below sm */}
        <CardAction className="flex w-full flex-col items-stretch gap-2 sm:w-auto sm:flex-row sm:items-center">
          <FormSelect
            name="reorder_window"
            options={WINDOW_DAYS_OPTIONS}
            value={windowDays}
            onChange={setWindowDays}
            className="w-full sm:w-40"
          />
          <Button size="sm" variant="outline" disabled={isRecalculating} onClick={handleRecalculate}>
            <RefreshCw className={isRecalculating ? 'animate-spin' : ''} />
            {isRecalculating ? 'Saving…' : 'Recalculate'}
          </Button>
        </CardAction>
      </CardHeader>

      <CardContent>
        <div className="overflow-x-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50">
                <TableHead className="w-16">Rank</TableHead>
                <TableHead>Model</TableHead>
                <TableHead className="text-right">Units sold</TableHead>
                <TableHead className="text-right">Saved priority</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && (
                <TableRow>
                  <TableCell colSpan={4} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Loader2 className="size-5 animate-spin" />
                      Loading…
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {isError && (
                <TableRow>
                  <TableCell colSpan={4} className="h-32 text-center text-destructive">
                    Failed to load.
                  </TableCell>
                </TableRow>
              )}
              {!isLoading && !isError && entries.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Inbox className="size-6 text-muted-foreground/60" />
                      No active models.
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {entries.map((entry) => {
                const saved = savedPriorityByModelId[entry.model_id];
                const isStale = saved !== undefined && saved !== entry.rank;
                return (
                  <TableRow key={entry.model_id} className="hover:bg-muted/40">
                    <TableCell className="font-medium text-foreground">{entry.rank}</TableCell>
                    <TableCell>{entry.model_name}</TableCell>
                    <TableCell className="text-right">{entry.qty_sold}</TableCell>
                    <TableCell className="text-right">
                      {saved === undefined ? '—' : <Badge variant={isStale ? 'outline' : 'secondary'}>{saved}</Badge>}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
