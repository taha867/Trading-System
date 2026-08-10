import { Badge } from '@/components/ui/badge';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { CurrencyAmount } from '@/components/common/CurrencyAmount';
import { PartyRoleBadges } from '@/components/parties/PartyRoleBadges';

// Sign convention per backend spec §2.6: positive closing_balance means the party
// owes the business (receivable); negative means the business owes the party
// (payable). Surfaced as a label so nobody has to mentally flip the sign.
function balanceLabel(value) {
  const num = Number(value);
  if (num > 0) return 'Owes us';
  if (num < 0) return 'We owe them';
  return 'Settled';
}

export function PartyStatement({ statement }) {
  const { party, opening_balance, entries, closing_balance } = statement;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-foreground">{party.name}</h2>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <PartyRoleBadges roles={party.roles} />
            {party.contact && <span className="text-sm text-muted-foreground">{party.contact}</span>}
          </div>
        </div>
        <div className="text-right">
          <Badge variant={Number(closing_balance) >= 0 ? 'secondary' : 'destructive'}>
            {balanceLabel(closing_balance)}
          </Badge>
          <p className="mt-1 text-lg font-semibold text-foreground">
            <CurrencyAmount value={Math.abs(Number(closing_balance))} />
          </p>
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/50">
              <TableHead>Date</TableHead>
              <TableHead>Account</TableHead>
              <TableHead>Reference</TableHead>
              <TableHead className="text-right">Debit</TableHead>
              <TableHead className="text-right">Credit</TableHead>
              <TableHead className="text-right">Running balance</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow className="bg-muted/30">
              <TableCell colSpan={5} className="font-medium text-foreground">
                Opening balance
              </TableCell>
              <TableCell className="text-right font-medium text-foreground">
                <CurrencyAmount value={opening_balance} />
              </TableCell>
            </TableRow>
            {entries.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="h-24 text-center text-muted-foreground">
                  No ledger activity yet.
                </TableCell>
              </TableRow>
            )}
            {entries.map((entry) => (
              <TableRow key={entry.id} className="hover:bg-muted/40">
                <TableCell>{entry.entry_date}</TableCell>
                <TableCell>{entry.account}</TableCell>
                <TableCell className="text-muted-foreground">
                  {entry.reference_type ? `${entry.reference_type} #${entry.reference_id}` : '—'}
                </TableCell>
                <TableCell className="text-right">
                  {Number(entry.debit) > 0 ? <CurrencyAmount value={entry.debit} /> : '—'}
                </TableCell>
                <TableCell className="text-right">
                  {Number(entry.credit) > 0 ? <CurrencyAmount value={entry.credit} /> : '—'}
                </TableCell>
                <TableCell className="text-right">
                  <CurrencyAmount value={entry.running_balance} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
