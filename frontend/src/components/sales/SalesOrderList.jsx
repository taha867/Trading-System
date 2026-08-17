import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Loader2, Inbox, Receipt } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { Card, CardHeader, CardTitle, CardDescription, CardAction, CardContent } from '@/components/ui/card';
import { PaginationControls } from '@/components/common/PaginationControls';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { useSalesOrders } from '@/hooks/salesHooks/salesQueries';
import { useParties } from '@/hooks/partyHooks/partyQueries';
import { LOOKUP_PAGE } from '@/utils/queryParams';

const DEFAULT_PAGE_SIZE = 20;

export function SalesOrderList() {
  const [page, setPage] = useState(1);
  const { data, isLoading, isError } = useSalesOrders({ page, page_size: DEFAULT_PAGE_SIZE });
  const { data: partiesData } = useParties(LOOKUP_PAGE);

  const customerNameById = Object.fromEntries((partiesData?.items ?? []).map((p) => [p.id, p.name]));
  const orders = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <Card>
      <CardHeader className="[.border-b]:pb-4 border-b">
        <div className="flex items-center gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Receipt className="size-4.5" />
          </span>
          <div>
            <CardTitle className="text-base">Sales Orders</CardTitle>
            <CardDescription>Every invoice to a wholesale customer, FIFO-costed against the lots it drew from.</CardDescription>
          </div>
        </div>
        <CardAction>
          <Button size="sm" asChild>
            <Link to="/sales-orders/new">
              <Plus />
              New sales order
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
                <TableHead>Customer</TableHead>
                <TableHead>Order date</TableHead>
                <TableHead className="text-right">Total PKR</TableHead>
                <TableHead className="text-right">Margin PKR</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && (
                <TableRow>
                  <TableCell colSpan={5} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Loader2 className="size-5 animate-spin" />
                      Loading…
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {isError && (
                <TableRow>
                  <TableCell colSpan={5} className="h-32 text-center text-destructive">
                    Failed to load.
                  </TableCell>
                </TableRow>
              )}
              {!isLoading && !isError && orders.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="h-32 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Inbox className="size-6 text-muted-foreground/60" />
                      No sales orders yet — create the first one above.
                    </div>
                  </TableCell>
                </TableRow>
              )}
              {orders.map((order) => (
                <TableRow key={order.id} className="hover:bg-muted/40">
                  <TableCell>
                    <Link to={`/sales-orders/${order.id}`} className="font-medium text-primary hover:underline">
                      #{order.id}
                    </Link>
                  </TableCell>
                  <TableCell>{customerNameById[order.party_id] ?? `Party #${order.party_id}`}</TableCell>
                  <TableCell>{order.order_date}</TableCell>
                  <TableCell className="text-right">
                    <CurrencyAmount value={order.total_pkr} />
                  </TableCell>
                  <TableCell className="text-right">
                    <CurrencyAmount value={order.total_margin_pkr} />
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
