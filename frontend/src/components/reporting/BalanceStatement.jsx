import { Landmark, Wallet, Users2, Boxes, Loader2, Inbox } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { useBalanceStatement } from '@/hooks/reportingHooks/reportingQueries';

// Same sign convention + labeling PartyStatement.jsx already established for
// PartyBalanceRead.balance_pkr (positive = receivable/"Owes us", negative =
// payable/"We owe them") — duplicated locally rather than imported, matching
// this codebase's per-component small-helper convention.
function balanceLabel(value) {
  const num = Number(value);
  if (num > 0) return 'Owes us';
  if (num < 0) return 'We owe them';
  return 'Settled';
}

function SummaryTile({ icon: Icon, label, value }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border p-4">
      <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
        <Icon className="size-4.5" />
      </span>
      <div>
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-lg font-semibold text-foreground">
          <CurrencyAmount value={value} />
        </p>
      </div>
    </div>
  );
}

export function BalanceStatement() {
  const { data, isLoading, isError } = useBalanceStatement();

  return (
    <Card>
      <CardHeader className="border-b [.border-b]:pb-4">
        <div className="flex items-center gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Landmark className="size-4.5" />
          </span>
          <div>
            <CardTitle className="text-base">Balance Statement</CardTitle>
            <CardDescription>Where the business stands right now — cash, who owes what, stock on hand.</CardDescription>
          </div>
        </div>
      </CardHeader>

      <CardContent className="flex flex-col gap-6">
        {isLoading && (
          <div className="flex h-32 flex-col items-center justify-center gap-2 text-muted-foreground">
            <Loader2 className="size-5 animate-spin" />
            Loading…
          </div>
        )}
        {isError && <div className="flex h-32 items-center justify-center text-destructive">Failed to load.</div>}

        {!isLoading && !isError && data && (
          <>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <SummaryTile icon={Wallet} label="Cash on hand" value={data.total_cash_pkr} />
              <SummaryTile icon={Users2} label="Net receivable" value={data.total_receivable_pkr - data.total_payable_pkr} />
              <SummaryTile icon={Boxes} label="Inventory value" value={data.inventory_value_pkr} />
              <SummaryTile icon={Landmark} label="Net position" value={data.net_position_pkr} />
            </div>
            <p className="text-xs text-muted-foreground">As of {data.as_of}</p>

            <div>
              <h3 className="mb-2 text-sm font-medium text-foreground">Cash / bank / wallet accounts</h3>
              <div className="overflow-x-auto rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-muted/50">
                      <TableHead>Account</TableHead>
                      <TableHead className="text-right">Balance</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.cash_accounts.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={2} className="h-24 text-center text-muted-foreground">
                          <div className="flex flex-col items-center justify-center gap-2">
                            <Inbox className="size-5 text-muted-foreground/60" />
                            No active accounts.
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                    {data.cash_accounts.map((account) => (
                      <TableRow key={account.id} className="hover:bg-muted/40">
                        <TableCell>{account.label}</TableCell>
                        <TableCell className="text-right">
                          <CurrencyAmount value={account.balance} />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>

            <div>
              <h3 className="mb-2 text-sm font-medium text-foreground">Receivables & payables by party</h3>
              <div className="overflow-x-auto rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-muted/50">
                      <TableHead>Party</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Amount</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.party_balances.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={3} className="h-24 text-center text-muted-foreground">
                          <div className="flex flex-col items-center justify-center gap-2">
                            <Inbox className="size-5 text-muted-foreground/60" />
                            Every party is settled — nothing outstanding.
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                    {data.party_balances.map((party) => (
                      <TableRow key={party.party_id} className="hover:bg-muted/40">
                        <TableCell>
                          <Link to={`/parties/${party.party_id}`} className="font-medium text-primary hover:underline">
                            {party.name}
                          </Link>
                        </TableCell>
                        <TableCell>
                          <Badge variant={Number(party.balance_pkr) >= 0 ? 'secondary' : 'destructive'}>
                            {balanceLabel(party.balance_pkr)}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <CurrencyAmount value={Math.abs(Number(party.balance_pkr))} />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
