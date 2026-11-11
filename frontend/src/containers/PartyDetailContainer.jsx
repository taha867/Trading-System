import { useParams, Link } from 'react-router-dom';
import { Loader2, ArrowLeft } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { DateFilter } from '@/components/custom';
import { PartyStatement } from '@/components/parties/PartyStatement';
import { usePartyStatement } from '@/hooks/partyHooks/partyQueries';
import { useDateFilter } from '@/hooks/useDateFilter';
import { useSearchParamFilters } from '@/hooks/useSearchParamFilters';

export function PartyDetailContainer() {
  const { partyId } = useParams();
  const id = Number(partyId);
  const isValidId = Number.isInteger(id) && id > 0;

  // A statement is a full history, so it opens on all dates; pick a month or From – To to see one period
  // (the opening balance is then the balance as of the From date).
  const dates = useDateFilter(useSearchParamFilters(), { defaultMode: 'all' });
  const { data: statement, isLoading, isError } = usePartyStatement(isValidId ? id : undefined, {
    dateFrom: dates.dateFrom,
    dateTo: dates.dateTo,
  });

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Party Statement</h1>
          <p className="mt-1 text-sm text-muted-foreground">Ledger history and running balance for one party — all dates, or one month or From – To period.</p>
        </div>
        <Button variant="outline" size="sm" asChild>
          <Link to="/parties">
            <ArrowLeft />
            Back to parties
          </Link>
        </Button>
      </div>

      <Card>
        <CardContent className="flex flex-col gap-6 py-6">
          {isValidId && <DateFilter filter={dates} id="statement_date" className="max-w-xl" />}
          {!isValidId || isError ? (
            <p className="py-10 text-center text-destructive">Party not found.</p>
          ) : isLoading ? (
            <div className="flex flex-col items-center justify-center gap-2 py-10 text-muted-foreground">
              <Loader2 className="size-5 animate-spin" />
              Loading…
            </div>
          ) : (
            <PartyStatement statement={statement} dates={dates} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
