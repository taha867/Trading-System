import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Loader2, Inbox, Ship } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { Card, CardHeader, CardTitle, CardDescription, CardAction, CardContent } from '@/components/ui/card';
import { PaginationControls } from '@/components/common/PaginationControls';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { useCargoShipments, useCargoModes, useCargoCostBases } from '@/hooks/cargoHooks/cargoQueries';
import { useParties } from '@/hooks/partyHooks/partyQueries';
import { LOOKUP_PAGE } from '@/utils/queryParams';

const DEFAULT_PAGE_SIZE = 20;

export function CargoShipmentList() {
  const [page, setPage] = useState(1);
  const { data, isLoading, isError } = useCargoShipments({ page, page_size: DEFAULT_PAGE_SIZE });
  const { data: partiesData } = useParties(LOOKUP_PAGE);
  const { data: modesData } = useCargoModes(LOOKUP_PAGE);
  const { data: costBasesData } = useCargoCostBases(LOOKUP_PAGE);

  const agentNameById = Object.fromEntries((partiesData?.items ?? []).map((p) => [p.id, p.name]));
  const modeNameById = Object.fromEntries((modesData?.items ?? []).map((m) => [m.id, m.name]));
  const costBasisNameById = Object.fromEntries((costBasesData?.items ?? []).map((b) => [b.id, b.name]));
  const shipments = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <Card>
      <CardHeader className="[.border-b]:pb-4 border-b">
        <div className="flex items-center gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Ship className="size-4.5" />
          </span>
          <div>
            <CardTitle className="text-base">Cargo Shipments</CardTitle>
            <CardDescription>Freight cost split across attached purchase-order lines.</CardDescription>
          </div>
        </div>
        <CardAction>
          <Button size="sm" asChild>
            <Link to="/cargo-shipments/new">
              <Plus />
              New shipment
            </Link>
          </Button>
        </CardAction>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        <div className="overflow-x-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50">
                <TableHead>ID</TableHead>
                <TableHead>Agent</TableHead>
                <TableHead>Mode</TableHead>
                <TableHead>Cost basis</TableHead>
                <TableHead>Shipment date</TableHead>
                <TableHead className="text-right">Total cost</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && (
                <TableRow>
                  <TableCell colSpan={6} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Loader2 className="size-5 animate-spin" />
                      Loading…
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {isError && (
                <TableRow>
                  <TableCell colSpan={6} className="h-32 text-center text-destructive">
                    Failed to load.
                  </TableCell>
                </TableRow>
              )}
              {!isLoading && !isError && shipments.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Inbox className="size-6 text-muted-foreground/60" />
                      No cargo shipments yet — create the first one above.
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {shipments.map((shipment) => (
                <TableRow key={shipment.id} className="hover:bg-muted/40">
                  <TableCell>
                    <Link to={`/cargo-shipments/${shipment.id}`} className="font-medium text-primary hover:underline">
                      #{shipment.id}
                    </Link>
                  </TableCell>
                  <TableCell>{agentNameById[shipment.cargo_agent_id] ?? `Party #${shipment.cargo_agent_id}`}</TableCell>
                  <TableCell>{modeNameById[shipment.cargo_mode_id] ?? `Mode #${shipment.cargo_mode_id}`}</TableCell>
                  <TableCell>{costBasisNameById[shipment.cost_basis_id] ?? `Basis #${shipment.cost_basis_id}`}</TableCell>
                  <TableCell>{shipment.shipment_date}</TableCell>
                  <TableCell className="text-right">
                    <CurrencyAmount value={shipment.total_cost_pkr} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        <PaginationControls page={page} pageSize={DEFAULT_PAGE_SIZE} total={total} onPageChange={setPage} />
      </CardContent>
    </Card>
  );
}
